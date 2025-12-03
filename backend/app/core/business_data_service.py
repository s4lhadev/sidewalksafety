import logging
import httpx
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from shapely.geometry import Point, shape
from sqlalchemy.orm import Session
from geoalchemy2.shape import from_shape
import uuid

from app.core.config import settings
from app.models.business import Business

logger = logging.getLogger(__name__)


# Categories relevant for parking lot repair outreach
RELEVANT_CATEGORIES = {
    # High priority - definitely have parking lots
    "high": [
        "shopping_mall", "shopping_center", "mall",
        "supermarket", "grocery", "big_box_store",
        "hotel", "motel", "lodging",
        "hospital", "medical_center", "clinic",
        "office_building", "office_park", "corporate",
        "warehouse", "distribution_center",
        "car_dealership", "auto_dealer",
        "restaurant", "fast_food",
        "bank", "financial",
        "church", "religious",
        "school", "university", "college",
        "apartment", "apartment_complex", "multifamily",
        "retail", "store",
    ],
    # Medium priority - likely have parking lots
    "medium": [
        "gym", "fitness",
        "movie_theater", "cinema",
        "bowling", "entertainment",
        "pharmacy", "drugstore",
        "gas_station",
        "storage", "self_storage",
        "industrial",
    ],
    # Low priority - may or may not have parking lots
    "low": [
        "small_business",
        "professional_services",
        "salon", "spa",
    ],
}


@dataclass
class RawBusiness:
    """Normalized business from any data source."""
    source: str  # "google_places"
    source_id: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    county: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    latitude: float = None
    longitude: float = None
    raw_metadata: Optional[Dict[str, Any]] = None


