-- Migration: Add Regrid property boundary columns to property_analyses table
-- Run this in Supabase SQL Editor

-- Add property boundary polygon column (stores the legal property boundary from Regrid)
ALTER TABLE property_analyses 
ADD COLUMN IF NOT EXISTS property_boundary_polygon geography(GEOMETRY, 4326);

-- Add property boundary source (regrid, osm, or estimated)
ALTER TABLE property_analyses 
ADD COLUMN IF NOT EXISTS property_boundary_source varchar(50);

-- Add Regrid parcel identifiers
ALTER TABLE property_analyses 
ADD COLUMN IF NOT EXISTS property_parcel_id varchar(200);

-- Add property owner from Regrid
ALTER TABLE property_analyses 
ADD COLUMN IF NOT EXISTS property_owner text;

-- Add Assessor Parcel Number (APN)
ALTER TABLE property_analyses 
ADD COLUMN IF NOT EXISTS property_apn varchar(100);

-- Add land use classification
ALTER TABLE property_analyses 
ADD COLUMN IF NOT EXISTS property_land_use varchar(100);

-- Add zoning code
ALTER TABLE property_analyses 
ADD COLUMN IF NOT EXISTS property_zoning varchar(100);

-- Create index on property_boundary_source for filtering
CREATE INDEX IF NOT EXISTS idx_property_analyses_boundary_source 
ON property_analyses(property_boundary_source);

-- Create spatial index on property_boundary_polygon for efficient queries
CREATE INDEX IF NOT EXISTS idx_property_analyses_boundary_polygon 
ON property_analyses USING GIST(property_boundary_polygon);

-- Verify the columns were added
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'property_analyses' 
AND column_name LIKE 'property_%'
ORDER BY column_name;

