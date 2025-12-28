"""Test Regrid API - Full property details"""
import asyncio
import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv()

REGRID_API_KEY = os.getenv("REGRID_API_KEY")

async def test_regrid():
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # Dallas City Hall
        lat, lon = 32.7767, -96.7970
        
        print("Testing Dallas City Hall parcel lookup...")
        url = "https://app.regrid.com/api/v2/parcels/point"
        params = {
            "lat": lat,
            "lon": lon,
            "token": REGRID_API_KEY,
        }
        response = await client.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            parcels = data.get("parcels", {}).get("features", [])
            
            if parcels:
                parcel = parcels[0]
                props = parcel.get("properties", {})
                geom = parcel.get("geometry", {})
                
                print("\n" + "="*60)
                print("✅ PARCEL DATA RETRIEVED SUCCESSFULLY")
                print("="*60)
                
                # Print all available properties
                print("\n📋 ALL PROPERTIES:")
                for key, value in props.items():
                    if value and key != 'fields':
                        print(f"   {key}: {value}")
                
                # Check the 'fields' subobject for detailed data
                fields = props.get('fields', {})
                if fields:
                    print("\n📋 PARCEL FIELDS:")
                    for key, value in fields.items():
                        if value:
                            print(f"   {key}: {value}")
                
                # Print geometry info
                print("\n🗺️  GEOMETRY:")
                print(f"   Type: {geom.get('type')}")
                coords = geom.get('coordinates', [[]])
                if geom.get('type') == 'Polygon':
                    print(f"   Vertices: {len(coords[0])}")
                elif geom.get('type') == 'MultiPolygon':
                    total = sum(len(ring) for poly in coords for ring in poly)
                    print(f"   Total vertices: {total}")
                
                # Print raw geometry coords for visualization
                print("\n📍 BOUNDARY COORDINATES (first 5):")
                if geom.get('type') == 'Polygon':
                    for coord in coords[0][:5]:
                        print(f"   [{coord[1]:.6f}, {coord[0]:.6f}]")

asyncio.run(test_regrid())

