"""Test Regrid API with correct parameters"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

REGRID_API_KEY = os.getenv("REGRID_API_KEY")

async def test_regrid():
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # Test 1: v1/query with lat/lon
        print("=== Test 1: v1/query with lat/lon ===")
        url = "https://app.regrid.com/api/v1/query"
        params = {
            "lat": 38.4756607,
            "lon": -121.4160123,  # NOT lng!
            "token": REGRID_API_KEY,
        }
        response = await client.get(url, params=params)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        # Test 2: Try a well-known address (Google HQ)
        print("\n=== Test 2: Google HQ location ===")
        url = "https://app.regrid.com/api/v1/query"
        params = {
            "lat": 37.4220656,
            "lon": -122.0840897,
            "token": REGRID_API_KEY,
        }
        response = await client.get(url, params=params)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        # Test 3: v2 API with correct params
        print("\n=== Test 3: v2/parcels with path param ===")
        url = "https://app.regrid.com/api/v2/parcel/38.4756607,-121.4160123"
        params = {"token": REGRID_API_KEY}
        response = await client.get(url, params=params)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        # Test 4: Check if Sacramento has coverage
        print("\n=== Test 4: Sacramento County known address ===")
        url = "https://app.regrid.com/api/v1/typeahead"
        params = {
            "query": "500 Capitol Mall Sacramento CA",
            "token": REGRID_API_KEY,
        }
        response = await client.get(url, params=params)
        print(f"Status: {response.status_code}")
        data = response.json()
        if data:
            print(f"Found {len(data)} results")
            for item in data[:3]:
                print(f"  - {item.get('address')} | {item.get('context')} | {item.get('path')}")

asyncio.run(test_regrid())

