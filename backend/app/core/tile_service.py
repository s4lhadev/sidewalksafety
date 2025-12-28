"""
TileService - Calculate tile grid for property coverage.

This service determines how to divide a property into high-resolution tiles
for comprehensive satellite imagery analysis.

Design Principles:
- Each tile is small enough for high-resolution imagery (zoom 19-20)
- Tiles cover the entire property boundary with slight overlap
- Tile count adapts to property size
"""

import math
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from shapely.geometry import Polygon, box, Point
from shapely.ops import unary_union

from app.core.config import settings


@dataclass
class Tile:
    """A single tile for analysis."""
    index: int
    center_lat: float
    center_lng: float
    zoom: int
    bounds: Dict[str, float]  # {min_lat, max_lat, min_lng, max_lng}
    width_m: float
    height_m: float
    
    @property
    def area_m2(self) -> float:
        return self.width_m * self.height_m


@dataclass
class TileGrid:
    """Complete tile grid for a property."""
    tiles: List[Tile]
    total_tiles: int
    rows: int
    cols: int
    zoom: int
    tile_size_m: float
    property_bounds: Dict[str, float]
    property_area_m2: float
    coverage_area_m2: float
    
    @property
    def estimated_api_calls(self) -> int:
        """Estimate number of API calls needed."""
        # 1 Google Maps call + 1-2 Roboflow calls per tile
        return self.total_tiles * 3


