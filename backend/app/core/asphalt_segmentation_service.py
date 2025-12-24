"""
AsphaltSegmentationService - Stage 1 CV

Detects buildings and paved surfaces in satellite imagery using Roboflow.
Uses the Roboflow SDK for reliable API access.

Tested working models:
- ics483/satellite-building-segmentation/2 (classes: building, road)
- conversion-qmb4v/aerial-segmentation-3/1 (classes: building, road, vegetation)
"""
import logging
import tempfile
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
from io import BytesIO
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

# Roboflow SDK import (with fallback)
try:
    from roboflow import Roboflow
    ROBOFLOW_SDK_AVAILABLE = True
except ImportError:
    ROBOFLOW_SDK_AVAILABLE = False
    logger.warning("⚠️ Roboflow SDK not installed - pip install roboflow")


@dataclass
class DetectedPolygon:
    """Represents a detected polygon from segmentation."""
    polygon: Polygon
    pixel_points: List[Dict[str, float]]  # Original pixel coordinates
    class_name: str  # 'building' or 'road'
    confidence: float
    area_m2: Optional[float] = None


@dataclass
class SegmentationResult:
    """Complete result from segmentation analysis."""
    buildings: List[DetectedPolygon] = field(default_factory=list)
    paved_surfaces: List[DetectedPolygon] = field(default_factory=list)
    raw_response: Dict[str, Any] = field(default_factory=dict)
    image_width: int = 0
    image_height: int = 0


