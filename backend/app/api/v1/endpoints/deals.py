from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from datetime import datetime
from geoalchemy2.shape import to_shape

from app.db.base import get_db
from app.models.deal import Deal
from app.models.parking_lot import ParkingLot
from app.models.business import Business
from app.models.user import User
from app.schemas.deal import (
    DealCreate,
    DealUpdate,
    DealResponse,
    DealDetailResponse,
    DealListResponse,
    DealStatus,
    ParkingLotSummaryForDeal,
    BusinessSummaryForDeal,
)
from app.core.dependencies import get_current_user

router = APIRouter()


@router.post("", response_model=DealResponse, status_code=status.HTTP_201_CREATED)
def create_deal(
    deal_data: DealCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a deal from a parking lot."""
    # Verify parking lot exists and belongs to user
    parking_lot = db.query(ParkingLot).filter(
        ParkingLot.id == deal_data.parking_lot_id,
        ParkingLot.user_id == current_user.id
    ).first()
    
    if not parking_lot:
        raise HTTPException(status_code=404, detail="Parking lot not found")
    
    # Check if deal already exists for this parking lot
    existing_deal = db.query(Deal).filter(
        Deal.parking_lot_id == deal_data.parking_lot_id,
        Deal.user_id == current_user.id
    ).first()
    
    if existing_deal:
        raise HTTPException(
            status_code=400,
            detail="Deal already exists for this parking lot"
        )
    
    # Verify business if provided
    if deal_data.business_id:
        business = db.query(Business).filter(Business.id == deal_data.business_id).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business not found")
    
    # Calculate priority score
    priority_score = _calculate_priority_score(parking_lot)
    
    # Create deal
    deal = Deal(
        user_id=current_user.id,
        parking_lot_id=deal_data.parking_lot_id,
        business_id=deal_data.business_id,
        estimated_job_value=deal_data.estimated_job_value,
        priority_score=priority_score,
        notes=deal_data.notes,
        status="pending",
    )
    
    db.add(deal)
    db.commit()
    db.refresh(deal)
    
    return DealResponse.model_validate(deal)


@router.get("", response_model=DealListResponse)
def list_deals(
    status: Optional[DealStatus] = Query(None),
    min_priority_score: Optional[float] = Query(None),
    min_estimated_value: Optional[float] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List deals with filters."""
    query = db.query(Deal).filter(Deal.user_id == current_user.id)
    
    if status:
        query = query.filter(Deal.status == status.value)
    
    if min_priority_score is not None:
        query = query.filter(Deal.priority_score >= min_priority_score)
    
    if min_estimated_value is not None:
        query = query.filter(Deal.estimated_job_value >= min_estimated_value)
    
    total = query.count()
    
    deals = query.order_by(Deal.priority_score.desc().nullslast()).offset(offset).limit(limit).all()
    
    results = []
    for deal in deals:
        deal_dict = {
            "id": deal.id,
            "parking_lot_id": deal.parking_lot_id,
            "business_id": deal.business_id,
            "status": DealStatus(deal.status),
            "estimated_job_value": float(deal.estimated_job_value) if deal.estimated_job_value else None,
            "quoted_amount": float(deal.quoted_amount) if deal.quoted_amount else None,
            "final_amount": float(deal.final_amount) if deal.final_amount else None,
            "priority_score": float(deal.priority_score) if deal.priority_score else None,
            "notes": deal.notes,
            "created_at": deal.created_at,
            "updated_at": deal.updated_at,
            "contacted_at": deal.contacted_at,
            "quoted_at": deal.quoted_at,
            "closed_at": deal.closed_at,
        }
        
        # Add parking lot summary
        if deal.parking_lot:
            centroid = to_shape(deal.parking_lot.centroid)
            deal_dict["parking_lot"] = ParkingLotSummaryForDeal(
                id=deal.parking_lot.id,
                area_sqft=float(deal.parking_lot.area_sqft) if deal.parking_lot.area_sqft else None,
                condition_score=float(deal.parking_lot.condition_score) if deal.parking_lot.condition_score else None,
                satellite_image_url=deal.parking_lot.satellite_image_url,
                centroid={"lat": centroid.y, "lng": centroid.x},
            )
        
        # Add business summary
        if deal.business:
            deal_dict["business"] = BusinessSummaryForDeal(
                id=deal.business.id,
                name=deal.business.name,
                phone=deal.business.phone,
                email=deal.business.email,
                website=deal.business.website,
                address=deal.business.address,
                category=deal.business.category,
            )
        
        results.append(DealDetailResponse(**deal_dict))
    
    return DealListResponse(
        total=total,
        limit=limit,
        offset=offset,
        results=results,
    )


@router.get("/{deal_id}", response_model=DealDetailResponse)
def get_deal(
    deal_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get deal details."""
    deal = db.query(Deal).filter(
        Deal.id == deal_id,
        Deal.user_id == current_user.id
    ).first()
    
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    response = {
        "id": deal.id,
        "parking_lot_id": deal.parking_lot_id,
        "business_id": deal.business_id,
        "status": DealStatus(deal.status),
        "estimated_job_value": float(deal.estimated_job_value) if deal.estimated_job_value else None,
        "quoted_amount": float(deal.quoted_amount) if deal.quoted_amount else None,
        "final_amount": float(deal.final_amount) if deal.final_amount else None,
        "priority_score": float(deal.priority_score) if deal.priority_score else None,
        "notes": deal.notes,
        "created_at": deal.created_at,
        "updated_at": deal.updated_at,
        "contacted_at": deal.contacted_at,
        "quoted_at": deal.quoted_at,
        "closed_at": deal.closed_at,
    }
    
    if deal.parking_lot:
        centroid = to_shape(deal.parking_lot.centroid)
        response["parking_lot"] = ParkingLotSummaryForDeal(
            id=deal.parking_lot.id,
            area_sqft=float(deal.parking_lot.area_sqft) if deal.parking_lot.area_sqft else None,
            condition_score=float(deal.parking_lot.condition_score) if deal.parking_lot.condition_score else None,
            satellite_image_url=deal.parking_lot.satellite_image_url,
            centroid={"lat": centroid.y, "lng": centroid.x},
        )
    
    if deal.business:
        response["business"] = BusinessSummaryForDeal(
            id=deal.business.id,
            name=deal.business.name,
            phone=deal.business.phone,
            email=deal.business.email,
            website=deal.business.website,
            address=deal.business.address,
            category=deal.business.category,
        )
    
    return DealDetailResponse(**response)


@router.patch("/{deal_id}", response_model=DealResponse)
def update_deal(
    deal_id: UUID,
    deal_update: DealUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update deal status and details."""
    deal = db.query(Deal).filter(
        Deal.id == deal_id,
        Deal.user_id == current_user.id
    ).first()
    
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    # Update fields
    if deal_update.status is not None:
        old_status = deal.status
        deal.status = deal_update.status.value
        
        # Set timestamps based on status change
        if deal_update.status == DealStatus.CONTACTED and not deal.contacted_at:
            deal.contacted_at = datetime.utcnow()
        elif deal_update.status == DealStatus.QUOTED and not deal.quoted_at:
            deal.quoted_at = datetime.utcnow()
        elif deal_update.status in [DealStatus.WON, DealStatus.LOST] and not deal.closed_at:
            deal.closed_at = datetime.utcnow()
    
    if deal_update.quoted_amount is not None:
        deal.quoted_amount = deal_update.quoted_amount
    
    if deal_update.final_amount is not None:
        deal.final_amount = deal_update.final_amount
    
    if deal_update.notes is not None:
        deal.notes = deal_update.notes
    
    db.commit()
    db.refresh(deal)
    
    return DealResponse.model_validate(deal)


@router.delete("/{deal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deal(
    deal_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a deal."""
    deal = db.query(Deal).filter(
        Deal.id == deal_id,
        Deal.user_id == current_user.id
    ).first()
    
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    db.delete(deal)
    db.commit()


def _calculate_priority_score(parking_lot: ParkingLot) -> float:
    """Calculate priority score for a deal based on parking lot metrics."""
    score = 50  # Base score
    
    # Higher area = higher priority (max 25 points)
    if parking_lot.area_sqft:
        area_score = min(float(parking_lot.area_sqft) / 50000 * 25, 25)
        score += area_score
    
    # Lower condition score = higher priority (max 25 points)
    if parking_lot.condition_score:
        condition_score = (100 - float(parking_lot.condition_score)) / 100 * 25
        score += condition_score
    
    return min(100, max(0, score))
