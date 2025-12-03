import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from shapely.geometry import shape
from geoalchemy2.shape import to_shape

from app.models.parking_lot import ParkingLot
from app.schemas.discovery import DiscoveryStep, DiscoveryProgress, DiscoveryFilters
from app.core.parking_lot_discovery_service import parking_lot_discovery_service
from app.core.normalization_service import normalization_service
from app.core.business_data_service import business_data_service
from app.core.association_service import association_service
from app.core.imagery_service import imagery_service
from app.core.condition_evaluation_service import condition_evaluation_service
from app.core.usage_tracking_service import usage_tracking_service
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class DiscoveryOrchestrator:
    """Orchestrates the complete parking lot discovery pipeline."""
    
    # In-memory job storage (use Redis in production)
    _jobs: Dict[str, Dict[str, Any]] = {}
    
    def initialize_job(self, job_id: UUID, user_id: UUID) -> None:
        """Initialize job status before starting background task."""
        job_key = str(job_id)
        self._jobs[job_key] = {
            "status": DiscoveryStep.QUEUED,
            "progress": DiscoveryProgress(
                current_step=DiscoveryStep.QUEUED,
                steps_completed=0,
            ),
            "started_at": datetime.utcnow(),
            "user_id": str(user_id),
        }
    
    async def start_discovery(
        self,
        job_id: UUID,
        user_id: UUID,
        area_polygon: Dict[str, Any],
        filters: DiscoveryFilters,
        db: Session
    ) -> None:
        """
        Start the discovery pipeline.
        This runs as a background task.
        """
        job_key = str(job_id)
        
        # Ensure job is initialized (might already be done by initialize_job)
        if job_key not in self._jobs:
            self.initialize_job(job_id, user_id)
        
        try:
            await self._run_pipeline(job_id, user_id, area_polygon, filters, db)
        except Exception as e:
            logger.error(f"❌ Discovery pipeline failed: {e}")
            self._update_job(job_key, DiscoveryStep.FAILED, error=str(e))
    
    async def _run_pipeline(
        self,
        job_id: UUID,
        user_id: UUID,
        area_polygon: Dict[str, Any],
        filters: DiscoveryFilters,
        db: Session
    ) -> None:
        """Run the complete discovery pipeline."""
        job_key = str(job_id)
        start_time = datetime.utcnow()
        
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"🚀 DISCOVERY PIPELINE STARTED")
        logger.info(f"   Job ID: {job_id}")
        logger.info(f"   User ID: {user_id}")
        logger.info(f"   Max lots to process: {filters.max_lots}")
        logger.info("=" * 60)
        
        # ============ Step 1: Collect parking lots ============
        logger.info("")
        logger.info("📍 STEP 1: Collecting parking lots from APIs...")
        self._update_job(job_key, DiscoveryStep.COLLECTING_PARKING_LOTS)
        
        raw_lots = await parking_lot_discovery_service.discover_parking_lots(area_polygon)
        self._jobs[job_key]["progress"].parking_lots_found = len(raw_lots)
        
        logger.info(f"   ✅ Found {len(raw_lots)} raw parking lots from all sources")
        
        # ============ Step 2: Normalize and deduplicate ============
        logger.info("")
        logger.info("🔄 STEP 2: Normalizing and deduplicating...")
        self._update_job(job_key, DiscoveryStep.NORMALIZING)
        
        normalized_lots = normalization_service.normalize_and_deduplicate(raw_lots)
        logger.info(f"   ✅ Normalized to {len(normalized_lots)} unique lots")
        
        # Apply max_lots limit
        if len(normalized_lots) > filters.max_lots:
            logger.info(f"   ⚠️  Limiting to {filters.max_lots} lots (from {len(normalized_lots)})")
            normalized_lots = normalized_lots[:filters.max_lots]
        
        # ============ Step 3: Save to database ============
        logger.info("")
        logger.info("💾 STEP 3: Saving parking lots to database...")
        
        saved_lots = normalization_service.save_to_database(normalized_lots, user_id, db)
        parking_lot_ids = [lot.id for lot in saved_lots]
        
        logger.info(f"   ✅ Saved {len(saved_lots)} parking lots to database")
        for i, lot in enumerate(saved_lots[:5]):  # Log first 5
            logger.info(f"      [{i+1}] ID: {lot.id}, Area: {lot.area_m2:.0f}m²")
        if len(saved_lots) > 5:
            logger.info(f"      ... and {len(saved_lots) - 5} more")
        
        # ============ Step 4: Fetch imagery and evaluate condition ============
        logger.info("")
        logger.info("🛰️  STEP 4: Fetching satellite imagery...")
        self._update_job(job_key, DiscoveryStep.FETCHING_IMAGERY)
        
        await self._fetch_imagery_and_evaluate(parking_lot_ids, db, job_key, user_id, job_id)
        
        evaluated_count = self._jobs[job_key]["progress"].parking_lots_evaluated
        logger.info(f"   ✅ Evaluated {evaluated_count}/{len(parking_lot_ids)} parking lots")
        
        # ============ Step 5: Load businesses ============
        logger.info("")
        logger.info("🏢 STEP 5: Loading business data...")
        self._update_job(job_key, DiscoveryStep.LOADING_BUSINESSES)
        
        raw_businesses = await business_data_service.load_businesses(
            area_polygon, 
            max_businesses=filters.max_businesses
        )
        logger.info(f"   📥 Fetched {len(raw_businesses)} businesses from Google Places")
        
        saved_businesses = business_data_service.save_to_database(raw_businesses, db)
        self._jobs[job_key]["progress"].businesses_loaded = len(saved_businesses)
        
        logger.info(f"   ✅ Saved {len(saved_businesses)} businesses to database")
        for i, biz in enumerate(saved_businesses[:5]):  # Log first 5
            logger.info(f"      [{i+1}] {biz.name} - {biz.category or 'Unknown category'}")
        if len(saved_businesses) > 5:
            logger.info(f"      ... and {len(saved_businesses) - 5} more")
        
        # ============ Step 6: Associate parking lots with businesses ============
        logger.info("")
        logger.info("🔗 STEP 6: Associating parking lots with businesses...")
        self._update_job(job_key, DiscoveryStep.ASSOCIATING)
        
        assoc_stats = association_service.associate_parking_lots_with_businesses(
            parking_lot_ids, db
        )
        self._jobs[job_key]["progress"].associations_made = assoc_stats["associations_made"]
        
        logger.info(f"   ✅ Made {assoc_stats['associations_made']} associations")
        logger.info(f"      Lots with business: {assoc_stats.get('lots_with_business', 0)}")
        logger.info(f"      Avg match score: {assoc_stats.get('avg_match_score', 0):.1f}")
        
        # ============ Step 7: Filter high-value leads ============
        logger.info("")
        logger.info("🎯 STEP 7: Filtering high-value leads...")
        self._update_job(job_key, DiscoveryStep.FILTERING)
        
        high_value_count = self._count_high_value_leads(parking_lot_ids, filters, db)
        self._jobs[job_key]["progress"].high_value_leads = high_value_count
        
        logger.info(f"   ✅ Found {high_value_count} high-value leads")
        logger.info(f"      (condition_score <= {filters.max_condition_score}, area >= {filters.min_area_m2}m²)")
        
        # ============ Complete ============
        self._update_job(job_key, DiscoveryStep.COMPLETED)
        self._jobs[job_key]["completed_at"] = datetime.utcnow()
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"✅ DISCOVERY PIPELINE COMPLETED")
        logger.info(f"   Job ID: {job_id}")
        logger.info(f"   Duration: {elapsed:.1f} seconds")
        logger.info(f"   Parking lots found: {len(raw_lots)}")
        logger.info(f"   Parking lots processed: {len(saved_lots)}")
        logger.info(f"   Parking lots evaluated: {evaluated_count}")
        logger.info(f"   Businesses loaded: {len(saved_businesses)}")
        logger.info(f"   Associations made: {assoc_stats['associations_made']}")
        logger.info(f"   High-value leads: {high_value_count}")
        logger.info("=" * 60)
        logger.info("")
        
        # Log usage for the complete discovery job
        usage_tracking_service.log_discovery_job(
            db=db,
            user_id=user_id,
            job_id=job_id,
            parking_lots_found=len(raw_lots),
            parking_lots_evaluated=evaluated_count,
            businesses_loaded=len(saved_businesses),
            metadata={
                "high_value_leads": high_value_count,
                "associations_made": assoc_stats["associations_made"],
                "duration_seconds": elapsed,
            }
        )
    
    async def _fetch_imagery_and_evaluate(
        self,
        parking_lot_ids: List[UUID],
        db: Session,
        job_key: str,
        user_id: UUID,
        job_id: UUID
    ) -> None:
        """Fetch imagery and evaluate condition for each parking lot."""
        evaluated_count = 0
        total = len(parking_lot_ids)
        
        for idx, lot_id in enumerate(parking_lot_ids):
            try:
                lot = db.query(ParkingLot).filter(ParkingLot.id == lot_id).first()
                if not lot:
                    continue
                
                logger.info(f"   [{idx+1}/{total}] Processing lot {lot_id}...")
                
                # Get centroid coordinates
                centroid = to_shape(lot.centroid)
                lat, lng = centroid.y, centroid.x
                
                logger.info(f"      📍 Location: {lat:.6f}, {lng:.6f}")
                
                # Get polygon if available
                polygon = to_shape(lot.geometry) if lot.geometry else None
                
                # Fetch imagery
                logger.info(f"      🛰️  Fetching satellite image...")
                image_bytes, storage_path, image_url = await imagery_service.fetch_imagery_for_parking_lot(
                    lot_id,
                    lat,
                    lng,
                    polygon
                )
                
                if image_bytes:
                    logger.info(f"      ✅ Image fetched: {len(image_bytes)/1024:.1f} KB")
                    
                    # Update lot with imagery info
                    lot.satellite_image_url = image_url
                    lot.satellite_image_path = storage_path
                    lot.image_captured_at = datetime.utcnow()
                    
                    # Evaluate condition
                    self._jobs[job_key]["progress"].current_step = DiscoveryStep.EVALUATING_CONDITION
                    
                    logger.info(f"      🤖 Running CV analysis...")
                    condition = await condition_evaluation_service.evaluate_condition(
                        image_bytes,
                        parking_lot_id=str(lot_id)
                    )
                    
                    lot.condition_score = condition.get("condition_score")
                    lot.crack_density = condition.get("crack_density")
                    lot.pothole_score = condition.get("pothole_score")
                    lot.line_fading_score = condition.get("line_fading_score")
                    lot.degradation_areas = condition.get("degradation_areas")
                    lot.is_evaluated = True
                    lot.evaluated_at = datetime.utcnow()
                    
                    if condition.get("error"):
                        lot.evaluation_error = condition["error"]
                        logger.warning(f"      ⚠️  CV error: {condition['error']}")
                    else:
                        logger.info(f"      📊 Condition score: {lot.condition_score}/100")
                    
                    # Log CV usage
                    usage_tracking_service.log_cv_evaluation(
                        db=db,
                        user_id=user_id,
                        parking_lot_id=lot_id,
                        job_id=job_id,
                        bytes_processed=len(image_bytes),
                        evaluation_time_seconds=condition.get("evaluation_time_seconds", 0),
                        detections=condition.get("detection_count", 0),
                    )
                    
                    evaluated_count += 1
                else:
                    logger.warning(f"      ❌ Failed to fetch imagery")
                    lot.evaluation_error = "Failed to fetch imagery"
                
                db.commit()
                self._jobs[job_key]["progress"].parking_lots_evaluated = evaluated_count
                
            except Exception as e:
                logger.error(f"      ❌ Error processing lot {lot_id}: {e}")
                try:
                    lot = db.query(ParkingLot).filter(ParkingLot.id == lot_id).first()
                    if lot:
                        lot.evaluation_error = str(e)
                        db.commit()
                except:
                    pass
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.2)
    
    def _count_high_value_leads(
        self,
        parking_lot_ids: List[UUID],
        filters: DiscoveryFilters,
        db: Session
    ) -> int:
        """Count parking lots that meet high-value lead criteria."""
        query = db.query(ParkingLot).filter(
            ParkingLot.id.in_(parking_lot_ids),
            ParkingLot.is_evaluated == True,
        )
        
        if filters.min_area_m2:
            query = query.filter(ParkingLot.area_m2 >= filters.min_area_m2)
        
        if filters.max_condition_score:
            query = query.filter(ParkingLot.condition_score <= filters.max_condition_score)
        
        return query.count()
    
    def _update_job(
        self,
        job_key: str,
        step: DiscoveryStep,
        error: Optional[str] = None
    ) -> None:
        """Update job status."""
        if job_key not in self._jobs:
            return
        
        self._jobs[job_key]["status"] = step
        self._jobs[job_key]["progress"].current_step = step
        
        step_order = [
            DiscoveryStep.QUEUED,
            DiscoveryStep.CONVERTING_AREA,
            DiscoveryStep.COLLECTING_PARKING_LOTS,
            DiscoveryStep.NORMALIZING,
            DiscoveryStep.FETCHING_IMAGERY,
            DiscoveryStep.EVALUATING_CONDITION,
            DiscoveryStep.LOADING_BUSINESSES,
            DiscoveryStep.ASSOCIATING,
            DiscoveryStep.FILTERING,
            DiscoveryStep.COMPLETED,
        ]
        
        if step in step_order:
            self._jobs[job_key]["progress"].steps_completed = step_order.index(step)
        
        if error:
            self._jobs[job_key]["error"] = error
            self._jobs[job_key]["progress"].errors.append(error)
    
    def get_job_status(self, job_id: UUID) -> Optional[Dict[str, Any]]:
        """Get current job status."""
        job_key = str(job_id)
        return self._jobs.get(job_key)
    
    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """Remove old completed jobs from memory."""
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        removed = 0
        
        for job_key in list(self._jobs.keys()):
            job = self._jobs[job_key]
            if job.get("completed_at") and job["completed_at"] < cutoff:
                del self._jobs[job_key]
                removed += 1
        
        return removed


# Singleton instance
discovery_orchestrator = DiscoveryOrchestrator()
