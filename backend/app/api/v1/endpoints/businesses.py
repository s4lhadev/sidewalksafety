from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from geoalchemy2.shape import to_shape

from app.db.base import get_db
from app.models.business import Business
from app.models.association import ParkingLotBusinessAssociation
from app.models.parking_lot import ParkingLot
from app.models.user import User
from app.schemas.business import BusinessResponse, BusinessDetailResponse
from app.core.dependencies import get_current_user

router = APIRouter()


@router.get("/{business_id}", response_model=BusinessDetailResponse)
def get_business(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get business details with associated parking lots."""
    business = db.query(Business).filter(Business.id == business_id).first()
    
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    
    # Get associated parking lots (only those owned by current user)
    associations = db.query(ParkingLotBusinessAssociation).filter(
        ParkingLotBusinessAssociation.business_id == business_id
    ).all()
    
    parking_lots = []
    for assoc in associations:
        lot = db.query(ParkingLot).filter(
            ParkingLot.id == assoc.parking_lot_id,
            ParkingLot.user_id == current_user.id
        ).first()
        
        if lot:
            parking_lots.append({
                "id": lot.id,
                "area_sqft": float(lot.area_sqft) if lot.area_sqft else None,
                "condition_score": float(lot.condition_score) if lot.condition_score else None,
                "match_score": float(assoc.match_score),
                "distance_meters": float(assoc.distance_meters),
            })
    
    location = to_shape(business.geometry)
    
    return BusinessDetailResponse(
        id=business.id,
        name=business.name,
        phone=business.phone,
        email=business.email,
        website=business.website,
        address=business.address,
        city=business.city,
        state=business.state,
        zip=business.zip,
        county=business.county,
        category=business.category,
        subcategory=business.subcategory,
        geometry={"lat": location.y, "lng": location.x},
        data_source=business.data_source,
        created_at=business.created_at,
        updated_at=business.updated_at,
        raw_metadata=business.raw_metadata,
        parking_lots=parking_lots if parking_lots else None,
    )


@router.get("")
def list_businesses(
    category: Optional[str] = Query(None, description="Filter by category"),
    city: Optional[str] = Query(None, description="Filter by city"),
    state: Optional[str] = Query(None, description="Filter by state"),
    has_parking_lot: Optional[bool] = Query(None, description="Filter by parking lot association"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List businesses.
    
    Only returns businesses that are associated with parking lots owned by the current user.
    """
    # Get business IDs associated with user's parking lots
    user_lot_ids = db.query(ParkingLot.id).filter(
        ParkingLot.user_id == current_user.id
    ).subquery()
    
    business_ids = db.query(ParkingLotBusinessAssociation.business_id).filter(
        ParkingLotBusinessAssociation.parking_lot_id.in_(user_lot_ids)
    ).distinct().subquery()
    
    query = db.query(Business).filter(Business.id.in_(business_ids))
    
    # Apply filters
    if category:
        query = query.filter(Business.category.ilike(f"%{category}%"))
    
    if city:
        query = query.filter(Business.city.ilike(f"%{city}%"))
    
    if state:
        query = query.filter(Business.state == state.upper())
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    businesses = query.offset(offset).limit(limit).all()
    
    results = []
    for biz in businesses:
        location = to_shape(biz.geometry)
        results.append({
            "id": biz.id,
            "name": biz.name,
            "phone": biz.phone,
            "email": biz.email,
            "website": biz.website,
            "address": biz.address,
            "city": biz.city,
            "state": biz.state,
            "category": biz.category,
            "geometry": {"lat": location.y, "lng": location.x},
            "data_source": biz.data_source,
        })
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": results,
    }

