"""Test Regrid API with different endpoints"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

REGRID_API_KEY = os.getenv("REGRID_API_KEY")
lat, lng = 38.4756607, -121.4160123

async def test_regrid():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # According to Regrid docs, the correct endpoint for point lookup
        # might use different base URLs or formats
        
        endpoints_to_try = [
            # V2 API
            ("https://app.regrid.com/api/v2/parcels/point", {"lat": lat, "lon": lng, "token": REGRID_API_KEY}),
            # Alternative format
            ("https://app.regrid.com/api/v1/parcel", {"lat": lat, "lng": lng, "token": REGRID_API_KEY}),
            # With path parameter
            (f"https://app.regrid.com/api/v1/parcels/point/{lat}/{lng}", {"token": REGRID_API_KEY}),
            # Query format
            ("https://app.regrid.com/api/v1/query", {"lat": lat, "lng": lng, "token": REGRID_API_KEY}),
            # GeoJSON format
            ("https://app.regrid.com/api/v1/parcels.json", {"lat": lat, "lon": lng, "token": REGRID_API_KEY}),
        ]
        
        for url, params in endpoints_to_try:
            print(f"\n=== Testing: {url} ===")
            try:
                response = await client.get(url, params=params)
                print(f"Status: {response.status_code}")
                content = response.text[:300]
                if response.status_code == 200 and "geometry" in content.lower():
                    print(f"✅ SUCCESS! Found geometry in response")
                    print(f"Response: {content}")
                else:
                    print(f"Response: {content}...")
            except Exception as e:
                print(f"Error: {e}")

asyncio.run(test_regrid())

