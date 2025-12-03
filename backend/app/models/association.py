from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.db.base import Base


class ParkingLotBusinessAssociation(Base):
    __tablename__ = "parking_lot_business_associations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parking_lot_id = Column(UUID(as_uuid=True), ForeignKey("parking_lots.id", ondelete="CASCADE"), nullable=False, index=True)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Match scoring
    match_score = Column(Numeric(5, 2), nullable=False)  # 0-100
    distance_meters = Column(Numeric(8, 2), nullable=False)
    
    # Match details
    association_method = Column(String, nullable=False)  # "spatial_proximity", "operator_match", "name_similarity"
    category_weight = Column(Numeric(3, 2), nullable=True)  # Category relevance score
    name_similarity = Column(Numeric(3, 2), nullable=True)  # Fuzzy match score if applicable
    
    # Priority
    is_primary = Column(Boolean, default=False, nullable=False, index=True)  # Best match for this parking lot
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    parking_lot = relationship("ParkingLot", back_populates="business_associations")
    business = relationship("Business", back_populates="parking_lot_associations")

    # Indexes
    __table_args__ = (
        Index('idx_association_match_score', match_score),
        Index('idx_association_primary', is_primary),
    )

