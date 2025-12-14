import logging
import httpx
import boto3
from typing import Optional, Tuple, List
from shapely.geometry import Polygon
import uuid
from datetime import datetime
import math
import io

from PIL import Image, ImageDraw

from app.core.config import settings

logger = logging.getLogger(__name__)


class ImageryService:
    """
    Service to fetch satellite imagery for parking lots using Google Maps Static API.
    
    Uses center + zoom approach with scale=2 for maximum resolution.
    Calculates optimal zoom level to fill the image with the parking lot.
    """
    
    # Google Maps Static API limits
    MAX_SIZE = 640  # Max dimension (with scale=2, returns 1280x1280)
    TILE_SIZE = 256  # Google Maps tile size
    
    # Buffer around parking lot (5% for tight framing)
    DEFAULT_BUFFER_PERCENT = 0.05
    
    def __init__(self):
        self.google_key = settings.GOOGLE_MAPS_KEY
        
        # Object storage
        self.supabase_storage_url = settings.SUPABASE_STORAGE_URL
        self.supabase_storage_key = settings.SUPABASE_STORAGE_KEY
        self.s3_bucket = settings.AWS_S3_BUCKET
        
        # Initialize S3 client if configured
        self.s3_client = None
        if self.s3_bucket and settings.AWS_ACCESS_KEY_ID:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
            )
    
    async def fetch_imagery_for_parking_lot(
        self,
        parking_lot_id: uuid.UUID,
        centroid_lat: float,
        centroid_lng: float,
        polygon: Optional[Polygon] = None,
        area_m2: Optional[float] = None,
        buffer_percent: float = None
    ) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
        """
        Fetch satellite imagery for a parking lot.
        
        Uses center + zoom approach with scale=2 for maximum resolution.
        Calculates optimal zoom level so parking lot fills ~90% of image.
        
        Args:
            parking_lot_id: Unique identifier for the parking lot
            centroid_lat: Latitude of parking lot centroid
            centroid_lng: Longitude of parking lot centroid
            polygon: Shapely Polygon geometry of the parking lot
            area_m2: Area of parking lot in square meters
            buffer_percent: Buffer around lot (default 5%)
        
        Returns:
            Tuple of (image_bytes, storage_path, image_url)
        """
        if not self.google_key:
            logger.warning("Google Maps API key not configured")
            return None, None, None
        
        if buffer_percent is None:
            buffer_percent = self.DEFAULT_BUFFER_PERCENT
        
        try:
            if polygon and not polygon.is_empty:
                # Calculate from polygon geometry
                center_lat, center_lng, zoom = self._calculate_center_and_zoom_from_polygon(
                    polygon, buffer_percent
                )
                
                logger.info(
                    f"Fetching imagery for lot {parking_lot_id}: "
                    f"center=({center_lat:.6f}, {center_lng:.6f}), zoom={zoom}"
                )
                
            elif area_m2:
                # Estimate from area (assume square-ish lot)
                center_lat = centroid_lat
                center_lng = centroid_lng
                zoom = self._calculate_zoom_from_area(area_m2, center_lat, buffer_percent)
                
                logger.info(
                    f"Fetching imagery for lot {parking_lot_id} (area-based): "
                    f"center=({center_lat:.6f}, {center_lng:.6f}), zoom={zoom}, area={area_m2:.0f}m²"
                )
            else:
                logger.warning(
                    f"No polygon or area for lot {parking_lot_id}, cannot fetch accurate imagery"
                )
                return None, None, None
            
            # Fetch image with calculated parameters
            image_bytes = await self._fetch_satellite_image(center_lat, center_lng, zoom)
            
            if image_bytes:
                logger.info(f"Fetched imagery for lot {parking_lot_id}: {len(image_bytes)/1024:.1f} KB")
                
                # Determine polygon for overlay
                overlay_polygon = polygon if (polygon and not polygon.is_empty) else None
                
                # If no polygon but we have area, create estimated square polygon
                if overlay_polygon is None and area_m2:
                    overlay_polygon = self._create_estimated_polygon(
                        center_lat, center_lng, area_m2
                    )
                    logger.info(f"Created estimated polygon for lot {parking_lot_id} from area")
                
                # Add polygon overlay
                if overlay_polygon:
                    image_bytes = self._add_polygon_overlay(
                        image_bytes, overlay_polygon, center_lat, center_lng, zoom
                    )
                    logger.info(f"Added polygon overlay for lot {parking_lot_id}")
                
                # Store image if storage is configured
                storage_path, image_url = await self._store_image(image_bytes, parking_lot_id)
                
                # If no storage, generate direct URL
                if not image_url:
                    image_url = self._build_static_map_url(center_lat, center_lng, zoom)
                
                return image_bytes, storage_path, image_url
            
        except Exception as e:
            logger.error(f"Failed to fetch imagery for lot {parking_lot_id}: {e}", exc_info=True)
        
        return None, None, None
    
    def _calculate_center_and_zoom_from_polygon(
        self,
        polygon: Polygon,
        buffer_percent: float = 0.05
    ) -> Tuple[float, float, int]:
        """
        Calculate center point and optimal zoom level from polygon.
        
        Uses the formula: zoom = log2(image_size / (256 * max_range))
        This ensures the parking lot fills most of the image.
        
        Args:
            polygon: Shapely Polygon geometry
            buffer_percent: Buffer around lot (default 5%)
        
        Returns:
            Tuple of (center_lat, center_lng, zoom_level)
        """
        # Get bounding box: (minx, miny, maxx, maxy) = (min_lng, min_lat, max_lng, max_lat)
        bounds = polygon.bounds
        min_lng, min_lat, max_lng, max_lat = bounds
        
        # Calculate center from polygon centroid (more accurate)
        centroid = polygon.centroid
        center_lat = centroid.y
        center_lng = centroid.x
        
        # Calculate ranges
        lat_range = max_lat - min_lat
        lng_range = max_lng - min_lng
        
        # Add buffer (default 5%)
        lat_range_buffered = lat_range * (1 + 2 * buffer_percent)
        lng_range_buffered = lng_range * (1 + 2 * buffer_percent)
        
        # Adjust longitude range for latitude (mercator projection)
        lng_range_adjusted = lng_range_buffered * math.cos(math.radians(center_lat))
        
        # Use the larger range to ensure everything fits
        max_range = max(lat_range_buffered, lng_range_adjusted)
        
        # Calculate zoom level
        # Formula: At zoom z, 1 degree = 256 * 2^z / 360 pixels
        # We want: max_range degrees fits in image_size pixels
        # image_size = max_range * 256 * 2^z / 360
        # Solving: 2^z = image_size * 360 / (256 * max_range)
        # z = log2(image_size * 360 / (256 * max_range))
        
        if max_range <= 0:
            zoom = 20  # Default for very small/point geometries
        else:
            # Use MAX_SIZE (640) as the image dimension
            # With scale=2, we get 1280 actual pixels
            zoom_float = math.log2(self.MAX_SIZE * 360 / (self.TILE_SIZE * max_range))
            zoom = int(math.floor(zoom_float))
        
        # Clamp to valid range (15-20 for satellite imagery)
        zoom = max(15, min(20, zoom))
        
        logger.debug(
            f"Polygon bounds: lat=[{min_lat:.6f}, {max_lat:.6f}], "
            f"lng=[{min_lng:.6f}, {max_lng:.6f}], "
            f"range={max_range:.6f}°, zoom={zoom}"
        )
        
        return center_lat, center_lng, zoom
    
    def _calculate_zoom_from_area(
        self,
        area_m2: float,
        center_lat: float,
        buffer_percent: float = 0.05
    ) -> int:
        """
        Estimate optimal zoom level from parking lot area.
        
        Assumes roughly square parking lot and calculates zoom
        based on estimated side length.
        
        Args:
            area_m2: Parking lot area in square meters
            center_lat: Latitude for mercator correction
            buffer_percent: Buffer around lot (default 5%)
        
        Returns:
            Optimal zoom level (15-20)
        """
        # Estimate side length from area (assume square)
        side_length_m = math.sqrt(area_m2)
        
        # Add buffer
        total_size_m = side_length_m * (1 + 2 * buffer_percent)
        
        # Convert meters to degrees (approximate)
        # 1 degree latitude ≈ 111,000 meters
        size_degrees = total_size_m / 111000.0
        
        # Calculate zoom using same formula
        if size_degrees <= 0:
            zoom = 20
        else:
            zoom_float = math.log2(self.MAX_SIZE * 360 / (self.TILE_SIZE * size_degrees))
            zoom = int(math.floor(zoom_float))
        
        # Clamp to valid range
        zoom = max(15, min(20, zoom))
        
        return zoom
    
    def _create_estimated_polygon(
        self,
        center_lat: float,
        center_lng: float,
        area_m2: float
    ) -> Polygon:
        """
        Create an estimated square polygon from centroid and area.
        
        Used when actual polygon geometry is not available but we have
        the parking lot's area. Creates a square centered on the centroid.
        
        Args:
            center_lat: Center latitude
            center_lng: Center longitude
            area_m2: Area in square meters
        
        Returns:
            Shapely Polygon representing estimated parking lot bounds
        """
        # Calculate side length of equivalent square
        side_length_m = math.sqrt(area_m2)
        
        # Convert to degrees (approximate)
        # 1 degree latitude ≈ 111,000 meters
        half_lat = (side_length_m / 2) / 111000.0
        
        # Longitude degrees vary with latitude
        half_lng = (side_length_m / 2) / (111000.0 * math.cos(math.radians(center_lat)))
        
        # Create square polygon
        min_lat = center_lat - half_lat
        max_lat = center_lat + half_lat
        min_lng = center_lng - half_lng
        max_lng = center_lng + half_lng
        
        # Return polygon (note: Polygon takes [(lng, lat), ...] order)
        return Polygon([
            (min_lng, min_lat),
            (max_lng, min_lat),
            (max_lng, max_lat),
            (min_lng, max_lat),
            (min_lng, min_lat),  # Close the polygon
        ])
    
    def _latlon_to_pixel(
        self,
        lat: float,
        lng: float,
        center_lat: float,
        center_lng: float,
        zoom: int,
        image_size: int
    ) -> Tuple[int, int]:
        """
        Convert lat/lng coordinates to pixel coordinates on the image.
        
        Uses Mercator projection formula to calculate pixel position
        relative to the image center.
        
        Args:
            lat: Latitude to convert
            lng: Longitude to convert
            center_lat: Center latitude of the image
            center_lng: Center longitude of the image
            zoom: Zoom level
            image_size: Image dimension in pixels (assumes square)
        
        Returns:
            Tuple of (x, y) pixel coordinates
        """
        # Scale factor for the zoom level
        scale = 2 ** zoom
        
        # Convert to world coordinates (Mercator projection)
        # World coordinates range from 0 to 256 at zoom 0
        def lat_to_world_y(lat_deg: float) -> float:
            lat_rad = math.radians(lat_deg)
            return (1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * 256
        
        def lng_to_world_x(lng_deg: float) -> float:
            return (lng_deg + 180) / 360 * 256
        
        # Calculate world coordinates for point and center
        world_x = lng_to_world_x(lng) * scale
        world_y = lat_to_world_y(lat) * scale
        center_world_x = lng_to_world_x(center_lng) * scale
        center_world_y = lat_to_world_y(center_lat) * scale
        
        # Calculate pixel offset from center
        pixel_x = int((world_x - center_world_x) + image_size / 2)
        pixel_y = int((world_y - center_world_y) + image_size / 2)
        
        return pixel_x, pixel_y
    
    def _add_polygon_overlay(
        self,
        image_bytes: bytes,
        polygon: Polygon,
        center_lat: float,
        center_lng: float,
        zoom: int
    ) -> bytes:
        """
        Add a semi-transparent polygon overlay to highlight the parking lot.
        
        Draws the parking lot boundary with a colored fill and outline
        to clearly show which area is the parking lot vs streets/buildings.
        
        Args:
            image_bytes: Original satellite image bytes
            polygon: Shapely Polygon geometry
            center_lat: Center latitude of the image
            center_lng: Center longitude of the image
            zoom: Zoom level used for the image
        
        Returns:
            Modified image bytes with polygon overlay
        """
        try:
            # Load image
            image = Image.open(io.BytesIO(image_bytes))
            image_size = image.width  # Assumes square image (1280x1280)
            
            # Convert polygon coordinates to pixel coordinates
            exterior_coords = list(polygon.exterior.coords)
            pixel_coords = [
                self._latlon_to_pixel(lat, lng, center_lat, center_lng, zoom, image_size)
                for lng, lat in exterior_coords  # Note: shapely uses (lng, lat) order
            ]
            
            # Create overlay layer with transparency
            overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            # Draw semi-transparent fill (cyan/teal with 25% opacity)
            fill_color = (0, 200, 200, 64)  # RGBA: cyan with alpha
            draw.polygon(pixel_coords, fill=fill_color)
            
            # Draw outline (bright cyan, 3px width)
            outline_color = (0, 255, 255, 255)  # Solid cyan
            draw.line(pixel_coords + [pixel_coords[0]], fill=outline_color, width=3)
            
            # Composite overlay onto original image
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            result = Image.alpha_composite(image, overlay)
            
            # Convert back to RGB for JPEG
            result = result.convert('RGB')
            
            # Save to bytes
            output = io.BytesIO()
            result.save(output, format='JPEG', quality=95)
            output.seek(0)
            
            return output.read()
            
        except Exception as e:
            logger.error(f"Failed to add polygon overlay: {e}", exc_info=True)
            # Return original image if overlay fails
            return image_bytes
    
    async def _fetch_satellite_image(
        self,
        lat: float,
        lng: float,
        zoom: int
    ) -> Optional[bytes]:
        """
        Fetch satellite image from Google Maps Static API.
        
        Uses scale=2 for maximum resolution (1280x1280 actual pixels).
        
        Args:
            lat: Center latitude
            lng: Center longitude
            zoom: Zoom level (15-20)
        
        Returns:
            Image bytes or None if failed
        """
        if not self.google_key:
            return None
        
        url = "https://maps.googleapis.com/maps/api/staticmap"
        
        params = {
            "center": f"{lat},{lng}",
            "zoom": zoom,
            "size": f"{self.MAX_SIZE}x{self.MAX_SIZE}",  # 640x640
            "scale": 2,  # Returns 1280x1280 actual pixels
            "maptype": "satellite",
            "key": self.google_key,
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                return response.content
            
            # Log detailed error
            error_text = response.text[:500] if response.text else str(response.content[:500])
            logger.error(f"Google Maps API returned {response.status_code}: {error_text}")
            
            if response.status_code == 403:
                logger.error(
                    "Google Maps API 403 - Check: "
                    "1) Static Maps API enabled? "
                    "2) Billing enabled? "
                    "3) API key restrictions?"
                )
            
            return None
    
    def _build_static_map_url(
        self,
        lat: float,
        lng: float,
        zoom: int
    ) -> str:
        """
        Build a static map URL for direct access.
        
        Args:
            lat: Center latitude
            lng: Center longitude
            zoom: Zoom level
        
        Returns:
            Google Maps Static API URL
        """
        return (
            f"https://maps.googleapis.com/maps/api/staticmap"
            f"?center={lat},{lng}"
            f"&zoom={zoom}"
            f"&size={self.MAX_SIZE}x{self.MAX_SIZE}"
            f"&scale=2"
            f"&maptype=satellite"
            f"&key={self.google_key}"
        )
    
    async def _store_image(
        self,
        image_bytes: bytes,
        parking_lot_id: uuid.UUID
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Store image in object storage (Supabase or S3).
        
        Args:
            image_bytes: Image data
            parking_lot_id: Parking lot identifier
        
        Returns:
            Tuple of (storage_path, public_url) or (None, None) if no storage
        """
        filename = f"parking_lots/{parking_lot_id}/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jpg"
        
        # Try Supabase Storage first
        if self.supabase_storage_url and self.supabase_storage_key:
            try:
                url = f"{self.supabase_storage_url}/object/parking-lot-images/{filename}"
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        url,
                        content=image_bytes,
                        headers={
                            "Authorization": f"Bearer {self.supabase_storage_key}",
                            "Content-Type": "image/jpeg",
                        }
                    )
                    
                    if response.status_code in [200, 201]:
                        public_url = f"{self.supabase_storage_url}/object/public/parking-lot-images/{filename}"
                        return filename, public_url
                        
            except Exception as e:
                logger.warning(f"Supabase storage failed: {e}")
        
        # Try S3
        if self.s3_client and self.s3_bucket:
            try:
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=filename,
                    Body=image_bytes,
                    ContentType="image/jpeg",
                )
                
                public_url = f"https://{self.s3_bucket}.s3.amazonaws.com/{filename}"
                return filename, public_url
                
            except Exception as e:
                logger.warning(f"S3 storage failed: {e}")
        
        logger.debug("No object storage configured, using direct URL")
        return None, None


# Singleton instance
imagery_service = ImageryService()
