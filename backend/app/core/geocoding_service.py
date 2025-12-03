import logging
import httpx
from typing import Optional, Dict, Any
from shapely.geometry import Polygon, box
from app.core.config import settings

logger = logging.getLogger(__name__)


class GeocodingService:
    """Service to convert ZIP codes and counties to GeoJSON polygons."""
    
    def __init__(self):
        self.google_key = settings.GOOGLE_MAPS_KEY
    
    async def get_area_polygon(
        self,
        area_type: str,
        value: str,
        state: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Convert ZIP code or county to GeoJSON polygon.
        
        Args:
            area_type: "zip" or "county"
            value: ZIP code or county name
            state: State code (required for county)
            
        Returns:
            GeoJSON polygon or None
        """
        if area_type == "zip":
            return await self._get_zip_polygon(value)
        elif area_type == "county":
            if not state:
                raise ValueError("State is required for county lookup")
            return await self._get_county_polygon(value, state)
        else:
            raise ValueError(f"Unknown area_type: {area_type}")
    
    async def _get_zip_polygon(self, zip_code: str) -> Optional[Dict[str, Any]]:
        """Get polygon for a ZIP code using geocoding + approximate bounds."""
        
        # First, geocode the ZIP code to get center point
        center = await self._geocode_address(f"{zip_code}, USA")
        
        if not center:
            logger.error(f"Failed to geocode ZIP code: {zip_code}")
            return None
        
        # Create approximate polygon (ZIP codes are roughly 5-10 km across)
        # This is an approximation - for production, use Census Bureau TIGER data
        lat, lng = center["lat"], center["lng"]
        
        # Approximate 5km radius in degrees
        lat_offset = 0.045  # ~5km
        lng_offset = 0.055  # ~5km (varies by latitude)
        
        polygon = box(
            lng - lng_offset,
            lat - lat_offset,
            lng + lng_offset,
            lat + lat_offset
        )
        
        return {
            "type": "Polygon",
            "coordinates": [list(polygon.exterior.coords)]
        }
    
    async def _get_county_polygon(self, county: str, state: str) -> Optional[Dict[str, Any]]:
        """Get polygon for a county using geocoding + approximate bounds."""
        
        # Geocode the county
        center = await self._geocode_address(f"{county} County, {state}, USA")
        
        if not center:
            logger.error(f"Failed to geocode county: {county}, {state}")
            return None
        
        lat, lng = center["lat"], center["lng"]
        
        # Counties are larger - approximate 30km radius
        lat_offset = 0.27  # ~30km
        lng_offset = 0.33  # ~30km
        
        polygon = box(
            lng - lng_offset,
            lat - lat_offset,
            lng + lng_offset,
            lat + lat_offset
        )
        
        return {
            "type": "Polygon",
            "coordinates": [list(polygon.exterior.coords)]
        }
    
    async def _geocode_address(self, address: str) -> Optional[Dict[str, float]]:
        """Geocode an address to lat/lng."""
        if not self.google_key:
            logger.warning("   ⚠️  GOOGLE_MAPS_KEY not configured")
            return None
        
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        
        logger.info(f"   📍 Geocoding: {address}")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    url,
                    params={"address": address, "key": self.google_key}
                )
                
                logger.info(f"   📡 Geocoding response status: {response.status_code}")
                
                data = response.json()
                
                if data.get("status") != "OK":
                    logger.error(f"   ❌ Geocoding error: {data.get('status')} - {data.get('error_message', 'No message')}")
                    return None
                
                results = data.get("results", [])
                if not results:
                    logger.error(f"   ❌ No geocoding results found")
                    return None
                
                location = results[0].get("geometry", {}).get("location", {})
                lat, lng = location.get("lat"), location.get("lng")
                
                logger.info(f"   ✅ Geocoded to: {lat}, {lng}")
                
                return {"lat": lat, "lng": lng}
                
        except Exception as e:
            logger.error(f"   ❌ Geocoding failed: {e}")
            return None


# Singleton instance
geocoding_service = GeocodingService()
