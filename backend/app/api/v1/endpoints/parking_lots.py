from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import and_, func, text
from typing import List, Optional
from uuid import UUID
from geoalchemy2.shape import to_shape
from geoalchemy2.functions import ST_X, ST_Y, ST_MakeEnvelope, ST_Intersects

from app.db.base import get_db
from app.models.parking_lot import ParkingLot
from app.models.association import ParkingLotBusinessAssociation
from app.models.business import Business
from app.models.user import User
from app.models.property_analysis import PropertyAnalysis
from app.models.asphalt_area import AsphaltArea
from app.schemas.parking_lot import (
    ParkingLotResponse,
    ParkingLotDetailResponse,
    ParkingLotMapResponse,
    ParkingLotWithBusiness,
    ParkingLotListResponse,
    Coordinates,
    BusinessSummary,
)
from app.core.dependencies import get_current_user

router = APIRouter()


def parking_lot_to_response(lot: ParkingLot, include_business: bool = False) -> dict:
    """Convert ParkingLot model to response dict."""
    centroid = to_shape(lot.centroid)
    
    response = {
        "id": lot.id,
        "centroid": Coordinates(lat=centroid.y, lng=centroid.x),
        "area_m2": float(lot.area_m2) if lot.area_m2 else None,
        "area_sqft": float(lot.area_sqft) if lot.area_sqft else None,
        "operator_name": lot.operator_name,
        "address": lot.address,
        "surface_type": lot.surface_type,
        "condition_score": float(lot.condition_score) if lot.condition_score else None,
        "crack_density": float(lot.crack_density) if lot.crack_density else None,
        "pothole_score": float(lot.pothole_score) if lot.pothole_score else None,
        "line_fading_score": float(lot.line_fading_score) if lot.line_fading_score else None,
        "satellite_image_url": lot.satellite_image_url,
        "is_evaluated": lot.is_evaluated,
        "data_sources": lot.data_sources or [],
        "created_at": lot.created_at,
        "evaluated_at": lot.evaluated_at,
        # Business-first discovery fields
        "business_type_tier": lot.business_type_tier,
        "discovery_mode": lot.discovery_mode,
    }
    
    # Add geometry if available
    if lot.geometry:
        geom = to_shape(lot.geometry)
        response["geometry"] = {
            "type": "Polygon",
            "coordinates": [list(geom.exterior.coords)]
        }
    
    return response


def get_primary_business_from_associations(associations) -> tuple:
    """
    Extract primary business from eagerly-loaded associations.
    Returns (business, association) or (None, None).
    """
    for assoc in associations:
        if assoc.is_primary:
            return assoc.business, assoc
    return None, None