class BusinessDataService:
    """Service to load business contact data using Google Places API."""
    
    def __init__(self):
        self.google_places_key = settings.GOOGLE_PLACES_KEY
    
    async def load_businesses(
        self,
        area_polygon: Dict[str, Any],
        categories: Optional[List[str]] = None,
        max_businesses: int = 100
    ) -> List[RawBusiness]:
        """
        Load businesses within the given area polygon using Google Places API.
        
        Args:
            area_polygon: GeoJSON polygon defining the search area
            categories: Optional list of categories to search (defaults to common commercial)
            max_businesses: Maximum number of businesses to return (for testing, use low values)
        """
        if not self.google_places_key:
            logger.warning("   ⚠️  Google Places API key not configured")
            return []
        
        logger.info(f"   📡 Querying Google Places API (max: {max_businesses})...")
        
        try:
            businesses = await self._query_google_places(area_polygon, categories, max_businesses)
            logger.info(f"   ✅ Google Places: {len(businesses)} businesses found")
            
            # Log category breakdown
            categories_count = {}
            for biz in businesses:
                cat = biz.category or "unknown"
                categories_count[cat] = categories_count.get(cat, 0) + 1
            
            for cat, count in sorted(categories_count.items(), key=lambda x: -x[1])[:5]:
                logger.info(f"      - {cat}: {count}")
            
            return businesses
        except Exception as e:
            logger.error(f"   ❌ Google Places query failed: {e}")
            return []
    
    async def load_businesses_near_point(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int = 100
    ) -> List[RawBusiness]:
        """
        Load businesses near a specific point (for parking lot association).
        """
        if not self.google_places_key:
            logger.warning("Google Places API key not configured")
            return []
        
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        
        businesses = []
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                params={
                    "location": f"{latitude},{longitude}",
                    "radius": radius_meters,
                    "key": self.google_places_key,
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Google Places API returned {response.status_code}")
                return []
            
            data = response.json()
            
            if data.get("status") not in ["OK", "ZERO_RESULTS"]:
                logger.error(f"Google Places API error: {data.get('status')}")
                return []
            
            for item in data.get("results", []):
                business = await self._parse_google_place(item)
                if business:
                    businesses.append(business)
        
        return businesses
    
    async def _query_google_places(
        self,
        area_polygon: Dict[str, Any],
        categories: Optional[List[str]] = None,
        max_businesses: int = 100
    ) -> List[RawBusiness]:
        """Query Google Places API for businesses in an area."""
        
        # Get centroid for search
        poly = shape(area_polygon)
        centroid = poly.centroid
        
        # Calculate radius from polygon bounds
        bounds = poly.bounds
        radius = max(
            abs(bounds[2] - bounds[0]) * 111000,  # lng to meters
            abs(bounds[3] - bounds[1]) * 111000   # lat to meters
        ) / 2
        radius = min(radius, 50000)  # Google max radius
        
        # Search for commercial businesses that likely have parking lots
        # For small limits, only search a few categories to reduce API calls
        if max_businesses <= 10:
            queries = ["shopping center", "hotel"]  # Just 2 queries for testing
        elif max_businesses <= 30:
            queries = ["shopping center", "hotel", "restaurant", "supermarket"]
        else:
            queries = [
                "shopping center",
                "shopping mall",
                "hotel",
                "restaurant",
                "office building",
                "apartment complex",
                "church",
                "school",
                "hospital",
                "supermarket",
            ]
        
        logger.info(f"      Searching {len(queries)} categories...")
        
        businesses = []
        seen_place_ids = set()
        
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for query in queries:
                if len(businesses) >= max_businesses:
                    logger.info(f"      Reached max_businesses limit ({max_businesses})")
                    break
                
                try:
                    response = await client.get(
                        url,
                        params={
                            "query": query,
                            "location": f"{centroid.y},{centroid.x}",
                            "radius": int(radius),
                            "key": self.google_places_key,
                        }
                    )
                    
                    if response.status_code != 200:
                        continue
                    
                    data = response.json()
                    
                    if data.get("status") not in ["OK", "ZERO_RESULTS"]:
                        continue
                    
                    for item in data.get("results", []):
                        if len(businesses) >= max_businesses:
                            break
                            
                        place_id = item.get("place_id")
                        if place_id in seen_place_ids:
                            continue
                        seen_place_ids.add(place_id)
                        
                        # Check if within polygon
                        location = item.get("geometry", {}).get("location", {})
                        lat = location.get("lat")
                        lng = location.get("lng")
                        
                        if lat and lng:
                            point = Point(lng, lat)
                            if not poly.contains(point):
                                continue
                            
                            business = await self._parse_google_place(item, client)
                            if business:
                                businesses.append(business)
                
                except Exception as e:
                    logger.warning(f"Failed to query '{query}': {e}")
        
        return businesses
    
    async def _parse_google_place(
        self,
        item: Dict[str, Any],
        client: Optional[httpx.AsyncClient] = None
    ) -> Optional[RawBusiness]:
        """Parse a Google Places result into RawBusiness."""
        try:
            location = item.get("geometry", {}).get("location", {})
            lat = location.get("lat")
            lng = location.get("lng")
            
            if not lat or not lng:
                return None
            
            place_id = item.get("place_id", "")
            
            # Basic info from search result
            business = RawBusiness(
                source="google_places",
                source_id=place_id,
                name=item.get("name", ""),
                address=item.get("formatted_address") or item.get("vicinity"),
                category=", ".join(item.get("types", [])[:2]),
                latitude=float(lat),
                longitude=float(lng),
                raw_metadata=item,
            )
            
            # Get detailed info (phone, website) if we have a client
            if client and place_id and self.google_places_key:
                try:
                    details = await self._get_place_details(place_id, client)
                    if details:
                        business.phone = details.get("formatted_phone_number")
                        business.website = details.get("website")
                        
                        # Parse address components
                        for component in details.get("address_components", []):
                            types = component.get("types", [])
                            if "locality" in types:
                                business.city = component.get("long_name")
                            elif "administrative_area_level_1" in types:
                                business.state = component.get("short_name")
                            elif "postal_code" in types:
                                business.zip = component.get("long_name")
                            elif "administrative_area_level_2" in types:
                                business.county = component.get("long_name")
                except Exception as e:
                    logger.debug(f"Failed to get place details: {e}")
            
            return business
            
        except Exception as e:
            logger.warning(f"Failed to parse Google Place: {e}")
            return None
    
    async def _get_place_details(
        self,
        place_id: str,
        client: httpx.AsyncClient
    ) -> Optional[Dict[str, Any]]:
        """Get detailed place information including phone and website."""
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        
        response = await client.get(
            url,
            params={
                "place_id": place_id,
                "fields": "formatted_phone_number,website,address_components",
                "key": self.google_places_key,
            }
        )
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        if data.get("status") != "OK":
            return None
        
        return data.get("result", {})
    
    def save_to_database(
        self,
        raw_businesses: List[RawBusiness],
        db: Session
    ) -> List[Business]:
        """Save businesses to database, deduplicating by name and location."""
        saved = []
        seen = set()  # Track (name, lat, lng) to deduplicate
        
        for biz in raw_businesses:
            try:
                # Simple deduplication key
                key = (biz.name.lower(), round(biz.latitude, 4), round(biz.longitude, 4))
                if key in seen:
                    continue
                seen.add(key)
                
                db_business = Business(
                    name=biz.name,
                    phone=biz.phone,
                    email=biz.email,
                    website=biz.website,
                    address=biz.address,
                    city=biz.city,
                    state=biz.state,
                    zip=biz.zip,
                    county=biz.county,
                    category=biz.category,
                    subcategory=biz.subcategory,
                    geometry=from_shape(Point(biz.longitude, biz.latitude), srid=4326),
                    data_source=biz.source,
                    places_id=biz.source_id if biz.source == "google_places" else None,
                    raw_metadata=biz.raw_metadata,
                )
                db.add(db_business)
                saved.append(db_business)
            except Exception as e:
                logger.error(f"Failed to save business: {e}")
        
        db.commit()
        
        for biz in saved:
            db.refresh(biz)
        
        return saved
    
    def get_category_priority(self, category: str) -> str:
        """Get priority level for a business category."""
        if not category:
            return "low"
        
        category_lower = category.lower()
        
        for keyword in RELEVANT_CATEGORIES["high"]:
            if keyword in category_lower:
                return "high"
        
        for keyword in RELEVANT_CATEGORIES["medium"]:
            if keyword in category_lower:
                return "medium"
        
        return "low"


# Singleton instance
business_data_service = BusinessDataService()
