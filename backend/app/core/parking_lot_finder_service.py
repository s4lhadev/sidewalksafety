"""
Parking Lot Finder Service

Finds parking lots for a given business location.
Uses OSM Overpass API to find actual parking lot geometries,
or creates an estimated parking area if none found.

This is the second step in the business-first discovery pipeline:
1. Find businesses by type → 2. Find their parking lots → 3. Evaluate condition
"""

import logging
import httpx
import math
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from shapely.geometry import Polygon, Point, shape
from shapely.ops import unary_union

logger = logging.getLogger(__name__)


@dataclass
class FoundParkingLot:
    """Parking lot found for a business."""
    geometry: Optional[Polygon]
    centroid: Point
    area_m2: float
    area_sqft: float
    source: str  # "osm", "here", "estimated"
    source_id: Optional[str] = None
    surface_type: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    
    @property
    def has_geometry(self) -> bool:
        """Check if actual polygon geometry is available."""
        return self.geometry is not None and not self.geometry.is_empty


class ParkingLotFinderService:
    """
    Service to find parking lots near a business location.
    
    Searches OSM for actual parking lot polygons, falling back to
    estimated parking areas based on business type and typical sizes.
    """
    
    # Typical parking lot sizes by business type (in m²)
    TYPICAL_SIZES = {
        "apartment": 2000,
        "apartments": 2000,
        "hoa": 3000,
        "homeowner": 3000,
        "condo": 2500,
        "shopping": 8000,
        "mall": 15000,
        "hotel": 3000,
        "motel": 1500,
        "office": 4000,
        "warehouse": 5000,
        "church": 2000,
        "school": 4000,
        "hospital": 6000,
        "gym": 1500,
        "default": 2000,
    }
    
    async def find_parking_lot(
        self,
        business_lat: float,
        business_lng: float,
        business_type: str,
        search_radius_m: int = 150,
    ) -> FoundParkingLot:
        """
        Find parking lot for a business location.
        
        Args:
            business_lat: Business latitude
            business_lng: Business longitude
            business_type: Type of business (for size estimation)
            search_radius_m: Search radius in meters
        
        Returns:
            FoundParkingLot with geometry or estimated area
        """
        
        # Try to find actual parking lot from OSM
        osm_lots = await self._search_osm(business_lat, business_lng, search_radius_m)
        
        if osm_lots:
            # Find the closest parking lot
            business_point = Point(business_lng, business_lat)
            closest = min(osm_lots, key=lambda lot: lot.centroid.distance(business_point))
            
            logger.info(
                f"Found OSM parking lot: {closest.area_m2:.0f}m² "
                f"at {closest.centroid.y:.6f}, {closest.centroid.x:.6f}"
            )
            return closest
        
        # Fallback: Create estimated parking lot
        estimated = self._create_estimated_lot(
            business_lat, business_lng, business_type
        )
        
        logger.info(
            f"Created estimated parking lot: {estimated.area_m2:.0f}m² "
            f"for {business_type}"
        )
        
        return estimated
    
    async def _search_osm(
        self,
        lat: float,
        lng: float,
        radius_m: int,
    ) -> List[FoundParkingLot]:
        """Search OSM Overpass for parking lots near location."""
        
        url = "https://overpass-api.de/api/interpreter"
        
        # Overpass query for parking amenities within radius
        query = f"""
        [out:json][timeout:30];
        (
          way["amenity"="parking"](around:{radius_m},{lat},{lng});
          relation["amenity"="parking"](around:{radius_m},{lat},{lng});
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
                    logger.warning("OSM Overpass rate limit exceeded")
                    return []
                
                if response.status_code != 200:
                    logger.warning(f"OSM API error: {response.status_code}")
                    return []
                
                data = response.json()
                
        except Exception as e:
            logger.warning(f"OSM search failed: {e}")
            return []
        
        lots: List[FoundParkingLot] = []
        
        for element in data.get("elements", []):
            try:
                lot = self._parse_osm_element(element)
                if lot:
                    lots.append(lot)
            except Exception as e:
                logger.debug(f"Failed to parse OSM element: {e}")
        
        return lots
    
    def _parse_osm_element(self, element: Dict[str, Any]) -> Optional[FoundParkingLot]:
        """Parse OSM element into FoundParkingLot."""
        
        element_type = element.get("type")
        
        if element_type == "way" and "geometry" in element:
            # Build polygon from way geometry
            coords = [(p["lon"], p["lat"]) for p in element["geometry"]]
            
            if len(coords) < 3:
                return None
            
            # Close polygon if not closed
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            
            polygon = Polygon(coords)
            
            if not polygon.is_valid or polygon.is_empty:
                return None
            
            # Calculate area
            area_m2 = self._calculate_geodesic_area(polygon)
            
            # Get surface type from tags
            tags = element.get("tags", {})
            surface = tags.get("surface")
            
            return FoundParkingLot(
                geometry=polygon,
                centroid=polygon.centroid,
                area_m2=area_m2,
                area_sqft=area_m2 * 10.764,
                source="osm",
                source_id=str(element.get("id")),
                surface_type=surface,
                raw_data=element,
            )
        
        return None
    
    def _calculate_geodesic_area(self, polygon: Polygon) -> float:
        """Calculate geodesic area of polygon in square meters."""
        from pyproj import Geod
        
        geod = Geod(ellps="WGS84")
        
        coords = list(polygon.exterior.coords)
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        
        area, _ = geod.polygon_area_perimeter(lons, lats)
        
        return abs(area)
    
    def _create_estimated_lot(
        self,
        lat: float,
        lng: float,
        business_type: str,
    ) -> FoundParkingLot:
        """Create estimated parking lot based on business type."""
        
        # Determine typical size for business type
        area_m2 = self.TYPICAL_SIZES.get("default")
        
        business_type_lower = business_type.lower()
        for key, size in self.TYPICAL_SIZES.items():
            if key in business_type_lower:
                area_m2 = size
                break
        
        # Create square polygon centered slightly offset from business
        # (parking lots are usually behind or beside buildings)
        offset_lat = 0.0003  # ~30m south
        offset_lng = 0.0003  # ~30m east
        
        center_lat = lat - offset_lat
        center_lng = lng + offset_lng
        
        # Calculate polygon from area
        side_length_m = math.sqrt(area_m2)
        half_lat = (side_length_m / 2) / 111000.0
        half_lng = (side_length_m / 2) / (111000.0 * math.cos(math.radians(center_lat)))
        
        polygon = Polygon([
            (center_lng - half_lng, center_lat - half_lat),
            (center_lng + half_lng, center_lat - half_lat),
            (center_lng + half_lng, center_lat + half_lat),
            (center_lng - half_lng, center_lat + half_lat),
            (center_lng - half_lng, center_lat - half_lat),
        ])
        
        return FoundParkingLot(
            geometry=polygon,
            centroid=Point(center_lng, center_lat),
            area_m2=area_m2,
            area_sqft=area_m2 * 10.764,
            source="estimated",
            source_id=None,
            surface_type="asphalt",  # Assume asphalt
            raw_data=None,
        )
    
    async def find_all_parking_lots(
        self,
        business_lat: float,
        business_lng: float,
        search_radius_m: int = 200,
    ) -> List[FoundParkingLot]:
        """
        Find all parking lots near a business location.
        
        Returns all OSM parking lots within radius, merged if overlapping.
        
        Args:
            business_lat: Business latitude
            business_lng: Business longitude
            search_radius_m: Search radius in meters
        
        Returns:
            List of all parking lots found
        """
        
        lots = await self._search_osm(business_lat, business_lng, search_radius_m)
        
        if not lots:
            return []
        
        # Merge overlapping lots
        merged = self._merge_overlapping_lots(lots)
        
        return merged
    
    def _merge_overlapping_lots(
        self,
        lots: List[FoundParkingLot]
    ) -> List[FoundParkingLot]:
        """Merge overlapping parking lots into single geometries."""
        
        if len(lots) <= 1:
            return lots
        
        # Group by overlap
        merged_lots: List[FoundParkingLot] = []
        used_indices: set = set()
        
        for i, lot1 in enumerate(lots):
            if i in used_indices:
                continue
            
            if not lot1.geometry:
                merged_lots.append(lot1)
                used_indices.add(i)
                continue
            
            # Find all overlapping lots
            overlapping = [lot1]
            
            for j, lot2 in enumerate(lots):
                if j <= i or j in used_indices or not lot2.geometry:
                    continue
                
                if lot1.geometry.intersects(lot2.geometry):
                    overlapping.append(lot2)
                    used_indices.add(j)
            
            if len(overlapping) == 1:
                merged_lots.append(lot1)
            else:
                # Merge geometries
                merged_geom = unary_union([lot.geometry for lot in overlapping])
                
                if merged_geom.geom_type == "Polygon":
                    area_m2 = self._calculate_geodesic_area(merged_geom)
                    
                    merged_lots.append(FoundParkingLot(
                        geometry=merged_geom,
                        centroid=merged_geom.centroid,
                        area_m2=area_m2,
                        area_sqft=area_m2 * 10.764,
                        source="osm_merged",
                        source_id=None,
                        surface_type=overlapping[0].surface_type,
                        raw_data=None,
                    ))
                else:
                    # If merge results in MultiPolygon, keep largest
                    if hasattr(merged_geom, 'geoms'):
                        largest = max(merged_geom.geoms, key=lambda g: g.area)
                        area_m2 = self._calculate_geodesic_area(largest)
                        
                        merged_lots.append(FoundParkingLot(
                            geometry=largest,
                            centroid=largest.centroid,
                            area_m2=area_m2,
                            area_sqft=area_m2 * 10.764,
                            source="osm_merged",
                            source_id=None,
                            surface_type=overlapping[0].surface_type,
                            raw_data=None,
                        ))
            
            used_indices.add(i)
        
        return merged_lots


# Singleton instance
parking_lot_finder_service = ParkingLotFinderService()


