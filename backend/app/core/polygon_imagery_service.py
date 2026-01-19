"""
PolygonImageryService - Fetches high-resolution satellite imagery for property polygons.

This service:
1. Takes a Shapely polygon (from Regrid)
2. Fetches satellite imagery via:
   - Google Static Maps API (best quality, requires API key, ~$2/1000 requests)
   - ESRI WorldImagery (free fallback)
3. Draws the polygon boundary on the image
4. Returns image ready for VLM analysis
"""

import contextily as ctx
from shapely.geometry import Polygon, MultiPolygon
from PIL import Image, ImageDraw
import numpy as np
from pyproj import Transformer
from typing import Tuple, Optional, Union
import io
import base64
import logging
import httpx
import math

from app.core.config import settings

logger = logging.getLogger(__name__)


class PolygonImageryService:
    """Service for fetching high-resolution satellite imagery of property polygons."""
    
    # ESRI satellite tiles - FREE and legitimate
    ESRI_TILES = ctx.providers.Esri.WorldImagery
    
    # Bing tiles as fallback
    BING_TILES = "https://ecn.t0.tiles.virtualearth.net/tiles/a{q}.jpeg?g=14038"
    
    # Default settings
    DEFAULT_ZOOM = 20  # High detail
    DEFAULT_BOUNDARY_COLOR = (255, 0, 0)  # Red
    DEFAULT_BOUNDARY_WIDTH = 4
    
    # Google Static Maps settings
    GOOGLE_STATIC_MAPS_URL = "https://maps.googleapis.com/maps/api/staticmap"
    GOOGLE_MAX_SIZE = 640  # Max size without premium (640x640)
    GOOGLE_PREMIUM_MAX_SIZE = 2048  # With premium plan
    
    def __init__(self):
        """Initialize the service."""
        # Transformer for converting lat/lng to Web Mercator
        self.transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        self._http_client = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client
    
    def get_polygon_image(
        self,
        polygon: Union[Polygon, MultiPolygon],
        zoom: int = None,
        draw_boundary: bool = True,
        boundary_color: Tuple[int, int, int] = None,
        boundary_width: int = None,
        padding_percent: float = 10.0,
        source: str = "google",  # Default to Google (best quality)
    ) -> Tuple[Image.Image, dict]:
        """
        Fetch high-resolution satellite image for a polygon (sync version).
        
        For Google Static Maps, use get_polygon_image_async instead.
        Falls back to ESRI for sync calls.
        """
        # For sync calls, use ESRI (contextily is sync)
        if source == "google":
            logger.info("Sync call - using ESRI instead of Google (use async for Google)")
            source = "esri"
        
        return self._fetch_with_contextily(
            polygon, zoom, draw_boundary, boundary_color, 
            boundary_width, padding_percent, source
        )
    
    async def get_polygon_image_async(
        self,
        polygon: Union[Polygon, MultiPolygon],
        zoom: int = None,
        draw_boundary: bool = True,
        boundary_color: Tuple[int, int, int] = None,
        boundary_width: int = None,
        padding_percent: float = 10.0,
        source: str = "google",  # Default to Google (best quality)
    ) -> Tuple[Image.Image, dict]:
        """
        Fetch high-resolution satellite image for a polygon (async version).
        
        Args:
            polygon: Shapely Polygon with coordinates in (lng, lat) format
            zoom: Tile zoom level (default: 20 for high detail)
            draw_boundary: Whether to draw the polygon boundary on the image
            boundary_color: RGB tuple for boundary color (default: red)
            boundary_width: Line width for boundary (default: 4)
            padding_percent: Extra padding around polygon (default: 10%)
            source: "google" (best quality, API key required), "esri" (free), "bing"
        
        Returns:
            Tuple of (PIL Image, metadata dict)
        """
        zoom = zoom or self.DEFAULT_ZOOM
        boundary_color = boundary_color or self.DEFAULT_BOUNDARY_COLOR
        boundary_width = boundary_width or self.DEFAULT_BOUNDARY_WIDTH
        
        # Handle MultiPolygon - use the largest polygon
        if isinstance(polygon, MultiPolygon):
            polygon = max(polygon.geoms, key=lambda p: p.area)
        
        # Try Google first if requested and API key available
        if source == "google" and settings.GOOGLE_MAPS_KEY:
            try:
                img, metadata = await self._fetch_google_static_maps(
                    polygon, zoom, padding_percent
                )
                
                # Draw boundary
                if draw_boundary:
                    # Calculate extent for boundary drawing
                    minx, miny, maxx, maxy = polygon.bounds
                    pad_x = (maxx - minx) * (padding_percent / 100)
                    pad_y = (maxy - miny) * (padding_percent / 100)
                    
                    # Convert bounds to Mercator for extent
                    left, bottom = self.transformer.transform(minx - pad_x, miny - pad_y)
                    right, top = self.transformer.transform(maxx + pad_x, maxy + pad_y)
                    extent = (left, right, bottom, top)
                    
                    img = self._draw_polygon_boundary(
                        img, polygon, extent, boundary_color, boundary_width
                    )
                
                metadata["boundary_drawn"] = draw_boundary
                return img, metadata
                
            except Exception as e:
                logger.warning(f"Google Static Maps failed: {e}, falling back to ESRI")
                source = "esri"
        
        # Fall back to contextily-based sources
        return self._fetch_with_contextily(
            polygon, zoom, draw_boundary, boundary_color,
            boundary_width, padding_percent, source
        )
    
    async def _fetch_google_static_maps(
        self,
        polygon: Polygon,
        zoom: int,
        padding_percent: float,
    ) -> Tuple[Image.Image, dict]:
        """
        Fetch satellite imagery using Google Static Maps API.
        
        This is the LEGITIMATE way to use Google satellite imagery.
        Cost: ~$2 per 1,000 requests (with $200 free monthly credit)
        """
        if not settings.GOOGLE_MAPS_KEY:
            raise ValueError("GOOGLE_MAPS_KEY not configured")
        
        # Get bounds with padding
        minx, miny, maxx, maxy = polygon.bounds
        width = maxx - minx
        height = maxy - miny
        pad_x = width * (padding_percent / 100)
        pad_y = height * (padding_percent / 100)
        
        # Calculate center point
        center_lng = (minx + maxx) / 2
        center_lat = (miny + maxy) / 2
        
        # Calculate optimal zoom to fit the polygon
        # Google zoom formula: at zoom N, pixel width = 256 * 2^N / 360 degrees
        padded_width = width + 2 * pad_x
        padded_height = height + 2 * pad_y
        
        # Use the specified zoom but cap based on bounds if needed
        actual_zoom = min(zoom, 21)  # Google max is 21
        
        # Request maximum size for best quality
        size = self.GOOGLE_MAX_SIZE
        
        # Build request URL
        params = {
            "center": f"{center_lat},{center_lng}",
            "zoom": actual_zoom,
            "size": f"{size}x{size}",
            "maptype": "satellite",
            "key": settings.GOOGLE_MAPS_KEY,
            "scale": 2,  # 2x resolution (1280x1280 actual)
        }
        
        logger.info(f"Fetching Google Static Maps: center={center_lat:.6f},{center_lng:.6f}, zoom={actual_zoom}")
        
        client = await self._get_client()
        response = await client.get(self.GOOGLE_STATIC_MAPS_URL, params=params)
        
        if response.status_code != 200:
            error_text = response.text[:200] if response.text else "Unknown error"
            raise Exception(f"Google Static Maps API error {response.status_code}: {error_text}")
        
        # Check for API error (returns image with error text)
        content_type = response.headers.get("content-type", "")
        if "image" not in content_type:
            raise Exception(f"Google API returned non-image: {response.text[:200]}")
        
        # Parse image
        img = Image.open(io.BytesIO(response.content))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        logger.info(f"Google Static Maps: {img.size[0]}x{img.size[1]} pixels")
        
        # Calculate extent in Web Mercator for boundary drawing
        # This is approximate since Google doesn't return exact bounds
        meters_per_pixel = 156543.03392 * math.cos(math.radians(center_lat)) / (2 ** actual_zoom)
        half_width_m = (img.size[0] / 2) * meters_per_pixel
        half_height_m = (img.size[1] / 2) * meters_per_pixel
        
        center_mx, center_my = self.transformer.transform(center_lng, center_lat)
        extent_left = center_mx - half_width_m
        extent_right = center_mx + half_width_m
        extent_bottom = center_my - half_height_m
        extent_top = center_my + half_height_m
        
        metadata = {
            "source": "google_static_maps",
            "zoom": actual_zoom,
            "image_width": img.size[0],
            "image_height": img.size[1],
            "bounds_lnglat": {
                "west": minx - pad_x,
                "south": miny - pad_y,
                "east": maxx + pad_x,
                "north": maxy + pad_y,
            },
            "bounds_mercator": {
                "left": extent_left,
                "right": extent_right,
                "bottom": extent_bottom,
                "top": extent_top,
            },
            "polygon_area_sqm": self._calculate_area_sqm(polygon),
            "api_cost_estimate": 0.002,  # ~$2 per 1000 requests
        }
        
        return img, metadata
    
    def _fetch_with_contextily(
        self,
        polygon: Union[Polygon, MultiPolygon],
        zoom: int,
        draw_boundary: bool,
        boundary_color: Tuple[int, int, int],
        boundary_width: int,
        padding_percent: float,
        source: str,
    ) -> Tuple[Image.Image, dict]:
        """Fetch imagery using contextily (ESRI/Bing tiles)."""
        zoom = zoom or self.DEFAULT_ZOOM
        boundary_color = boundary_color or self.DEFAULT_BOUNDARY_COLOR
        boundary_width = boundary_width or self.DEFAULT_BOUNDARY_WIDTH
        
        # Handle MultiPolygon
        if isinstance(polygon, MultiPolygon):
            polygon = max(polygon.geoms, key=lambda p: p.area)
        
        # Get bounds with padding
        minx, miny, maxx, maxy = polygon.bounds
        width = maxx - minx
        height = maxy - miny
        pad_x = width * (padding_percent / 100)
        pad_y = height * (padding_percent / 100)
        
        padded_bounds = (
            minx - pad_x,
            miny - pad_y,
            maxx + pad_x,
            maxy + pad_y,
        )
        
        # Select tile source
        tile_source = self._get_tile_source(source)
        
        logger.info(f"Fetching imagery ({source}) for polygon at zoom {zoom}")
        
        # Fetch tiles
        try:
            img_array, extent = ctx.bounds2img(
                padded_bounds[0], padded_bounds[1],
                padded_bounds[2], padded_bounds[3],
                zoom=zoom,
                source=tile_source,
                ll=True
            )
        except Exception as e:
            logger.warning(f"Failed with {source}, trying fallback: {e}")
            fallback_source = self.BING_TILES if source == "esri" else self.ESRI_TILES
            img_array, extent = ctx.bounds2img(
                padded_bounds[0], padded_bounds[1],
                padded_bounds[2], padded_bounds[3],
                zoom=zoom,
                source=fallback_source,
                ll=True
            )
        
        extent_left, extent_right, extent_bottom, extent_top = extent
        
        # Convert to PIL Image
        img = Image.fromarray(img_array)
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        logger.info(f"Image size: {img.size[0]}x{img.size[1]} pixels")
        
        # Draw boundary
        if draw_boundary:
            img = self._draw_polygon_boundary(
                img, polygon, extent, boundary_color, boundary_width
            )
        
        metadata = {
            "source": source,
            "zoom": zoom,
            "image_width": img.size[0],
            "image_height": img.size[1],
            "bounds_lnglat": {
                "west": padded_bounds[0],
                "south": padded_bounds[1],
                "east": padded_bounds[2],
                "north": padded_bounds[3],
            },
            "bounds_mercator": {
                "left": extent_left,
                "right": extent_right,
                "bottom": extent_bottom,
                "top": extent_top,
            },
            "polygon_area_sqm": self._calculate_area_sqm(polygon),
            "boundary_drawn": draw_boundary,
        }
        
        return img, metadata
    
    def get_polygon_image_base64(
        self,
        polygon: Union[Polygon, MultiPolygon],
        **kwargs
    ) -> Tuple[str, dict]:
        """Same as get_polygon_image but returns base64-encoded image."""
        img, metadata = self.get_polygon_image(polygon, **kwargs)
        
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=95)
        buffer.seek(0)
        
        base64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        metadata["format"] = "jpeg"
        metadata["base64_length"] = len(base64_str)
        
        return base64_str, metadata
    
    async def get_polygon_image_base64_async(
        self,
        polygon: Union[Polygon, MultiPolygon],
        **kwargs
    ) -> Tuple[str, dict]:
        """Async version - returns base64-encoded image."""
        img, metadata = await self.get_polygon_image_async(polygon, **kwargs)
        
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=95)
        buffer.seek(0)
        
        base64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        metadata["format"] = "jpeg"
        metadata["base64_length"] = len(base64_str)
        
        return base64_str, metadata
    
    def get_polygon_image_bytes(
        self,
        polygon: Union[Polygon, MultiPolygon],
        **kwargs
    ) -> Tuple[bytes, dict]:
        """Same as get_polygon_image but returns image bytes."""
        img, metadata = self.get_polygon_image(polygon, **kwargs)
        
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=95)
        buffer.seek(0)
        
        metadata["format"] = "jpeg"
        return buffer.getvalue(), metadata
    
    def _get_tile_source(self, source: str):
        """Get the tile source URL/provider."""
        sources = {
            "esri": self.ESRI_TILES,
            "bing": self.BING_TILES,
        }
        return sources.get(source.lower(), self.ESRI_TILES)
    
    def _draw_polygon_boundary(
        self,
        img: Image.Image,
        polygon: Polygon,
        extent: Tuple[float, float, float, float],
        color: Tuple[int, int, int],
        width: int,
    ) -> Image.Image:
        """Draw the polygon boundary on the image."""
        extent_left, extent_right, extent_bottom, extent_top = extent
        img_width, img_height = img.size
        
        coords = list(polygon.exterior.coords)
        
        # Convert each coordinate from lat/lng to pixel
        pixel_coords = []
        for lng, lat in coords:
            mx, my = self.transformer.transform(lng, lat)
            px = (mx - extent_left) / (extent_right - extent_left) * img_width
            py = (extent_top - my) / (extent_top - extent_bottom) * img_height
            pixel_coords.append((px, py))
        
        draw = ImageDraw.Draw(img)
        
        if len(pixel_coords) >= 3:
            draw.polygon(pixel_coords, outline=color, width=width)
            for i in range(len(pixel_coords)):
                start = pixel_coords[i]
                end = pixel_coords[(i + 1) % len(pixel_coords)]
                draw.line([start, end], fill=color, width=width)
        
        # Draw interior rings (holes)
        for interior in polygon.interiors:
            interior_coords = list(interior.coords)
            interior_pixel_coords = []
            for lng, lat in interior_coords:
                mx, my = self.transformer.transform(lng, lat)
                px = (mx - extent_left) / (extent_right - extent_left) * img_width
                py = (extent_top - my) / (extent_top - extent_bottom) * img_height
                interior_pixel_coords.append((px, py))
            
            for i in range(len(interior_pixel_coords)):
                start = interior_pixel_coords[i]
                end = interior_pixel_coords[(i + 1) % len(interior_pixel_coords)]
                draw.line([start, end], fill=color, width=width)
        
        return img
    
    def _calculate_area_sqm(self, polygon: Polygon) -> float:
        """Calculate approximate area in square meters."""
        coords = list(polygon.exterior.coords)
        mercator_coords = [self.transformer.transform(lng, lat) for lng, lat in coords]
        mercator_polygon = Polygon(mercator_coords)
        return mercator_polygon.area


# Singleton instance
_service_instance = None

def get_polygon_imagery_service() -> PolygonImageryService:
    """Get or create the singleton service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = PolygonImageryService()
    return _service_instance
