"""
Private Asphalt Detection Service

This is the KEY service that solves the core problem:
"How do we analyze ONLY private asphalt (parking lots, driveways)
and NOT public roads?"

NEW APPROACH (v2): Uses Grounding DINO + SAM 2 for high-accuracy detection
- Detects ASPHALT surfaces (dark pavement)
- Detects CONCRETE surfaces (light pavement) 
- Detects BUILDINGS (to exclude from analysis)
- Filters out public roads using OSM

Flow:
1. Take satellite image of property
2. Run Grounded SAM to detect asphalt, concrete, buildings
3. Query OSM for public roads in the area
4. SUBTRACT public roads from detected pavement
5. Result = Private pavement polygons with surface types

This ensures we only run damage detection on areas that
property owners are responsible for, AND we know what type
of surface we're analyzing.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from shapely.geometry import Polygon, MultiPolygon, Point, mapping
from shapely.ops import unary_union
from io import BytesIO
from PIL import Image

from app.core.grounded_sam_service import (
    grounded_sam_service,
    SurfaceDetectionResult,
    DetectedSurface,
)
from app.core.osm_road_filter_service import (
    osm_road_filter_service,
    OSMRoadFilterResult,
)

logger = logging.getLogger(__name__)


@dataclass
class PrivateAsphaltResult:
    """Result of private asphalt detection with surface type breakdown."""
    
    # ============ ASPHALT (dark pavement) ============
    asphalt_polygon: Optional[Polygon] = None
    asphalt_area_m2: float = 0
    asphalt_area_sqft: float = 0
    asphalt_geojson: Optional[Dict] = None
    
    # ============ CONCRETE (light pavement) ============
    concrete_polygon: Optional[Polygon] = None
    concrete_area_m2: float = 0
    concrete_area_sqft: float = 0
    concrete_geojson: Optional[Dict] = None
    
    # ============ TOTAL PAVED (asphalt + concrete) ============
    total_paved_polygon: Optional[Polygon] = None
    total_paved_area_m2: float = 0
    total_paved_area_sqft: float = 0
    
    # ============ PUBLIC ROADS (filtered out) ============
    public_road_polygon: Optional[Polygon] = None
    public_road_area_m2: float = 0
    
    # ============ BUILDINGS (for reference) ============
    building_polygon: Optional[Polygon] = None
    building_area_m2: float = 0
    building_geojson: Optional[Dict] = None
    
    # ============ LEGACY FIELDS (for backwards compat) ============
    # These map to asphalt for backwards compatibility
    private_asphalt_polygon: Optional[Polygon] = None
    private_asphalt_area_m2: float = 0
    private_asphalt_area_sqft: float = 0
    total_asphalt_polygon: Optional[Polygon] = None
    total_asphalt_area_m2: float = 0
    building_polygons: List[Polygon] = field(default_factory=list)
    
    # ============ SURFACE BREAKDOWN FOR UI ============
    surfaces: List[Dict] = field(default_factory=list)  # List of {type, polygon, area, color}
    
    # ============ METADATA ============
    detection_method: str = "grounded_sam"
    osm_road_filter_used: bool = True
    source: str = "grounded_sam_with_osm"
    success: bool = False
    error_message: Optional[str] = None
    
    # Raw data for debugging
    raw_detection: Optional[SurfaceDetectionResult] = None
    raw_road_filter: Optional[OSMRoadFilterResult] = None
    
    @property
    def has_paved_surfaces(self) -> bool:
        return self.total_paved_area_m2 > 0
    
    @property
    def has_private_asphalt(self) -> bool:
        """Legacy property for backwards compatibility."""
        return self.asphalt_area_m2 > 0
    
    @property
    def private_asphalt_percentage(self) -> float:
        """Percentage of detected pavement that is asphalt."""
        if self.total_paved_area_m2 <= 0:
            return 0
        return (self.asphalt_area_m2 / self.total_paved_area_m2) * 100


class PrivateAsphaltService:
    """
    Detects private paved surfaces from satellite imagery using Grounded SAM.
    
    This service orchestrates:
    1. Grounded SAM detection (detect asphalt, concrete, buildings)
    2. OSM road filtering (identify public roads)
    3. Polygon subtraction (pavement - roads = private pavement)
    
    The result includes polygons for each surface type (asphalt, concrete)
    that can be analyzed for damage without including public roads.
    """
    
    # Minimum area thresholds
    MIN_PAVED_AREA_M2 = 50  # Ignore tiny paved patches
    
    # Surface colors for UI
    SURFACE_COLORS = {
        "asphalt": "#374151",  # Dark gray
        "concrete": "#9CA3AF",  # Light gray  
        "building": "#DC2626",  # Red
        "public_road": "#3B82F6",  # Blue
    }
    
    async def detect_private_asphalt(
        self,
        image_bytes: bytes,
        image_bounds: Dict[str, float],
        property_boundary: Optional[Polygon] = None,
        skip_osm_filter: bool = False,
    ) -> PrivateAsphaltResult:
        """
        Detect private paved surfaces from satellite image using Grounded SAM.
        
        Args:
            image_bytes: Satellite image bytes
            image_bounds: {min_lat, max_lat, min_lng, max_lng}
            property_boundary: Optional property boundary to clip to
            skip_osm_filter: Skip OSM road filtering (for testing)
            
        Returns:
            PrivateAsphaltResult with surface type breakdown
        """
        result = PrivateAsphaltResult()
        
        try:
            # ============ STEP 1: Run Grounded SAM Detection ============
            logger.info("   🎯 Step 1: Running Grounded SAM surface detection...")
            
            detection = await grounded_sam_service.detect_surfaces(
                image_bytes=image_bytes,
                image_bounds=image_bounds,
                property_boundary=property_boundary,
                detect_asphalt=True,
                detect_concrete=True,
                detect_buildings=True,
            )
            
            result.raw_detection = detection
            
            if not detection.success:
                logger.warning(f"   ⚠️ Grounded SAM detection failed: {detection.error_message}")
                result.error_message = detection.error_message
                result.source = "detection_failed"
                return result
            
            # Store building polygon
            if detection.building_polygon and not detection.building_polygon.is_empty:
                result.building_polygon = detection.building_polygon
                result.building_area_m2 = self._calculate_area_m2(detection.building_polygon, image_bounds)
                result.building_geojson = self._polygon_to_geojson(
                    detection.building_polygon, 
                    {"type": "building", "color": self.SURFACE_COLORS["building"]}
                )
                result.building_polygons = [detection.building_polygon]
            
            # Check if any paved surfaces detected
            total_paved_area = detection.total_paved_area_m2
            
            if total_paved_area < self.MIN_PAVED_AREA_M2:
                logger.info(f"   ℹ️ No significant paved surfaces detected ({total_paved_area:.0f}m²)")
                result.source = "no_pavement"
                result.success = True
                return result
            
            logger.info(f"   ✅ Detected: {detection.total_asphalt_area_sqft:,.0f} sqft asphalt, {detection.total_concrete_area_sqft:,.0f} sqft concrete")
            
            # Store raw detection areas (before road filtering)
            result.total_asphalt_area_m2 = detection.total_asphalt_area_m2
            result.total_asphalt_polygon = detection.asphalt_polygon
            
            # ============ STEP 2: Get Public Roads from OSM ============
            if skip_osm_filter:
                logger.info("   ⏭️ Skipping OSM road filter")
                result.osm_road_filter_used = False
            else:
                logger.info("   🛣️ Step 2: Fetching public roads from OSM...")
                
                # Query OSM using property boundary
                if property_boundary and not property_boundary.is_empty:
                    prop_bounds = property_boundary.bounds
                    query_bounds = {
                        "min_lng": prop_bounds[0],
                        "min_lat": prop_bounds[1],
                        "max_lng": prop_bounds[2],
                        "max_lat": prop_bounds[3],
                    }
                else:
                    query_bounds = image_bounds
                
                road_filter = await osm_road_filter_service.get_public_roads(
                    bounds=query_bounds,
                    buffer_roads=True
                )
                
                result.raw_road_filter = road_filter
                
                # Clip roads to property boundary
                road_polygon = road_filter.public_road_polygon
                if road_polygon and property_boundary and not property_boundary.is_empty:
                    try:
                        road_polygon = road_polygon.intersection(property_boundary)
                        if road_polygon.is_empty:
                            road_polygon = None
                    except Exception:
                        pass
                
                result.public_road_polygon = road_polygon
                result.public_road_area_m2 = self._calculate_area_m2(road_polygon, image_bounds) if road_polygon else 0
                
                logger.info(f"   ✅ Found {result.public_road_area_m2:.0f}m² of public roads")
            
            # ============ STEP 3: Subtract Roads from Paved Surfaces ============
            logger.info("   ➖ Step 3: Filtering out public roads...")
            
            # Process asphalt
            asphalt_poly = detection.asphalt_polygon
            if asphalt_poly and result.public_road_polygon and not skip_osm_filter:
                try:
                    asphalt_poly = asphalt_poly.difference(result.public_road_polygon)
                    if asphalt_poly.is_empty:
                        asphalt_poly = None
                except Exception:
                    pass
            
            if asphalt_poly and not asphalt_poly.is_empty:
                result.asphalt_polygon = asphalt_poly
                result.asphalt_area_m2 = self._calculate_area_m2(asphalt_poly, image_bounds)
                result.asphalt_area_sqft = result.asphalt_area_m2 * 10.764
                result.asphalt_geojson = self._polygon_to_geojson(
                    asphalt_poly,
                    {"type": "asphalt", "color": self.SURFACE_COLORS["asphalt"], "area_sqft": result.asphalt_area_sqft}
                )
            
            # Process concrete
            concrete_poly = detection.concrete_polygon
            if concrete_poly and result.public_road_polygon and not skip_osm_filter:
                try:
                    concrete_poly = concrete_poly.difference(result.public_road_polygon)
                    if concrete_poly.is_empty:
                        concrete_poly = None
                except Exception:
                    pass
            
            if concrete_poly and not concrete_poly.is_empty:
                result.concrete_polygon = concrete_poly
                result.concrete_area_m2 = self._calculate_area_m2(concrete_poly, image_bounds)
                result.concrete_area_sqft = result.concrete_area_m2 * 10.764
                result.concrete_geojson = self._polygon_to_geojson(
                    concrete_poly,
                    {"type": "concrete", "color": self.SURFACE_COLORS["concrete"], "area_sqft": result.concrete_area_sqft}
                )
            
            # Calculate totals
            result.total_paved_area_m2 = result.asphalt_area_m2 + result.concrete_area_m2
            result.total_paved_area_sqft = result.total_paved_area_m2 * 10.764
            
            # Merge paved polygons
            paved_polys = []
            if result.asphalt_polygon:
                paved_polys.append(result.asphalt_polygon)
            if result.concrete_polygon:
                paved_polys.append(result.concrete_polygon)
            
            if paved_polys:
                result.total_paved_polygon = unary_union(paved_polys)
            
            # ============ LEGACY FIELDS (backwards compatibility) ============
            result.private_asphalt_polygon = result.asphalt_polygon or result.concrete_polygon
            result.private_asphalt_area_m2 = result.total_paved_area_m2
            result.private_asphalt_area_sqft = result.total_paved_area_sqft
            
            # ============ BUILD SURFACE LIST FOR UI ============
            result.surfaces = []
            
            if result.asphalt_polygon:
                result.surfaces.append({
                    "type": "asphalt",
                    "label": "Asphalt",
                    "color": self.SURFACE_COLORS["asphalt"],
                    "area_m2": result.asphalt_area_m2,
                    "area_sqft": result.asphalt_area_sqft,
                    "geojson": result.asphalt_geojson,
                })
            
            if result.concrete_polygon:
                result.surfaces.append({
                    "type": "concrete", 
                    "label": "Concrete",
                    "color": self.SURFACE_COLORS["concrete"],
                    "area_m2": result.concrete_area_m2,
                    "area_sqft": result.concrete_area_sqft,
                    "geojson": result.concrete_geojson,
                })
            
            if result.building_polygon:
                result.surfaces.append({
                    "type": "building",
                    "label": "Buildings",
                    "color": self.SURFACE_COLORS["building"],
                    "area_m2": result.building_area_m2,
                    "area_sqft": result.building_area_m2 * 10.764,
                    "geojson": result.building_geojson,
                })
            
            result.success = True
            result.source = "grounded_sam_with_osm" if not skip_osm_filter else "grounded_sam_only"
            result.detection_method = "grounded_sam"
            
            logger.info(f"   ✅ Private surfaces: {result.asphalt_area_sqft:,.0f} sqft asphalt, {result.concrete_area_sqft:,.0f} sqft concrete")
            
            return result
            
        except Exception as e:
            logger.error(f"   ❌ Surface detection failed: {e}")
            import traceback
            traceback.print_exc()
            
            result.error_message = str(e)
            result.source = "error"
            return result
    
    def _polygon_to_geojson(
        self,
        polygon: Polygon,
        properties: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Convert polygon to GeoJSON Feature."""
        if polygon is None or polygon.is_empty:
            return None
        
        try:
            return {
                "type": "Feature",
                "geometry": mapping(polygon),
                "properties": properties or {}
            }
        except Exception as e:
            logger.warning(f"   ⚠️ Failed to convert polygon: {e}")
            return None
    
    def _calculate_area_m2(
        self,
        polygon,
        bounds: Dict[str, float]
    ) -> float:
        """Calculate approximate area in square meters."""
        if polygon is None or polygon.is_empty:
            return 0
        
        import math
        
        center_lat = (bounds["min_lat"] + bounds["max_lat"]) / 2
        
        # Approximate conversion from degrees² to m²
        m_per_deg_lat = 111000
        m_per_deg_lng = 111000 * math.cos(math.radians(center_lat))
        scale = m_per_deg_lat * m_per_deg_lng
        
        return polygon.area * scale
    
    def create_asphalt_mask_for_image(
        self,
        private_asphalt_polygon: Polygon,
        image_bounds: Dict[str, float],
        image_width: int,
        image_height: int
    ) -> Optional[bytes]:
        """
        Create a binary mask image for the private asphalt polygon.
        
        This mask can be used to filter damage detection to only
        analyze pixels within the private asphalt area.
        
        Args:
            private_asphalt_polygon: The private asphalt polygon
            image_bounds: {min_lat, max_lat, min_lng, max_lng}
            image_width: Image width in pixels
            image_height: Image height in pixels
            
        Returns:
            PNG image bytes of the mask (white = asphalt, black = not asphalt)
        """
        if private_asphalt_polygon is None or private_asphalt_polygon.is_empty:
            return None
        
        try:
            from PIL import Image, ImageDraw
            
            # Create blank mask
            mask = Image.new("L", (image_width, image_height), 0)
            draw = ImageDraw.Draw(mask)
            
            # Convert geo coordinates to pixel coordinates
            def geo_to_pixel(lng: float, lat: float) -> Tuple[int, int]:
                lat_range = image_bounds["max_lat"] - image_bounds["min_lat"]
                lng_range = image_bounds["max_lng"] - image_bounds["min_lng"]
                
                x = int((lng - image_bounds["min_lng"]) / lng_range * image_width)
                y = int((image_bounds["max_lat"] - lat) / lat_range * image_height)
                
                return (x, y)
            
            # Handle MultiPolygon
            polygons_to_draw = []
            if hasattr(private_asphalt_polygon, 'geoms'):
                polygons_to_draw = list(private_asphalt_polygon.geoms)
            else:
                polygons_to_draw = [private_asphalt_polygon]
            
            # Draw each polygon
            for poly in polygons_to_draw:
                if poly.exterior:
                    coords = list(poly.exterior.coords)
                    pixel_coords = [geo_to_pixel(c[0], c[1]) for c in coords]
                    draw.polygon(pixel_coords, fill=255)
                    
                    # Handle holes
                    for interior in poly.interiors:
                        hole_coords = list(interior.coords)
                        hole_pixels = [geo_to_pixel(c[0], c[1]) for c in hole_coords]
                        draw.polygon(hole_pixels, fill=0)
            
            # Convert to bytes
            output = BytesIO()
            mask.save(output, format="PNG")
            return output.getvalue()
            
        except Exception as e:
            logger.warning(f"   ⚠️ Failed to create asphalt mask: {e}")
            return None
    
    def get_polygon_geojson(
        self,
        polygon: Polygon,
        properties: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Convert polygon to GeoJSON for frontend display."""
        if polygon is None or polygon.is_empty:
            return None
        
        try:
            from shapely.geometry import mapping
            
            geojson = {
                "type": "Feature",
                "geometry": mapping(polygon),
                "properties": properties or {}
            }
            
            return geojson
            
        except Exception as e:
            logger.warning(f"   ⚠️ Failed to convert polygon to GeoJSON: {e}")
            return None


# Singleton instance
private_asphalt_service = PrivateAsphaltService()

