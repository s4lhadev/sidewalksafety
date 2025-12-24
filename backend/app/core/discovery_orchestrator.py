import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from uuid import UUID
from enum import Enum
from sqlalchemy.orm import Session
from shapely.geometry import shape
from geoalchemy2.shape import to_shape, from_shape

from app.models.parking_lot import ParkingLot
from app.models.business import Business
from app.models.association import ParkingLotBusinessAssociation
from app.schemas.discovery import DiscoveryStep, DiscoveryProgress, DiscoveryFilters
from app.core.parking_lot_discovery_service import parking_lot_discovery_service
from app.core.normalization_service import normalization_service
from app.core.business_data_service import business_data_service
from app.core.association_service import association_service
from app.core.imagery_service import imagery_service
from app.core.condition_evaluation_service import condition_evaluation_service
from app.core.usage_tracking_service import usage_tracking_service
from app.core.business_first_discovery_service import (
    business_first_discovery_service,
    BusinessTier,
    DiscoveredBusiness,
)
from app.core.parking_lot_finder_service import parking_lot_finder_service
from app.core.config import settings

# NEW: Two-stage CV pipeline services
from app.core.asphalt_segmentation_service import asphalt_segmentation_service
from app.core.property_association_service import property_association_service
from app.core.cv_visualization_service import cv_visualization_service
from app.core.regrid_service import regrid_service
from app.models.property_analysis import PropertyAnalysis
from app.models.asphalt_area import AsphaltArea
from app.models.cv_image import CVImage
import os
import math


