"""
Discovery API Endpoints

Two discovery modes:
1. Places Discovery: Google Places -> Regrid Tiles (for business-focused searches)
2. Area Discovery: Regrid Tiles directly (for size-based parcel searches)

Tiles are free (200k/month), only record queries count against Regrid quota (2k/month).
"""

import asyncio
import json
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, AsyncGenerator
from sqlalchemy.orm import Session
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
import logging

from app.core.arcgis_parcel_service import get_parcel_discovery_service, DiscoveryParcel
from app.core.google_places_service import get_google_places_service, PlaceResult
from app.core.llm_enrichment_service import llm_enrichment_service
from app.db.base import SessionLocal
from app.models.property import Property
from app.core.dependencies import get_current_user, get_db
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


def sse_message(data: dict) -> str:
    """Format data as SSE message"""
    return f"data: {json.dumps(data)}\n\n"


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


class ProcessPlacesRequest(BaseModel):
    """Request to process selected places with parcels"""
    places: List[PlaceWithParcel]


class EnrichedContact(BaseModel):
    """Enriched contact information"""
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    website: Optional[str] = None
    confidence: float = 0.0


class ProcessedPlace(BaseModel):
    """A processed place with enrichment results"""
    place_id: str
    name: str
    address: str
    property_id: Optional[str] = None
    contact: Optional[EnrichedContact] = None
    enrichment_status: str = "pending"  # pending, success, not_found, error
    enrichment_steps: Optional[List[str]] = None
    error: Optional[str] = None


class ProcessPlacesResponse(BaseModel):
    """Response from places processing"""
    success: bool
    message: str
    processed: List[ProcessedPlace]
    total: int
    with_contacts: int
    

class ProcessParcelsRequest(BaseModel):
    """Request to process selected parcels (legacy)"""
    parcels: List[ParcelResponse]


class ProcessParcelsResponse(BaseModel):
    """Response from parcel processing (legacy)"""
    success: bool
    message: str
    job_id: Optional[str] = None


@router.post("/process", response_model=ProcessParcelsResponse)
async def process_parcels(request: ProcessParcelsRequest):
    """
    Process selected parcels for lead enrichment (legacy endpoint).
    Use /process/places for the new discovery flow.
    """
    logger.info(f"📋 Legacy process endpoint called with {len(request.parcels)} parcels")
    return ProcessParcelsResponse(
        success=True,
        message=f"Use /discover/process/places for processing. Received {len(request.parcels)} parcels.",
        job_id="use_new_endpoint",
    )


