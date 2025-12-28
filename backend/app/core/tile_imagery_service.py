"""
TileImageryService - Fetch high-resolution satellite imagery for tiles.

This service fetches satellite imagery for each tile in a tile grid,
ensuring consistent high-resolution coverage across the entire property.

Design Principles:
- Fetch at maximum resolution for each tile
- Handle rate limiting gracefully
- Store images efficiently (base64)
- Track fetch status for each tile
"""

import asyncio
import logging
import math
import httpx
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from app.core.config import settings
from app.core.tile_service import Tile, TileGrid

logger = logging.getLogger(__name__)


@dataclass
class TileImage:
    """A tile with its fetched imagery."""
    tile: Tile
    image_bytes: Optional[bytes] = None
    image_base64: Optional[str] = None
    fetch_status: str = "pending"  # pending, success, failed
    error_message: Optional[str] = None
    fetched_at: Optional[datetime] = None
    size_bytes: int = 0
    
    @property
    def is_valid(self) -> bool:
        return self.fetch_status == "success" and self.image_bytes is not None


@dataclass
class TileImageryResult:
    """Result of fetching imagery for a tile grid."""
    tiles: List[TileImage]
    total_tiles: int
    successful_tiles: int
    failed_tiles: int
    total_size_bytes: int
    fetch_duration_seconds: float
    zoom: int
    
    @property
    def success_rate(self) -> float:
        if self.total_tiles == 0:
            return 0
        return self.successful_tiles / self.total_tiles * 100


class TileImageryService:
    """
    Fetch high-resolution satellite imagery for tiles.
    
    Uses Google Maps Static API to fetch each tile at high zoom level.
    Handles rate limiting and retries gracefully.
    """
    
    # API configuration
    IMAGE_SIZE = 640  # Maximum size for Google Maps Static API
    SCALE = 2  # 2x scale for higher resolution (1280x1280 effective)
    MAP_TYPE = "satellite"
    
    # Rate limiting
    MAX_CONCURRENT_REQUESTS = 5  # Don't overwhelm the API
    REQUEST_DELAY_MS = 100  # Delay between requests
    MAX_RETRIES = 3
    
    def __init__(self):
        self.api_key = settings.GOOGLE_MAPS_KEY
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def fetch_tile_imagery(
        self,
        tile_grid: TileGrid,
        progress_callback: Optional[callable] = None
    ) -> TileImageryResult:
        """
        Fetch imagery for all tiles in a grid.
        
        Args:
            tile_grid: The tile grid to fetch imagery for
            progress_callback: Optional callback(completed, total) for progress updates
            
        Returns:
            TileImageryResult with all fetched tile images
        """
        if not self.is_configured:
            raise ValueError("Google Maps API key not configured")
        
        start_time = datetime.utcnow()
        
        logger.info(f"🛰️  Fetching {tile_grid.total_tiles} tiles at zoom {tile_grid.zoom}")
        
        # Create tile image objects
        tile_images = [TileImage(tile=tile) for tile in tile_grid.tiles]
        
        # Fetch tiles with concurrency limit
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
        
        async def fetch_with_semaphore(tile_image: TileImage, index: int):
            async with semaphore:
                await self._fetch_single_tile(tile_image)
                if progress_callback:
                    progress_callback(index + 1, len(tile_images))
                # Small delay to avoid rate limiting
                await asyncio.sleep(self.REQUEST_DELAY_MS / 1000)
        
        # Fetch all tiles concurrently
        tasks = [
            fetch_with_semaphore(tile_image, i) 
            for i, tile_image in enumerate(tile_images)
        ]
        await asyncio.gather(*tasks)
        
        # Calculate results
        successful = sum(1 for t in tile_images if t.is_valid)
        failed = sum(1 for t in tile_images if t.fetch_status == "failed")
        total_size = sum(t.size_bytes for t in tile_images if t.is_valid)
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(f"   ✅ Fetched {successful}/{len(tile_images)} tiles in {duration:.1f}s ({total_size/1024/1024:.1f} MB)")
        
        return TileImageryResult(
            tiles=tile_images,
            total_tiles=len(tile_images),
            successful_tiles=successful,
            failed_tiles=failed,
            total_size_bytes=total_size,
            fetch_duration_seconds=duration,
            zoom=tile_grid.zoom
        )
    
    async def fetch_single_tile(self, tile: Tile) -> TileImage:
        """Fetch imagery for a single tile."""
        tile_image = TileImage(tile=tile)
        await self._fetch_single_tile(tile_image)
        return tile_image
    
    async def _fetch_single_tile(self, tile_image: TileImage) -> None:
        """
        Internal method to fetch imagery for a single tile.
        
        Updates the tile_image object in place.
        """
        tile = tile_image.tile
        
        for attempt in range(self.MAX_RETRIES):
            try:
                client = await self._get_client()
                
                # Build Google Maps Static API URL
                url = "https://maps.googleapis.com/maps/api/staticmap"
                params = {
                    "center": f"{tile.center_lat},{tile.center_lng}",
                    "zoom": tile.zoom,
                    "size": f"{self.IMAGE_SIZE}x{self.IMAGE_SIZE}",
                    "scale": self.SCALE,
                    "maptype": self.MAP_TYPE,
                    "key": self.api_key,
                }
                
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    tile_image.image_bytes = response.content
                    tile_image.size_bytes = len(response.content)
                    tile_image.fetch_status = "success"
                    tile_image.fetched_at = datetime.utcnow()
                    
                    # Convert to base64
                    import base64
                    tile_image.image_base64 = base64.b64encode(response.content).decode('utf-8')
                    
                    return
                
                elif response.status_code == 429:
                    # Rate limited, wait and retry
                    logger.warning(f"   ⚠️  Rate limited on tile {tile.index}, waiting...")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
                else:
                    tile_image.error_message = f"HTTP {response.status_code}"
                    
            except Exception as e:
                tile_image.error_message = str(e)
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(1)
        
        # All retries failed
        tile_image.fetch_status = "failed"
        logger.error(f"   ❌ Failed to fetch tile {tile.index}: {tile_image.error_message}")
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Singleton instance
tile_imagery_service = TileImageryService()

