"""
Pydantic schemas for Property Analysis API.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class PropertyAnalysisRequest(BaseModel):
    """Request to start a property analysis."""
    latitude: float = Field(..., ge=-90, le=90, description="Business latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Business longitude")
    business_id: Optional[UUID] = Field(None, description="Optional linked business ID")
    parking_lot_id: Optional[UUID] = Field(None, description="Optional linked parking lot ID")


class AsphaltAreaResponse(BaseModel):
    """Single asphalt area in analysis response."""
    id: UUID
    area_type: Optional[str]
    area_m2: Optional[float]
    is_associated: bool
    association_reason: Optional[str]
    distance_to_building_m: Optional[float]
    condition_score: Optional[float]
    crack_count: Optional[int]
    pothole_count: Optional[int]
    crack_density: Optional[float]
    
    class Config:
        from_attributes = True


class PropertyAnalysisImages(BaseModel):
    """Base64 encoded images from property analysis."""
    wide_satellite: Optional[str] = None  # Base64 encoded
    segmentation: Optional[str] = None  # Base64 encoded
    property_boundary: Optional[str] = None  # Base64 encoded
    condition_analysis: Optional[str] = None  # Base64 encoded


class PropertyAnalysisResponse(BaseModel):
    """Complete property analysis response."""
    id: UUID
    status: str
    
    # Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Metrics
    total_asphalt_area_m2: Optional[float] = None
    weighted_condition_score: Optional[float] = None
    total_crack_count: Optional[int] = None
    total_pothole_count: Optional[int] = None
    
    # Images
    images: PropertyAnalysisImages
    
    # Asphalt areas
    asphalt_areas: List[AsphaltAreaResponse] = []
    
    # Linked entities
    business_id: Optional[UUID] = None
    parking_lot_id: Optional[UUID] = None
    
    # Timestamps
    analyzed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    
    # Error info
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True


class PropertyAnalysisJobResponse(BaseModel):
    """Response when starting an analysis job."""
    job_id: str
    analysis_id: UUID
    status: str
    message: str


class PropertyAnalysisListResponse(BaseModel):
    """List of property analyses."""
    total: int
    limit: int
    offset: int
    results: List[PropertyAnalysisResponse]

