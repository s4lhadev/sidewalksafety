from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class AreaType(str, Enum):
    ZIP = "zip"
    COUNTY = "county"
    POLYGON = "polygon"


class DiscoveryMode(str, Enum):
    """Discovery pipeline mode."""
    BUSINESS_FIRST = "business_first"  # Find businesses → parking lots (recommended)
    PARKING_FIRST = "parking_first"    # Find parking lots → businesses (legacy)


class BusinessTierEnum(str, Enum):
    """Business priority tiers."""
    PREMIUM = "premium"
    HIGH = "high"
    STANDARD = "standard"


# Available business types by tier (for frontend display)
# NOTE: We search for ACTUAL properties, not management companies
BUSINESS_TYPE_OPTIONS = {
    "premium": [
        {"id": "apartments", "label": "Apartment Complexes", "queries": ["apartment complex", "apartments for rent", "apartment building"]},
        {"id": "condos", "label": "Condo Buildings", "queries": ["condominium complex", "condo building"]},
        {"id": "townhomes", "label": "Townhome Communities", "queries": ["townhome community", "townhouse complex"]},
        {"id": "mobile_home", "label": "Mobile Home Parks", "queries": ["mobile home park", "trailer park", "manufactured home community"]},
    ],
    "high": [
        {"id": "shopping", "label": "Shopping Centers / Malls", "queries": ["shopping center", "shopping mall", "retail plaza", "strip mall"]},
        {"id": "hotels", "label": "Hotels / Motels", "queries": ["hotel", "motel", "extended stay"]},
        {"id": "offices", "label": "Office Parks / Complexes", "queries": ["office park", "office complex", "business park"]},
        {"id": "warehouses", "label": "Warehouses / Industrial", "queries": ["warehouse", "distribution center", "industrial park", "logistics center"]},
    ],
    "standard": [
        {"id": "churches", "label": "Churches", "queries": ["church", "religious center", "place of worship"]},
        {"id": "schools", "label": "Schools", "queries": ["school", "private school", "charter school"]},
        {"id": "hospitals", "label": "Hospitals / Medical", "queries": ["hospital", "medical center", "urgent care"]},
        {"id": "gyms", "label": "Gyms / Fitness", "queries": ["gym", "fitness center", "recreation center"]},
        {"id": "grocery", "label": "Grocery Stores", "queries": ["grocery store", "supermarket"]},
        {"id": "car_dealers", "label": "Car Dealerships", "queries": ["car dealership", "auto dealership"]},
    ],
}


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
    mode: DiscoveryMode = Field(
        default=DiscoveryMode.BUSINESS_FIRST,
        description="Discovery mode: 'business_first' (recommended) finds businesses then parking lots, 'parking_first' finds parking lots then businesses"
    )
    # Business type selection (for business_first mode)
    tiers: Optional[List[BusinessTierEnum]] = Field(
        default=None,
        description="Tiers to search: 'premium', 'high', 'standard'. If None, searches all tiers."
    )
    business_type_ids: Optional[List[str]] = Field(
        default=None,
        description="Specific business type IDs to search (e.g., 'hoa', 'apartments'). If None, searches all types in selected tiers."
    )
    max_results: Optional[int] = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of businesses to discover (1-50). Default is 10."
    )


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