class TileService:
    """
    Calculate optimal tile grid for property coverage.
    
    The goal is to cover the entire property with high-resolution tiles
    while minimizing API calls and ensuring no gaps.
    """
    
    # Tile configuration
    DEFAULT_ZOOM = 19  # High resolution, ~1.5m per pixel
    MAX_ZOOM = 20  # Highest resolution, ~0.75m per pixel
    IMAGE_SIZE_PX = 640  # Google Maps Static API max size
    
    # Coverage settings
    TILE_OVERLAP_PERCENT = 10  # 10% overlap between tiles
    MAX_TILES_PER_PROPERTY = 100  # Safety limit
    
    def calculate_tile_grid(
        self,
        boundary: Polygon,
        zoom: Optional[int] = None,
        min_zoom: int = 18,
        max_zoom: int = 20
    ) -> TileGrid:
        """
        Calculate tile grid for a property boundary.
        
        Args:
            boundary: Property boundary polygon (WGS84)
            zoom: Fixed zoom level (if None, auto-calculate based on property size)
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            
        Returns:
            TileGrid with all tiles needed to cover the property
        """
        # Get property bounds
        bounds = boundary.bounds  # (minx, miny, maxx, maxy) = (min_lng, min_lat, max_lng, max_lat)
        min_lng, min_lat, max_lng, max_lat = bounds
        
        # Calculate property dimensions
        center_lat = (min_lat + max_lat) / 2
        width_m = self._haversine_distance(center_lat, min_lng, center_lat, max_lng)
        height_m = self._haversine_distance(min_lat, min_lng, max_lat, min_lng)
        property_area_m2 = width_m * height_m  # Approximate
        
        # Auto-calculate zoom if not specified
        if zoom is None:
            zoom = self._calculate_optimal_zoom(width_m, height_m, min_zoom, max_zoom)
        
        # Calculate tile size at this zoom level
        tile_size_m = self._tile_size_meters(center_lat, zoom)
        
        # Calculate effective tile size with overlap
        effective_tile_size_m = tile_size_m * (1 - self.TILE_OVERLAP_PERCENT / 100)
        
        # Calculate number of rows and columns
        cols = max(1, math.ceil(width_m / effective_tile_size_m))
        rows = max(1, math.ceil(height_m / effective_tile_size_m))
        
        # Safety check
        if rows * cols > self.MAX_TILES_PER_PROPERTY:
            # Reduce zoom to fit within limit
            zoom = self._reduce_zoom_to_fit(width_m, height_m, min_zoom)
            tile_size_m = self._tile_size_meters(center_lat, zoom)
            effective_tile_size_m = tile_size_m * (1 - self.TILE_OVERLAP_PERCENT / 100)
            cols = max(1, math.ceil(width_m / effective_tile_size_m))
            rows = max(1, math.ceil(height_m / effective_tile_size_m))
        
        # Generate tiles
        tiles = self._generate_tiles(
            min_lat, max_lat, min_lng, max_lng,
            rows, cols, zoom, tile_size_m, center_lat
        )
        
        # Filter tiles that actually intersect with property boundary
        tiles = [t for t in tiles if self._tile_intersects_boundary(t, boundary)]
        
        return TileGrid(
            tiles=tiles,
            total_tiles=len(tiles),
            rows=rows,
            cols=cols,
            zoom=zoom,
            tile_size_m=tile_size_m,
            property_bounds={
                "min_lat": min_lat,
                "max_lat": max_lat,
                "min_lng": min_lng,
                "max_lng": max_lng
            },
            property_area_m2=property_area_m2,
            coverage_area_m2=len(tiles) * tile_size_m * tile_size_m
        )
    
    def calculate_tiles_for_point(
        self,
        lat: float,
        lng: float,
        radius_m: float,
        zoom: int = 19
    ) -> TileGrid:
        """
        Calculate tiles for a circular area around a point.
        
        Useful when we don't have an exact boundary but know the approximate size.
        
        Args:
            lat: Center latitude
            lng: Center longitude
            radius_m: Radius in meters
            zoom: Zoom level
            
        Returns:
            TileGrid covering the circular area
        """
        # Create circular boundary
        boundary = self._create_circular_boundary(lat, lng, radius_m)
        return self.calculate_tile_grid(boundary, zoom=zoom)
    
    def estimate_property_radius(self, property_type: str) -> float:
        """
        Estimate property radius based on type.
        
        Used when we don't have boundary data.
        """
        estimates = {
            # Large properties (our target)
            "hoa": 400,  # 400m radius ~ 50 acres
            "homeowner_association": 400,
            "apartment_complex": 200,  # 200m radius ~ 12 acres
            "shopping_center": 300,  # 300m radius ~ 28 acres
            "shopping_mall": 400,
            "mobile_home_park": 300,
            "office_park": 250,
            "industrial_park": 350,
            "gated_community": 500,
            
            # Medium properties
            "hotel": 100,
            "school": 150,
            "church": 80,
            "hospital": 200,
            
            # Small properties (less interesting)
            "restaurant": 50,
            "retail": 40,
            "default": 100,
        }
        
        # Normalize property type
        normalized = property_type.lower().replace(" ", "_").replace("-", "_")
        
        return estimates.get(normalized, estimates["default"])
    
    def _generate_tiles(
        self,
        min_lat: float,
        max_lat: float,
        min_lng: float,
        max_lng: float,
        rows: int,
        cols: int,
        zoom: int,
        tile_size_m: float,
        center_lat: float
    ) -> List[Tile]:
        """Generate all tiles in the grid."""
        tiles = []
        
        # Calculate tile size in degrees
        tile_lat_deg = tile_size_m / 111000
        tile_lng_deg = tile_size_m / (111000 * math.cos(math.radians(center_lat)))
        
        # Effective size with overlap
        overlap = self.TILE_OVERLAP_PERCENT / 100
        step_lat = tile_lat_deg * (1 - overlap)
        step_lng = tile_lng_deg * (1 - overlap)
        
        # Starting position (center of first tile)
        start_lat = min_lat + tile_lat_deg / 2
        start_lng = min_lng + tile_lng_deg / 2
        
        index = 0
        for row in range(rows):
            for col in range(cols):
                center_lat = start_lat + row * step_lat
                center_lng = start_lng + col * step_lng
                
                tile = Tile(
                    index=index,
                    center_lat=center_lat,
                    center_lng=center_lng,
                    zoom=zoom,
                    bounds={
                        "min_lat": center_lat - tile_lat_deg / 2,
                        "max_lat": center_lat + tile_lat_deg / 2,
                        "min_lng": center_lng - tile_lng_deg / 2,
                        "max_lng": center_lng + tile_lng_deg / 2,
                    },
                    width_m=tile_size_m,
                    height_m=tile_size_m,
                )
                tiles.append(tile)
                index += 1
        
        return tiles
    
    def _tile_intersects_boundary(self, tile: Tile, boundary: Polygon) -> bool:
        """Check if a tile intersects with the property boundary."""
        tile_box = box(
            tile.bounds["min_lng"],
            tile.bounds["min_lat"],
            tile.bounds["max_lng"],
            tile.bounds["max_lat"]
        )
        return tile_box.intersects(boundary)
    
    def _calculate_optimal_zoom(
        self,
        width_m: float,
        height_m: float,
        min_zoom: int,
        max_zoom: int
    ) -> int:
        """
        Calculate optimal zoom level based on property size.
        
        Goal: Balance between resolution and number of tiles.
        """
        max_dim = max(width_m, height_m)
        
        # For large properties, use lower zoom to reduce tile count
        if max_dim > 800:
            return min_zoom
        elif max_dim > 400:
            return min(max_zoom, min_zoom + 1)
        else:
            return max_zoom
    
    def _reduce_zoom_to_fit(
        self,
        width_m: float,
        height_m: float,
        min_zoom: int
    ) -> int:
        """Reduce zoom level to fit within tile limit."""
        for zoom in range(self.MAX_ZOOM, min_zoom - 1, -1):
            tile_size = self._tile_size_meters(0, zoom)
            cols = math.ceil(width_m / tile_size)
            rows = math.ceil(height_m / tile_size)
            if rows * cols <= self.MAX_TILES_PER_PROPERTY:
                return zoom
        return min_zoom
    
    def _tile_size_meters(self, lat: float, zoom: int) -> float:
        """
        Calculate tile size in meters at a given zoom level.
        
        At zoom 20, each pixel is ~0.15m (at equator)
        Image size is 640x640, so tile covers ~96m x 96m
        """
        # Meters per pixel at equator at zoom 0
        meters_per_pixel_z0 = 156543.03
        
        # Adjust for zoom and latitude
        meters_per_pixel = meters_per_pixel_z0 * math.cos(math.radians(lat)) / (2 ** zoom)
        
        # Tile size = pixels * meters per pixel
        return self.IMAGE_SIZE_PX * meters_per_pixel
    
    def _haversine_distance(
        self,
        lat1: float,
        lng1: float,
        lat2: float,
        lng2: float
    ) -> float:
        """Calculate distance between two points in meters."""
        R = 6371000  # Earth's radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def _create_circular_boundary(
        self,
        lat: float,
        lng: float,
        radius_m: float,
        num_points: int = 32
    ) -> Polygon:
        """Create a circular polygon boundary."""
        points = []
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            
            # Calculate offset in degrees
            lat_offset = (radius_m * math.cos(angle)) / 111000
            lng_offset = (radius_m * math.sin(angle)) / (111000 * math.cos(math.radians(lat)))
            
            points.append((lng + lng_offset, lat + lat_offset))
        
        points.append(points[0])  # Close the polygon
        return Polygon(points)


# Singleton instance
tile_service = TileService()

