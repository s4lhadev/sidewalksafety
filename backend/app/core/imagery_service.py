import logging
import httpx
import boto3
from typing import Optional, Tuple
from shapely.geometry import Polygon
from geoalchemy2.shape import to_shape
import uuid
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class ImageryService:
    """Service to fetch satellite imagery for parking lots using Google Maps Static API."""
    
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
        buffer_meters: float = 20.0
    ) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
        """
        Fetch satellite imagery for a parking lot.
        
        Returns:
            Tuple of (image_bytes, storage_path, image_url)
        """
        if not self.google_key:
            logger.warning("Google Maps API key not configured")
            return None, None, None
        
        try:
            image_bytes = await self._fetch_google_maps(centroid_lat, centroid_lng)
            
            if image_bytes:
                logger.info(f"Fetched imagery from Google Maps for lot {parking_lot_id}")
                
                # Store image if storage is configured
                storage_path, image_url = await self._store_image(image_bytes, parking_lot_id)
                
                # If no storage, generate direct URL
                if not image_url:
                    image_url = self.get_static_image_url(centroid_lat, centroid_lng)
                
                return image_bytes, storage_path, image_url
            
        except Exception as e:
            logger.error(f"Failed to fetch imagery for lot {parking_lot_id}: {e}")
        
        return None, None, None
    
    async def _fetch_google_maps(
        self,
        lat: float,
        lng: float,
        zoom: int = 20,
        size: str = "640x640"
    ) -> Optional[bytes]:
        """Fetch imagery from Google Maps Static API."""
        if not self.google_key:
            return None
        
        url = "https://maps.googleapis.com/maps/api/staticmap"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                params={
                    "center": f"{lat},{lng}",
                    "zoom": zoom,
                    "size": size,
                    "maptype": "satellite",
                    "key": self.google_key,
                }
            )
            
            if response.status_code == 200:
                return response.content
            
            # Log detailed error
            error_text = response.text[:500] if hasattr(response, 'text') else str(response.content[:500])
            logger.error(f"Google Maps API returned {response.status_code}: {error_text}")
            
            # 403 usually means API not enabled, billing not set up, or restrictions
            if response.status_code == 403:
                logger.error("Google Maps API 403 - Check: 1) Static Maps API enabled? 2) Billing enabled? 3) API key restrictions?")
            
            return None
    
    async def _store_image(
        self,
        image_bytes: bytes,
        parking_lot_id: uuid.UUID
    ) -> Tuple[Optional[str], Optional[str]]:
        """Store image in object storage."""
        
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
    
    def get_static_image_url(
        self,
        lat: float,
        lng: float,
        zoom: int = 20,
        size: str = "640x640"
    ) -> Optional[str]:
        """Generate a static image URL (Google Maps)."""
        if not self.google_key:
            return None
        
        return (
            f"https://maps.googleapis.com/maps/api/staticmap"
            f"?center={lat},{lng}&zoom={zoom}&size={size}"
            f"&maptype=satellite&key={self.google_key}"
        )


# Singleton instance
imagery_service = ImageryService()
