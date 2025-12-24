"""
PropertyAnalysis model - stores results of two-stage CV pipeline.
Tracks the complete analysis of a property's asphalt surfaces.
"""
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geography
import uuid

from app.db.base import Base


class PropertyAnalysis(Base):
    """
    Stores the complete CV analysis of a property.
    Links to multiple AsphaltArea records for each detected surface.
    """
    __tablename__ = "property_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parking_lot_id = Column(UUID(as_uuid=True), ForeignKey("parking_lots.id"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Business location used for analysis
    business_location = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=True, index=True)
    
    # Wide satellite image used for analysis
    wide_image_url = Column(Text, nullable=True)
    wide_image_base64 = Column(Text, nullable=True)  # Base64 encoded image
    wide_image_bounds = Column(JSONB, nullable=True)  # {min_lat, max_lat, min_lng, max_lng}
    wide_image_zoom = Column(Float, nullable=True)
    
    # Stage 1: Segmentation results
    segmentation_model_id = Column(String(200), nullable=True)
    segmentation_result_image_url = Column(Text, nullable=True)  # Annotated image
    segmentation_image_base64 = Column(Text, nullable=True)  # Base64 encoded
    raw_segmentation_data = Column(JSONB, nullable=True)  # Full API response
    buildings_detected = Column(JSONB, nullable=True)  # List of building polygons
    paved_surfaces_detected = Column(JSONB, nullable=True)  # List of paved surface polygons
    
    # Property boundary from Regrid (legal parcel boundary)
    property_boundary_polygon = Column(Geography(geometry_type='GEOMETRY', srid=4326), nullable=True)
    property_boundary_source = Column(String(50), nullable=True)  # "regrid", "osm", "estimated"
    property_parcel_id = Column(String(200), nullable=True)  # Regrid parcel ID
    property_owner = Column(Text, nullable=True)  # Property owner from Regrid
    property_apn = Column(String(100), nullable=True)  # Assessor Parcel Number
    property_land_use = Column(String(100), nullable=True)  # Land use classification
    property_zoning = Column(String(100), nullable=True)  # Zoning code
    
    # Property boundary image (overlay)
    property_boundary_image_url = Column(Text, nullable=True)
    property_boundary_image_base64 = Column(Text, nullable=True)  # Base64 encoded
    
    # Business building polygon (from segmentation)
    business_building_polygon = Column(Geography(geometry_type='GEOMETRY', srid=4326), nullable=True)
    
    # Stage 2: Condition analysis
    condition_analysis_image_url = Column(Text, nullable=True)
    condition_analysis_image_base64 = Column(Text, nullable=True)  # Base64 encoded
    
    # Aggregated metrics
    total_asphalt_area_m2 = Column(Float, nullable=True)
    weighted_condition_score = Column(Float, nullable=True)  # 0-100, area-weighted average
    total_crack_count = Column(Numeric, nullable=True)
    total_pothole_count = Column(Numeric, nullable=True)
    
    # Status
    status = Column(String(50), default="pending", nullable=False)  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    analyzed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="property_analyses")
    parking_lot = relationship("ParkingLot", back_populates="property_analysis")
    business = relationship("Business", back_populates="property_analyses")
    asphalt_areas = relationship("AsphaltArea", back_populates="property_analysis", cascade="all, delete-orphan")
    cv_images = relationship("CVImage", back_populates="property_analysis", cascade="all, delete-orphan")

