-- Migration: Add surface type fields for Grounded SAM detection
-- This adds support for distinguishing asphalt vs concrete surfaces

-- Add new columns to property_analyses table
ALTER TABLE property_analyses
ADD COLUMN IF NOT EXISTS concrete_area_m2 DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS concrete_area_sqft DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS concrete_geojson JSONB,
ADD COLUMN IF NOT EXISTS total_paved_area_m2 DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS total_paved_area_sqft DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS surfaces_geojson JSONB,
ADD COLUMN IF NOT EXISTS building_area_m2 DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS building_geojson JSONB,
ADD COLUMN IF NOT EXISTS detection_method VARCHAR(50);

-- Add index for detection_method filtering
CREATE INDEX IF NOT EXISTS idx_property_analyses_detection_method 
ON property_analyses(detection_method);

-- Comment explaining the new fields
COMMENT ON COLUMN property_analyses.concrete_area_m2 IS 'Area of detected concrete surfaces in square meters';
COMMENT ON COLUMN property_analyses.surfaces_geojson IS 'GeoJSON FeatureCollection of all detected surfaces (asphalt, concrete, buildings)';
COMMENT ON COLUMN property_analyses.detection_method IS 'CV detection method used: grounded_sam, legacy_cv';

