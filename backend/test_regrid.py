"""Test Regrid API directly"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

REGRID_API_KEY = os.getenv("REGRID_API_KEY")
print(f"API Key configured: {'Yes' if REGRID_API_KEY else 'NO - MISSING!'}")
if REGRID_API_KEY:
    print(f"API Key (first 10 chars): {REGRID_API_KEY[:10]}...")

# Suncountry Owners Association coordinates
lat, lng = 38.4756607, -121.4160123
address = "7801 Suncountry Ln, Sacramento, CA 95828"

async def test_regrid():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Point lookup
        print(f"\n=== Test 1: Point lookup ({lat}, {lng}) ===")
        url = "https://app.regrid.com/api/v1/parcels/point"
        params = {
            "lat": lat,
            "lon": lng,
            "token": REGRID_API_KEY,
        }
        response = await client.get(url, params=params)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        # Test 2: Address search
        print(f"\n=== Test 2: Address search ===")
        url = "https://app.regrid.com/api/v1/search"
        params = {
            "query": address,
            "token": REGRID_API_KEY,
        }
        response = await client.get(url, params=params)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
        # Test 3: Typeahead/autocomplete
        print(f"\n=== Test 3: Typeahead search ===")
        url = "https://app.regrid.com/api/v1/typeahead"
        params = {
            "query": "7801 Suncountry Ln Sacramento",
            "token": REGRID_API_KEY,
        }
        response = await client.get(url, params=params)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")

asyncio.run(test_regrid())

