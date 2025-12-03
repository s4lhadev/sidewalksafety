import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
from sqlalchemy.orm import Session
from sqlalchemy import text
from geoalchemy2.shape import from_shape, to_shape
from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_Area, ST_Centroid
import uuid

from app.models.parking_lot import ParkingLot
from app.core.parking_lot_discovery_service import RawParkingLot

logger = logging.getLogger(__name__)


@dataclass
class NormalizedParkingLot:
    """Deduplicated and normalized parking lot."""
    geometry: Optional[Polygon]
    centroid: Point
    area_m2: float
    area_sqft: float
    inrix_id: Optional[str] = None
    here_id: Optional[str] = None
    osm_id: Optional[str] = None
    data_sources: List[str] = None
    operator_name: Optional[str] = None
    address: Optional[str] = None
    surface_type: Optional[str] = None
    raw_metadata: Optional[Dict[str, Any]] = None


class NormalizationService:
    """Service to normalize and deduplicate parking lots from multiple sources."""
    
    DUPLICATE_DISTANCE_METERS = 20  # Consider lots within 20m as duplicates
    
    def normalize_and_deduplicate(
        self,
        raw_lots: List[RawParkingLot]
    ) -> List[NormalizedParkingLot]:
        """
        Normalize and deduplicate parking lots.
        
        1. Group lots that are within DUPLICATE_DISTANCE_METERS of each other
        2. Merge overlapping lots
        3. Pick best geometry (prefer polygons over points)
        4. Compute accurate centroid and area
        """
        if not raw_lots:
            return []
        
        # Group by proximity
        clusters = self._cluster_by_proximity(raw_lots)
        logger.info(f"Clustered {len(raw_lots)} raw lots into {len(clusters)} unique lots")
        
        # Normalize each cluster
        normalized = []
        for cluster in clusters:
            try:
                lot = self._merge_cluster(cluster)
                if lot:
                    normalized.append(lot)
            except Exception as e:
                logger.warning(f"Failed to merge cluster: {e}")
        
        return normalized
    
    def _cluster_by_proximity(
        self,
        lots: List[RawParkingLot]
    ) -> List[List[RawParkingLot]]:
        """Group lots that are within DUPLICATE_DISTANCE_METERS of each other."""
        if not lots:
            return []
        
        # Simple clustering: assign each lot to a cluster
        clusters: List[List[RawParkingLot]] = []
        assigned = [False] * len(lots)
        
        for i, lot in enumerate(lots):
            if assigned[i]:
                continue
            
            # Start new cluster
            cluster = [lot]
            assigned[i] = True
            
            # Find all lots within distance
            for j, other in enumerate(lots):
                if assigned[j]:
                    continue
                
                # Calculate distance between centroids
                dist = self._haversine_distance(
                    lot.centroid.y, lot.centroid.x,
                    other.centroid.y, other.centroid.x
                )
                
                if dist <= self.DUPLICATE_DISTANCE_METERS:
                    cluster.append(other)
                    assigned[j] = True
            
            clusters.append(cluster)
        
        return clusters
    
    def _merge_cluster(self, cluster: List[RawParkingLot]) -> Optional[NormalizedParkingLot]:
        """Merge a cluster of duplicate lots into a single normalized lot."""
        if not cluster:
            return None
        
        # Pick best geometry (prefer HERE/OSM polygons over INRIX points)
        best_geometry = None
        source_priority = {"here": 1, "osm": 2, "inrix": 3}
        
        polygon_lots = [lot for lot in cluster if lot.geometry is not None]
        if polygon_lots:
            # Sort by source priority
            polygon_lots.sort(key=lambda x: source_priority.get(x.source, 99))
            best_geometry = polygon_lots[0].geometry
        
        # Compute centroid
        if best_geometry:
            centroid = best_geometry.centroid
        else:
            # Average centroids from all lots in cluster
            avg_lng = sum(lot.centroid.x for lot in cluster) / len(cluster)
            avg_lat = sum(lot.centroid.y for lot in cluster) / len(cluster)
            centroid = Point(avg_lng, avg_lat)
        
        # Compute area
        if best_geometry:
            # Use geodesic area calculation (approximate)
            area_m2 = self._calculate_geodesic_area(best_geometry)
        else:
            # Default area for point-only lots (estimate based on typical parking lot)
            area_m2 = 1000.0  # Default 1000 m²
        
        area_sqft = area_m2 * 10.764
        
        # Collect source IDs
        inrix_id = None
        here_id = None
        osm_id = None
        data_sources = []
        
        for lot in cluster:
            if lot.source == "inrix" and lot.source_id:
                inrix_id = lot.source_id
                if "inrix" not in data_sources:
                    data_sources.append("inrix")
            elif lot.source == "here" and lot.source_id:
                here_id = lot.source_id
                if "here" not in data_sources:
                    data_sources.append("here")
            elif lot.source == "osm" and lot.source_id:
                osm_id = lot.source_id
                if "osm" not in data_sources:
                    data_sources.append("osm")
        
        # Pick best metadata (prefer non-null values)
        operator_name = None
        address = None
        surface_type = None
        raw_metadata = {}
        
        for lot in cluster:
            if lot.operator_name and not operator_name:
                operator_name = lot.operator_name
            if lot.address and not address:
                address = lot.address
            if lot.surface_type and not surface_type:
                surface_type = lot.surface_type
            if lot.raw_metadata:
                raw_metadata[lot.source] = lot.raw_metadata
        
        return NormalizedParkingLot(
            geometry=best_geometry,
            centroid=centroid,
            area_m2=area_m2,
            area_sqft=area_sqft,
            inrix_id=inrix_id,
            here_id=here_id,
            osm_id=osm_id,
            data_sources=data_sources,
            operator_name=operator_name,
            address=address,
            surface_type=surface_type,
            raw_metadata=raw_metadata if raw_metadata else None,
        )
    
    def _haversine_distance(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """Calculate distance between two points in meters using Haversine formula."""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371000  # Earth's radius in meters
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    def _calculate_geodesic_area(self, polygon: Polygon) -> float:
        """Calculate geodesic area of polygon in square meters."""
        from pyproj import Geod
        
        geod = Geod(ellps="WGS84")
        
        # Get exterior coordinates
        coords = list(polygon.exterior.coords)
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        
        # Calculate area
        area, _ = geod.polygon_area_perimeter(lons, lats)
        
        return abs(area)
    
    def save_to_database(
        self,
        normalized_lots: List[NormalizedParkingLot],
        user_id: uuid.UUID,
        db: Session
    ) -> List[ParkingLot]:
        """Save normalized parking lots to database."""
        saved_lots = []
        
        for lot in normalized_lots:
            try:
                db_lot = ParkingLot(
                    user_id=user_id,
                    geometry=from_shape(lot.geometry, srid=4326) if lot.geometry else None,
                    centroid=from_shape(lot.centroid, srid=4326),
                    area_m2=lot.area_m2,
                    area_sqft=lot.area_sqft,
                    inrix_id=lot.inrix_id,
                    here_id=lot.here_id,
                    osm_id=lot.osm_id,
                    data_sources=lot.data_sources or [],
                    operator_name=lot.operator_name,
                    address=lot.address,
                    surface_type=lot.surface_type,
                    raw_metadata=lot.raw_metadata,
                )
                db.add(db_lot)
                saved_lots.append(db_lot)
            except Exception as e:
                logger.error(f"Failed to save parking lot: {e}")
        
        db.commit()
        
        for lot in saved_lots:
            db.refresh(lot)
        
        return saved_lots


# Singleton instance
normalization_service = NormalizationService()

