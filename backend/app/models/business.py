from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geography
import uuid

from app.db.base import Base


class Business(Base):
    __tablename__ = "businesses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Contact information
    name = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    website = Column(String, nullable=True)
    
    # Address
    address = Column(String, nullable=True)
    city = Column(String, nullable=True, index=True)
    state = Column(String, nullable=True, index=True)
    zip = Column(String, nullable=True, index=True)
    county = Column(String, nullable=True, index=True)
    
    # Category
    category = Column(String, nullable=True, index=True)
    subcategory = Column(String, nullable=True)
    
    # Geometry (PostGIS)
    geometry = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    building_polygon = Column(Geography(geometry_type='POLYGON', srid=4326), nullable=True)
    
    # Data source IDs
    infobel_id = Column(String, nullable=True, index=True)
    safegraph_id = Column(String, nullable=True, index=True)
    places_id = Column(String, nullable=True, index=True)
    data_source = Column(String, nullable=False)  # "infobel", "safegraph", "google_places"
    
    # Metadata
    raw_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    parking_lot_associations = relationship("ParkingLotBusinessAssociation", back_populates="business", cascade="all, delete-orphan")
    deals = relationship("Deal", back_populates="business", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_businesses_geometry', geometry, postgresql_using='gist'),
        Index('idx_businesses_building', building_polygon, postgresql_using='gist'),
    )

