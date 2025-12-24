"""
PropertyAnalysisService - Main orchestrator for two-stage CV pipeline

Coordinates the complete property analysis:
1. Fetch wide satellite image
2. Run segmentation (Stage 1 CV)
3. Associate asphalt with business
4. Evaluate condition (Stage 2 CV)
5. Generate annotated images
6. Store results
"""
import logging
import math
import os
import uuid
from typing import Tuple, Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass

from sqlalchemy.orm import Session
from shapely.geometry import Point
from geoalchemy2.shape import from_shape

from app.core.config import settings
from app.core.imagery_service import imagery_service
from app.core.asphalt_segmentation_service import asphalt_segmentation_service, SegmentationResult
from app.core.property_association_service import property_association_service, AssociatedAsphaltArea
from app.core.cv_visualization_service import cv_visualization_service, ConditionResult
from app.core.condition_evaluation_service import condition_evaluation_service
from app.models.property_analysis import PropertyAnalysis
from app.models.asphalt_area import AsphaltArea
from app.models.cv_image import CVImage

logger = logging.getLogger(__name__)


@dataclass
class PropertyAnalysisResult:
    """Complete result from property analysis."""
    property_analysis: PropertyAnalysis
    asphalt_areas: List[AsphaltArea]
    images: Dict[str, str]  # {type: url}
    success: bool
    error: Optional[str] = None


