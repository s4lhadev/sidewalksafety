"""
CVImage model - stores references to CV-generated images.
Tracks all visual outputs from the analysis pipeline.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.db.base import Base


class CVImage(Base):
    """
    Stores references to images generated during CV analysis.
    Supports multiple image types per analysis.
    """
    __tablename__ = "cv_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_analysis_id = Column(UUID(as_uuid=True), ForeignKey("property_analyses.id"), nullable=False, index=True)
    
    # Image type
    image_type = Column(String(50), nullable=False)  # 'wide_satellite', 'segmentation', 'property_boundary', 'condition'
    
    # Storage
    image_url = Column(Text, nullable=False)
    thumbnail_url = Column(Text, nullable=True)
    storage_path = Column(String(500), nullable=True)  # Local or S3 path
    
    # Metadata
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    content_type = Column(String(50), nullable=True)  # 'image/jpeg', 'image/png'
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    property_analysis = relationship("PropertyAnalysis", back_populates="cv_images")

