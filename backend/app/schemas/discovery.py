from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class AreaType(str, Enum):
    ZIP = "zip"
    COUNTY = "county"
    POLYGON = "polygon"


class GeoJSONPolygon(BaseModel):
    type: str = "Polygon"
    coordinates: List[List[List[float]]]


class DiscoveryFilters(BaseModel):
    min_area_m2: float = Field(default=200.0, ge=0, description="Minimum lot area in square meters")
    max_condition_score: float = Field(default=70.0, ge=0, le=100, description="Maximum condition score (lower = worse = better lead)")
    min_match_score: float = Field(default=50.0, ge=0, le=100, description="Minimum business match confidence")
    max_lots: int = Field(default=10, ge=1, le=1000, description="Maximum parking lots to process (for testing, use low values)")
    max_businesses: int = Field(default=10, ge=1, le=500, description="Maximum businesses to load (for testing, use low values)")


# ============ Discovery Request ============

class DiscoveryRequest(BaseModel):
    area_type: AreaType
    value: str = Field(..., description="ZIP code or county name")
    state: Optional[str] = Field(None, description="Required if area_type is 'county'")
    polygon: Optional[GeoJSONPolygon] = Field(None, description="Required if area_type is 'polygon'")
    filters: Optional[DiscoveryFilters] = None


# ============ Discovery Job Status ============

class DiscoveryStep(str, Enum):
    QUEUED = "queued"
    CONVERTING_AREA = "converting_area"
    COLLECTING_PARKING_LOTS = "collecting_parking_lots"
    NORMALIZING = "normalizing"
    FETCHING_IMAGERY = "fetching_imagery"
    EVALUATING_CONDITION = "evaluating_condition"
    LOADING_BUSINESSES = "loading_businesses"
    ASSOCIATING = "associating"
    FILTERING = "filtering"
    COMPLETED = "completed"
    FAILED = "failed"


class DiscoveryProgress(BaseModel):
    current_step: DiscoveryStep
    steps_completed: int
    total_steps: int = 9
    parking_lots_found: int = 0
    parking_lots_evaluated: int = 0
    businesses_loaded: int = 0
    associations_made: int = 0
    high_value_leads: int = 0
    errors: List[str] = []


class DiscoveryJobResponse(BaseModel):
    job_id: UUID
    status: DiscoveryStep
    message: str
    estimated_completion: Optional[datetime] = None


class DiscoveryStatusResponse(BaseModel):
    job_id: UUID
    status: DiscoveryStep
    progress: DiscoveryProgress
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class DiscoveryResultsResponse(BaseModel):
    job_id: UUID
    status: DiscoveryStep
    results: Dict[str, int]
    message: str


# ============ Discovery Job (for DB storage) ============

class DiscoveryJobCreate(BaseModel):
    user_id: UUID
    area_type: AreaType
    area_value: str
    area_polygon: Optional[Dict[str, Any]] = None
    filters: DiscoveryFilters


class DiscoveryJobUpdate(BaseModel):
    status: Optional[DiscoveryStep] = None
    progress: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None

