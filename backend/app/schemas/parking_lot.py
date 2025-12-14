from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class Coordinates(BaseModel):
    lat: float
    lng: float


class GeoJSONPolygon(BaseModel):
    type: str = "Polygon"
    coordinates: List[List[List[float]]]


class GeoJSONPoint(BaseModel):
    type: str = "Point"
    coordinates: List[float]


# ============ Parking Lot Schemas ============

class ParkingLotBase(BaseModel):
    area_m2: Optional[float] = None
    area_sqft: Optional[float] = None
    operator_name: Optional[str] = None
    address: Optional[str] = None
    surface_type: Optional[str] = None


class ParkingLotCreate(ParkingLotBase):
    geometry: Optional[GeoJSONPolygon] = None
    centroid: Coordinates
    inrix_id: Optional[str] = None
    here_id: Optional[str] = None
    osm_id: Optional[str] = None
    data_sources: List[str] = []
    raw_metadata: Optional[Dict[str, Any]] = None


class ParkingLotCondition(BaseModel):
    condition_score: Optional[float] = None
    crack_density: Optional[float] = None
    pothole_score: Optional[float] = None
    line_fading_score: Optional[float] = None
    degradation_areas: Optional[List[Dict[str, Any]]] = None


# ============ Business Summary (for embedding) ============

class BusinessSummary(BaseModel):
    id: UUID
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    category: Optional[str] = None

    class Config:
        from_attributes = True


class ParkingLotResponse(ParkingLotBase):
    id: UUID
    centroid: Coordinates
    geometry: Optional[GeoJSONPolygon] = None
    
    # Condition
    condition_score: Optional[float] = None
    crack_density: Optional[float] = None
    pothole_score: Optional[float] = None
    line_fading_score: Optional[float] = None
    
    # Imagery
    satellite_image_url: Optional[str] = None
    
    # Status
    is_evaluated: bool
    data_sources: List[str]
    
    # Business-first discovery fields
    business_type_tier: Optional[str] = None  # "premium", "high", "standard"
    discovery_mode: Optional[str] = None  # "business_first", "parking_first"
    
    # Timestamps
    created_at: datetime
    evaluated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ParkingLotDetailResponse(ParkingLotResponse):
    degradation_areas: Optional[List[Dict[str, Any]]] = None
    raw_metadata: Optional[Dict[str, Any]] = None
    evaluation_error: Optional[str] = None
    updated_at: Optional[datetime] = None
    business: Optional[BusinessSummary] = None
    match_score: Optional[float] = None
    distance_meters: Optional[float] = None

    class Config:
        from_attributes = True


class ParkingLotMapResponse(BaseModel):
    """Optimized response for map display."""
    id: UUID
    centroid: Coordinates
    area_m2: Optional[float] = None
    condition_score: Optional[float] = None
    is_evaluated: bool
    has_business: bool
    business_name: Optional[str] = None
    business_type_tier: Optional[str] = None  # "premium", "high", "standard"
    business: Optional[BusinessSummary] = None

    class Config:
        from_attributes = True


class ParkingLotWithBusiness(ParkingLotResponse):
    """Parking lot with associated business info."""
    business: Optional[BusinessSummary] = None
    match_score: Optional[float] = None
    distance_meters: Optional[float] = None

    class Config:
        from_attributes = True


# ============ List/Filter Schemas ============

class ParkingLotListParams(BaseModel):
    min_area_m2: Optional[float] = None
    max_condition_score: Optional[float] = None  # Lower = worse = better lead
    min_match_score: Optional[float] = None
    has_business: Optional[bool] = None
    is_evaluated: Optional[bool] = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class ParkingLotListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    results: List[ParkingLotWithBusiness]


# Forward reference update
ParkingLotWithBusiness.model_rebuild()

