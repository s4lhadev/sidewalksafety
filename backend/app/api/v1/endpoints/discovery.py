"""
Discovery API Endpoints

Two discovery modes:
1. Places Discovery: Google Places -> Regrid Tiles (for business-focused searches)
2. Area Discovery: Regrid Tiles directly (for size-based parcel searches)

Tiles are free (200k/month), only record queries count against Regrid quota (2k/month).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

from app.core.arcgis_parcel_service import get_parcel_discovery_service, DiscoveryParcel
from app.core.google_places_service import get_google_places_service, PlaceResult

logger = logging.getLogger(__name__)

router = APIRouter()


class DiscoveryQueryRequest(BaseModel):
    """Request to query parcels in an area"""
    geometry: Dict[str, Any]  # GeoJSON Polygon or MultiPolygon
    min_acres: Optional[float] = None
    max_acres: Optional[float] = None
    limit: int = 500


class ParcelResponse(BaseModel):
    """Individual parcel in response"""
    id: str
    address: str
    acreage: float
    apn: str
    regrid_id: str
    geometry: Dict[str, Any]
    centroid: Dict[str, float]
    owner: Optional[str] = None


class DiscoveryQueryResponse(BaseModel):
    """Response from parcel discovery query"""
    success: bool
    parcels: List[ParcelResponse]
    total_count: int
    error: Optional[str] = None


@router.post("/parcels", response_model=DiscoveryQueryResponse)
async def query_parcels(request: DiscoveryQueryRequest):
    """
    Query parcels within a given area with optional size filter.
    
    This uses ArcGIS Feature Service which doesn't count against Regrid API limits.
    
    Args:
        geometry: GeoJSON Polygon or MultiPolygon defining the search area
        min_acres: Minimum parcel size in acres (optional)
        max_acres: Maximum parcel size in acres (optional)
        limit: Maximum number of parcels to return (default 500)
    """
    try:
        print(f"🔍 DISCOVERY ENDPOINT: Received query - min_acres={request.min_acres}, max_acres={request.max_acres}, limit={request.limit}")
        print(f"🔍 DISCOVERY ENDPOINT: Geometry type: {request.geometry.get('type')}")
        logger.info(f"🔍 Discovery query: min_acres={request.min_acres}, max_acres={request.max_acres}, limit={request.limit}")
        
        # Validate geometry
        geom_type = request.geometry.get("type")
        if geom_type not in ["Polygon", "MultiPolygon"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid geometry type: {geom_type}. Must be Polygon or MultiPolygon."
            )
        
        # Query parcels
        service = get_parcel_discovery_service()
        parcels = await service.query_parcels_in_area(
            geometry=request.geometry,
            min_acres=request.min_acres,
            max_acres=request.max_acres,
            limit=request.limit,
        )
        
        print(f"✅ DISCOVERY ENDPOINT: Service returned {len(parcels)} parcels")
        logger.info(f"✅ Found {len(parcels)} parcels")
        
        # Convert to response format
        parcel_responses = [
            ParcelResponse(
                id=p.id,
                address=p.address,
                acreage=p.acreage,
                apn=p.apn,
                regrid_id=p.regrid_id,
                geometry=p.geometry,
                centroid=p.centroid,
                owner=getattr(p, 'owner', None),
            )
            for p in parcels
        ]
        
        return DiscoveryQueryResponse(
            success=True,
            parcels=parcel_responses,
            total_count=len(parcel_responses),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Discovery query error: {e}", exc_info=True)
        return DiscoveryQueryResponse(
            success=False,
            parcels=[],
            total_count=0,
            error=str(e),
        )


class PlacesDiscoveryRequest(BaseModel):
    """Request to discover businesses and their parcels"""
    geometry: Dict[str, Any]  # GeoJSON Polygon defining the search area
    property_type: str  # Natural language description (e.g., "big restaurants", "auto repair shops")
    included_type: Optional[str] = None  # Optional Google Places type filter (e.g., "restaurant")
    max_results: int = 60  # Max places to return (capped at 60 by Google)


class PlaceWithParcel(BaseModel):
    """A business place with its associated parcel"""
    # Place info (from Google Places)
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
    
    # Parcel info (from Regrid Tiles)
    parcel_id: Optional[str] = None
    parcel_address: Optional[str] = None
    parcel_acreage: Optional[float] = None
    parcel_apn: Optional[str] = None
    parcel_owner: Optional[str] = None
    parcel_geometry: Optional[Dict[str, Any]] = None
    parcel_centroid: Optional[Dict[str, float]] = None


class PlacesDiscoveryResponse(BaseModel):
    """Response from places-based discovery"""
    success: bool
    places: List[PlaceWithParcel]
    total_places: int
    places_with_parcels: int
    error: Optional[str] = None


@router.post("/places", response_model=PlacesDiscoveryResponse)
async def discover_places(request: PlacesDiscoveryRequest):
    """
    Discover businesses by type and get their parcel geometries.
    
    Flow:
    1. Query Google Places for businesses matching the property type
    2. For each place, find the parcel containing that location
    3. Return places with their parcel geometries for map display
    
    Args:
        geometry: GeoJSON Polygon defining the search area (ZIP boundary, drawn polygon, etc.)
        property_type: Natural language description of what to search for
        included_type: Optional Google Places type filter
        max_results: Maximum results (capped at 60)
    """
    try:
        print(f"🔍 PLACES DISCOVERY: property_type='{request.property_type}', max_results={request.max_results}")
        logger.info(f"Places discovery: '{request.property_type}' in {request.geometry.get('type')}")
        
        # Validate geometry
        geom_type = request.geometry.get("type")
        if geom_type not in ["Polygon", "MultiPolygon"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid geometry type: {geom_type}. Must be Polygon or MultiPolygon."
            )
        
        # Step 1: Query Google Places
        places_service = get_google_places_service()
        places = await places_service.search_in_polygon(
            query=request.property_type,
            polygon=request.geometry,
            max_results=min(request.max_results, 60),  # Cap at 60
            included_type=request.included_type,
        )
        
        print(f"📍 PLACES DISCOVERY: Google returned {len(places)} places")
        logger.info(f"Google Places returned {len(places)} results")
        
        if not places:
            return PlacesDiscoveryResponse(
                success=True,
                places=[],
                total_places=0,
                places_with_parcels=0,
            )
        
        # Step 2: Get parcels for each place
        parcel_service = get_parcel_discovery_service()
        points = [{"lat": p.lat, "lng": p.lng} for p in places]
        parcels = await parcel_service.get_parcels_at_points(points)
        
        # Step 3: Combine places with parcels
        results: List[PlaceWithParcel] = []
        places_with_parcels = 0
        
        for place, parcel in zip(places, parcels):
            result = PlaceWithParcel(
                # Place info
                place_id=place.place_id,
                name=place.name,
                address=place.address,
                lat=place.lat,
                lng=place.lng,
                types=place.types,
                primary_type=place.primary_type,
                rating=place.rating,
                user_ratings_count=place.user_ratings_count,
                website=place.website,
                phone=place.phone,
            )
            
            # Add parcel info if found
            if parcel:
                places_with_parcels += 1
                result.parcel_id = parcel.id
                result.parcel_address = parcel.address
                result.parcel_acreage = parcel.acreage
                result.parcel_apn = parcel.apn
                result.parcel_owner = parcel.owner
                result.parcel_geometry = parcel.geometry
                result.parcel_centroid = parcel.centroid
            
            results.append(result)
        
        print(f"✅ PLACES DISCOVERY: {len(results)} places, {places_with_parcels} with parcels")
        logger.info(f"Discovery complete: {len(results)} places, {places_with_parcels} with parcels")
        
        return PlacesDiscoveryResponse(
            success=True,
            places=results,
            total_places=len(results),
            places_with_parcels=places_with_parcels,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Places discovery error: {e}", exc_info=True)
        return PlacesDiscoveryResponse(
            success=False,
            places=[],
            total_places=0,
            places_with_parcels=0,
            error=str(e),
        )


class ProcessParcelsRequest(BaseModel):
    """Request to process selected parcels"""
    parcels: List[ParcelResponse]


class ProcessParcelsResponse(BaseModel):
    """Response from parcel processing"""
    success: bool
    message: str
    job_id: Optional[str] = None


@router.post("/process", response_model=ProcessParcelsResponse)
async def process_parcels(request: ProcessParcelsRequest):
    """
    Process selected parcels for lead enrichment.
    
    This endpoint queues the parcels for LLM enrichment to find contact information.
    
    Args:
        parcels: List of parcels to process
    """
    try:
        logger.info(f"📋 Processing {len(request.parcels)} parcels for enrichment")
        
        if not request.parcels:
            raise HTTPException(status_code=400, detail="No parcels provided")
        
        # TODO: Queue parcels for LLM enrichment
        # For now, return a placeholder response
        
        return ProcessParcelsResponse(
            success=True,
            message=f"Queued {len(request.parcels)} parcels for enrichment",
            job_id="pending_implementation",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Process parcels error: {e}", exc_info=True)
        return ProcessParcelsResponse(
            success=False,
            message=str(e),
        )


# ============ Viewport Parcels (for map tile layer) ============

class ViewportRequest(BaseModel):
    """Request to get parcels in a viewport bounding box"""
    min_lng: float
    min_lat: float
    max_lng: float
    max_lat: float
    limit: int = 2000


class ViewportParcel(BaseModel):
    """Simplified parcel for viewport display (just geometry)"""
    id: str
    geometry: Dict[str, Any]


class ViewportResponse(BaseModel):
    """Response with parcels for viewport"""
    success: bool
    parcels: List[ViewportParcel]
    count: int
    error: Optional[str] = None


@router.post("/viewport", response_model=ViewportResponse)
async def get_viewport_parcels(request: ViewportRequest):
    """
    Get parcel boundaries for a map viewport.
    
    Used by the parcel tile layer to display parcel boundaries as the user navigates.
    Returns simplified data (just geometry, no attributes) for performance.
    
    Args:
        min_lng, min_lat, max_lng, max_lat: Bounding box coordinates
        limit: Max parcels to return (default 2000)
    """
    try:
        # Create a polygon from the bounding box
        bbox_polygon = {
            "type": "Polygon",
            "coordinates": [[
                [request.min_lng, request.min_lat],
                [request.max_lng, request.min_lat],
                [request.max_lng, request.max_lat],
                [request.min_lng, request.max_lat],
                [request.min_lng, request.min_lat],
            ]]
        }
        
        # Use existing parcel discovery service
        service = get_parcel_discovery_service()
        parcels = await service.query_parcels_in_area(
            geometry=bbox_polygon,
            min_acres=None,
            max_acres=None,
            limit=request.limit,
        )
        
        # Convert to simplified response
        result_parcels = [
            ViewportParcel(
                id=p.id,
                geometry=p.geometry,
            )
            for p in parcels
        ]
        
        return ViewportResponse(
            success=True,
            parcels=result_parcels,
            count=len(result_parcels),
        )
        
    except Exception as e:
        logger.error(f"Viewport parcels error: {e}", exc_info=True)
        return ViewportResponse(
            success=False,
            parcels=[],
            count=0,
            error=str(e),
        )
