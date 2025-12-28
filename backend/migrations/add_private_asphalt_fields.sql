-- Migration: Add private asphalt fields to analysis tables
-- Date: 2024-12-28
-- Purpose: Store private asphalt polygons (after filtering public roads from OSM)

-- ============================================
-- PropertyAnalysis table additions
-- ============================================

-- Private asphalt (after filtering public roads)
ALTER TABLE property_analyses 
ADD COLUMN IF NOT EXISTS private_asphalt_area_m2 FLOAT;

ALTER TABLE property_analyses 
ADD COLUMN IF NOT EXISTS private_asphalt_area_sqft FLOAT;

ALTER TABLE property_analyses 
ADD COLUMN IF NOT EXISTS private_asphalt_geojson JSONB;

ALTER TABLE property_analyses 
ADD COLUMN IF NOT EXISTS public_road_area_m2 FLOAT;

-- ============================================
-- AnalysisTile table additions
-- ============================================

-- Private asphalt per tile
ALTER TABLE analysis_tiles 
ADD COLUMN IF NOT EXISTS private_asphalt_area_m2 FLOAT DEFAULT 0;

ALTER TABLE analysis_tiles 
ADD COLUMN IF NOT EXISTS private_asphalt_area_sqft FLOAT DEFAULT 0;

-- Private asphalt polygon (geometry for map display)
ALTER TABLE analysis_tiles 
ADD COLUMN IF NOT EXISTS private_asphalt_polygon geography(GEOMETRY, 4326);

-- GeoJSON for frontend display
ALTER TABLE analysis_tiles 
ADD COLUMN IF NOT EXISTS private_asphalt_geojson JSONB;

-- Public roads filtered out
ALTER TABLE analysis_tiles 
ADD COLUMN IF NOT EXISTS public_road_area_m2 FLOAT DEFAULT 0;

ALTER TABLE analysis_tiles 
ADD COLUMN IF NOT EXISTS public_road_polygon geography(GEOMETRY, 4326);

-- Source of asphalt detection
ALTER TABLE analysis_tiles 
ADD COLUMN IF NOT EXISTS asphalt_source VARCHAR(50);

-- ============================================
-- Add comments for documentation
-- ============================================

COMMENT ON COLUMN property_analyses.private_asphalt_area_m2 IS 'Private asphalt area after filtering public roads (m²)';
COMMENT ON COLUMN property_analyses.private_asphalt_area_sqft IS 'Private asphalt area after filtering public roads (sqft)';
COMMENT ON COLUMN property_analyses.private_asphalt_geojson IS 'Merged GeoJSON of all private asphalt for map display';
COMMENT ON COLUMN property_analyses.public_road_area_m2 IS 'Area of public roads that were filtered out (m²)';

COMMENT ON COLUMN analysis_tiles.private_asphalt_area_m2 IS 'Private asphalt area in this tile (after filtering public roads)';
COMMENT ON COLUMN analysis_tiles.private_asphalt_polygon IS 'Polygon of private asphalt for map overlay';
COMMENT ON COLUMN analysis_tiles.private_asphalt_geojson IS 'GeoJSON of private asphalt for frontend';
COMMENT ON COLUMN analysis_tiles.public_road_area_m2 IS 'Area of public roads filtered out in this tile';
COMMENT ON COLUMN analysis_tiles.asphalt_source IS 'Source of asphalt detection: cv_only, cv_with_osm_filter, fallback';

-- ============================================
-- Create index for efficient queries
-- ============================================

CREATE INDEX IF NOT EXISTS idx_analysis_tiles_private_asphalt 
ON analysis_tiles (property_analysis_id) 
WHERE private_asphalt_area_m2 > 0;

CREATE INDEX IF NOT EXISTS idx_property_analyses_private_asphalt 
ON property_analyses (private_asphalt_area_sqft DESC) 
WHERE private_asphalt_area_sqft > 0;

COMMIT;

