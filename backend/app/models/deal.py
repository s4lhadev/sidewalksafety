from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.db.base import Base


class Deal(Base):
    __tablename__ = "deals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    parking_lot_id = Column(UUID(as_uuid=True), ForeignKey("parking_lots.id", ondelete="CASCADE"), nullable=False, index=True)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Status tracking
    status = Column(String, default="pending", nullable=False, index=True)
    # pending -> contacted -> quoted -> negotiating -> won/lost
    
    # Financials
    estimated_job_value = Column(Numeric(12, 2), nullable=True)
    quoted_amount = Column(Numeric(12, 2), nullable=True)
    final_amount = Column(Numeric(12, 2), nullable=True)
    
    # Priority scoring
    priority_score = Column(Numeric(5, 2), nullable=True)  # 0-100
    
    # Notes and tracking
    notes = Column(Text, nullable=True)
    contacted_at = Column(DateTime(timezone=True), nullable=True)
    quoted_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="deals")
    parking_lot = relationship("ParkingLot", back_populates="deals")
    business = relationship("Business", back_populates="deals")

    # Indexes
    __table_args__ = (
        Index('idx_deals_status', status),
        Index('idx_deals_priority', priority_score),
    )
