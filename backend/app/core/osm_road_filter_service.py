"""
OSM Road Filter Service

Queries OpenStreetMap for public roads in a given area.
These roads are used to SUBTRACT from detected asphalt surfaces,
leaving only PRIVATE asphalt (parking lots, driveways, private roads).

This is a critical step to avoid analyzing public roads which are
not the responsibility of property owners.
"""

import logging
import httpx
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from shapely.geometry import Polygon, LineString, MultiPolygon, Point, box
from shapely.ops import unary_union

logger = logging.getLogger(__name__)


@dataclass
class OSMRoad:
    """Represents a road from OpenStreetMap."""
    osm_id: str
    name: Optional[str]
    road_type: str  # highway tag value
    geometry: LineString  # Road centerline
    buffered_polygon: Optional[Polygon] = None  # Road with width buffer
    width_m: float = 6.0  # Default road width in meters
    is_private: bool = False  # True if access=private
    raw_data: Optional[Dict] = None


@dataclass 
class OSMRoadFilterResult:
    """Result of OSM road filtering."""
    public_roads: List[OSMRoad] = field(default_factory=list)
    private_roads: List[OSMRoad] = field(default_factory=list)
    public_road_polygon: Optional[Polygon] = None  # Merged polygon of all public roads
    total_public_road_area_m2: float = 0
    raw_response: Optional[Dict] = None