class PropertyAnalysisService:
    """
    Orchestrates the complete two-stage CV pipeline.
    
    Pipeline:
    1. Fetch wide satellite image around business
    2. Run segmentation to detect buildings + paved surfaces
    3. Associate paved surfaces with the business
    4. Run condition evaluation on associated areas
    5. Generate annotated images
    6. Store everything in database
    """
    
    def __init__(self):
        self.wide_image_radius = settings.WIDE_IMAGE_RADIUS_METERS
        self.image_size = settings.WIDE_IMAGE_SIZE
        
        # Create storage directory if needed
        self.storage_path = settings.CV_IMAGE_STORAGE_PATH
        if settings.CV_IMAGE_STORAGE_TYPE == "local":
            os.makedirs(self.storage_path, exist_ok=True)
    
    async def analyze_property(
        self,
        business_location: Tuple[float, float],  # (lat, lng)
        user_id: str,
        db: Session,
        business_id: Optional[str] = None,
        parking_lot_id: Optional[str] = None,
        job_id: Optional[str] = None
    ) -> PropertyAnalysisResult:
        """
        Run complete property analysis pipeline.
        
        Args:
            business_location: (lat, lng) of the business
            user_id: User performing the analysis
            db: Database session
            business_id: Optional linked business ID
            parking_lot_id: Optional linked parking lot ID
            job_id: Optional job ID for tracking
        
        Returns:
            PropertyAnalysisResult with analysis data and images
        """
        analysis_id = uuid.uuid4()
        lat, lng = business_location
        
        logger.info(f"🚀 Starting property analysis {analysis_id}")
        logger.info(f"   Location: ({lat:.6f}, {lng:.6f})")
        logger.info(f"   Wide image radius: {self.wide_image_radius}m")
        
        # Create property analysis record
        property_analysis = PropertyAnalysis(
            id=analysis_id,
            user_id=uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
            business_location=from_shape(Point(lng, lat), srid=4326),
            business_id=uuid.UUID(business_id) if business_id else None,
            parking_lot_id=uuid.UUID(parking_lot_id) if parking_lot_id else None,
            status="processing",
            segmentation_model_id=settings.ROBOFLOW_SEGMENTATION_MODEL
        )
        
        db.add(property_analysis)
        db.commit()
        
        try:
            # Step 1: Fetch wide satellite image
            logger.info("📸 Step 1: Fetching wide satellite image")
            wide_image, image_bounds = await self._fetch_wide_image(lat, lng)
            
            if not wide_image:
                raise ValueError("Failed to fetch satellite image")
            
            logger.info(f"   ✅ Fetched image: {len(wide_image)/1024:.1f} KB")
            
            # Update analysis with image bounds
            property_analysis.wide_image_bounds = image_bounds
            
            # Step 2: Run segmentation (Stage 1 CV)
            logger.info("🔍 Step 2: Running segmentation (Stage 1 CV)")
            segmentation = await asphalt_segmentation_service.segment_property(
                image_bytes=wide_image,
                image_bounds=image_bounds
            )
            
            logger.info(f"   ✅ Detected {len(segmentation.buildings)} buildings, {len(segmentation.paved_surfaces)} paved surfaces")
            
            # Store raw segmentation data
            property_analysis.raw_segmentation_data = segmentation.raw_response
            property_analysis.buildings_detected = [
                {"points": b.pixel_points, "confidence": b.confidence}
                for b in segmentation.buildings
            ]
            property_analysis.paved_surfaces_detected = [
                {"points": p.pixel_points, "confidence": p.confidence}
                for p in segmentation.paved_surfaces
            ]
            
            # Step 3: Associate asphalt with business
            logger.info("🔗 Step 3: Associating asphalt with business")
            business_building, associated_areas = property_association_service.associate_with_business(
                buildings=segmentation.buildings,
                paved_surfaces=segmentation.paved_surfaces,
                business_location=business_location
            )
            
            associated_count = sum(1 for a in associated_areas if a.is_associated)
            total_area = sum(a.area_m2 for a in associated_areas if a.is_associated)
            logger.info(f"   ✅ Associated {associated_count} areas, total {total_area:.0f} m²")
            
            # Store business building polygon
            if business_building:
                property_analysis.business_building_polygon = from_shape(
                    business_building.polygon, srid=4326
                )
            
            # Step 4: Run condition evaluation (Stage 2 CV)
            logger.info("🔬 Step 4: Evaluating condition (Stage 2 CV)")
            
            associated_for_eval = [a for a in associated_areas if a.is_associated]
            
            # If no associated areas, run condition evaluation on full image
            if not associated_for_eval:
                logger.info("   ⚠️ No segmented areas - evaluating full image")
                # Create a synthetic area covering the whole image for evaluation
                full_image_result = await condition_evaluation_service.evaluate_condition(
                    image_bytes=wide_image,
                    parking_lot_id=str(analysis_id)
                )
                
                if full_image_result.get("condition_score") is not None:
                    weighted_score = full_image_result.get("condition_score")
                    total_cracks = full_image_result.get("detection_count", 0)
                    total_potholes = len([
                        d for d in full_image_result.get("degradation_areas", [])
                        if "pothole" in d.get("class", "").lower()
                    ])
                    total_cracks -= total_potholes  # Cracks are total detections minus potholes
                    
                    # Estimate area from image bounds
                    lat_range = image_bounds["max_lat"] - image_bounds["min_lat"]
                    lng_range = image_bounds["max_lng"] - image_bounds["min_lng"]
                    center_lat = (image_bounds["max_lat"] + image_bounds["min_lat"]) / 2
                    area_m2 = (lat_range * 111000) * (lng_range * 111000 * math.cos(math.radians(center_lat)))
                    total_area = area_m2 * 0.6  # Estimate 60% is paved
                    
                    condition_results = []  # Empty since we evaluated full image
                    logger.info(f"   ✅ Full image condition: {weighted_score:.1f}/100")
                else:
                    weighted_score = None
                    total_cracks = 0
                    total_potholes = 0
                    total_area = 0
                    condition_results = []
            else:
                condition_results = await self._evaluate_conditions(
                    associated_areas=associated_for_eval,
                    original_image=wide_image,
                    image_bounds=image_bounds
                )
                
                # Calculate aggregated metrics
                if condition_results:
                    total_area_weighted = sum(r.area.area_m2 for r in condition_results if r.condition_score)
                    if total_area_weighted > 0:
                        weighted_score = sum(
                            r.condition_score * r.area.area_m2 
                            for r in condition_results 
                            if r.condition_score
                        ) / total_area_weighted
                    else:
                        weighted_score = None
                    
                    total_cracks = sum(r.crack_count for r in condition_results)
                    total_potholes = sum(r.pothole_count for r in condition_results)
                else:
                    weighted_score = None
                    total_cracks = 0
                    total_potholes = 0
            
            property_analysis.total_asphalt_area_m2 = total_area
            property_analysis.weighted_condition_score = weighted_score
            property_analysis.total_crack_count = total_cracks
            property_analysis.total_pothole_count = total_potholes
            
            logger.info(f"   ✅ Condition score: {weighted_score:.1f}/100" if weighted_score else "   ⚠️ No condition data")
            
            # Step 5: Generate annotated images
            logger.info("🎨 Step 5: Generating annotated images")
            annotated_images = await cv_visualization_service.generate_all_images(
                original_image=wide_image,
                segmentation=segmentation,
                business_building=business_building,
                associated_areas=associated_areas,
                condition_results=condition_results
            )
            
            # Step 6: Store images
            logger.info("💾 Step 6: Storing images")
            image_urls = await self._store_images(
                analysis_id=analysis_id,
                wide_image=wide_image,
                annotated_images=annotated_images,
                db=db
            )
            
            # Update analysis with image URLs
            property_analysis.wide_image_url = image_urls.get("wide_satellite")
            property_analysis.segmentation_result_image_url = image_urls.get("segmentation")
            property_analysis.property_boundary_image_url = image_urls.get("property_boundary")
            property_analysis.condition_analysis_image_url = image_urls.get("condition_analysis")
            
            # Step 7: Store asphalt areas
            logger.info("💾 Step 7: Storing asphalt areas")
            asphalt_area_records = []
            
            for i, area in enumerate(associated_areas):
                condition = next(
                    (r for r in condition_results if r.area == area),
                    None
                )
                
                asphalt_record = AsphaltArea(
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
                    detections=condition.detections if condition else None
                )
                
                db.add(asphalt_record)
                asphalt_area_records.append(asphalt_record)
            
            # Mark as completed
            property_analysis.status = "completed"
            property_analysis.analyzed_at = datetime.utcnow()
            
            db.commit()
            
            logger.info(f"✅ Property analysis {analysis_id} completed successfully")
            
            return PropertyAnalysisResult(
                property_analysis=property_analysis,
                asphalt_areas=asphalt_area_records,
                images=image_urls,
                success=True
            )
            
        except Exception as e:
            logger.error(f"❌ Property analysis failed: {e}", exc_info=True)
            
            property_analysis.status = "failed"
            property_analysis.error_message = str(e)
            db.commit()
            
            return PropertyAnalysisResult(
                property_analysis=property_analysis,
                asphalt_areas=[],
                images={},
                success=False,
                error=str(e)
            )
    
    async def _fetch_wide_image(
        self,
        lat: float,
        lng: float
    ) -> Tuple[Optional[bytes], Optional[Dict[str, float]]]:
        """
        Fetch wide satellite image centered on location.
        
        Returns:
            Tuple of (image_bytes, bounds_dict)
        """
        if not settings.GOOGLE_MAPS_KEY:
            logger.error("Google Maps API key not configured")
            return None, None
        
        # Calculate zoom level for desired radius
        # We want the image to cover approximately 2 * radius
        diameter_m = self.wide_image_radius * 2
        
        # At zoom z, one pixel covers (156543.03 * cos(lat) / 2^z) meters
        # For our image size, total coverage = image_size * meters_per_pixel
        # We want: diameter_m = image_size * (156543.03 * cos(lat) / 2^z)
        # Solving: 2^z = image_size * 156543.03 * cos(lat) / diameter_m
        
        import math
        meters_per_pixel_at_z0 = 156543.03 * math.cos(math.radians(lat))
        zoom_float = math.log2(self.image_size * meters_per_pixel_at_z0 / diameter_m)
        zoom = int(math.floor(zoom_float))
        
        # Clamp to valid range
        zoom = max(15, min(20, zoom))
        
        logger.info(f"   Calculated zoom level: {zoom} for {diameter_m:.0f}m coverage")
        
        # Calculate actual bounds at this zoom
        meters_per_pixel = 156543.03 * math.cos(math.radians(lat)) / (2 ** zoom)
        half_size_m = (self.image_size / 2) * meters_per_pixel
        
        # Convert to degrees
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
    
    async def _evaluate_conditions(
        self,
        associated_areas: List[AssociatedAsphaltArea],
        original_image: bytes,
        image_bounds: Dict[str, float]
    ) -> List[ConditionResult]:
        """
        Run condition evaluation on each associated asphalt area.
        """
        results = []
        
        for area in associated_areas:
            try:
                # For now, run condition evaluation on the full image
                # In production, we'd crop to each polygon
                eval_result = await condition_evaluation_service.evaluate_condition(
                    image_bytes=original_image,
                    parking_lot_id=str(area.polygon.centroid)
                )
                
                if eval_result and eval_result.get("condition_score") is not None:
                    results.append(ConditionResult(
                        area=area,
                        condition_score=eval_result.get("condition_score", 100),
                        crack_count=eval_result.get("detection_count", 0) - len([
                            d for d in eval_result.get("degradation_areas", [])
                            if "pothole" in d.get("class", "").lower()
                        ]),
                        pothole_count=len([
                            d for d in eval_result.get("degradation_areas", [])
                            if "pothole" in d.get("class", "").lower()
                        ]),
                        crack_density=eval_result.get("crack_density", 0),
                        detections=eval_result.get("degradation_areas", [])
                    ))
                else:
                    # No detections - perfect condition
                    results.append(ConditionResult(
                        area=area,
                        condition_score=100,
                        crack_count=0,
                        pothole_count=0,
                        crack_density=0,
                        detections=[]
                    ))
                    
            except Exception as e:
                logger.warning(f"   Failed to evaluate area: {e}")
                continue
        
        return results
    
    async def _store_images(
        self,
        analysis_id: uuid.UUID,
        wide_image: bytes,
        annotated_images,
        db: Session
    ) -> Dict[str, str]:
        """
        Store images locally or in cloud storage.
        """
        image_urls = {}
        
        if settings.CV_IMAGE_STORAGE_TYPE == "local":
            # Create directory for this analysis
            analysis_dir = os.path.join(self.storage_path, str(analysis_id))
            os.makedirs(analysis_dir, exist_ok=True)
            
            # Save each image
            images_to_save = [
                ("wide_satellite", wide_image),
                ("segmentation", annotated_images.segmentation),
                ("property_boundary", annotated_images.property_boundary),
                ("condition_analysis", annotated_images.condition_analysis),
            ]
            
            for image_type, image_bytes in images_to_save:
                filename = f"{image_type}.jpg"
                filepath = os.path.join(analysis_dir, filename)
                
                with open(filepath, "wb") as f:
                    f.write(image_bytes)
                
                # Generate URL
                url = f"{settings.CV_IMAGE_BASE_URL}/{analysis_id}/{filename}"
                image_urls[image_type] = url
                
                # Create CVImage record
                cv_image = CVImage(
                    property_analysis_id=analysis_id,
                    image_type=image_type,
                    image_url=url,
                    storage_path=filepath,
                    file_size_bytes=len(image_bytes),
                    content_type="image/jpeg"
                )
                db.add(cv_image)
                
                logger.info(f"   Saved {image_type}: {len(image_bytes)/1024:.1f} KB")
        
        return image_urls


# Singleton instance
property_analysis_service = PropertyAnalysisService()