@router.get("", response_model=ParkingLotListResponse)
def list_parking_lots(
    min_area_m2: Optional[float] = Query(None, description="Minimum lot area in m²"),
    max_condition_score: Optional[float] = Query(None, description="Maximum condition score (lower = worse)"),
    min_match_score: Optional[float] = Query(None, description="Minimum business match score"),
    has_business: Optional[bool] = Query(None, description="Filter by business association"),
    is_evaluated: Optional[bool] = Query(None, description="Filter by evaluation status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List parking lots with filters.
    
    Returns parking lots owned by the current user with optional filtering.
    Uses eager loading to avoid N+1 queries.
    """
    # Base query with eager loading of associations and businesses
    query = (
        db.query(ParkingLot)
        .filter(ParkingLot.user_id == current_user.id)
        .options(
            selectinload(ParkingLot.business_associations)
            .joinedload(ParkingLotBusinessAssociation.business)
        )
    )
    
    # Apply filters
    if min_area_m2 is not None:
        query = query.filter(ParkingLot.area_m2 >= min_area_m2)
    
    if max_condition_score is not None:
        query = query.filter(ParkingLot.condition_score <= max_condition_score)
    
    if is_evaluated is not None:
        query = query.filter(ParkingLot.is_evaluated == is_evaluated)
    
    if has_business is not None:
        if has_business:
            # Use exists subquery for filtering
            subquery = (
                db.query(ParkingLotBusinessAssociation.parking_lot_id)
                .filter(ParkingLotBusinessAssociation.is_primary == True)
                .subquery()
            )
            query = query.filter(ParkingLot.id.in_(db.query(subquery)))
        else:
            subquery = (
                db.query(ParkingLotBusinessAssociation.parking_lot_id)
                .filter(ParkingLotBusinessAssociation.is_primary == True)
                .subquery()
            )
            query = query.filter(~ParkingLot.id.in_(db.query(subquery)))
    
    # Get total count (before pagination)
    total = query.count()
    
    # Apply pagination and ordering
    lots = (
        query
        .order_by(ParkingLot.condition_score.asc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    # Build response - no additional queries needed due to eager loading
    results = []
    for lot in lots:
        lot_dict = parking_lot_to_response(lot)
        
        # Get primary business from already-loaded associations
        business, assoc = get_primary_business_from_associations(lot.business_associations)
        
        if business and assoc:
            lot_dict["business"] = BusinessSummary(
                id=business.id,
                name=business.name,
                phone=business.phone,
                email=business.email,
                website=business.website,
                address=business.address,
                category=business.category,
            )
            lot_dict["match_score"] = float(assoc.match_score)
            lot_dict["distance_meters"] = float(assoc.distance_meters)
        
        results.append(ParkingLotWithBusiness(**lot_dict))
    
    return ParkingLotListResponse(
        total=total,
        limit=limit,
        offset=offset,
        results=results,
    )


@router.get("/map")
def get_parking_lots_for_map(
    min_lat: Optional[float] = Query(None),
    max_lat: Optional[float] = Query(None),
    min_lng: Optional[float] = Query(None),
    max_lng: Optional[float] = Query(None),
    max_condition_score: Optional[float] = Query(None),
    has_business: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get parking lots optimized for map display.
    
    Uses PostGIS spatial filtering and eager loading for optimal performance.
    Returns GeoJSON FeatureCollection.
    """
    # Base query with eager loading - single query for all data
    query = (
        db.query(ParkingLot)
        .filter(ParkingLot.user_id == current_user.id)
        .options(
            selectinload(ParkingLot.business_associations)
            .joinedload(ParkingLotBusinessAssociation.business)
        )
    )
    
    # Apply PostGIS bounding box filter if all bounds provided
    if all(v is not None for v in [min_lat, max_lat, min_lng, max_lng]):
        # Use PostGIS ST_MakeEnvelope for efficient spatial filtering
        # ST_MakeEnvelope(xmin, ymin, xmax, ymax, srid)
        envelope = func.ST_MakeEnvelope(min_lng, min_lat, max_lng, max_lat, 4326)
        query = query.filter(
            func.ST_Intersects(
                func.ST_SetSRID(ParkingLot.centroid, 4326),
                envelope
            )
        )
    
    if max_condition_score is not None:
        query = query.filter(ParkingLot.condition_score <= max_condition_score)
    
    if has_business is not None:
        if has_business:
            subquery = (
                db.query(ParkingLotBusinessAssociation.parking_lot_id)
                .filter(ParkingLotBusinessAssociation.is_primary == True)
                .subquery()
            )
            query = query.filter(ParkingLot.id.in_(db.query(subquery)))
        else:
            subquery = (
                db.query(ParkingLotBusinessAssociation.parking_lot_id)
                .filter(ParkingLotBusinessAssociation.is_primary == True)
                .subquery()
            )
            query = query.filter(~ParkingLot.id.in_(db.query(subquery)))
    
    # Limit results for map display
    lots = query.limit(500).all()
    
    # Build features - no additional queries due to eager loading
    features = []
    for lot in lots:
        centroid = to_shape(lot.centroid)
        
        # Get business from already-loaded associations
        business, _ = get_primary_business_from_associations(lot.business_associations)
        business_name = business.name if business else None
        has_biz = business is not None
        
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [centroid.x, centroid.y]
            },
            "properties": {
                "id": str(lot.id),
                "area_m2": float(lot.area_m2) if lot.area_m2 else None,
                "condition_score": float(lot.condition_score) if lot.condition_score else None,
                "business_name": business_name,
                "address": lot.address,
                "satellite_image_url": lot.satellite_image_url,
                "operator_name": lot.operator_name,
                "has_business": has_biz,
                "is_evaluated": lot.is_evaluated,
                "business_type_tier": lot.business_type_tier,
                "discovery_mode": lot.discovery_mode,
            }
        })
    
    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get("/{parking_lot_id}", response_model=ParkingLotDetailResponse)
