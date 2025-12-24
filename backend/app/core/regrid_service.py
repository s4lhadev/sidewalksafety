"""
Regrid Property Parcel Service

Fetches property parcel boundaries from Regrid API.
This provides the legal property boundary polygon for a given address or coordinates.

API Documentation: https://regrid.com/api
"""

import logging
import httpx
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from shapely.geometry import shape, Polygon, MultiPolygon, Point
from shapely.ops import unary_union

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PropertyParcel:
    """Property parcel data from Regrid."""
    parcel_id: str
    apn: Optional[str]  # Assessor Parcel Number
    address: Optional[str]
    owner: Optional[str]
    polygon: Polygon  # Property boundary
    centroid: Point
    area_m2: float
    area_acres: Optional[float]
    land_use: Optional[str]
    zoning: Optional[str]
    year_built: Optional[int]
    raw_data: Dict[str, Any]
    
    @property
    def has_valid_geometry(self) -> bool:
        """Check if the parcel has a valid polygon."""
        return self.polygon is not None and not self.polygon.is_empty and self.polygon.is_valid


class RegridService:
    """
    Service to fetch property parcel data from Regrid API.
    
    Regrid provides:
    - Property boundaries (legal parcel polygons)
    - Owner information
    - Land use and zoning
    - Building footprints (matched)
    
    This enables us to know exactly what land belongs to a business,
    so we can accurately identify asphalt within their property.
    """
    
    def __init__(self):
        self.api_key = settings.REGRID_API_KEY
        self.base_url = settings.REGRID_API_URL
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def is_configured(self) -> bool:
        """Check if Regrid API is configured."""
        return bool(self.api_key)
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def get_parcel_by_coordinates(
        self,
        lat: float,
        lng: float
    ) -> Optional[PropertyParcel]:
        """
        Get property parcel that contains the given coordinates.
        
        Args:
            lat: Latitude
            lng: Longitude
            
        Returns:
            PropertyParcel if found, None otherwise
        """
        if not self.is_configured:
            logger.warning("Regrid API not configured (REGRID_API_KEY not set)")
            return None
        
        try:
            client = await self._get_client()
            
            # Regrid API endpoint for point lookup
            url = f"{self.base_url}/parcels/point"
            params = {
                "lat": lat,
                "lon": lng,
                "token": self.api_key,
            }
            
            logger.info(f"   🗺️  Fetching parcel from Regrid for ({lat:.6f}, {lng:.6f})")
            
            response = await client.get(url, params=params)
            
            if response.status_code == 401:
                logger.error("   ❌ Regrid API authentication failed - check API key")
                return None
            
            if response.status_code == 404:
                logger.warning(f"   ⚠️ No parcel found at ({lat:.6f}, {lng:.6f})")
                return None
            
            if response.status_code != 200:
                logger.error(f"   ❌ Regrid API error: {response.status_code} - {response.text[:200]}")
                return None
            
            data = response.json()
            
            # Parse the response
            parcels = self._parse_response(data)
            
            if parcels:
                parcel = parcels[0]  # Return the first (closest) parcel
                logger.info(f"   ✅ Found parcel: {parcel.parcel_id}, {parcel.area_m2:.0f} m²")
                return parcel
            
            logger.warning(f"   ⚠️ No parcels in response for ({lat:.6f}, {lng:.6f})")
            return None
            
        except Exception as e:
            logger.error(f"   ❌ Regrid API error: {e}")
            return None
    
    async def get_parcel_by_address(
        self,
        address: str
    ) -> Optional[PropertyParcel]:
        """
        Get property parcel by address.
        
        Args:
            address: Full street address
            
        Returns:
            PropertyParcel if found, None otherwise
        """
        if not self.is_configured:
            logger.warning("Regrid API not configured (REGRID_API_KEY not set)")
            return None
        
        try:
            client = await self._get_client()
            
            # Regrid API endpoint for address search
            url = f"{self.base_url}/parcels"
            params = {
                "query": address,
                "token": self.api_key,
            }
            
            logger.info(f"   🗺️  Fetching parcel from Regrid for address: {address[:50]}...")
            
            response = await client.get(url, params=params)
            
            if response.status_code == 401:
                logger.error("   ❌ Regrid API authentication failed - check API key")
                return None
            
            if response.status_code != 200:
                logger.error(f"   ❌ Regrid API error: {response.status_code} - {response.text[:200]}")
                return None
            
            data = response.json()
            
            # Parse the response
            parcels = self._parse_response(data)
            
            if parcels:
                parcel = parcels[0]  # Return the first (best match) parcel
                logger.info(f"   ✅ Found parcel: {parcel.parcel_id}, {parcel.area_m2:.0f} m²")
                return parcel
            
            logger.warning(f"   ⚠️ No parcels found for address: {address[:50]}...")
            return None
            
        except Exception as e:
            logger.error(f"   ❌ Regrid API error: {e}")
            return None
    
    async def get_parcels_in_area(
        self,
        min_lat: float,
        min_lng: float,
        max_lat: float,
        max_lng: float,
        limit: int = 100
    ) -> List[PropertyParcel]:
        """
        Get all parcels within a bounding box.
        
        Args:
            min_lat: South boundary
            min_lng: West boundary
            max_lat: North boundary
            max_lng: East boundary
            limit: Maximum number of parcels to return
            
        Returns:
            List of PropertyParcel objects
        """
        if not self.is_configured:
            logger.warning("Regrid API not configured (REGRID_API_KEY not set)")
            return []
        
        try:
            client = await self._get_client()
            
            # Regrid API endpoint for bounding box search
            url = f"{self.base_url}/parcels"
            params = {
                "bounds": f"{min_lng},{min_lat},{max_lng},{max_lat}",
                "limit": limit,
                "token": self.api_key,
            }
            
            logger.info(f"   🗺️  Fetching parcels in bounding box...")
            
            response = await client.get(url, params=params)
            
            if response.status_code != 200:
                logger.error(f"   ❌ Regrid API error: {response.status_code}")
                return []
            
            data = response.json()
            
            return self._parse_response(data)
            
        except Exception as e:
            logger.error(f"   ❌ Regrid API error: {e}")
            return []
    
    def _parse_response(self, data: Dict[str, Any]) -> List[PropertyParcel]:
        """
        Parse Regrid API response into PropertyParcel objects.
        
        Regrid returns GeoJSON FeatureCollection format.
        """
        parcels: List[PropertyParcel] = []
        
        # Handle GeoJSON FeatureCollection
        features = data.get("features", [])
        
        # Also handle direct feature response
        if not features and "geometry" in data:
            features = [data]
        
        for feature in features:
            try:
                parcel = self._parse_feature(feature)
                if parcel and parcel.has_valid_geometry:
                    parcels.append(parcel)
            except Exception as e:
                logger.debug(f"Failed to parse parcel feature: {e}")
        
        return parcels
    
    def _parse_feature(self, feature: Dict[str, Any]) -> Optional[PropertyParcel]:
        """Parse a single GeoJSON feature into PropertyParcel."""
        geometry = feature.get("geometry")
        properties = feature.get("properties", {})
        
        if not geometry:
            return None
        
        # Parse geometry
        try:
            geom = shape(geometry)
            
            # Handle MultiPolygon by taking the largest polygon
            if isinstance(geom, MultiPolygon):
                geom = max(geom.geoms, key=lambda g: g.area)
            
            if not isinstance(geom, Polygon):
                return None
            
            if not geom.is_valid:
                geom = geom.buffer(0)  # Fix invalid geometry
            
            if geom.is_empty:
                return None
                
        except Exception as e:
            logger.debug(f"Failed to parse geometry: {e}")
            return None
        
        # Extract properties (Regrid uses various field names)
        # Common Regrid fields:
        parcel_id = (
            properties.get("ll_uuid") or  # Regrid's unique ID
            properties.get("parcelnumb") or  # Parcel number
            properties.get("id") or
            str(feature.get("id", "unknown"))
        )
        
        # Calculate area
        from pyproj import Geod
        geod = Geod(ellps="WGS84")
        coords = list(geom.exterior.coords)
        area_m2, _ = geod.polygon_area_perimeter(
            [c[0] for c in coords],
            [c[1] for c in coords]
        )
        area_m2 = abs(area_m2)
        
        # Get area in acres from properties if available
        area_acres = properties.get("ll_gisacre") or properties.get("gisacre")
        if area_acres:
            try:
                area_acres = float(area_acres)
            except:
                area_acres = None
        
        return PropertyParcel(
            parcel_id=str(parcel_id),
            apn=properties.get("parcelnumb") or properties.get("apn"),
            address=properties.get("address") or properties.get("situs"),
            owner=properties.get("owner") or properties.get("ownername"),
            polygon=geom,
            centroid=geom.centroid,
            area_m2=area_m2,
            area_acres=area_acres,
            land_use=properties.get("usecode") or properties.get("landuse"),
            zoning=properties.get("zoning") or properties.get("zoning_code"),
            year_built=properties.get("yearbuilt"),
            raw_data=feature,
        )
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Singleton instance
regrid_service = RegridService()

