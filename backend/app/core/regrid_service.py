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
            lng: Longitude (note: Regrid uses 'lon' not 'lng')
            
        Returns:
            PropertyParcel if found, None otherwise
        """
        if not self.is_configured:
            logger.warning("Regrid API not configured (REGRID_API_KEY not set)")
            return None
        
        try:
            client = await self._get_client()
            
            # Regrid V2 API endpoint for point lookup (this is the correct endpoint!)
            url = "https://app.regrid.com/api/v2/parcels/point"
            params = {
                "lat": lat,
                "lon": lng,  # Note: Regrid uses 'lon' not 'lng'
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
            
            # V2 API returns parcels in a nested structure
            parcels_data = data.get("parcels", {})
            
            # Parse the response
            parcels = self._parse_response(parcels_data)
            
            if parcels:
                parcel = parcels[0]  # Return the first (closest) parcel
                logger.info(f"   ✅ Found parcel: {parcel.address or parcel.parcel_id}")
                logger.info(f"      Owner: {parcel.owner}")
                logger.info(f"      Area: {parcel.area_m2:,.0f} m² ({parcel.area_acres or 0:.2f} acres)")
                return parcel
            
            logger.warning(f"   ⚠️ No parcels in response for ({lat:.6f}, {lng:.6f})")
            return None
            
        except Exception as e:
            logger.error(f"   ❌ Regrid API error: {e}")
            return None
    
    async def get_parcel_by_address(
        self,
        address: str,
        fallback_lat: Optional[float] = None,
        fallback_lng: Optional[float] = None
    ) -> Optional[PropertyParcel]:
        """
        Get property parcel by address using Regrid's typeahead + detail lookup.
        
        This is MORE ACCURATE than point lookup because it matches the actual
        street address rather than relying on coordinates that might land on
        an adjacent parcel.
        
        Args:
            address: Full street address (e.g., "2929 Oak Lawn Ave, Dallas, TX 75219")
            fallback_lat: Fallback latitude if address search fails
            fallback_lng: Fallback longitude if address search fails
            
        Returns:
            PropertyParcel if found, None otherwise
        """
        if not self.is_configured:
            logger.warning("Regrid API not configured (REGRID_API_KEY not set)")
            return None
        
        try:
            client = await self._get_client()
            
            logger.info(f"   🗺️  Fetching parcel from Regrid for address: {address[:60]}...")
            
            # Step 1: Use typeahead to find the parcel path
            typeahead_url = "https://app.regrid.com/api/v1/typeahead"
            typeahead_params = {
                "query": address,
                "token": self.api_key,
            }
            
            response = await client.get(typeahead_url, params=typeahead_params)
            
            if response.status_code != 200:
                logger.warning(f"   ⚠️ Typeahead failed: {response.status_code}")
                # Fall back to point lookup if address search fails
                if fallback_lat and fallback_lng:
                    logger.info(f"   🔄 Falling back to point lookup...")
                    return await self.get_parcel_by_coordinates(fallback_lat, fallback_lng)
                return None
            
            typeahead_data = response.json()
            
            # Typeahead API returns a list directly, or a dict with "results"
            if isinstance(typeahead_data, list):
                results = typeahead_data
            else:
                results = typeahead_data.get("results", [])
            
            if not results:
                logger.warning(f"   ⚠️ No typeahead results for: {address[:50]}")
                if fallback_lat and fallback_lng:
                    logger.info(f"   🔄 Falling back to point lookup...")
                    return await self.get_parcel_by_coordinates(fallback_lat, fallback_lng)
                return None
            
            # Find the best matching result (prefer parcels over other types)
            best_result = None
            for result in results:
                result_type = result.get("type", "")
                if result_type == "parcel":
                    best_result = result
                    break
            
            if not best_result:
                best_result = results[0]  # Take first result if no parcel type
            
            parcel_path = best_result.get("path")
            
            if not parcel_path:
                logger.warning(f"   ⚠️ No parcel path in result")
                if fallback_lat and fallback_lng:
                    return await self.get_parcel_by_coordinates(fallback_lat, fallback_lng)
                return None
            
            logger.info(f"   📍 Found parcel path: {parcel_path}")
            
            # Step 2: Fetch the parcel details using the path
            detail_url = f"https://app.regrid.com/api/v1/parcel{parcel_path}.json"
            detail_params = {"token": self.api_key}
            
            detail_response = await client.get(detail_url, params=detail_params)
            
            if detail_response.status_code != 200:
                logger.warning(f"   ⚠️ Parcel detail fetch failed: {detail_response.status_code}")
                if fallback_lat and fallback_lng:
                    return await self.get_parcel_by_coordinates(fallback_lat, fallback_lng)
                return None
            
            detail_data = detail_response.json()
            
            # Parse as GeoJSON feature
            parcels = self._parse_response(detail_data)
            
            if parcels:
                parcel = parcels[0]
                logger.info(f"   ✅ Found parcel by ADDRESS: {parcel.address or parcel.parcel_id}")
                logger.info(f"      Owner: {parcel.owner}")
                logger.info(f"      Area: {parcel.area_m2:,.0f} m² ({parcel.area_acres or 0:.2f} acres)")
                return parcel
            
            logger.warning(f"   ⚠️ Could not parse parcel data")
            if fallback_lat and fallback_lng:
                return await self.get_parcel_by_coordinates(fallback_lat, fallback_lng)
            return None
            
        except Exception as e:
            logger.error(f"   ❌ Regrid address search error: {e}")
            if fallback_lat and fallback_lng:
                logger.info(f"   🔄 Falling back to point lookup...")
                return await self.get_parcel_by_coordinates(fallback_lat, fallback_lng)
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
        
        # V2 API stores detailed fields in a 'fields' subobject
        fields = properties.get("fields", {})
        
        # Merge properties and fields (fields takes precedence)
        all_props = {**properties, **fields}
        
        # Extract properties (Regrid uses various field names)
        parcel_id = (
            all_props.get("ll_uuid") or  # Regrid's unique ID
            all_props.get("parcelnumb") or  # Parcel number
            properties.get("ll_uuid") or
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
        area_acres = all_props.get("ll_gisacre") or all_props.get("gisacre")
        if area_acres:
            try:
                area_acres = float(area_acres)
            except:
                area_acres = None
        
        # Get address - try multiple field names
        address = (
            all_props.get("address") or 
            all_props.get("situs") or
            properties.get("headline")  # V2 API uses 'headline' for address
        )
        
        # Get owner
        owner = (
            all_props.get("owner") or 
            all_props.get("ownername")
        )
        
        return PropertyParcel(
            parcel_id=str(parcel_id),
            apn=all_props.get("parcelnumb") or all_props.get("apn"),
            address=address,
            owner=owner,
            polygon=geom,
            centroid=geom.centroid,
            area_m2=area_m2,
            area_acres=area_acres,
            land_use=all_props.get("usedesc") or all_props.get("usecode") or all_props.get("landuse"),
            zoning=all_props.get("zoning") or all_props.get("zoning_code"),
            year_built=all_props.get("yearbuilt"),
            raw_data=feature,
        )
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Singleton instance
regrid_service = RegridService()


