"""Test Regrid API - fetch parcel by path from typeahead"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

REGRID_API_KEY = os.getenv("REGRID_API_KEY")

async def test_regrid():
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # Step 1: Use typeahead to find parcels in Sacramento
        print("=== Step 1: Typeahead search ===")
        url = "https://app.regrid.com/api/v1/typeahead"
        params = {
            "query": "Suncountry Sacramento",
            "token": REGRID_API_KEY,
        }
        response = await client.get(url, params=params)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Found {len(data)} results")
        
        for item in data[:5]:
            ll_uuid = item.get('ll_uuid')
            path = item.get('path')
            address = item.get('address')
            context = item.get('context')
            print(f"  - {address} | {context}")
            print(f"    UUID: {ll_uuid}")
            print(f"    Path: {path}")
            
            # Step 2: Try to fetch parcel by ll_uuid
            if ll_uuid:
                print(f"\n=== Fetching parcel by UUID: {ll_uuid} ===")
                url2 = f"https://app.regrid.com/api/v1/parcel/{ll_uuid}"
                params2 = {"token": REGRID_API_KEY}
                response2 = await client.get(url2, params=params2)
                print(f"Status: {response2.status_code}")
                print(f"Response: {response2.text[:500]}")
                
                # Try alternative endpoint
                url3 = f"https://app.regrid.com/api/v2/parcel/{ll_uuid}"
                response3 = await client.get(url3, params=params2)
                print(f"\nV2 Status: {response3.status_code}")
                print(f"V2 Response: {response3.text[:500]}")
                break

asyncio.run(test_regrid())

