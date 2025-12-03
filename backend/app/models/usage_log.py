from sqlalchemy import Column, String, Integer, BigInteger, Numeric, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base


class UsageLog(Base):
    """Track API and compute usage per user."""
    
    __tablename__ = "usage_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # What was used
    action = Column(String, nullable=False, index=True)  # 'discovery', 'cv_evaluation', 'api_call'
    resource = Column(String, index=True)  # 'inrix', 'here', 'osm', 'google_maps', 'google_places', 'roboflow'
    
    # Quantities
    count = Column(Integer, default=1)
    bytes_processed = Column(BigInteger)  # For CV: image size in bytes
    
    # Cost tracking (estimated)
    estimated_cost = Column(Numeric(10, 6))  # In USD
    
    # Context
    job_id = Column(UUID(as_uuid=True), index=True)
    parking_lot_id = Column(UUID(as_uuid=True))
    
    # Additional details
    details = Column(JSONB)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    user = relationship("User", back_populates="usage_logs")
    
    def __repr__(self):
        return f"<UsageLog {self.action}:{self.resource} user={self.user_id}>"