class AsphaltSegmentationService:
    """
    Stage 1 CV: Detect buildings and paved surfaces using Roboflow segmentation.
    
    Uses instance segmentation to get polygon boundaries for:
    - Buildings (to identify the business building)
    - Roads/Paved surfaces (includes parking lots, driveways, all asphalt)
    
    Uses the Roboflow SDK for reliable API access.
    """
    
    # Default model that's been tested to work
    DEFAULT_MODEL = "ics483/satellite-building-segmentation/2"
    
    def __init__(self):
        self.api_key = settings.ROBOFLOW_API_KEY
        self.model_id = settings.ROBOFLOW_SEGMENTATION_MODEL or self.DEFAULT_MODEL
        self.model = None
        self._initialized = False
        
        if not ROBOFLOW_SDK_AVAILABLE:
            logger.error("❌ Roboflow SDK not available - install with: pip install roboflow")
            return
        
        if not self.api_key:
            logger.warning("⚠️ Roboflow API key not configured - segmentation disabled")
            return
        
        # Parse model ID: "workspace/project/version"
        try:
            parts = self.model_id.split("/")
            if len(parts) != 3:
                raise ValueError(f"Invalid model ID format: {self.model_id}")
            
            self.workspace_id = parts[0]
            self.project_id = parts[1]
            self.version_id = int(parts[2])
            
            logger.info(f"✅ Segmentation service configured:")
            logger.info(f"   Model: {self.model_id}")
            logger.info(f"   Workspace: {self.workspace_id}")
            logger.info(f"   Project: {self.project_id}")
            logger.info(f"   Version: {self.version_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to parse model ID: {e}")
    
    def _ensure_initialized(self):
        """Lazily initialize the Roboflow model."""
        if self._initialized:
            return self.model is not None
        
        self._initialized = True
        
        if not ROBOFLOW_SDK_AVAILABLE or not self.api_key:
            return False
        
        try:
            logger.info(f"🔌 Initializing Roboflow connection...")
            rf = Roboflow(api_key=self.api_key)
            project = rf.workspace(self.workspace_id).project(self.project_id)
            self.model = project.version(self.version_id).model
            logger.info(f"   ✅ Model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"   ❌ Failed to load model: {e}")
            self.model = None
            return False
    
    async def segment_property(
        self,
        image_bytes: bytes,
        image_bounds: Dict[str, float]  # {min_lat, max_lat, min_lng, max_lng}
    ) -> SegmentationResult:
        """
        Segment satellite image to detect buildings and paved surfaces.
        
        Args:
            image_bytes: Raw satellite image bytes
            image_bounds: Geographic bounds of the image
        
        Returns:
            SegmentationResult with detected polygons
        """
        # Ensure model is initialized
        if not self._ensure_initialized():
            logger.warning("   ⚠️ Model not initialized, using fallback")
            return await self._fallback_segmentation(image_bytes, image_bounds)
        
        try:
            logger.info(f"🔍 Running segmentation with model: {self.model_id}")
            
            # Save image to temp file (Roboflow SDK needs file path)
            img = Image.open(BytesIO(image_bytes))
            image_width, image_height = img.size
            
            # Convert to RGB if needed (palette mode 'P' can't be saved as JPEG)
            if img.mode != 'RGB':
                logger.info(f"   Converting image from mode '{img.mode}' to RGB")
                img = img.convert('RGB')
            
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
                img.save(f, format='JPEG', quality=95)
                temp_path = f.name
            
            logger.info(f"   📸 Image: {image_width}x{image_height}")
            
            try:
                # Run prediction using SDK
                logger.info(f"   🤖 Calling Roboflow API...")
                result = self.model.predict(temp_path, confidence=40).json()
                
                predictions = result.get("predictions", [])
                logger.info(f"   ✅ Received {len(predictions)} predictions")
                
                # Parse response
                return self._parse_segmentation_response(
                    {"predictions": predictions, "image": {"width": image_width, "height": image_height}},
                    image_bounds
                )
                
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_path)
                except:
                    pass
                
        except Exception as e:
            logger.error(f"   ❌ Segmentation failed: {e}", exc_info=True)
            return await self._fallback_segmentation(image_bytes, image_bounds)
    
    def _parse_segmentation_response(
        self,
        data: Dict[str, Any],
        image_bounds: Dict[str, float]
    ) -> SegmentationResult:
        """
        Parse Roboflow segmentation response into DetectedPolygon objects.
        
        Args:
            data: Raw API response
            image_bounds: Geographic bounds for coordinate conversion
        
        Returns:
            SegmentationResult with parsed polygons
        """
        buildings = []
        paved_surfaces = []
        
        # Get image dimensions
        image_info = data.get("image", {})
        image_width = image_info.get("width", 640)
        image_height = image_info.get("height", 640)
        
        predictions = data.get("predictions", [])
        logger.info(f"   📊 Received {len(predictions)} predictions")
        
        for pred in predictions:
            class_name = pred.get("class", "").lower()
            confidence = pred.get("confidence", 0)
            points = pred.get("points", [])
            
            if len(points) < 3:
                logger.debug(f"   Skipping prediction with {len(points)} points")
                continue
            
            # Convert pixel points to geo coordinates
            geo_points = self._pixel_to_geo(
                points, image_width, image_height, image_bounds
            )
            
            if len(geo_points) < 3:
                continue
            
            try:
                # Create Shapely polygon
                polygon = Polygon(geo_points)
                
                if not polygon.is_valid:
                    polygon = polygon.buffer(0)  # Fix invalid geometries
                
                if polygon.is_empty:
                    continue
                
                # Calculate area in m² (approximate)
                area_m2 = self._calculate_area_m2(polygon, image_bounds)
                
                detected = DetectedPolygon(
                    polygon=polygon,
                    pixel_points=points,
                    class_name=class_name,
                    confidence=confidence,
                    area_m2=area_m2
                )
                
                if class_name == "building":
                    buildings.append(detected)
                    logger.debug(f"   🏢 Building: {area_m2:.0f}m², conf={confidence:.0%}")
                elif class_name == "road":
                    paved_surfaces.append(detected)
                    logger.debug(f"   🛣️ Paved: {area_m2:.0f}m², conf={confidence:.0%}")
                else:
                    # Unknown class - treat as paved surface
                    paved_surfaces.append(detected)
                    logger.debug(f"   ❓ Unknown '{class_name}': {area_m2:.0f}m²")
                    
            except Exception as e:
                logger.warning(f"   Failed to create polygon: {e}")
                continue
        
        logger.info(f"   ✅ Detected: {len(buildings)} buildings, {len(paved_surfaces)} paved surfaces")
        
        return SegmentationResult(
            buildings=buildings,
            paved_surfaces=paved_surfaces,
            raw_response=data,
            image_width=image_width,
            image_height=image_height
        )
    
    def _pixel_to_geo(
        self,
        points: List[Dict[str, float]],
        image_width: int,
        image_height: int,
        bounds: Dict[str, float]
    ) -> List[Tuple[float, float]]:
        """
        Convert pixel coordinates to geographic coordinates.
        
        Args:
            points: List of {x, y} pixel coordinates
            image_width: Image width in pixels
            image_height: Image height in pixels
            bounds: {min_lat, max_lat, min_lng, max_lng}
        
        Returns:
            List of (lng, lat) tuples for Shapely
        """
        geo_points = []
        
        lat_range = bounds["max_lat"] - bounds["min_lat"]
        lng_range = bounds["max_lng"] - bounds["min_lng"]
        
        for point in points:
            x = point.get("x", 0)
            y = point.get("y", 0)
            
            # Convert pixel to normalized [0, 1]
            norm_x = x / image_width
            norm_y = y / image_height
            
            # Convert to geo coordinates
            # Note: y is inverted (0 at top, max at bottom)
            lng = bounds["min_lng"] + norm_x * lng_range
            lat = bounds["max_lat"] - norm_y * lat_range
            
            geo_points.append((lng, lat))  # Shapely uses (lng, lat) order
        
        return geo_points
    
    def _calculate_area_m2(
        self,
        polygon: Polygon,
        bounds: Dict[str, float]
    ) -> float:
        """
        Calculate approximate area in square meters.
        
        Uses the centroid latitude for conversion.
        """
        import math
        
        centroid = polygon.centroid
        center_lat = centroid.y
        
        # Get polygon area in square degrees
        area_deg2 = polygon.area
        
        # Convert to m² (approximate)
        # 1 degree latitude ≈ 111,000 meters
        # 1 degree longitude ≈ 111,000 * cos(lat) meters
        m_per_deg_lat = 111000
        m_per_deg_lng = 111000 * math.cos(math.radians(center_lat))
        
        # Average scale factor
        scale = m_per_deg_lat * m_per_deg_lng
        area_m2 = area_deg2 * scale
        
        return area_m2
    
    async def _fallback_segmentation(
        self,
        image_bytes: bytes,
        image_bounds: Dict[str, float]
    ) -> SegmentationResult:
        """
        Fallback when segmentation model fails.
        Creates an estimated paved surface polygon covering most of the image.
        
        This allows the pipeline to continue with condition evaluation
        even when building/road segmentation isn't available.
        """
        from PIL import Image
        from io import BytesIO
        
        try:
            # Get image dimensions
            img = Image.open(BytesIO(image_bytes))
            width, height = img.size
            
            # Create a polygon covering the center 80% of the image
            # This is a reasonable estimate for a business parking area
            margin = 0.1  # 10% margin on each side
            
            pixel_points = [
                {"x": width * margin, "y": height * margin},
                {"x": width * (1 - margin), "y": height * margin},
                {"x": width * (1 - margin), "y": height * (1 - margin)},
                {"x": width * margin, "y": height * (1 - margin)},
            ]
            
            # Convert to geo coordinates
            geo_points = self._pixel_to_geo(pixel_points, width, height, image_bounds)
            
            polygon = Polygon(geo_points)
            area_m2 = self._calculate_area_m2(polygon, image_bounds)
            
            # Create a single "paved surface" polygon
            paved_surface = DetectedPolygon(
                polygon=polygon,
                pixel_points=pixel_points,
                class_name="road",  # Treat as paved surface
                confidence=0.5,  # Low confidence since it's estimated
                area_m2=area_m2
            )
            
            logger.info(f"   📍 Fallback: Created estimated paved area of {area_m2:.0f}m²")
            
            return SegmentationResult(
                buildings=[],  # No building detection
                paved_surfaces=[paved_surface],
                raw_response={"fallback": True},
                image_width=width,
                image_height=height
            )
            
        except Exception as e:
            logger.error(f"   ❌ Fallback segmentation failed: {e}")
            return SegmentationResult()


# Singleton instance
asphalt_segmentation_service = AsphaltSegmentationService()