class OSMRoadFilterService:
    """
    Service to query OSM for roads and create filter polygons.
    
    Used to subtract public roads from CV-detected asphalt,
    leaving only private asphalt for analysis.
    """
    
    # Road widths in meters by highway type
    ROAD_WIDTHS = {
        "motorway": 12.0,
        "motorway_link": 6.0,
        "trunk": 10.0,
        "trunk_link": 5.0,
        "primary": 9.0,
        "primary_link": 4.5,
        "secondary": 7.0,
        "secondary_link": 3.5,
        "tertiary": 6.0,
        "tertiary_link": 3.0,
        "residential": 5.0,
        "unclassified": 4.0,
        "service": 3.5,  # Will be filtered by access tag
        "living_street": 4.0,
        "pedestrian": 3.0,
        "footway": 1.5,
        "cycleway": 2.0,
        "path": 1.5,
        "default": 5.0,
    }
    
    # Road types that are typically public (we want to filter these out)
    PUBLIC_ROAD_TYPES = {
        "motorway", "motorway_link",
        "trunk", "trunk_link", 
        "primary", "primary_link",
        "secondary", "secondary_link",
        "tertiary", "tertiary_link",
        "residential",
        "unclassified",
        "living_street",
    }
    
    # Road types that could be private (check access tag)
    MAYBE_PRIVATE_TYPES = {
        "service",  # Often private driveways/parking lot lanes
    }
    
    async def get_public_roads(
        self,
        bounds: Dict[str, float],
        buffer_roads: bool = True
    ) -> OSMRoadFilterResult:
        """
        Get public roads within bounds from OSM.
        
        Args:
            bounds: {min_lat, max_lat, min_lng, max_lng}
            buffer_roads: Whether to create buffered polygons for roads
            
        Returns:
            OSMRoadFilterResult with road data
        """
        try:
            # Fetch roads from OSM Overpass API
            roads = await self._fetch_roads_from_osm(bounds)
            
            if not roads:
                logger.info("   ℹ️ No public roads found in area")
                return OSMRoadFilterResult()
            
            # Separate public and private roads
            public_roads = []
            private_roads = []
            
            for road in roads:
                if road.is_private:
                    private_roads.append(road)
                else:
                    public_roads.append(road)
            
            logger.info(f"   🛣️ Found {len(public_roads)} public roads, {len(private_roads)} private")
            
            # Create merged polygon of all public roads
            if buffer_roads and public_roads:
                public_road_polygon = self._create_merged_road_polygon(public_roads, bounds)
                total_area = self._calculate_area_m2(public_road_polygon, bounds) if public_road_polygon else 0
            else:
                public_road_polygon = None
                total_area = 0
            
            return OSMRoadFilterResult(
                public_roads=public_roads,
                private_roads=private_roads,
                public_road_polygon=public_road_polygon,
                total_public_road_area_m2=total_area,
            )
            
        except Exception as e:
            logger.warning(f"   ⚠️ OSM road query failed: {e}")
            return OSMRoadFilterResult()
    
    async def _fetch_roads_from_osm(
        self,
        bounds: Dict[str, float]
    ) -> List[OSMRoad]:
        """Fetch roads from OSM Overpass API."""
        
        url = "https://overpass-api.de/api/interpreter"
        
        # Build bounding box string (south, west, north, east)
        bbox = f"{bounds['min_lat']},{bounds['min_lng']},{bounds['max_lat']},{bounds['max_lng']}"
        
        # Query for all highway types within bounds
        # We'll filter by type and access tag later
        query = f"""
        [out:json][timeout:30];
        (
          way["highway"]({bbox});
        );
        out geom;
        """
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    data={"data": query},
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code == 429:
                    logger.warning("   ⚠️ OSM Overpass rate limit exceeded")
                    return []
                
                if response.status_code != 200:
                    logger.warning(f"   ⚠️ OSM API error: {response.status_code}")
                    return []
                
                data = response.json()
                
        except httpx.TimeoutException:
            logger.warning("   ⚠️ OSM Overpass API timeout")
            return []
        except Exception as e:
            logger.warning(f"   ⚠️ OSM request failed: {e}")
            return []
        
        roads: List[OSMRoad] = []
        
        for element in data.get("elements", []):
            try:
                road = self._parse_osm_road(element)
                if road:
                    roads.append(road)
            except Exception as e:
                logger.debug(f"   Failed to parse OSM road: {e}")
        
        return roads
    
    def _parse_osm_road(self, element: Dict[str, Any]) -> Optional[OSMRoad]:
        """Parse an OSM way element into an OSMRoad."""
        
        if element.get("type") != "way":
            return None
        
        geometry = element.get("geometry", [])
        if len(geometry) < 2:
            return None
        
        tags = element.get("tags", {})
        highway_type = tags.get("highway", "")
        
        # Skip non-road types
        if highway_type in ("footway", "cycleway", "path", "steps", "pedestrian"):
            return None
        
        # Check if it's a public or private road
        access = tags.get("access", "")
        is_private = access in ("private", "no", "customers", "permissive")
        
        # For service roads, default to private unless explicitly public
        if highway_type == "service" and access not in ("yes", "public", ""):
            is_private = True
        
        # Skip if it's a public road type that we need to filter
        # But keep track of all roads for filtering
        is_public_type = highway_type in self.PUBLIC_ROAD_TYPES
        
        # Only include roads that are public (we want to filter these out of asphalt)
        if not is_public_type and not (highway_type == "service" and not is_private):
            # Skip private driveways and service roads with private access
            if is_private:
                pass  # We'll track these separately
        
        # Build LineString geometry
        coords = [(p["lon"], p["lat"]) for p in geometry]
        line = LineString(coords)
        
        if line.is_empty or not line.is_valid:
            return None
        
        # Get road width
        width = self.ROAD_WIDTHS.get(highway_type, self.ROAD_WIDTHS["default"])
        
        # Check for explicit width tag
        width_tag = tags.get("width")
        if width_tag:
            try:
                width = float(width_tag.replace("m", "").strip())
            except:
                pass
        
        return OSMRoad(
            osm_id=str(element.get("id", "")),
            name=tags.get("name"),
            road_type=highway_type,
            geometry=line,
            width_m=width,
            is_private=is_private,
            raw_data=element,
        )
    
    def _create_merged_road_polygon(
        self,
        roads: List[OSMRoad],
        bounds: Dict[str, float]
    ) -> Optional[Polygon]:
        """Create a merged polygon of all road buffers."""
        
        if not roads:
            return None
        
        # Convert width from meters to degrees (approximate)
        center_lat = (bounds["min_lat"] + bounds["max_lat"]) / 2
        meters_per_degree = 111000 * math.cos(math.radians(center_lat))
        
        polygons = []
        
        for road in roads:
            if road.geometry and not road.geometry.is_empty:
                # Convert width to degrees
                width_degrees = road.width_m / meters_per_degree
                
                # Buffer the line to create a polygon
                try:
                    buffered = road.geometry.buffer(width_degrees / 2)
                    if buffered and not buffered.is_empty and buffered.is_valid:
                        polygons.append(buffered)
                        road.buffered_polygon = buffered
                except Exception as e:
                    logger.debug(f"   Failed to buffer road: {e}")
        
        if not polygons:
            return None
        
        # Merge all polygons
        try:
            merged = unary_union(polygons)
            
            # Clip to bounds
            bounds_box = box(
                bounds["min_lng"], bounds["min_lat"],
                bounds["max_lng"], bounds["max_lat"]
            )
            merged = merged.intersection(bounds_box)
            
            if merged.is_empty:
                return None
            
            # Handle MultiPolygon
            if isinstance(merged, MultiPolygon):
                # Return the merged MultiPolygon or convert to single polygon
                return merged
            
            return merged
            
        except Exception as e:
            logger.warning(f"   ⚠️ Failed to merge road polygons: {e}")
            return None
    
    def _calculate_area_m2(
        self,
        polygon,
        bounds: Dict[str, float]
    ) -> float:
        """Calculate approximate area in square meters."""
        if polygon is None or polygon.is_empty:
            return 0
        
        center_lat = (bounds["min_lat"] + bounds["max_lat"]) / 2
        
        # Approximate conversion from degrees² to m²
        m_per_deg_lat = 111000
        m_per_deg_lng = 111000 * math.cos(math.radians(center_lat))
        scale = m_per_deg_lat * m_per_deg_lng
        
        return polygon.area * scale
    
    def subtract_roads_from_asphalt(
        self,
        asphalt_polygon: Polygon,
        road_polygon: Polygon,
        min_area_m2: float = 50.0,
        bounds: Optional[Dict[str, float]] = None
    ) -> Optional[Polygon]:
        """
        Subtract public roads from detected asphalt to get private asphalt only.
        
        Args:
            asphalt_polygon: Detected asphalt from CV
            road_polygon: Public roads from OSM
            min_area_m2: Minimum area to keep after subtraction
            bounds: Optional bounds for area calculation
            
        Returns:
            Private asphalt polygon (asphalt minus roads)
        """
        if asphalt_polygon is None or asphalt_polygon.is_empty:
            return None
        
        if road_polygon is None or road_polygon.is_empty:
            return asphalt_polygon  # No roads to subtract
        
        try:
            # Subtract roads from asphalt
            private_asphalt = asphalt_polygon.difference(road_polygon)
            
            if private_asphalt.is_empty:
                return None
            
            # Calculate area if bounds provided
            if bounds and min_area_m2 > 0:
                area = self._calculate_area_m2(private_asphalt, bounds)
                if area < min_area_m2:
                    logger.debug(f"   Private asphalt too small: {area:.0f}m² < {min_area_m2}m²")
                    return None
            
            return private_asphalt
            
        except Exception as e:
            logger.warning(f"   ⚠️ Failed to subtract roads from asphalt: {e}")
            return asphalt_polygon  # Return original on error


# Singleton instance
osm_road_filter_service = OSMRoadFilterService()

