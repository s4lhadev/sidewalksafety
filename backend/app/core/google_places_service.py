"""
Google Places Service - Search for businesses using Google Places API (New)

Features:
- Text Search with automatic pagination (up to 60 results)
- Natural language property type queries
- Location restriction by polygon or circle
- Returns place details with lat/lng for parcel matching
"""

import httpx
import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PlaceResult:
    """A place returned from Google Places API"""
    place_id: str
    name: str
    address: str
    lat: float
    lng: float
    types: List[str]
    primary_type: Optional[str] = None
    rating: Optional[float] = None
    user_ratings_count: Optional[int] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GooglePlacesService:
    """
    Service for searching businesses using Google Places API (New).
    
    Uses Text Search endpoint with automatic pagination to get up to 60 results.
    """
    
    BASE_URL = "https://places.googleapis.com/v1/places:searchText"
    
    # Fields to request - balance between data and cost
    # Pro tier fields (lower cost)
    PRO_FIELDS = [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.types",
        "places.primaryType",
    ]
    
    # Enterprise tier fields (higher cost, optional)
    ENTERPRISE_FIELDS = [
        "places.rating",
        "places.userRatingCount",
        "places.websiteUri",
        "places.nationalPhoneNumber",
    ]
    
    def __init__(self, include_enterprise_fields: bool = True):
        self.api_key = settings.GOOGLE_PLACES_KEY
        self.include_enterprise = include_enterprise_fields
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Build field mask
        fields = self.PRO_FIELDS.copy()
        if include_enterprise_fields:
            fields.extend(self.ENTERPRISE_FIELDS)
        self.field_mask = ",".join(fields)
        
    async def search_places(
        self,
        query: str,
        location_restriction: Optional[Dict[str, Any]] = None,
        location_bias: Optional[Dict[str, Any]] = None,
        max_results: int = 60,
        included_type: Optional[str] = None,
    ) -> List[PlaceResult]:
        """
        Search for places using natural language query.
        
        Automatically paginates to get up to max_results (max 60).
        
        Args:
            query: Natural language search query (e.g., "big restaurants", "auto repair shops")
            location_restriction: Restrict to area (rectangle only) - results MUST be inside
            location_bias: Bias toward area (circle or rectangle) - results can be outside
            max_results: Maximum results to return (capped at 60 by Google)
            included_type: Optional place type filter (e.g., "restaurant")
            
        Returns:
            List of PlaceResult objects
        """
        if not self.api_key:
            logger.error("GOOGLE_PLACES_KEY not configured")
            return []
        
        all_results: List[PlaceResult] = []
        next_page_token: Optional[str] = None
        page_count = 0
        max_pages = 3  # Google caps at 60 results (3 pages of 20)
        
        logger.info(f"Google Places search: '{query}' (max {max_results} results)")
        
        while len(all_results) < max_results and page_count < max_pages:
            page_count += 1
            
            # Build request body
            body: Dict[str, Any] = {
                "textQuery": query,
                "pageSize": min(20, max_results - len(all_results)),
            }
            
            # Add location restriction or bias
            if location_restriction:
                body["locationRestriction"] = location_restriction
            elif location_bias:
                body["locationBias"] = location_bias
            
            # Add type filter if specified
            if included_type:
                body["includedType"] = included_type
            
            # Add pagination token if not first page
            if next_page_token:
                body["pageToken"] = next_page_token
            
            # Make request
            try:
                response = await self.client.post(
                    self.BASE_URL,
                    json=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Goog-Api-Key": self.api_key,
                        "X-Goog-FieldMask": self.field_mask + ",nextPageToken",
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"Google Places API error: {response.status_code} - {response.text}")
                    break
                
                data = response.json()
                
                # Parse places
                places = data.get("places", [])
                for place in places:
                    result = self._parse_place(place)
                    if result:
                        all_results.append(result)
                
                logger.info(f"Page {page_count}: Got {len(places)} places (total: {len(all_results)})")
                
                # Check for next page
                next_page_token = data.get("nextPageToken")
                if not next_page_token:
                    break
                    
                # Small delay between pagination requests (recommended by Google)
                await asyncio.sleep(0.2)
                
            except Exception as e:
                logger.error(f"Error in Google Places search: {e}", exc_info=True)
                break
        
        logger.info(f"Google Places search complete: {len(all_results)} results")
        return all_results
    
    async def search_in_polygon(
        self,
        query: str,
        polygon: Dict[str, Any],
        max_results: int = 60,
        included_type: Optional[str] = None,
    ) -> List[PlaceResult]:
        """
        Search for places within a polygon area.
        
        Note: Google Places API only supports rectangle location restriction,
        so we convert polygon to bounding box and filter results afterward.
        
        Args:
            query: Natural language search query
            polygon: GeoJSON Polygon geometry
            max_results: Maximum results to return
            included_type: Optional place type filter
            
        Returns:
            List of PlaceResult objects within the polygon
        """
        from shapely.geometry import shape, Point
        
        # Convert polygon to shapely for filtering
        try:
            poly_shape = shape(polygon)
            bounds = poly_shape.bounds  # (minx, miny, maxx, maxy) = (min_lng, min_lat, max_lng, max_lat)
        except Exception as e:
            logger.error(f"Invalid polygon geometry: {e}")
            return []
        
        # Create rectangle location restriction from bounds
        location_restriction = {
            "rectangle": {
                "low": {
                    "latitude": bounds[1],  # min_lat
                    "longitude": bounds[0],  # min_lng
                },
                "high": {
                    "latitude": bounds[3],  # max_lat
                    "longitude": bounds[2],  # max_lng
                }
            }
        }
        
        # Search with bounding box
        results = await self.search_places(
            query=query,
            location_restriction=location_restriction,
            max_results=max_results,
            included_type=included_type,
        )
        
        # Filter to only include results actually inside the polygon
        filtered = []
        for place in results:
            point = Point(place.lng, place.lat)
            if poly_shape.contains(point):
                filtered.append(place)
        
        logger.info(f"Filtered to {len(filtered)} places inside polygon (from {len(results)} in bbox)")
        return filtered
    
    async def search_in_circle(
        self,
        query: str,
        center_lat: float,
        center_lng: float,
        radius_meters: float = 5000,
        max_results: int = 60,
        included_type: Optional[str] = None,
    ) -> List[PlaceResult]:
        """
        Search for places within a circular area.
        
        Args:
            query: Natural language search query
            center_lat: Center latitude
            center_lng: Center longitude
            radius_meters: Search radius in meters (max 50000)
            max_results: Maximum results to return
            included_type: Optional place type filter
            
        Returns:
            List of PlaceResult objects
        """
        # Create circle location bias
        location_bias = {
            "circle": {
                "center": {
                    "latitude": center_lat,
                    "longitude": center_lng,
                },
                "radius": min(radius_meters, 50000),  # Max 50km
            }
        }
        
        return await self.search_places(
            query=query,
            location_bias=location_bias,
            max_results=max_results,
            included_type=included_type,
        )
    
    def _parse_place(self, place: Dict[str, Any]) -> Optional[PlaceResult]:
        """Parse a place from Google Places API response"""
        try:
            # Required fields
            place_id = place.get("id", "")
            display_name = place.get("displayName", {})
            name = display_name.get("text", "Unknown")
            address = place.get("formattedAddress", "")
            
            location = place.get("location", {})
            lat = location.get("latitude")
            lng = location.get("longitude")
            
            if not lat or not lng:
                return None
            
            # Optional fields
            types = place.get("types", [])
            primary_type = place.get("primaryType")
            rating = place.get("rating")
            user_ratings_count = place.get("userRatingCount")
            website = place.get("websiteUri")
            phone = place.get("nationalPhoneNumber")
            
            return PlaceResult(
                place_id=place_id,
                name=name,
                address=address,
                lat=lat,
                lng=lng,
                types=types,
                primary_type=primary_type,
                rating=rating,
                user_ratings_count=user_ratings_count,
                website=website,
                phone=phone,
            )
            
        except Exception as e:
            logger.debug(f"Error parsing place: {e}")
            return None
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Singleton instance
_service: Optional[GooglePlacesService] = None


def get_google_places_service() -> GooglePlacesService:
    """Get or create the Google Places service singleton"""
    global _service
    if _service is None:
        _service = GooglePlacesService()
    return _service