@router.post("/process/places/stream")
async def process_places_stream(
    request: ProcessPlacesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Process selected places for LLM enrichment with SSE streaming.
    
    For each place:
    1. Create or find property record
    2. Run LLM enrichment to find decision-maker contact
    3. Stream progress updates
    
    Returns SSE stream with progress and results.
    """
    if not request.places:
        raise HTTPException(status_code=400, detail="No places provided")
    
    async def generate() -> AsyncGenerator[str, None]:
        processed: List[ProcessedPlace] = []
        with_contacts = 0
        
        # Start message
        yield sse_message({
            "type": "start",
            "message": f"Processing {len(request.places)} places",
            "total": len(request.places),
        })
        
        for idx, place in enumerate(request.places):
            place_name = place.name[:30] + "..." if len(place.name) > 30 else place.name
            
            # Progress update
            yield sse_message({
                "type": "processing",
                "message": f"Processing: {place_name}",
                "current": idx + 1,
                "total": len(request.places),
                "place_id": place.place_id,
            })
            await asyncio.sleep(0.05)
            
            try:
                # Step 1: Create or find property
                property_id = None
                prop = None
                
                # Check if property already exists by address
                existing = db.query(Property).filter(
                    Property.user_id == current_user.id,
                    Property.address == place.address,
                ).first()
                
                if existing:
                    prop = existing
                    property_id = str(existing.id)
                    yield sse_message({
                        "type": "property_found",
                        "message": f"Found existing property",
                        "property_id": property_id,
                        "place_id": place.place_id,
                    })
                else:
                    # Create new property from place data
                    new_prop = Property(
                        id=uuid.uuid4(),
                        user_id=current_user.id,
                        centroid=from_shape(Point(place.lng, place.lat), srid=4326),
                        address=place.address,
                        regrid_id=place.parcel_id,
                        regrid_apn=place.parcel_apn,
                        regrid_owner=place.parcel_owner,
                        regrid_area_acres=place.parcel_acreage,
                        discovery_source="places_discovery",
                        status="discovered",
                    )
                    
                    # Add polygon if available
                    if place.parcel_geometry:
                        from shapely.geometry import shape
                        try:
                            parcel_shape = shape(place.parcel_geometry)
                            new_prop.regrid_polygon = from_shape(parcel_shape, srid=4326)
                        except Exception as e:
                            logger.warning(f"Could not parse parcel geometry: {e}")
                    
                    db.add(new_prop)
                    db.commit()
                    db.refresh(new_prop)
                    prop = new_prop
                    property_id = str(new_prop.id)
                    
                    yield sse_message({
                        "type": "property_created",
                        "message": f"Created property",
                        "property_id": property_id,
                        "place_id": place.place_id,
                    })
                
                await asyncio.sleep(0.05)
                
                # Step 2: LLM Enrichment
                yield sse_message({
                    "type": "enriching",
                    "message": f"Finding contact for: {place_name}",
                    "place_id": place.place_id,
                })
                
                # Determine property type from Google Places types
                property_type = "commercial"
                if place.types:
                    if any(t in place.types for t in ["restaurant", "food", "cafe", "bakery"]):
                        property_type = "restaurant"
                    elif any(t in place.types for t in ["store", "shopping", "retail"]):
                        property_type = "retail"
                    elif any(t in place.types for t in ["lodging", "hotel", "motel"]):
                        property_type = "lodging"
                    elif any(t in place.types for t in ["car_repair", "car_dealer", "gas_station"]):
                        property_type = "automotive"
                    elif any(t in place.types for t in ["gym", "fitness"]):
                        property_type = "fitness"
                    elif any(t in place.types for t in ["medical", "doctor", "dentist", "hospital"]):
                        property_type = "medical"
                
                enrichment_result = await llm_enrichment_service.enrich(
                    address=place.address,
                    property_type=property_type,
                    owner_name=place.parcel_owner or place.name,
                    lbcs_code=None,
                )
                
                # Process enrichment result
                contact = None
                enrichment_status = "not_found"
                enrichment_steps = []
                
                if enrichment_result.detailed_steps:
                    enrichment_steps = [s.description for s in enrichment_result.detailed_steps]
                
                if enrichment_result.success and enrichment_result.contact:
                    enrichment_status = "success"
                    with_contacts += 1
                    contact = EnrichedContact(
                        name=enrichment_result.contact.name,
                        first_name=enrichment_result.contact.first_name,
                        last_name=enrichment_result.contact.last_name,
                        email=enrichment_result.contact.email,
                        phone=enrichment_result.contact.phone,
                        title=enrichment_result.contact.title,
                        company=enrichment_result.management_company,
                        website=enrichment_result.management_website,
                        confidence=enrichment_result.confidence,
                    )
                    
                    # Update property with contact info
                    if prop:
                        prop.contact_name = enrichment_result.contact.name
                        prop.contact_first_name = enrichment_result.contact.first_name
                        prop.contact_last_name = enrichment_result.contact.last_name
                        prop.contact_email = enrichment_result.contact.email
                        prop.contact_phone = enrichment_result.contact.phone
                        prop.contact_title = enrichment_result.contact.title
                        prop.contact_company = enrichment_result.management_company
                        prop.contact_company_website = enrichment_result.management_website
                        prop.enrichment_status = "success"
                        prop.enrichment_source = "llm_enrichment"
                        prop.enrichment_confidence = enrichment_result.confidence
                        prop.enriched_at = datetime.utcnow()
                        prop.enrichment_steps = json.dumps([
                            step.to_dict() for step in enrichment_result.detailed_steps
                        ]) if enrichment_result.detailed_steps else None
                        db.commit()
                    
                    yield sse_message({
                        "type": "contact_found",
                        "message": f"Contact found: {contact.phone or contact.email or contact.company}",
                        "place_id": place.place_id,
                        "contact": contact.model_dump(),
                    })
                else:
                    if prop:
                        prop.enrichment_status = "not_found"
                        prop.enrichment_steps = json.dumps([
                            step.to_dict() for step in enrichment_result.detailed_steps
                        ]) if enrichment_result.detailed_steps else None
                        db.commit()
                    
                    yield sse_message({
                        "type": "no_contact",
                        "message": f"No contact found for: {place_name}",
                        "place_id": place.place_id,
                    })
                
                # Add to processed list
                processed.append(ProcessedPlace(
                    place_id=place.place_id,
                    name=place.name,
                    address=place.address,
                    property_id=property_id,
                    contact=contact,
                    enrichment_status=enrichment_status,
                    enrichment_steps=enrichment_steps,
                ))
                
            except Exception as e:
                logger.error(f"Error processing place {place.place_id}: {e}", exc_info=True)
                processed.append(ProcessedPlace(
                    place_id=place.place_id,
                    name=place.name,
                    address=place.address,
                    enrichment_status="error",
                    error=str(e)[:100],
                ))
                yield sse_message({
                    "type": "error",
                    "message": f"Error processing: {place_name}",
                    "place_id": place.place_id,
                    "error": str(e)[:100],
                })
            
            await asyncio.sleep(0.1)  # Small delay between places
        
        # Complete message
        yield sse_message({
            "type": "complete",
            "message": f"Processed {len(processed)} places, {with_contacts} with contacts",
            "total": len(processed),
            "with_contacts": with_contacts,
            "results": [p.model_dump() for p in processed],
        })
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/process/places", response_model=ProcessPlacesResponse)
async def process_places(
    request: ProcessPlacesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Process selected places for LLM enrichment (non-streaming version).
    
    For faster processing with progress updates, use /process/places/stream
    """
    if not request.places:
        raise HTTPException(status_code=400, detail="No places provided")
    
    processed: List[ProcessedPlace] = []
    with_contacts = 0
    
    for place in request.places:
        try:
            # Check if property already exists
            existing = db.query(Property).filter(
                Property.user_id == current_user.id,
                Property.address == place.address,
            ).first()
            
            prop = existing
            if not existing:
                # Create new property
                new_prop = Property(
                    id=uuid.uuid4(),
                    user_id=current_user.id,
                    centroid=from_shape(Point(place.lng, place.lat), srid=4326),
                    address=place.address,
                    regrid_id=place.parcel_id,
                    regrid_apn=place.parcel_apn,
                    regrid_owner=place.parcel_owner,
                    regrid_area_acres=place.parcel_acreage,
                    discovery_source="places_discovery",
                    status="discovered",
                )
                db.add(new_prop)
                db.commit()
                db.refresh(new_prop)
                prop = new_prop
            
            # Run enrichment
            property_type = "commercial"
            enrichment_result = await llm_enrichment_service.enrich(
                address=place.address,
                property_type=property_type,
                owner_name=place.parcel_owner or place.name,
            )
            
            contact = None
            enrichment_status = "not_found"
            
            if enrichment_result.success and enrichment_result.contact:
                enrichment_status = "success"
                with_contacts += 1
                contact = EnrichedContact(
                    name=enrichment_result.contact.name,
                    email=enrichment_result.contact.email,
                    phone=enrichment_result.contact.phone,
                    company=enrichment_result.management_company,
                    confidence=enrichment_result.confidence,
                )
                
                # Update property
                prop.contact_name = enrichment_result.contact.name
                prop.contact_email = enrichment_result.contact.email
                prop.contact_phone = enrichment_result.contact.phone
                prop.contact_company = enrichment_result.management_company
                prop.enrichment_status = "success"
                prop.enriched_at = datetime.utcnow()
                db.commit()
            
            processed.append(ProcessedPlace(
                place_id=place.place_id,
                name=place.name,
                address=place.address,
                property_id=str(prop.id),
                contact=contact,
                enrichment_status=enrichment_status,
            ))
            
        except Exception as e:
            logger.error(f"Error processing place: {e}")
            processed.append(ProcessedPlace(
                place_id=place.place_id,
                name=place.name,
                address=place.address,
                enrichment_status="error",
                error=str(e)[:100],
            ))
    
    return ProcessPlacesResponse(
        success=True,
        message=f"Processed {len(processed)} places",
        processed=processed,
        total=len(processed),
        with_contacts=with_contacts,
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
