from pydantic_settings import BaseSettings
from typing import Optional
import secrets


class Settings(BaseSettings):
    # Database (PostGIS required)
    DATABASE_URL: str
    
    # Parking Lot Data Sources
    # INRIX uses AppId + HashToken for authentication
    INRIX_APP_ID: Optional[str] = None
    INRIX_HASH_TOKEN: Optional[str] = None
    # HERE uses API Key
    HERE_API_KEY: Optional[str] = None
    # OSM Overpass is free (no key needed)
    
    # Business Contact Data (Google Places is primary)
    GOOGLE_PLACES_KEY: Optional[str] = None
    
    # Satellite Imagery
    GOOGLE_MAPS_KEY: Optional[str] = None
    
    # Object Storage (optional - for storing images)
    SUPABASE_STORAGE_URL: Optional[str] = None
    SUPABASE_STORAGE_KEY: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    
    # Computer Vision (Roboflow hosted API)
    # API docs: https://docs.roboflow.com/deploy/serverless/object-detection
    ROBOFLOW_API_KEY: Optional[str] = None
    ROBOFLOW_MODEL_ID: str = "pavement-crack-detection-r4n7n/1"
    
    # Security
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    
    # App
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    
    # Discovery Settings
    DEFAULT_MIN_LOT_AREA_M2: float = 200.0  # Minimum 200 m²
    DEFAULT_MAX_CONDITION_SCORE: float = 70.0  # Lower = worse condition
    DEFAULT_MIN_MATCH_SCORE: float = 50.0  # Minimum business match confidence
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env (like APOLLO_API_KEY)


# Create settings instance
_settings = Settings()

# Generate SECRET_KEY if not provided (development only)
if not _settings.SECRET_KEY:
    if _settings.ENVIRONMENT == "development":
        _settings.SECRET_KEY = secrets.token_urlsafe(32)
        print("⚠️  WARNING: Using auto-generated SECRET_KEY. Set SECRET_KEY in .env for production!")
    else:
        raise ValueError("SECRET_KEY is required in production. Set it in .env file.")

settings = _settings
