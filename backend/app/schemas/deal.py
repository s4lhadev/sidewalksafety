from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum


class DealStatus(str, Enum):
    PENDING = "pending"
    CONTACTED = "contacted"
    QUOTED = "quoted"
    NEGOTIATING = "negotiating"
    WON = "won"
    LOST = "lost"


# ============ Deal Schemas ============

class DealCreate(BaseModel):
    parking_lot_id: UUID
    business_id: Optional[UUID] = None
    estimated_job_value: Optional[float] = None
    notes: Optional[str] = None


class DealUpdate(BaseModel):
    status: Optional[DealStatus] = None
    quoted_amount: Optional[float] = None
    final_amount: Optional[float] = None
    notes: Optional[str] = None


class DealResponse(BaseModel):
    id: UUID
    parking_lot_id: UUID
    business_id: Optional[UUID] = None
    status: DealStatus
    estimated_job_value: Optional[float] = None
    quoted_amount: Optional[float] = None
    final_amount: Optional[float] = None
    priority_score: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    contacted_at: Optional[datetime] = None
    quoted_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DealDetailResponse(DealResponse):
    """Deal with full parking lot and business details."""
    parking_lot: Optional["ParkingLotSummaryForDeal"] = None
    business: Optional["BusinessSummaryForDeal"] = None

    class Config:
        from_attributes = True


class ParkingLotSummaryForDeal(BaseModel):
    id: UUID
    area_sqft: Optional[float] = None
    condition_score: Optional[float] = None
    satellite_image_url: Optional[str] = None
    centroid: Optional[dict] = None

    class Config:
        from_attributes = True


class BusinessSummaryForDeal(BaseModel):
    id: UUID
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    category: Optional[str] = None

    class Config:
        from_attributes = True


# ============ List/Filter Schemas ============

class DealListParams(BaseModel):
    status: Optional[DealStatus] = None
    min_priority_score: Optional[float] = None
    min_estimated_value: Optional[float] = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class DealListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    results: List[DealDetailResponse]


# Forward reference update
DealDetailResponse.model_rebuild()
