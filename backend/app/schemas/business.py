from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class Coordinates(BaseModel):
    lat: float
    lng: float


# ============ Business Schemas ============

class BusinessBase(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    county: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None


class BusinessCreate(BusinessBase):
    geometry: Coordinates
    data_source: str
    infobel_id: Optional[str] = None
    safegraph_id: Optional[str] = None
    places_id: Optional[str] = None
    raw_metadata: Optional[Dict[str, Any]] = None


class BusinessResponse(BusinessBase):
    id: UUID
    geometry: Coordinates
    data_source: str
    created_at: datetime

    class Config:
        from_attributes = True


class BusinessDetailResponse(BusinessResponse):
    building_polygon: Optional[Dict[str, Any]] = None
    raw_metadata: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None
    
    # Associated parking lots
    parking_lots: Optional[List["ParkingLotSummary"]] = None

    class Config:
        from_attributes = True


class ParkingLotSummary(BaseModel):
    id: UUID
    area_sqft: Optional[float] = None
    condition_score: Optional[float] = None
    match_score: Optional[float] = None
    distance_meters: Optional[float] = None

    class Config:
        from_attributes = True


# Forward reference update
BusinessDetailResponse.model_rebuild()

