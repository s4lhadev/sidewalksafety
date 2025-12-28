"""Test Regrid API Sandbox on FREE sample counties"""
import asyncio
import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv()

REGRID_API_KEY = os.getenv("REGRID_API_KEY")

async def test_regrid_sandbox():
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # Test location in Dallas County, Texas (one of the 7 free counties)
        # Let's use a well-known address: Dallas City Hall
        test_locations = [
            {"name": "Dallas City Hall", "lat": 32.7767, "lon": -96.7970},
            {"name": "Dallas Love Field Airport", "lat": 32.8481, "lon": -96.8512},
            {"name": "Random Dallas address", "lat": 32.8203, "lon": -96.7950},
        ]
        
        for loc in test_locations:
            print(f"\n{'='*60}")
            print(f"Testing: {loc['name']} ({loc['lat']}, {loc['lon']})")
            print('='*60)
            
            # Test 1: Point lookup via v2 API
            print("\n--- V2 Parcels Point Lookup ---")
            url = "https://app.regrid.com/api/v2/parcels/point"
            params = {
                "lat": loc['lat'],
                "lon": loc['lon'],
                "token": REGRID_API_KEY,
            }
            response = await client.get(url, params=params)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                parcels = data.get("parcels", {}).get("features", [])
                print(f"Found {len(parcels)} parcels")
                
                if parcels:
                    parcel = parcels[0]
                    props = parcel.get("properties", {})
                    geom = parcel.get("geometry", {})
                    
                    print(f"\n✅ PARCEL FOUND!")
                    print(f"   Address: {props.get('address', 'N/A')}")
                    print(f"   Owner: {props.get('owner', 'N/A')}")
                    print(f"   APN: {props.get('parcelnumb', 'N/A')}")
                    print(f"   Land Use: {props.get('usecode', 'N/A')}")
                    print(f"   Geometry Type: {geom.get('type', 'N/A')}")
                    
                    if geom.get("coordinates"):
                        coords = geom.get("coordinates", [[]])[0]
                        if coords:
                            print(f"   Polygon Points: {len(coords)} vertices")
                            print(f"   First 3 coords: {coords[:3]}")
                    
                    # Pretty print full response for first one
                    if loc == test_locations[0]:
                        print(f"\n   Full properties keys: {list(props.keys())[:15]}...")
            else:
                print(f"Response: {response.text[:300]}")

asyncio.run(test_regrid_sandbox())

