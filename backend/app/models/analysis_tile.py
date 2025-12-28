"""
AnalysisTile model for storing per-tile analysis data.

Each property analysis can have multiple tiles, each with:
- Satellite imagery
- Segmentation results
- Condition evaluation
"""

from sqlalchemy import Column, String, Float, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geography
import uuid
from datetime import datetime

from app.db.base import Base


class AnalysisTile(Base):
    """
    Individual tile from a property analysis.
    
    Each tile represents a high-resolution segment of the property
    that was analyzed independently.
    """
    __tablename__ = "analysis_tiles"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign key to property analysis
    property_analysis_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("property_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Tile identification
    tile_index = Column(Integer, nullable=False)  # Position in grid (0, 1, 2, ...)
    row = Column(Integer, nullable=True)
    col = Column(Integer, nullable=True)
    
    # Tile location
    center_lat = Column(Float, nullable=False)
    center_lng = Column(Float, nullable=False)
    zoom_level = Column(Integer, nullable=False, default=19)
    
    # Tile bounds
    bounds_min_lat = Column(Float, nullable=True)
    bounds_max_lat = Column(Float, nullable=True)
    bounds_min_lng = Column(Float, nullable=True)
    bounds_max_lng = Column(Float, nullable=True)
    
    # Tile polygon (for map display)
    tile_polygon = Column(Geography(geometry_type='POLYGON', srid=4326), nullable=True)
    
    # Imagery
    satellite_image_base64 = Column(Text, nullable=True)
    segmentation_image_base64 = Column(Text, nullable=True)
    condition_image_base64 = Column(Text, nullable=True)
    image_size_bytes = Column(Integer, nullable=True)
    
    # Segmentation results (total asphalt from CV)
    asphalt_area_m2 = Column(Float, nullable=True, default=0)
    parking_area_m2 = Column(Float, nullable=True, default=0)
    road_area_m2 = Column(Float, nullable=True, default=0)
    building_area_m2 = Column(Float, nullable=True, default=0)
    vegetation_area_m2 = Column(Float, nullable=True, default=0)
    segmentation_raw = Column(JSON, nullable=True)  # Raw segmentation response
    
    # Private asphalt (after filtering public roads via OSM)
    private_asphalt_area_m2 = Column(Float, nullable=True, default=0)
    private_asphalt_area_sqft = Column(Float, nullable=True, default=0)
    private_asphalt_polygon = Column(Geography(geometry_type='GEOMETRY', srid=4326), nullable=True)
    private_asphalt_geojson = Column(JSON, nullable=True)  # GeoJSON for frontend display
    
    # Public roads filtered out
    public_road_area_m2 = Column(Float, nullable=True, default=0)
    public_road_polygon = Column(Geography(geometry_type='GEOMETRY', srid=4326), nullable=True)
    
    # Source of asphalt detection
    asphalt_source = Column(String(50), nullable=True)  # cv_only, cv_with_osm_filter, fallback
    
    # Condition evaluation
    condition_score = Column(Float, nullable=True, default=100)
    crack_count = Column(Integer, nullable=True, default=0)
    pothole_count = Column(Integer, nullable=True, default=0)
    detection_count = Column(Integer, nullable=True, default=0)
    condition_raw = Column(JSON, nullable=True)  # Raw condition response
    
    # Status
    status = Column(String(50), nullable=False, default="pending")
    # pending, imagery_fetched, segmented, analyzed, failed
    
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    imagery_fetched_at = Column(DateTime, nullable=True)
    analyzed_at = Column(DateTime, nullable=True)
    
    # Relationship back to property analysis
    property_analysis = relationship("PropertyAnalysis", back_populates="tiles")
    
    def __repr__(self):
        return f"<AnalysisTile(id={self.id}, tile_index={self.tile_index}, status={self.status})>"

