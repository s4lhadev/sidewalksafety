"""
Database setup script.
Enables PostGIS extension, drops old tables, and creates new PostGIS-enabled tables.

Usage:
    python setup_db.py           # Create tables (safe, won't drop existing)
    python setup_db.py --drop    # Drop all tables first, then create
    python setup_db.py --check   # Just check PostGIS extension status
"""
import sys
from sqlalchemy import text
from app.db.base import Base, engine
from app.models import User, ParkingLot, Business, ParkingLotBusinessAssociation, Deal, UsageLog


def enable_postgis():
    """Enable PostGIS extension on the database."""
    print("Enabling PostGIS extension...")
    with engine.connect() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis_topology"))
            conn.commit()
            print("✅ PostGIS extension enabled")
        except Exception as e:
            print(f"⚠️  PostGIS extension error: {e}")
            print("   Make sure PostGIS is available on your database.")
            print("   For Supabase: Enable it in Dashboard > Database > Extensions")
            return False
    return True


def check_postgis():
    """Check if PostGIS is properly installed."""
    print("Checking PostGIS status...")
    with engine.connect() as conn:
        try:
            result = conn.execute(text("SELECT PostGIS_Version()"))
            version = result.scalar()
            print(f"✅ PostGIS version: {version}")
            return True
        except Exception as e:
            print(f"❌ PostGIS not available: {e}")
            return False


def drop_all_tables():
    """Drop all user tables and indexes, excluding PostGIS system tables."""
    print("Dropping all user tables and indexes...")
    
    with engine.connect() as conn:
        # Drop all user indexes first (exclude indexes on PostGIS system tables)
        conn.execute(text("""
            DO $$ DECLARE
                r RECORD;
                postgis_tables TEXT[] := ARRAY['spatial_ref_sys', 'geography_columns', 'geometry_columns', 'raster_columns', 'raster_overviews'];
            BEGIN
                FOR r IN (
                    SELECT i.indexname, i.tablename
                    FROM pg_indexes i
                    WHERE i.schemaname = 'public'
                    AND i.indexname NOT LIKE 'pg_%'
                ) LOOP
                    -- Skip indexes on PostGIS system tables
                    IF NOT (r.tablename = ANY(postgis_tables)) THEN
                        EXECUTE 'DROP INDEX IF EXISTS ' || quote_ident(r.indexname) || ' CASCADE';
                    END IF;
                END LOOP;
            END $$;
        """))
        
        # Drop user tables only (exclude PostGIS system tables)
        # PostGIS system tables: spatial_ref_sys, geography_columns, geometry_columns, etc.
        conn.execute(text("""
            DO $$ DECLARE
                r RECORD;
                postgis_tables TEXT[] := ARRAY['spatial_ref_sys', 'geography_columns', 'geometry_columns', 'raster_columns', 'raster_overviews'];
            BEGIN
                FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                    -- Skip PostGIS system tables
                    IF NOT (r.tablename = ANY(postgis_tables)) THEN
                        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                    END IF;
                END LOOP;
            END $$;
        """))
        conn.commit()
        print("✅ All user tables and indexes dropped")


def create_all_tables():
    """Create all tables."""
    print("Creating tables...")
    
    # Drop any remaining indexes that might conflict
    with engine.connect() as conn:
        try:
            conn.execute(text("DROP INDEX IF EXISTS idx_businesses_geometry CASCADE"))
            conn.execute(text("DROP INDEX IF EXISTS idx_businesses_building CASCADE"))
            conn.execute(text("DROP INDEX IF EXISTS idx_parking_lots_centroid CASCADE"))
            conn.execute(text("DROP INDEX IF EXISTS idx_parking_lots_geometry CASCADE"))
            conn.commit()
        except Exception:
            pass  # Ignore if they don't exist
    
    Base.metadata.create_all(bind=engine, checkfirst=True)
    print("✅ Tables created:")
    for table in Base.metadata.sorted_tables:
        print(f"   - {table.name}")


def main():
    args = sys.argv[1:]
    
    if "--check" in args:
        check_postgis()
        return
    
    # Enable PostGIS first
    if not enable_postgis():
        print("\n❌ Cannot proceed without PostGIS. Please enable it first.")
        print("\nFor Supabase:")
        print("1. Go to your Supabase Dashboard")
        print("2. Navigate to Database > Extensions")
        print("3. Search for 'postgis' and enable it")
        print("4. Run this script again")
        sys.exit(1)
    
    # Check PostGIS is working
    if not check_postgis():
        print("\n❌ PostGIS check failed.")
        sys.exit(1)
    
    # Drop tables if requested
    if "--drop" in args:
        drop_all_tables()
    
    # Create tables
    create_all_tables()
    
    print("\n✅ Database setup complete!")
    print("\nNext steps:")
    print("1. Copy env.example to .env and fill in your API keys")
    print("2. Run: uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
