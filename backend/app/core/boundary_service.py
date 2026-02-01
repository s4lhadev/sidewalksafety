"""
Boundary Service - Load and serve US boundary data from KML files

Supports: states, counties, zip codes, urban areas

Features:
- Load KML files for states, counties, ZIP codes, urban areas
- Point-in-polygon lookup (find boundary containing a lat/lng)
- Search boundaries by name
- Get boundary by ID
- R-tree spatial index for fast intersection queries
"""

import os
import re
import logging
import time
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from functools import lru_cache
import xml.etree.ElementTree as ET

from shapely.geometry import shape, Point, Polygon, MultiPolygon
from shapely.prepared import prep

logger = logging.getLogger(__name__)

# KML namespace - use full namespace URI for ElementTree
KML_NS_URI = 'http://www.opengis.net/kml/2.2'
KML_NS = {'kml': KML_NS_URI}

def _ns(tag: str) -> str:
    """Add KML namespace to tag"""
    return f'{{{KML_NS_URI}}}{tag}'

@dataclass
class BoundaryInfo:
    """Info about a boundary layer"""
    id: str
    name: str
    file_path: str
    count: int = 0
    loaded: bool = False


class BoundaryService:
    """Service for loading and querying US boundary data from KML files"""
    
    # Path to KML files
    KML_DIR = Path(__file__).parent.parent.parent / "usakmls"
    
    BOUNDARY_TYPES = {
        "states": {
            "file": "states.kml",
            "name": "US States",
            "name_field": "NAME",
            "id_field": "GEOID"
        },
        "counties": {
            "file": "counties.kml",
            "name": "US Counties",
            "name_field": "NAME",
            "id_field": "GEOID"
        },
        "zips": {
            "file": "zips.kml",
            "name": "ZIP Codes",
            "name_field": "ZCTA5CE10",  # ZIP code field
            "id_field": "GEOID10"
        },
        "urban_areas": {
            "file": "urban_areas.kml",
            "name": "Urban Areas",
            "name_field": "NAME10",
            "id_field": "GEOID10"
        }
    }
    
    def __init__(self):
        self._cache: Dict[str, List[Dict]] = {}
        self._loaded: Dict[str, bool] = {}
        # Prepared geometries for fast intersection (use prepared instead of R-tree for reliability)
        self._prepared_geoms: Dict[str, List[Tuple[Any, int]]] = {}  # (prepared_geom, feature_idx)
        logger.info(f"BoundaryService initialized, KML dir: {self.KML_DIR}")
    
    def _build_prepared_geometries(self, layer_id: str) -> None:
        """Build prepared geometries for faster intersection tests"""
        if layer_id in self._prepared_geoms:
            return  # Already built
        
        features = self._cache.get(layer_id, [])
        if not features:
            logger.warning(f"No features to prepare for {layer_id}")
            return
        
        start = time.time()
        prepared = []
        
        for i, feature in enumerate(features):
            try:
                geom = shape(feature.get("geometry", {}))
                # Store both the geometry and prepared version with index
                prepared.append((geom, prep(geom), i))
            except Exception as e:
                continue
        
        if prepared:
            self._prepared_geoms[layer_id] = prepared
            elapsed = time.time() - start
            logger.info(f"Prepared {len(prepared)} geometries for {layer_id} in {elapsed:.2f}s")
        else:
            logger.warning(f"No valid geometries found for {layer_id}")
    
    def get_features_intersecting(self, layer_id: str, search_geometry) -> List[Dict]:
        """
        Get features that intersect with a geometry.
        Uses prepared geometries and bounding box pre-filter for speed.
        """
        # Ensure layer is loaded
        if layer_id not in self._cache:
            self.get_layer(layer_id)
        
        # Build prepared geometries if not done
        if layer_id not in self._prepared_geoms:
            self._build_prepared_geometries(layer_id)
        
        prepared_list = self._prepared_geoms.get(layer_id, [])
        features = self._cache.get(layer_id, [])
        
        if not prepared_list:
            logger.warning(f"No prepared geometries for {layer_id}")
            return []
        
        start = time.time()
        
        # Get search bounding box for quick pre-filter
        search_bounds = search_geometry.bounds  # (minx, miny, maxx, maxy)
        search_prep = prep(search_geometry)
        
        intersecting = []
        checked = 0
        bbox_filtered = 0
        
        for geom, geom_prep, idx in prepared_list:
            # Quick bounding box check first
            geom_bounds = geom.bounds
            if (geom_bounds[2] < search_bounds[0] or  # geom max_x < search min_x
                geom_bounds[0] > search_bounds[2] or  # geom min_x > search max_x
                geom_bounds[3] < search_bounds[1] or  # geom max_y < search min_y
                geom_bounds[1] > search_bounds[3]):   # geom min_y > search max_y
                bbox_filtered += 1
                continue
            
            checked += 1
            # Use prepared geometry for fast intersection test
            if search_prep.intersects(geom):
                if idx < len(features):
                    intersecting.append(features[idx])
        
        elapsed = time.time() - start
        logger.info(f"Intersection query: {len(prepared_list)} total, {bbox_filtered} bbox-filtered, {checked} checked, {len(intersecting)} found in {elapsed:.3f}s")
        
        return intersecting
    
    def preload_layer(self, layer_id: str) -> int:
        """Preload a layer into cache and build prepared geometries"""
        logger.info(f"Preloading layer: {layer_id}")
        start = time.time()
        
        result = self.get_layer(layer_id)
        count = len(result.get("features", []))
        
        # Build prepared geometries for zips (most queried)
        if layer_id == "zips" and count > 0:
            self._build_prepared_geometries(layer_id)
        
        elapsed = time.time() - start
        logger.info(f"Preloaded {layer_id}: {count} features in {elapsed:.2f}s")
        return count
    
    def get_available_layers(self) -> List[Dict[str, Any]]:
        """Get list of available boundary layers"""
        layers = []
        for layer_id, config in self.BOUNDARY_TYPES.items():
            file_path = self.KML_DIR / config["file"]
            exists = file_path.exists()
            size_mb = file_path.stat().st_size / (1024 * 1024) if exists else 0
            layers.append({
                "id": layer_id,
                "name": config["name"],
                "available": exists,
                "size_mb": round(size_mb, 1),
                "loaded": self._loaded.get(layer_id, False)
            })
        return layers
    
    def _parse_coordinates(self, coord_text: str) -> List[List[float]]:
        """Parse KML coordinate string to list of [lng, lat] pairs"""
        coords = []
        # KML format: lng,lat,altitude lng,lat,altitude ...
        for point in coord_text.strip().split():
            parts = point.split(',')
            if len(parts) >= 2:
                try:
                    lng = float(parts[0])
                    lat = float(parts[1])
                    coords.append([lng, lat])
                except ValueError:
                    continue
        return coords
    
    def _parse_polygon(self, polygon_elem: ET.Element) -> Optional[Dict]:
        """Parse a KML Polygon element to GeoJSON geometry"""
        outer_coords = None
        inner_coords = []
        
        # Get outer boundary - use full namespace path
        outer_boundary = polygon_elem.find(f'.//{_ns("outerBoundaryIs")}/{_ns("LinearRing")}/{_ns("coordinates")}')
        if outer_boundary is not None and outer_boundary.text:
            outer_coords = self._parse_coordinates(outer_boundary.text)
        
        if not outer_coords:
            return None
        
        # Get inner boundaries (holes)
        for inner_boundary in polygon_elem.findall(f'.//{_ns("innerBoundaryIs")}/{_ns("LinearRing")}/{_ns("coordinates")}'):
            if inner_boundary.text:
                inner = self._parse_coordinates(inner_boundary.text)
                if inner:
                    inner_coords.append(inner)
        
        # Build GeoJSON polygon
        coordinates = [outer_coords] + inner_coords
        return {
            "type": "Polygon",
            "coordinates": coordinates
        }
    
    def _parse_multigeometry(self, multigeom_elem: ET.Element) -> Optional[Dict]:
        """Parse a KML MultiGeometry element to GeoJSON MultiPolygon"""
        polygons = []
        
        for polygon_elem in multigeom_elem.findall(f'.//{_ns("Polygon")}'):
            polygon = self._parse_polygon(polygon_elem)
            if polygon:
                polygons.append(polygon["coordinates"])
        
        if not polygons:
            return None
        
        if len(polygons) == 1:
            return {
                "type": "Polygon",
                "coordinates": polygons[0]
            }
        
        return {
            "type": "MultiPolygon",
            "coordinates": polygons
        }
    
    def _extract_properties(self, placemark: ET.Element, config: Dict) -> Dict[str, Any]:
        """Extract properties from a Placemark element"""
        properties = {}
        
        # Get name from <name> element
        name_elem = placemark.find(_ns('name'))
        if name_elem is not None and name_elem.text:
            # Clean up the name (remove <at><openparen> formatting)
            name = name_elem.text
            name = re.sub(r'<[^>]+>', '', name)  # Remove XML-like tags in name
            properties['display_name'] = name
        
        # Get properties from ExtendedData/SchemaData
        for simple_data in placemark.findall(f'.//{_ns("SimpleData")}'):
            field_name = simple_data.get('name')
            if field_name and simple_data.text:
                properties[field_name] = simple_data.text
        
        # Set standard name and id fields
        name_field = config.get('name_field', 'NAME')
        id_field = config.get('id_field', 'GEOID')
        
        properties['name'] = properties.get(name_field, properties.get('display_name', 'Unknown'))
        properties['id'] = properties.get(id_field, '')
        
        return properties
    
    def _load_layer(self, layer_id: str) -> List[Dict]:
        """Load a boundary layer from KML file"""
        if layer_id not in self.BOUNDARY_TYPES:
            raise ValueError(f"Unknown boundary layer: {layer_id}")
        
        config = self.BOUNDARY_TYPES[layer_id]
        file_path = self.KML_DIR / config["file"]
        
        if not file_path.exists():
            logger.error(f"KML file not found: {file_path}")
            return []
        
        logger.info(f"Loading boundary layer: {layer_id} from {file_path}")
        
        features = []
        try:
            # Parse KML - use iterparse for large files
            context = ET.iterparse(str(file_path), events=('end',))
            placemark_tag = _ns('Placemark')
            
            for event, elem in context:
                if elem.tag == placemark_tag:
                    # Extract geometry
                    geometry = None
                    
                    # Check for MultiGeometry first
                    multigeom = elem.find(_ns('MultiGeometry'))
                    if multigeom is not None:
                        geometry = self._parse_multigeometry(multigeom)
                    else:
                        # Try single Polygon
                        polygon = elem.find(_ns('Polygon'))
                        if polygon is not None:
                            geometry = self._parse_polygon(polygon)
                    
                    if geometry:
                        properties = self._extract_properties(elem, config)
                        features.append({
                            "type": "Feature",
                            "properties": properties,
                            "geometry": geometry
                        })
                    
                    # Clear element to save memory
                    elem.clear()
            
            logger.info(f"Loaded {len(features)} features from {layer_id}")
            self._loaded[layer_id] = True
            
        except Exception as e:
            logger.error(f"Error loading {layer_id}: {e}", exc_info=True)
            return []
        
        return features
    
    def get_layer(self, layer_id: str, use_cache: bool = True) -> Dict[str, Any]:
        """Get a boundary layer as GeoJSON FeatureCollection"""
        if use_cache and layer_id in self._cache:
            features = self._cache[layer_id]
        else:
            features = self._load_layer(layer_id)
            if use_cache:
                self._cache[layer_id] = features
        
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
        all_features = self.get_layer(layer_id).get("features", [])
        
        filtered = []
        for feature in all_features:
            # Get centroid of first polygon coordinate
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [])
            
            if not coords:
                continue
            
            # Get first ring of first polygon
            if geom.get("type") == "MultiPolygon":
                first_ring = coords[0][0] if coords and coords[0] else []
            else:
                first_ring = coords[0] if coords else []
            
            if not first_ring:
                continue
            
            # Calculate centroid (simple average)
            lngs = [p[0] for p in first_ring]
            lats = [p[1] for p in first_ring]
            centroid_lng = sum(lngs) / len(lngs)
            centroid_lat = sum(lats) / len(lats)
            
            # Check if centroid is within bounds
            if (min_lng <= centroid_lng <= max_lng and 
                min_lat <= centroid_lat <= max_lat):
                filtered.append(feature)
                
                if len(filtered) >= limit:
                    break
        
        return {
            "type": "FeatureCollection",
            "features": filtered,
            "total_in_layer": len(all_features),
            "returned": len(filtered),
            "truncated": len(filtered) >= limit
        }
    
    def search_boundaries(
        self, 
        layer_id: str, 
        query: str, 
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search boundaries by name"""
        all_features = self.get_layer(layer_id).get("features", [])
        query_lower = query.lower()
        
        results = []
        for feature in all_features:
            props = feature.get("properties", {})
            name = props.get("name", "")
            
            if query_lower in name.lower():
                # Return simplified result (no geometry for search)
                results.append({
                    "id": props.get("id", ""),
                    "name": name,
                    "properties": props
                })
                
                if len(results) >= limit:
                    break
        
        return results
    
    def get_boundary_by_id(self, layer_id: str, boundary_id: str) -> Optional[Dict]:
        """Get a specific boundary by its ID"""
        all_features = self.get_layer(layer_id).get("features", [])
        
        for feature in all_features:
            props = feature.get("properties", {})
            if props.get("id") == boundary_id:
                return feature
        
        return None
    
    def get_boundary_at_point(
        self, 
        layer_id: str, 
        lat: float, 
        lng: float
    ) -> Optional[Dict]:
        """
        Find the boundary that contains a given point.
        
        Args:
            layer_id: 'states', 'counties', or 'zips'
            lat: Latitude
            lng: Longitude
            
        Returns:
            GeoJSON Feature containing the point, or None if not found
        """
        all_features = self.get_layer(layer_id).get("features", [])
        point = Point(lng, lat)  # Shapely uses (x, y) = (lng, lat)
        
        logger.info(f"Finding {layer_id} boundary at ({lat}, {lng})")
        
        for feature in all_features:
            geom_dict = feature.get("geometry", {})
            if not geom_dict:
                continue
            
            try:
                # Convert GeoJSON geometry to Shapely shape
                geom = shape(geom_dict)
                
                # Check if point is inside
                if geom.contains(point):
                    props = feature.get("properties", {})
                    logger.info(f"Found: {props.get('name', 'Unknown')}")
                    return feature
                    
            except Exception as e:
                # Skip invalid geometries
                continue
        
        logger.info(f"No {layer_id} boundary found at ({lat}, {lng})")
        return None
    
    def get_boundary_info_at_point(
        self,
        lat: float,
        lng: float
    ) -> Dict[str, Any]:
        """
        Get all boundary info at a point (ZIP, county, state).
        
        Returns dict with keys: zip, county, state (each has id, name, geometry)
        """
        result = {}
        
        # Find ZIP
        zip_feature = self.get_boundary_at_point("zips", lat, lng)
        if zip_feature:
            props = zip_feature.get("properties", {})
            result["zip"] = {
                "id": props.get("id", ""),
                "code": props.get("name", ""),  # ZIP code is stored in name
                "name": props.get("name", ""),
                "geometry": zip_feature.get("geometry")
            }
        
        # Find County
        county_feature = self.get_boundary_at_point("counties", lat, lng)
        if county_feature:
            props = county_feature.get("properties", {})
            result["county"] = {
                "id": props.get("id", ""),  # FIPS code
                "name": props.get("name", ""),
                "state_fips": props.get("STATEFP", ""),
                "geometry": county_feature.get("geometry")
            }
        
        # Find State
        state_feature = self.get_boundary_at_point("states", lat, lng)
        if state_feature:
            props = state_feature.get("properties", {})
            result["state"] = {
                "id": props.get("id", ""),  # State FIPS
                "name": props.get("name", ""),
                "geometry": state_feature.get("geometry")
            }
        
        return result
    
    def clear_cache(self, layer_id: Optional[str] = None):
        """Clear cached boundary data"""
        if layer_id:
            self._cache.pop(layer_id, None)
            self._loaded.pop(layer_id, None)
        else:
            self._cache.clear()
            self._loaded.clear()


# Singleton instance
_boundary_service: Optional[BoundaryService] = None

def get_boundary_service() -> BoundaryService:
    """Get the boundary service singleton"""
    global _boundary_service
    if _boundary_service is None:
        _boundary_service = BoundaryService()
    return _boundary_service
