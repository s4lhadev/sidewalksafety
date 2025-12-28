-- Migration: Add tile-based analysis support
-- Run this in Supabase SQL Editor

-- ============================================================
-- PART 1: Update property_analyses table with new columns
-- ============================================================

-- Aggregate metrics from tile analysis
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS total_asphalt_area_sqft float;
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS parking_area_m2 float;
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS parking_area_sqft float;
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS road_area_m2 float;
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS road_area_sqft float;
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS worst_tile_score float;
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS best_tile_score float;
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS total_detection_count numeric;
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS damage_density float;

-- Tile-based analysis info
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS analysis_type varchar(50);
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS total_tiles numeric;
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS analyzed_tiles numeric;
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS tiles_with_asphalt numeric;
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS tiles_with_damage numeric;
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS tile_zoom_level numeric;
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS tile_grid_rows numeric;
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS tile_grid_cols numeric;

-- Lead quality scoring
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS lead_quality varchar(50);
ALTER TABLE property_analyses ADD COLUMN IF NOT EXISTS hotspot_count numeric;

-- ============================================================
-- PART 2: Create analysis_tiles table
-- ============================================================

CREATE TABLE IF NOT EXISTS analysis_tiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_analysis_id UUID NOT NULL REFERENCES property_analyses(id) ON DELETE CASCADE,
    
    -- Tile identification
    tile_index INTEGER NOT NULL,
    row INTEGER,
    col INTEGER,
    
    -- Tile location
    center_lat FLOAT NOT NULL,
    center_lng FLOAT NOT NULL,
    zoom_level INTEGER NOT NULL DEFAULT 19,
    
    -- Tile bounds
    bounds_min_lat FLOAT,
    bounds_max_lat FLOAT,
    bounds_min_lng FLOAT,
    bounds_max_lng FLOAT,
    
    -- Tile polygon (for map display)
    tile_polygon geography(POLYGON, 4326),
    
    -- Imagery (base64 encoded)
    satellite_image_base64 TEXT,
    segmentation_image_base64 TEXT,
    condition_image_base64 TEXT,
    image_size_bytes INTEGER,
    
    -- Segmentation results
    asphalt_area_m2 FLOAT DEFAULT 0,
    parking_area_m2 FLOAT DEFAULT 0,
    road_area_m2 FLOAT DEFAULT 0,
    building_area_m2 FLOAT DEFAULT 0,
    vegetation_area_m2 FLOAT DEFAULT 0,
    segmentation_raw JSONB,
    
    -- Condition evaluation
    condition_score FLOAT DEFAULT 100,
    crack_count INTEGER DEFAULT 0,
    pothole_count INTEGER DEFAULT 0,
    detection_count INTEGER DEFAULT 0,
    condition_raw JSONB,
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    imagery_fetched_at TIMESTAMP WITH TIME ZONE,
    analyzed_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_analysis_tiles_property_analysis_id 
    ON analysis_tiles(property_analysis_id);
    
CREATE INDEX IF NOT EXISTS idx_analysis_tiles_tile_index 
    ON analysis_tiles(property_analysis_id, tile_index);
    
CREATE INDEX IF NOT EXISTS idx_analysis_tiles_status 
    ON analysis_tiles(status);

-- Spatial index on tile polygon
CREATE INDEX IF NOT EXISTS idx_analysis_tiles_polygon 
    ON analysis_tiles USING GIST(tile_polygon);

-- ============================================================
-- PART 3: Enable Row Level Security (RLS)
-- ============================================================

ALTER TABLE analysis_tiles ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view tiles for analyses they own
CREATE POLICY "Users can view own analysis tiles" ON analysis_tiles
    FOR SELECT
    USING (
        property_analysis_id IN (
            SELECT id FROM property_analyses WHERE user_id = auth.uid()
        )
    );

-- Policy: Service role can manage all tiles
CREATE POLICY "Service role full access to tiles" ON analysis_tiles
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================
-- VERIFICATION
-- ============================================================

-- Verify property_analyses columns
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'property_analyses' 
AND column_name IN ('analysis_type', 'total_tiles', 'lead_quality')
ORDER BY column_name;

-- Verify analysis_tiles table exists
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_name = 'analysis_tiles'
);

