"""
Boundary Service - Load and serve US boundary data from PostGIS

Supports: states, counties, zip codes, urban areas

Features:
- Query PostGIS for boundary data (no KML files needed!)
- Point-in-polygon lookup using spatial index
- Search boundaries by name
- Get boundary by ID
"""

import logging
from typing import Optional, Dict, List, Any
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.base import SessionLocal, engine
from app.core.config import settings

logger = logging.getLogger(__name__)

# Map API layer names to database boundary_type values
LAYER_TO_DB_TYPE = {
    "states": "state",
    "counties": "county",
    "zips": "zip",
    "urban_areas": "urban_area",
}

DB_TYPE_TO_LAYER = {v: k for k, v in LAYER_TO_DB_TYPE.items()}


class BoundaryService:
    """Service for loading and querying US boundary data from PostGIS"""
    
    def __init__(self):
        self.schema = settings.DB_SCHEMA
        logger.info(f"BoundaryService initialized with PostGIS (schema: {self.schema})")
    
    def _get_db(self) -> Session:
        """Get a database session"""
        return SessionLocal()
    
    def get_available_layers(self) -> List[Dict[str, Any]]:
        """Get list of available boundary layers with counts"""
        layers = []
        
        with self._get_db() as db:
            for layer_id, db_type in LAYER_TO_DB_TYPE.items():
                result = db.execute(
                    text(f"""
                        SELECT COUNT(*) as count 
                        FROM {self.schema}.boundaries 
                        WHERE boundary_type = :type
                    """),
                    {"type": db_type}
                ).fetchone()
                
                count = result[0] if result else 0
                layers.append({
                    "id": layer_id,
                    "name": layer_id.replace("_", " ").title(),
                    "available": count > 0,
                    "count": count,
                    "loaded": True  # Always loaded in DB
                })
        
        return layers
    
    def preload_layer(self, layer_id: str) -> int:
        """No-op for PostGIS - data is already in DB"""
        # Just return count for compatibility
        with self._get_db() as db:
            db_type = LAYER_TO_DB_TYPE.get(layer_id, layer_id)
            result = db.execute(
                text(f"SELECT COUNT(*) FROM {self.schema}.boundaries WHERE boundary_type = :type"),
                {"type": db_type}
            ).fetchone()
            return result[0] if result else 0
    
    def get_layer(self, layer_id: str, use_cache: bool = True) -> Dict[str, Any]:
        """Get a boundary layer as GeoJSON FeatureCollection"""
        db_type = LAYER_TO_DB_TYPE.get(layer_id, layer_id)
        
        with self._get_db() as db:
            result = db.execute(
                text(f"""
                    SELECT 
                        id, name, code, geoid,
                        ST_AsGeoJSON(geometry)::json as geometry
                    FROM {self.schema}.boundaries 
                    WHERE boundary_type = :type
                    LIMIT 10000
                """),
                {"type": db_type}
            ).fetchall()
            
            features = []
            for row in result:
                features.append({
                    "type": "Feature",
                    "properties": {
                        "id": row[2] or row[3] or str(row[0]),  # code, geoid, or db id
                        "name": row[1],
                        "code": row[2],
                        "geoid": row[3],
                    },
                    "geometry": row[4]
                })
        
        return {
            "type": "FeatureCollection",
            "features": features
        }
    
    def get_layer_within_bounds(
        self, 
        layer_id: str, 
        min_lng: float, 
        min_lat: float, 
        max_lng: float, 
        max_lat: float,
        limit: int = 500
    ) -> Dict[str, Any]:
        """Get boundary features within a bounding box"""
        db_type = LAYER_TO_DB_TYPE.get(layer_id, layer_id)
        
        with self._get_db() as db:
            # Use spatial index for fast bbox query
            result = db.execute(
                text(f"""
                    SELECT 
                        id, name, code, geoid,
                        ST_AsGeoJSON(geometry)::json as geometry
                    FROM {self.schema}.boundaries 
                    WHERE boundary_type = :type
                      AND geometry && ST_MakeEnvelope(:min_lng, :min_lat, :max_lng, :max_lat, 4326)
                    LIMIT :limit
                """),
                {
                    "type": db_type,
                    "min_lng": min_lng,
                    "min_lat": min_lat,
                    "max_lng": max_lng,
                    "max_lat": max_lat,
                    "limit": limit
                }
            ).fetchall()
            
            features = []
            for row in result:
                features.append({
                    "type": "Feature",
                    "properties": {
                        "id": row[2] or row[3] or str(row[0]),
                        "name": row[1],
                        "code": row[2],
                        "geoid": row[3],
                    },
                    "geometry": row[4]
                })
            
            # Get total count
            total_result = db.execute(
                text(f"SELECT COUNT(*) FROM {self.schema}.boundaries WHERE boundary_type = :type"),
                {"type": db_type}
            ).fetchone()
            total = total_result[0] if total_result else 0
        
        return {
            "type": "FeatureCollection",
            "features": features,
            "total_in_layer": total,
            "returned": len(features),
            "truncated": len(features) >= limit
        }
    
    def search_boundaries(
        self, 
        layer_id: str, 
        query: str, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search boundaries by name"""
        db_type = LAYER_TO_DB_TYPE.get(layer_id, layer_id)
        
        with self._get_db() as db:
            result = db.execute(
                text(f"""
                    SELECT id, name, code, geoid
                    FROM {self.schema}.boundaries 
                    WHERE boundary_type = :type
                      AND (name ILIKE :query OR code ILIKE :query)
                    LIMIT :limit
                """),
                {
                    "type": db_type,
                    "query": f"%{query}%",
                    "limit": limit
                }
            ).fetchall()
            
            return [
                {
                    "id": row[2] or row[3] or str(row[0]),
                    "name": row[1],
                    "properties": {
                        "id": row[2] or row[3] or str(row[0]),
                        "name": row[1],
                        "code": row[2],
                        "geoid": row[3],
                    }
                }
                for row in result
            ]
    
    def get_boundary_by_id(self, layer_id: str, boundary_id: str) -> Optional[Dict]:
        """Get a specific boundary by its ID/code"""
        db_type = LAYER_TO_DB_TYPE.get(layer_id, layer_id)
        
        with self._get_db() as db:
            result = db.execute(
                text(f"""
                    SELECT 
                        id, name, code, geoid,
                        ST_AsGeoJSON(geometry)::json as geometry
                    FROM {self.schema}.boundaries 
                    WHERE boundary_type = :type
                      AND (code = :boundary_id OR geoid = :boundary_id)
                    LIMIT 1
                """),
                {"type": db_type, "boundary_id": boundary_id}
            ).fetchone()
            
            if not result:
                return None
            
            return {
                "type": "Feature",
                "properties": {
                    "id": result[2] or result[3] or str(result[0]),
                    "name": result[1],
                    "code": result[2],
                    "geoid": result[3],
                },
                "geometry": result[4]
            }
    
    def get_boundary_at_point(
        self, 
        layer_id: str, 
        lat: float, 
        lng: float
    ) -> Optional[Dict]:
        """
        Find the boundary that contains a given point.
        Uses PostGIS spatial index for fast lookup.
        """
        db_type = LAYER_TO_DB_TYPE.get(layer_id, layer_id)
        
        with self._get_db() as db:
            result = db.execute(
                text(f"""
                    SELECT 
                        id, name, code, geoid,
                        ST_AsGeoJSON(geometry)::json as geometry
                    FROM {self.schema}.boundaries 
                    WHERE boundary_type = :type
                      AND ST_Contains(geometry, ST_SetSRID(ST_Point(:lng, :lat), 4326))
                    LIMIT 1
                """),
                {"type": db_type, "lat": lat, "lng": lng}
            ).fetchone()
            
            if not result:
                logger.debug(f"No {layer_id} boundary found at ({lat}, {lng})")
                return None
            
            logger.debug(f"Found {layer_id}: {result[1]} at ({lat}, {lng})")
            
            return {
                "type": "Feature",
                "properties": {
                    "id": result[2] or result[3] or str(result[0]),
                    "name": result[1],
                    "code": result[2],
                    "geoid": result[3],
                },
                "geometry": result[4]
            }
    
    def get_boundary_info_at_point(
        self,
        lat: float,
        lng: float
    ) -> Dict[str, Any]:
        """
        Get all boundary info at a point (ZIP, county, state).
        Single optimized query using PostGIS.
        """
        result = {}
        
        # Find ZIP
        zip_feature = self.get_boundary_at_point("zips", lat, lng)
        if zip_feature:
            props = zip_feature.get("properties", {})
            result["zip"] = {
                "id": props.get("id", ""),
                "code": props.get("name", ""),
                "name": props.get("name", ""),
                "geometry": zip_feature.get("geometry")
            }
        
        # Find County
        county_feature = self.get_boundary_at_point("counties", lat, lng)
        if county_feature:
            props = county_feature.get("properties", {})
            result["county"] = {
                "id": props.get("id", ""),
                "name": props.get("name", ""),
                "geometry": county_feature.get("geometry")
            }
        
        # Find State
        state_feature = self.get_boundary_at_point("states", lat, lng)
        if state_feature:
            props = state_feature.get("properties", {})
            result["state"] = {
                "id": props.get("id", ""),
                "name": props.get("name", ""),
                "geometry": state_feature.get("geometry")
            }
        
        return result
    
    def get_features_intersecting(self, layer_id: str, search_geometry) -> List[Dict]:
        """
        Get features that intersect with a geometry.
        Uses PostGIS spatial index.
        """
        from shapely.geometry import mapping
        import json
        
        db_type = LAYER_TO_DB_TYPE.get(layer_id, layer_id)
        geojson = json.dumps(mapping(search_geometry))
        
        with self._get_db() as db:
            result = db.execute(
                text(f"""
                    SELECT 
                        id, name, code, geoid,
                        ST_AsGeoJSON(geometry)::json as geometry
                    FROM {self.schema}.boundaries 
                    WHERE boundary_type = :type
                      AND ST_Intersects(geometry, ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326))
                """),
                {"type": db_type, "geojson": geojson}
            ).fetchall()
            
            return [
                {
                    "type": "Feature",
                    "properties": {
                        "id": row[2] or row[3] or str(row[0]),
                        "name": row[1],
                        "code": row[2],
                        "geoid": row[3],
                    },
                    "geometry": row[4]
                }
                for row in result
            ]
    
    def clear_cache(self, layer_id: Optional[str] = None):
        """No-op for PostGIS - no caching needed"""
        pass


# Singleton instance
_boundary_service: Optional[BoundaryService] = None

def get_boundary_service() -> BoundaryService:
    """Get the boundary service singleton"""
    global _boundary_service
    if _boundary_service is None:
        _boundary_service = BoundaryService()
    return _boundary_service
