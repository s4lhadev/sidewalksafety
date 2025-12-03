import logging
import httpx
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from shapely.geometry import Polygon, Point, shape
import json

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RawParkingLot:
    """Normalized parking lot from any data source."""
    source: str  # "inrix", "here", "osm"
    source_id: str
    geometry: Optional[Polygon]  # Polygon or None
    centroid: Point
    operator_name: Optional[str] = None
    address: Optional[str] = None
    capacity: Optional[int] = None
    surface_type: Optional[str] = None
    raw_metadata: Optional[Dict[str, Any]] = None


class ParkingLotDiscoveryService:
    """Service to discover parking lots from multiple data sources."""
    
    def __init__(self):
        self.inrix_app_id = settings.INRIX_APP_ID
        self.inrix_hash_token = settings.INRIX_HASH_TOKEN
        self.here_key = settings.HERE_API_KEY
        # OSM Overpass is free
    
    async def discover_parking_lots(self, area_polygon: Dict[str, Any]) -> List[RawParkingLot]:
        """
        Discover all parking lots within the given area polygon.
        Queries INRIX, HERE, and OSM in parallel.
        """
        results = []
        errors = []
        
        logger.info("   🔍 Querying parking lot data sources...")
        
        # Query INRIX
        if self.inrix_app_id and self.inrix_hash_token:
            logger.info("      📡 Querying INRIX API...")
            try:
                inrix_lots = await self._query_inrix(area_polygon)
                results.extend(inrix_lots)
                logger.info(f"      ✅ INRIX: {len(inrix_lots)} parking lots")
            except Exception as e:
                logger.warning(f"      ⚠️  INRIX failed: {e}")
                errors.append(f"INRIX: {str(e)}")
        else:
            logger.info("      ⏭️  INRIX not configured, skipping")
        
        # Query HERE
        if self.here_key:
            logger.info("      📡 Querying HERE API...")
            try:
                here_lots = await self._query_here(area_polygon)
                results.extend(here_lots)
                logger.info(f"      ✅ HERE: {len(here_lots)} parking lots")
            except Exception as e:
                logger.warning(f"      ⚠️  HERE failed: {e}")
                errors.append(f"HERE: {str(e)}")
        else:
            logger.info("      ⏭️  HERE not configured, skipping")
        
        # Query OSM (always available, free)
        logger.info("      📡 Querying OSM Overpass API...")
        try:
            osm_lots = await self._query_osm(area_polygon)
            results.extend(osm_lots)
            logger.info(f"      ✅ OSM: {len(osm_lots)} parking lots")
        except Exception as e:
            logger.warning(f"      ⚠️  OSM failed: {e}")
            errors.append(f"OSM: {str(e)}")
        
        if not results and errors:
            raise Exception(f"All data sources failed: {'; '.join(errors)}")
        
        logger.info(f"   📊 Total from all sources: {len(results)} parking lots")
        
        return results
    
    async def _query_inrix(self, area_polygon: Dict[str, Any]) -> List[RawParkingLot]:
        """
        Query INRIX Off-Street Parking API.
        
        INRIX uses AppId + HashToken for authentication.
        HashToken = Base64(AppId|AppKey)
        """
        if not self.inrix_app_id or not self.inrix_hash_token:
            return []
        
        # INRIX Parking API - Off-Street endpoint
        # INRIX uses AppId as query param and HashToken in Authorization header
        bbox = self._polygon_to_bbox(area_polygon)
        
        # INRIX expects: north,south,east,west format for box parameter
        box_param = f"{bbox['north']}|{bbox['south']}|{bbox['east']}|{bbox['west']}"
        
        # Try IQ API endpoint first
        url = "https://api.iq.inrix.com/v1/parking/offstreet"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                params={
                    "appId": self.inrix_app_id,
                    "box": box_param,
                    "limit": 500,
                },
                headers={
                    "Authorization": f"Bearer {self.inrix_hash_token}",
                    "Accept": "application/json",
                }
            )
            
            # If IQ endpoint fails, try legacy endpoint
            if response.status_code == 404:
                url = "https://api.inrix.com/v1/parking/offstreet"
                response = await client.get(
                    url,
                    params={
                        "appId": self.inrix_app_id,
                        "box": box_param,
                        "limit": 500,
                    },
                    headers={
                        "Authorization": f"Bearer {self.inrix_hash_token}",
                        "Accept": "application/json",
                    }
                )
            
            if response.status_code == 401:
                logger.warning("INRIX API authentication failed - skipping INRIX (using HERE and OSM instead)")
                return []  # Return empty list instead of raising - INRIX is optional
            
            if response.status_code != 200:
                logger.error(f"INRIX API returned {response.status_code}: {response.text}")
                raise Exception(f"INRIX API error: {response.status_code}")
            
            data = response.json()
        
        lots = []
        
        # INRIX response structure
        parking_data = data.get("result", {}).get("offStreetParking", [])
        
        for item in parking_data:
            try:
                # INRIX provides point coordinates
                point = item.get("point", {})
                lat = point.get("coordinates", {}).get("lat")
                lng = point.get("coordinates", {}).get("lng")
                
                if lat and lng:
                    lots.append(RawParkingLot(
                        source="inrix",
                        source_id=str(item.get("id", "")),
                        geometry=None,  # INRIX typically returns points, not polygons
                        centroid=Point(float(lng), float(lat)),
                        operator_name=item.get("operator", {}).get("name") or item.get("name"),
                        address=item.get("address", {}).get("streetAddress"),
                        capacity=item.get("totalSpaces"),
                        raw_metadata=item,
                    ))
            except Exception as e:
                logger.warning(f"Failed to parse INRIX lot: {e}")
        
        return lots
    
    async def _query_here(self, area_polygon: Dict[str, Any]) -> List[RawParkingLot]:
        """Query HERE Discover API for parking lots."""
        if not self.here_key:
            return []
        
        # HERE Discover API for parking
        url = "https://discover.search.hereapi.com/v1/discover"
        
        # Get centroid and radius from polygon
        poly = shape(area_polygon)
        centroid = poly.centroid
        # Approximate radius in meters (rough estimate from polygon bounds)
        bounds = poly.bounds
        radius = max(
            abs(bounds[2] - bounds[0]) * 111000,  # lng to meters (approximate)
            abs(bounds[3] - bounds[1]) * 111000   # lat to meters
        ) / 2
        radius = min(radius, 50000)  # HERE API max radius
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                params={
                    "at": f"{centroid.y},{centroid.x}",
                    "q": "parking",
                    "limit": 100,
                    "apiKey": self.here_key,
                }
            )
            
            if response.status_code == 401:
                raise Exception("HERE API key invalid")
            
            if response.status_code != 200:
                logger.error(f"HERE API returned {response.status_code}: {response.text}")
                raise Exception(f"HERE API error: {response.status_code}")
            
            data = response.json()
        
        lots = []
        for item in data.get("items", []):
            try:
                position = item.get("position", {})
                lat = position.get("lat")
                lng = position.get("lng")
                
                if lat and lng:
                    # Check if within original polygon
                    point = Point(lng, lat)
                    if not poly.contains(point):
                        continue
                    
                    # Try to get polygon geometry if available
                    geometry = None
                    if "mapView" in item:
                        mv = item["mapView"]
                        if all(k in mv for k in ["west", "south", "east", "north"]):
                            geometry = Polygon([
                                (mv["west"], mv["south"]),
                                (mv["east"], mv["south"]),
                                (mv["east"], mv["north"]),
                                (mv["west"], mv["north"]),
                                (mv["west"], mv["south"]),
                            ])
                    
                    lots.append(RawParkingLot(
                        source="here",
                        source_id=item.get("id", ""),
                        geometry=geometry,
                        centroid=point,
                        operator_name=item.get("title"),
                        address=item.get("address", {}).get("label"),
                        raw_metadata=item,
                    ))
            except Exception as e:
                logger.warning(f"Failed to parse HERE lot: {e}")
        
        return lots
    
    async def _query_osm(self, area_polygon: Dict[str, Any]) -> List[RawParkingLot]:
        """Query OpenStreetMap Overpass API for parking lots."""
        url = "https://overpass-api.de/api/interpreter"
        
        # Convert polygon to Overpass poly format
        poly = shape(area_polygon)
        coords = list(poly.exterior.coords)
        poly_str = " ".join([f"{lat} {lng}" for lng, lat in coords])
        
        # Overpass QL query for parking lots
        query = f"""
        [out:json][timeout:60];
        (
          way["amenity"="parking"](poly:"{poly_str}");
          relation["amenity"="parking"](poly:"{poly_str}");
        );
        out geom;
        """
        
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                url,
                data={"data": query},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 429:
                raise Exception("OSM Overpass rate limit exceeded")
            
            if response.status_code != 200:
                logger.error(f"OSM API returned {response.status_code}")
                raise Exception(f"OSM API error: {response.status_code}")
            
            data = response.json()
        
        lots = []
        for element in data.get("elements", []):
            try:
                if element.get("type") == "way" and "geometry" in element:
                    # Build polygon from way geometry
                    coords = [(p["lon"], p["lat"]) for p in element["geometry"]]
                    if len(coords) >= 3:
                        # Close polygon if not closed
                        if coords[0] != coords[-1]:
                            coords.append(coords[0])
                        
                        geometry = Polygon(coords)
                        centroid = geometry.centroid
                        
                        tags = element.get("tags", {})
                        lots.append(RawParkingLot(
                            source="osm",
                            source_id=str(element.get("id", "")),
                            geometry=geometry,
                            centroid=centroid,
                            operator_name=tags.get("operator") or tags.get("name"),
                            address=tags.get("addr:full") or tags.get("addr:street"),
                            surface_type=tags.get("surface"),
                            raw_metadata={"tags": tags, "id": element.get("id")},
                        ))
                
                elif element.get("type") == "relation":
                    # Handle multipolygon relations (more complex)
                    # For now, just use the first outer way
                    members = element.get("members", [])
                    for member in members:
                        if member.get("role") == "outer" and "geometry" in member:
                            coords = [(p["lon"], p["lat"]) for p in member["geometry"]]
                            if len(coords) >= 3:
                                if coords[0] != coords[-1]:
                                    coords.append(coords[0])
                                
                                geometry = Polygon(coords)
                                centroid = geometry.centroid
                                
                                tags = element.get("tags", {})
                                lots.append(RawParkingLot(
                                    source="osm",
                                    source_id=str(element.get("id", "")),
                                    geometry=geometry,
                                    centroid=centroid,
                                    operator_name=tags.get("operator") or tags.get("name"),
                                    surface_type=tags.get("surface"),
                                    raw_metadata={"tags": tags, "id": element.get("id")},
                                ))
                            break
                            
            except Exception as e:
                logger.warning(f"Failed to parse OSM element: {e}")
        
        return lots
    
    def _polygon_to_bbox(self, geojson_polygon: Dict[str, Any]) -> Dict[str, float]:
        """Convert GeoJSON polygon to bounding box."""
        poly = shape(geojson_polygon)
        bounds = poly.bounds
        return {
            "west": bounds[0],
            "south": bounds[1],
            "east": bounds[2],
            "north": bounds[3],
        }


# Singleton instance
parking_lot_discovery_service = ParkingLotDiscoveryService()
