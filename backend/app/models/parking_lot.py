from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Boolean, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geography
import uuid

from app.db.base import Base


class ParkingLot(Base):
    __tablename__ = "parking_lots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Geometry (PostGIS)
    geometry = Column(Geography(geometry_type='POLYGON', srid=4326), nullable=True)
    centroid = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    
    # Area measurements
    area_m2 = Column(Numeric(12, 2), nullable=True)
    area_sqft = Column(Numeric(12, 2), nullable=True)
    
    # Data source IDs
    inrix_id = Column(String, nullable=True, index=True)
    here_id = Column(String, nullable=True, index=True)
    osm_id = Column(String, nullable=True, index=True)
    data_sources = Column(ARRAY(String), nullable=False, default=[])
    
    # Operator info (from INRIX/HERE)
    operator_name = Column(String, nullable=True)
    address = Column(String, nullable=True)
    
    # Surface info (from OSM)
    surface_type = Column(String, nullable=True)  # asphalt, concrete, gravel
    
    # Condition metrics (from CV evaluation)
    condition_score = Column(Numeric(5, 2), nullable=True)  # 0-100 (lower = worse)
    crack_density = Column(Numeric(5, 2), nullable=True)  # percentage
    pothole_score = Column(Numeric(3, 1), nullable=True)  # 0-10
    line_fading_score = Column(Numeric(3, 1), nullable=True)  # 0-10
    degradation_areas = Column(JSONB, nullable=True)  # polygon coordinates of damaged areas
    
    # Imagery
    satellite_image_url = Column(Text, nullable=True)
    satellite_image_path = Column(String, nullable=True)  # object storage path
    image_captured_at = Column(DateTime(timezone=True), nullable=True)
    
    # Evaluation status
    is_evaluated = Column(Boolean, default=False, nullable=False, index=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)
    evaluation_error = Column(Text, nullable=True)
    
    # Metadata
    raw_metadata = Column(JSONB, nullable=True)  # Original API responses
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Business-first discovery fields
    business_type_tier = Column(String(20), nullable=True)  # "premium", "high", "standard"
    discovery_mode = Column(String(20), nullable=True)  # "business_first" or "parking_first"

    # Relationships
    user = relationship("User", back_populates="parking_lots")
    business_associations = relationship("ParkingLotBusinessAssociation", back_populates="parking_lot", cascade="all, delete-orphan")
    deals = relationship("Deal", back_populates="parking_lot", cascade="all, delete-orphan")

    # Indexes for spatial queries
    __table_args__ = (
        Index('idx_parking_lots_centroid', centroid, postgresql_using='gist'),
        Index('idx_parking_lots_geometry', geometry, postgresql_using='gist'),
        Index('idx_parking_lots_condition', condition_score),
    )