def get_parking_lot(
    parking_lot_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get single parking lot with full details."""
    lot = (
        db.query(ParkingLot)
        .filter(
            ParkingLot.id == parking_lot_id,
            ParkingLot.user_id == current_user.id
        )
        .options(
            selectinload(ParkingLot.business_associations)
            .joinedload(ParkingLotBusinessAssociation.business)
        )
        .first()
    )
    
    if not lot:
        raise HTTPException(status_code=404, detail="Parking lot not found")
    
    response = parking_lot_to_response(lot)
    response["degradation_areas"] = lot.degradation_areas
    response["raw_metadata"] = lot.raw_metadata
    response["evaluation_error"] = lot.evaluation_error
    response["updated_at"] = lot.updated_at
    
    # Get primary business from already-loaded associations
    business, assoc = get_primary_business_from_associations(lot.business_associations)
    
    if business and assoc:
        response["business"] = BusinessSummary(
            id=business.id,
            name=business.name,
            phone=business.phone,
            email=business.email,
            website=business.website,
            address=business.address,
            category=business.category,
        )
        response["match_score"] = float(assoc.match_score)
        response["distance_meters"] = float(assoc.distance_meters)
    
    # Get property analysis if exists
    property_analysis = db.query(PropertyAnalysis).filter(
        PropertyAnalysis.parking_lot_id == parking_lot_id
    ).first()
    
    if property_analysis:
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"📸 PropertyAnalysis found for {parking_lot_id}")
        logger.info(f"   wide_image_base64: {len(property_analysis.wide_image_base64) if property_analysis.wide_image_base64 else 0} chars")
        logger.info(f"   segmentation_image_base64: {len(property_analysis.segmentation_image_base64) if property_analysis.segmentation_image_base64 else 0} chars")
        logger.info(f"   property_boundary_source: {property_analysis.property_boundary_source}")
        
        # Build property boundary info if available
        property_boundary_info = None
        if property_analysis.property_boundary_source:
            property_boundary_info = {
                "source": property_analysis.property_boundary_source,
                "parcel_id": property_analysis.property_parcel_id,
                "owner": property_analysis.property_owner,
                "apn": property_analysis.property_apn,
                "land_use": property_analysis.property_land_use,
                "zoning": property_analysis.property_zoning,
            }
            # Add polygon as GeoJSON if available
            if property_analysis.property_boundary_polygon:
                boundary_shape = to_shape(property_analysis.property_boundary_polygon)
                if hasattr(boundary_shape, 'exterior'):
                    property_boundary_info["polygon"] = {
                        "type": "Polygon",
                        "coordinates": [list(boundary_shape.exterior.coords)]
                    }
        
        response["property_analysis"] = {
            "id": str(property_analysis.id),
            "status": property_analysis.status,
            "total_asphalt_area_m2": property_analysis.total_asphalt_area_m2,
            "weighted_condition_score": property_analysis.weighted_condition_score,
            "total_crack_count": int(property_analysis.total_crack_count) if property_analysis.total_crack_count else 0,
            "total_pothole_count": int(property_analysis.total_pothole_count) if property_analysis.total_pothole_count else 0,
            "images": {
                "wide_satellite": property_analysis.wide_image_base64,
                "segmentation": property_analysis.segmentation_image_base64,
                "property_boundary": property_analysis.property_boundary_image_base64,
                "condition_analysis": property_analysis.condition_analysis_image_base64,
            },
            "analyzed_at": property_analysis.analyzed_at.isoformat() if property_analysis.analyzed_at else None,
            "property_boundary": property_boundary_info,
        }
    else:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"📸 No PropertyAnalysis found for {parking_lot_id}")
    
    return ParkingLotDetailResponse(**response)


@router.get("/{parking_lot_id}/businesses")
def get_parking_lot_businesses(
    parking_lot_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all businesses associated with a parking lot."""
    lot = db.query(ParkingLot).filter(
        ParkingLot.id == parking_lot_id,
        ParkingLot.user_id == current_user.id
    ).first()
    
    if not lot:
        raise HTTPException(status_code=404, detail="Parking lot not found")
    
    # Use eager loading for associations and businesses
    associations = (
        db.query(ParkingLotBusinessAssociation)
        .filter(ParkingLotBusinessAssociation.parking_lot_id == parking_lot_id)
        .options(joinedload(ParkingLotBusinessAssociation.business))
        .order_by(ParkingLotBusinessAssociation.match_score.desc())
        .all()
    )
    
    results = []
    for assoc in associations:
        business = assoc.business
        if business:
            biz_location = to_shape(business.geometry)
            results.append({
                "id": business.id,
                "name": business.name,
                "phone": business.phone,
                "email": business.email,
                "website": business.website,
                "address": business.address,
                "category": business.category,
                "match_score": float(assoc.match_score),
                "distance_meters": float(assoc.distance_meters),
                "is_primary": assoc.is_primary,
                "location": {"lat": biz_location.y, "lng": biz_location.x},
            })
    
    return results
