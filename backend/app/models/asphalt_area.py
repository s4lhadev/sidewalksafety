"""
AsphaltArea model - stores each detected asphalt surface with its condition.
Each PropertyAnalysis can have multiple AsphaltArea records.
"""
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Boolean, Text, Float, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geography
import uuid

from app.db.base import Base


class AsphaltArea(Base):
    """
    Stores individual asphalt/paved surface detected by CV.
    Includes geometry, association status, and condition metrics.
    """
    __tablename__ = "asphalt_areas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_analysis_id = Column(UUID(as_uuid=True), ForeignKey("property_analyses.id"), nullable=False, index=True)
    
    # Geometry (from segmentation)
    # Use GEOMETRY instead of POLYGON to support MultiPolygon from complex segmentations
    polygon = Column(Geography(geometry_type='GEOMETRY', srid=4326), nullable=False)
    centroid = Column(Geography(geometry_type='POINT', srid=4326), nullable=True)
    area_m2 = Column(Float, nullable=True)
    
    # Pixel coordinates in original image
    pixel_coordinates = Column(JSONB, nullable=True)  # [{x, y}, ...] polygon points
    bounding_box = Column(JSONB, nullable=True)  # {x, y, width, height}
    
    # Classification
    area_type = Column(String(50), nullable=True)  # 'parking', 'driveway', 'loading_dock', 'unknown'
    segmentation_confidence = Column(Float, nullable=True)
    segmentation_class = Column(String(50), nullable=True)  # 'road', 'building', etc.
    
    # Association with business
    is_associated = Column(Boolean, default=True, nullable=False)  # TRUE = belongs to business
    association_reason = Column(String(100), nullable=True)  # 'touches_building', 'connected_to_parking', etc.
    distance_to_building_m = Column(Float, nullable=True)
    
    # Condition (from Stage 2 CV)
    condition_score = Column(Float, nullable=True)  # 0-100, lower = worse
    crack_count = Column(Integer, nullable=True)
    pothole_count = Column(Integer, nullable=True)
    crack_density = Column(Float, nullable=True)  # percentage
    pothole_score = Column(Float, nullable=True)  # 0-10
    
    # Detections from CV
    detections = Column(JSONB, nullable=True)  # [{class, confidence, bbox}, ...]
    
    # Visual output
    cropped_image_url = Column(Text, nullable=True)  # Cropped satellite image of this area
    condition_image_url = Column(Text, nullable=True)  # Cropped + annotated with detections
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship
    property_analysis = relationship("PropertyAnalysis", back_populates="asphalt_areas")

