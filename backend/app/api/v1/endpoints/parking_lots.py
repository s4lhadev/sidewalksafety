from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from uuid import UUID
from geoalchemy2.shape import to_shape

from app.db.base import get_db
from app.models.parking_lot import ParkingLot
from app.models.association import ParkingLotBusinessAssociation
from app.models.business import Business
from app.models.user import User
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
    """
    query = db.query(ParkingLot).filter(ParkingLot.user_id == current_user.id)
    
    # Apply filters
    if min_area_m2 is not None:
        query = query.filter(ParkingLot.area_m2 >= min_area_m2)
    
    if max_condition_score is not None:
        query = query.filter(ParkingLot.condition_score <= max_condition_score)
    
    if is_evaluated is not None:
        query = query.filter(ParkingLot.is_evaluated == is_evaluated)
    
    if has_business is not None:
        if has_business:
            query = query.join(ParkingLotBusinessAssociation).filter(
                ParkingLotBusinessAssociation.is_primary == True
            )
        else:
            query = query.outerjoin(ParkingLotBusinessAssociation).filter(
                ParkingLotBusinessAssociation.id == None
            )
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    lots = query.order_by(ParkingLot.condition_score.asc().nullslast()).offset(offset).limit(limit).all()
    
    # Build response with business info
    results = []
    for lot in lots:
        lot_dict = parking_lot_to_response(lot)
        
        # Get primary business association
        primary_assoc = db.query(ParkingLotBusinessAssociation).filter(
            ParkingLotBusinessAssociation.parking_lot_id == lot.id,
            ParkingLotBusinessAssociation.is_primary == True
        ).first()
        
        if primary_assoc:
            business = db.query(Business).filter(Business.id == primary_assoc.business_id).first()
            if business:
                lot_dict["business"] = BusinessSummary(
                    id=business.id,
                    name=business.name,
                    phone=business.phone,
                    email=business.email,
                    website=business.website,
                    address=business.address,
                    category=business.category,
                )
                lot_dict["match_score"] = float(primary_assoc.match_score)
                lot_dict["distance_meters"] = float(primary_assoc.distance_meters)
        
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
    
    Returns GeoJSON FeatureCollection.
    """
    query = db.query(ParkingLot).filter(ParkingLot.user_id == current_user.id)
    
    # Apply bounding box filter if provided
    # Note: For proper spatial filtering, use PostGIS ST_Within
    # This is a simplified version
    
    if max_condition_score is not None:
        query = query.filter(ParkingLot.condition_score <= max_condition_score)
    
    lots = query.limit(500).all()
    
    features = []
    for lot in lots:
        centroid = to_shape(lot.centroid)
        
        # Check bounding box
        if min_lat is not None and centroid.y < min_lat:
            continue
        if max_lat is not None and centroid.y > max_lat:
            continue
        if min_lng is not None and centroid.x < min_lng:
            continue
        if max_lng is not None and centroid.x > max_lng:
            continue
        
        # Get business name if associated
        business_name = None
        has_biz = False
        
        primary_assoc = db.query(ParkingLotBusinessAssociation).filter(
            ParkingLotBusinessAssociation.parking_lot_id == lot.id,
            ParkingLotBusinessAssociation.is_primary == True
        ).first()
        
        if primary_assoc:
            has_biz = True
            business = db.query(Business).filter(Business.id == primary_assoc.business_id).first()
            if business:
                business_name = business.name
        
        if has_business is not None:
            if has_business and not has_biz:
                continue
            if not has_business and has_biz:
                continue
        
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
    lot = db.query(ParkingLot).filter(
        ParkingLot.id == parking_lot_id,
        ParkingLot.user_id == current_user.id
    ).first()
    
    if not lot:
        raise HTTPException(status_code=404, detail="Parking lot not found")
    
    response = parking_lot_to_response(lot)
    response["degradation_areas"] = lot.degradation_areas
    response["raw_metadata"] = lot.raw_metadata
    response["evaluation_error"] = lot.evaluation_error
    response["updated_at"] = lot.updated_at
    
    # Include primary business association if available
    primary_assoc = db.query(ParkingLotBusinessAssociation).filter(
        ParkingLotBusinessAssociation.parking_lot_id == parking_lot_id,
        ParkingLotBusinessAssociation.is_primary == True
    ).first()
    
    if primary_assoc:
        business = db.query(Business).filter(Business.id == primary_assoc.business_id).first()
        if business:
            response["business"] = BusinessSummary(
                id=business.id,
                name=business.name,
                phone=business.phone,
                email=business.email,
                website=business.website,
                address=business.address,
                category=business.category,
            )
            response["match_score"] = float(primary_assoc.match_score)
            response["distance_meters"] = float(primary_assoc.distance_meters)
    
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
    
    associations = db.query(ParkingLotBusinessAssociation).filter(
        ParkingLotBusinessAssociation.parking_lot_id == parking_lot_id
    ).order_by(ParkingLotBusinessAssociation.match_score.desc()).all()
    
    results = []
    for assoc in associations:
        business = db.query(Business).filter(Business.id == assoc.business_id).first()
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