class DiscoveryMode(str, Enum):
    """Discovery pipeline mode."""
    BUSINESS_FIRST = "business_first"  # Find businesses → parking lots
    PARKING_FIRST = "parking_first"    # Find parking lots → businesses (legacy)

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
        db: Session,
        mode: DiscoveryMode = DiscoveryMode.BUSINESS_FIRST,
        tiers: Optional[List[str]] = None,
        business_type_ids: Optional[List[str]] = None,
    ) -> None:
        """
        Start the discovery pipeline.
        This runs as a background task.
        
        Args:
            job_id: Unique job identifier
            user_id: User running the job
            area_polygon: GeoJSON polygon defining search area
            filters: Discovery filters (max_lots, etc.)
            db: Database session
            mode: Discovery mode (business_first or parking_first)
            tiers: List of tiers to search ("premium", "high", "standard")
            business_type_ids: Specific business type IDs to search
        """
        job_key = str(job_id)
        
        # Ensure job is initialized (might already be done by initialize_job)
        if job_key not in self._jobs:
            self.initialize_job(job_id, user_id)
        
        self._jobs[job_key]["mode"] = mode.value
        self._jobs[job_key]["tiers"] = tiers
        self._jobs[job_key]["business_type_ids"] = business_type_ids
        
        try:
            if mode == DiscoveryMode.BUSINESS_FIRST:
                await self._run_business_first_pipeline(
                    job_id, user_id, area_polygon, filters, db,
                    tiers=tiers,
                    business_type_ids=business_type_ids,
                )
            else:
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
                "mode": "parking_first",
            }
        )
    
    async def _run_business_first_pipeline(
        self,
        job_id: UUID,
        user_id: UUID,
        area_polygon: Dict[str, Any],
        filters: DiscoveryFilters,
        db: Session,
        tiers: Optional[List[str]] = None,
        business_type_ids: Optional[List[str]] = None,
    ) -> None:
        """
        Run the business-first discovery pipeline.
        
        1. Find businesses by type (HOA, apartments, etc.)
        2. Find parking lots near each business
        3. Fetch imagery and evaluate condition
        4. Create leads with business + parking lot + score
        
        Args:
            tiers: List of tier strings to search ("premium", "high", "standard")
            business_type_ids: Specific business type IDs to search
        """
        job_key = str(job_id)
        start_time = datetime.utcnow()
        
        # Convert tier strings to BusinessTier enums
        tier_enums = None
        if tiers:
            tier_enums = []
            for t in tiers:
                if t == "premium":
                    tier_enums.append(BusinessTier.PREMIUM)
                elif t == "high":
                    tier_enums.append(BusinessTier.HIGH)
                elif t == "standard":
                    tier_enums.append(BusinessTier.STANDARD)
        
        tier_desc = ", ".join(tiers) if tiers else "all"
        
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"🚀 BUSINESS-FIRST DISCOVERY PIPELINE STARTED")
        logger.info(f"   Job ID: {job_id}")
        logger.info(f"   User ID: {user_id}")
        logger.info(f"   Max results: {filters.max_lots}")
        logger.info(f"   Tiers: {tier_desc}")
        if business_type_ids:
            logger.info(f"   Business types: {', '.join(business_type_ids)}")
        logger.info("=" * 60)
        
        # Get polygon centroid and bounds
        poly = shape(area_polygon)
        centroid = poly.centroid
        bounds = poly.bounds  # (minx, miny, maxx, maxy)
        
        # Calculate search radius from bounds
        lat_range = bounds[3] - bounds[1]
        lng_range = bounds[2] - bounds[0]
        radius_meters = int(max(lat_range, lng_range) * 111000 / 2 * 1.2)
        radius_meters = min(radius_meters, 50000)  # Cap at 50km
        
        # ============ Step 1: Discover businesses by type ============
        logger.info("")
        logger.info("🏢 STEP 1: Discovering businesses by type...")
        self._update_job(job_key, DiscoveryStep.LOADING_BUSINESSES)
        
        discovered_businesses = await business_first_discovery_service.discover_businesses(
            center_lat=centroid.y,
            center_lng=centroid.x,
            radius_meters=radius_meters,
            tiers=tier_enums,
            business_type_ids=business_type_ids,
            max_per_tier=20,
            max_total=filters.max_lots,
        )
        
        # Count by tier
        premium_count = len([b for b in discovered_businesses if b.tier == BusinessTier.PREMIUM])
        high_count = len([b for b in discovered_businesses if b.tier == BusinessTier.HIGH])
        standard_count = len([b for b in discovered_businesses if b.tier == BusinessTier.STANDARD])
        
        logger.info(f"   ✅ Found {len(discovered_businesses)} businesses:")
        logger.info(f"      🏆 Premium (HOA/Apartments): {premium_count}")
        logger.info(f"      ⭐ High (Shopping/Hotels): {high_count}")
        logger.info(f"      📍 Standard (Other): {standard_count}")
        
        self._jobs[job_key]["progress"].businesses_loaded = len(discovered_businesses)
        
        if not discovered_businesses:
            logger.warning("   ⚠️  No businesses found in area")
            self._update_job(job_key, DiscoveryStep.COMPLETED)
            return
        
        # ============ Step 2: Find parking lots for each business ============
        logger.info("")
        logger.info("🅿️  STEP 2: Finding parking lots for each business...")
        self._update_job(job_key, DiscoveryStep.COLLECTING_PARKING_LOTS)
        
        processed_count = 0
        evaluated_count = 0
        parking_lot_ids: List[UUID] = []
        
        for idx, business in enumerate(discovered_businesses):
            try:
                logger.info(f"   [{idx+1}/{len(discovered_businesses)}] {business.name} ({business.tier.value})")
                
                # Find parking lot near business
                found_lot = await parking_lot_finder_service.find_parking_lot(
                    business_lat=business.latitude,
                    business_lng=business.longitude,
                    business_type=business.business_type,
                    search_radius_m=150,
                )
                
                logger.info(f"      📍 Found {found_lot.source} parking lot: {found_lot.area_m2:.0f}m²")
                
                # Save business to database
                existing_business = db.query(Business).filter(
                    Business.places_id == business.places_id
                ).first()
                
                if existing_business:
                    db_business = existing_business
                    # Update contact info if we have new data
                    if business.phone and not existing_business.phone:
                        existing_business.phone = business.phone
                    if business.website and not existing_business.website:
                        existing_business.website = business.website
                else:
                    db_business = Business(
                        places_id=business.places_id,
                        name=business.name,
                        address=business.address,
                        phone=business.phone,
                        website=business.website,
                        category=business.business_type,
                        geometry=from_shape(business.location, srid=4326),
                        data_source="google_places",
                        raw_metadata=business.raw_data,
                    )
                    db.add(db_business)
                    db.flush()
                
                # Save parking lot to database
                db_lot = ParkingLot(
                    user_id=user_id,
                    geometry=from_shape(found_lot.geometry, srid=4326) if found_lot.geometry else None,
                    centroid=from_shape(found_lot.centroid, srid=4326),
                    area_m2=found_lot.area_m2,
                    area_sqft=found_lot.area_sqft,
                    osm_id=found_lot.source_id if found_lot.source == "osm" else None,
                    data_sources=[found_lot.source],
                    operator_name=business.name,
                    address=business.address,
                    surface_type=found_lot.surface_type,
                    raw_metadata=found_lot.raw_data,
                    business_type_tier=business.tier.value,
                    discovery_mode="business_first",
                )
                db.add(db_lot)
                db.flush()
                
                parking_lot_ids.append(db_lot.id)
                
                # Create association
                association = ParkingLotBusinessAssociation(
                    parking_lot_id=db_lot.id,
                    business_id=db_business.id,
                    match_score=95.0,  # High score since we found business first
                    distance_meters=0,  # Parking lot is for this business
                    association_method="business_first",
                    is_primary=True,
                )
                db.add(association)
                
                processed_count += 1
                
                # ============ Step 3: NEW - Get Property Boundary from Regrid ============
                logger.info(f"      🗺️  Fetching property boundary from Regrid...")
                
                property_parcel = None
                property_boundary_source = "estimated"
                
                if regrid_service.is_configured:
                    # Try to get parcel by coordinates first
                    property_parcel = await regrid_service.get_parcel_by_coordinates(
                        lat=business.latitude,
                        lng=business.longitude
                    )
                    
                    # If not found, try by address
                    if not property_parcel and business.address:
                        property_parcel = await regrid_service.get_parcel_by_address(
                            address=business.address
                        )
                    
                    if property_parcel:
                        property_boundary_source = "regrid"
                        logger.info(f"      ✅ Property boundary from Regrid: {property_parcel.area_m2:.0f} m²")
                        if property_parcel.owner:
                            logger.info(f"         Owner: {property_parcel.owner[:50]}...")
                    else:
                        logger.warning(f"      ⚠️ No property boundary from Regrid, will use CV fallback")
                else:
                    logger.warning(f"      ⚠️ Regrid not configured, using CV-based boundary detection")
                
                # ============ Step 4: Fetch WIDE satellite image ============
                logger.info(f"      🛰️  Fetching WIDE satellite image (150m radius)...")
                
                wide_image, image_bounds = await self._fetch_wide_satellite_image(
                    business.latitude, business.longitude
                )
                
                if wide_image:
                    logger.info(f"      ✅ Wide image fetched: {len(wide_image)/1024:.1f} KB")
                    
                    # ============ Step 5: Run segmentation for asphalt detection ============
                    logger.info(f"      🔍 Running CV: Asphalt Segmentation...")
                    segmentation = await asphalt_segmentation_service.segment_property(
                        image_bytes=wide_image,
                        image_bounds=image_bounds
                    )
                    
                    logger.info(f"         Detected {len(segmentation.buildings)} buildings, {len(segmentation.paved_surfaces)} paved surfaces")
                    
                    # ============ Step 6: Associate asphalt with property ============
                    # If we have Regrid boundary, use it to filter asphalt areas
                    # Otherwise, use the old proximity-based association
                    logger.info(f"      🔗 Associating asphalt with property (source: {property_boundary_source})...")
                    
                    if property_parcel:
                        # Filter segmented areas to only those within property boundary
                        business_building, associated_areas = property_association_service.associate_with_property_boundary(
                            buildings=segmentation.buildings,
                            paved_surfaces=segmentation.paved_surfaces,
                            property_boundary=property_parcel.polygon,
                            business_location=(business.latitude, business.longitude)
                        )
                    else:
                        # Fallback: use proximity-based association
                        business_building, associated_areas = property_association_service.associate_with_business(
                            buildings=segmentation.buildings,
                            paved_surfaces=segmentation.paved_surfaces,
                            business_location=(business.latitude, business.longitude)
                        )
                    
                    associated_count = sum(1 for a in associated_areas if a.is_associated)
                    total_area = sum(a.area_m2 for a in associated_areas if a.is_associated)
                    logger.info(f"         Associated {associated_count} areas, total {total_area:.0f} m²")
                    
                    # Stage 4: Evaluate condition on associated areas
                    logger.info(f"      🔬 Running Stage 2 CV: Condition evaluation...")
                    condition_results = []
                    total_cracks = 0
                    total_potholes = 0
                    
                    for area in associated_areas:
                        if area.is_associated:
                            # Run condition evaluation on the whole wide image for now
                            # In production, we'd crop to each polygon
                            eval_result = await condition_evaluation_service.evaluate_condition(
                                image_bytes=wide_image,
                                parking_lot_id=str(db_lot.id)
                            )
                            
                            if eval_result:
                                from app.core.cv_visualization_service import ConditionResult
                                condition_results.append(ConditionResult(
                                    area=area,
                                    condition_score=eval_result.get("condition_score", 100),
                                    crack_count=eval_result.get("detection_count", 0),
                                    pothole_count=len([d for d in eval_result.get("degradation_areas", []) if "pothole" in d.get("class", "").lower()]),
                                    crack_density=eval_result.get("crack_density", 0),
                                    detections=eval_result.get("degradation_areas", [])
                                ))
                                total_cracks += eval_result.get("detection_count", 0)
                            break  # Only evaluate once for now
                    
                    # Calculate weighted condition score
                    if condition_results and total_area > 0:
                        weighted_score = sum(
                            r.condition_score * r.area.area_m2 
                            for r in condition_results if r.condition_score
                        ) / total_area
                    else:
                        weighted_score = 100
                    
                    logger.info(f"         Condition score: {weighted_score:.1f}/100, {total_cracks} cracks, {total_potholes} potholes")
                    
                    # Stage 5: Generate annotated images
                    logger.info(f"      🎨 Generating annotated images...")
                    annotated_images = await cv_visualization_service.generate_all_images(
                        original_image=wide_image,
                        segmentation=segmentation,
                        business_building=business_building,
                        associated_areas=associated_areas,
                        condition_results=condition_results
                    )
                    
                    # Stage 6: Store images as base64 and create/update PropertyAnalysis record
                    analysis_id = db_lot.id  # Use same ID for simplicity
                    
                    # Convert images to base64
                    import base64
                    wide_satellite_b64 = base64.b64encode(wide_image).decode('utf-8') if wide_image else None
                    segmentation_b64 = base64.b64encode(annotated_images.segmentation).decode('utf-8') if annotated_images.segmentation else None
                    property_boundary_b64 = base64.b64encode(annotated_images.property_boundary).decode('utf-8') if annotated_images.property_boundary else None
                    condition_analysis_b64 = base64.b64encode(annotated_images.condition_analysis).decode('utf-8') if annotated_images.condition_analysis else None
                    
                    logger.info(f"      💾 Encoded 4 images as base64")
                    logger.info(f"         wide_satellite: {len(wide_satellite_b64) if wide_satellite_b64 else 0} chars")
                    logger.info(f"         segmentation: {len(segmentation_b64) if segmentation_b64 else 0} chars")
                    
                    # Check if PropertyAnalysis already exists (update) or create new
                    existing_analysis = db.query(PropertyAnalysis).filter(
                        PropertyAnalysis.parking_lot_id == db_lot.id
                    ).first()
                    
                    if existing_analysis:
                        # Update existing record
                        logger.info(f"      📝 Updating existing PropertyAnalysis {existing_analysis.id}")
                        existing_analysis.business_id = db_business.id
                        existing_analysis.business_location = from_shape(business.location, srid=4326)
                        existing_analysis.wide_image_base64 = wide_satellite_b64
                        existing_analysis.wide_image_bounds = image_bounds
                        existing_analysis.segmentation_model_id = settings.ROBOFLOW_SEGMENTATION_MODEL
                        existing_analysis.segmentation_image_base64 = segmentation_b64
                        existing_analysis.property_boundary_image_base64 = property_boundary_b64
                        existing_analysis.condition_analysis_image_base64 = condition_analysis_b64
                        existing_analysis.raw_segmentation_data = segmentation.raw_response
                        existing_analysis.total_asphalt_area_m2 = total_area
                        existing_analysis.weighted_condition_score = weighted_score
                        existing_analysis.total_crack_count = total_cracks
                        existing_analysis.total_pothole_count = total_potholes
                        existing_analysis.status = "completed"
                        existing_analysis.analyzed_at = datetime.utcnow()
                        
                        # Store Regrid property boundary data
                        existing_analysis.property_boundary_source = property_boundary_source
                        if property_parcel:
                            existing_analysis.property_boundary_polygon = from_shape(property_parcel.polygon, srid=4326)
                            existing_analysis.property_parcel_id = property_parcel.parcel_id
                            existing_analysis.property_owner = property_parcel.owner
                            existing_analysis.property_apn = property_parcel.apn
                            existing_analysis.property_land_use = property_parcel.land_use
                            existing_analysis.property_zoning = property_parcel.zoning
                        
                        property_analysis = existing_analysis
                        
                        # Delete old asphalt areas
                        db.query(AsphaltArea).filter(
                            AsphaltArea.property_analysis_id == existing_analysis.id
                        ).delete()
                    else:
                        # Create new PropertyAnalysis record
                        logger.info(f"      ➕ Creating new PropertyAnalysis {analysis_id}")
                        property_analysis = PropertyAnalysis(
                            id=analysis_id,
                            parking_lot_id=db_lot.id,
                            business_id=db_business.id,
                            user_id=user_id,
                            business_location=from_shape(business.location, srid=4326),
                            wide_image_base64=wide_satellite_b64,
                            wide_image_bounds=image_bounds,
                            segmentation_model_id=settings.ROBOFLOW_SEGMENTATION_MODEL,
                            segmentation_image_base64=segmentation_b64,
                            property_boundary_image_base64=property_boundary_b64,
                            condition_analysis_image_base64=condition_analysis_b64,
                            raw_segmentation_data=segmentation.raw_response,
                            total_asphalt_area_m2=total_area,
                            weighted_condition_score=weighted_score,
                            total_crack_count=total_cracks,
                            total_pothole_count=total_potholes,
                            status="completed",
                            analyzed_at=datetime.utcnow(),
                            # Regrid property boundary data
                            property_boundary_source=property_boundary_source,
                            property_boundary_polygon=from_shape(property_parcel.polygon, srid=4326) if property_parcel else None,
                            property_parcel_id=property_parcel.parcel_id if property_parcel else None,
                            property_owner=property_parcel.owner if property_parcel else None,
                            property_apn=property_parcel.apn if property_parcel else None,
                            property_land_use=property_parcel.land_use if property_parcel else None,
                            property_zoning=property_parcel.zoning if property_parcel else None,
                        )
                        db.add(property_analysis)
                    
                    # Create AsphaltArea records
                    for area in associated_areas:
                        condition = next((r for r in condition_results if r.area == area), None)
                        
                        asphalt_area = AsphaltArea(
                            property_analysis_id=analysis_id,
                            polygon=from_shape(area.polygon, srid=4326),
                            centroid=from_shape(area.polygon.centroid, srid=4326),
                            area_m2=area.area_m2,
                            pixel_coordinates=area.pixel_points,
                            area_type=area.area_type,
                            segmentation_confidence=area.confidence,
                            segmentation_class=area.class_name,
                            is_associated=area.is_associated,
                            association_reason=area.association_reason,
                            distance_to_building_m=area.distance_to_building_m,
                            condition_score=condition.condition_score if condition else None,
                            crack_count=condition.crack_count if condition else None,
                            pothole_count=condition.pothole_count if condition else None,
                            crack_density=condition.crack_density if condition else None,
                            detections=condition.detections if condition else None,
                        )
                        db.add(asphalt_area)
                    
                    # Update parking lot with results
                    # satellite_image_url is now handled by property_analysis.images
                    db_lot.satellite_image_url = None  # Images stored in PropertyAnalysis
                    db_lot.condition_score = weighted_score
                    db_lot.area_m2 = total_area if total_area > 0 else found_lot.area_m2
                    db_lot.is_evaluated = True
                    db_lot.evaluated_at = datetime.utcnow()
                    db_lot.degradation_areas = [
                        {"class": d.get("class"), "confidence": d.get("confidence"), "x": d.get("x"), "y": d.get("y")}
                        for r in condition_results for d in r.detections
                    ] if condition_results else None
                    
                    logger.info(f"      ✅ Two-Stage CV Complete: {associated_count} areas, {total_area:.0f}m², score={weighted_score:.0f}/100")
                    
                    # Log CV usage
                    usage_tracking_service.log_cv_evaluation(
                        db=db,
                        user_id=user_id,
                        parking_lot_id=db_lot.id,
                        job_id=job_id,
                        bytes_processed=len(wide_image),
                        evaluation_time_seconds=0,
                        detections=total_cracks,
                    )
                    
                    evaluated_count += 1
                else:
                    logger.warning(f"      ❌ Failed to fetch wide imagery")
                    db_lot.evaluation_error = "Failed to fetch wide imagery"
                
                db.commit()
                self._jobs[job_key]["progress"].parking_lots_evaluated = evaluated_count
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.3)
                
            except Exception as e:
                logger.error(f"      ❌ Error processing business: {e}")
                db.rollback()
        
        self._jobs[job_key]["progress"].parking_lots_found = processed_count
        self._jobs[job_key]["progress"].associations_made = processed_count
        
        # ============ Step 4: Count high-value leads ============
        logger.info("")
        logger.info("🎯 STEP 4: Counting high-value leads...")
        self._update_job(job_key, DiscoveryStep.FILTERING)
        
        high_value_count = self._count_high_value_leads(parking_lot_ids, filters, db)
        self._jobs[job_key]["progress"].high_value_leads = high_value_count
        
        logger.info(f"   ✅ Found {high_value_count} high-value leads")
        logger.info(f"      (condition_score <= {filters.max_condition_score})")
        
        # ============ Complete ============
        self._update_job(job_key, DiscoveryStep.COMPLETED)
        self._jobs[job_key]["completed_at"] = datetime.utcnow()
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"✅ BUSINESS-FIRST DISCOVERY COMPLETED")
        logger.info(f"   Job ID: {job_id}")
        logger.info(f"   Duration: {elapsed:.1f} seconds")
        logger.info(f"   Businesses found: {len(discovered_businesses)}")
        logger.info(f"   Parking lots processed: {processed_count}")
        logger.info(f"   Parking lots evaluated: {evaluated_count}")
        logger.info(f"   High-value leads: {high_value_count}")
        logger.info(f"   By tier:")
        logger.info(f"      🏆 Premium: {premium_count}")
        logger.info(f"      ⭐ High: {high_count}")
        logger.info(f"      📍 Standard: {standard_count}")
        logger.info("=" * 60)
        logger.info("")
        
        # Log usage
        usage_tracking_service.log_discovery_job(
            db=db,
            user_id=user_id,
            job_id=job_id,
            parking_lots_found=processed_count,
            parking_lots_evaluated=evaluated_count,
            businesses_loaded=len(discovered_businesses),
            metadata={
                "high_value_leads": high_value_count,
                "associations_made": processed_count,
                "duration_seconds": elapsed,
                "mode": "business_first",
                "tiers": {
                    "premium": premium_count,
                    "high": high_count,
                    "standard": standard_count,
                },
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
                
                # Fetch imagery using polygon bounds
                logger.info(f"      🛰️  Fetching satellite image...")
                image_bytes, storage_path, image_url = await imagery_service.fetch_imagery_for_parking_lot(
                    lot_id,
                    lat,
                    lng,
                    polygon,
                    area_m2=float(lot.area_m2) if lot.area_m2 else None
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
    
    async def _fetch_wide_satellite_image(
        self,
        lat: float,
        lng: float,
        radius_m: float = 150.0
    ) -> tuple:
        """
        Fetch a wide satellite image centered on a location.
        
        Returns:
            Tuple of (image_bytes, bounds_dict)
        """
        if not settings.GOOGLE_MAPS_KEY:
            return None, None
        
        # Calculate zoom level for desired radius
        diameter_m = radius_m * 2
        image_size = 640  # Google Maps Static API max
        
        meters_per_pixel_at_z0 = 156543.03 * math.cos(math.radians(lat))
        zoom_float = math.log2(image_size * meters_per_pixel_at_z0 / diameter_m)
        zoom = int(math.floor(zoom_float))
        zoom = max(15, min(20, zoom))
        
        # Calculate actual bounds at this zoom
        meters_per_pixel = 156543.03 * math.cos(math.radians(lat)) / (2 ** zoom)
        half_size_m = (image_size / 2) * meters_per_pixel
        
        lat_offset = half_size_m / 111000
        lng_offset = half_size_m / (111000 * math.cos(math.radians(lat)))
        
        bounds = {
            "min_lat": lat - lat_offset,
            "max_lat": lat + lat_offset,
            "min_lng": lng - lng_offset,
            "max_lng": lng + lng_offset
        }
        
        # Fetch image using existing imagery service
        image_bytes = await imagery_service._fetch_satellite_image(lat, lng, zoom)
        
        return image_bytes, bounds
    
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
