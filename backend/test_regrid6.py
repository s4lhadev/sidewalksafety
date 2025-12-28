"""Test Regrid - using the path that worked earlier"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

REGRID_API_KEY = os.getenv("REGRID_API_KEY")

async def test_regrid():
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # The path from earlier successful typeahead
        path = "/us/tx/dallas/northeast-dallas/669677"
        ll_uuid = "84a5a372-c96d-4eb7-ad0b-39bbf8cf5d0b"
        
        print(f"=== Fetching parcel via GeoJSON path ===")
        url = f"https://app.regrid.com/api/v1{path}.geojson"
        params = {"token": REGRID_API_KEY}
        response = await client.get(url, params=params)
        print(f"Status: {response.status_code}")
        text = response.text[:1000]
        if "geometry" in text.lower() or "coordinates" in text.lower():
            print(f"✅ Got geometry!")
        print(f"Response: {text}")
        
        print(f"\n=== Fetching via parcel UUID endpoint ===")
        url = f"https://app.regrid.com/api/v2/parcel/{ll_uuid}"
        params = {"token": REGRID_API_KEY}
        response = await client.get(url, params=params)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:1000]}")
        
        print(f"\n=== Try path-based fetch endpoint ===")
        url = f"https://app.regrid.com{path}"
        params = {"format": "geojson", "token": REGRID_API_KEY}
        response = await client.get(url, params=params)
        print(f"Status: {response.status_code}")
        content_type = response.headers.get('content-type', '')
        print(f"Content-Type: {content_type}")
        if 'json' in content_type.lower():
            print(f"Response: {response.text[:1000]}")

asyncio.run(test_regrid())

