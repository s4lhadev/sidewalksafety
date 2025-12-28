"""Test Regrid API - check California coverage"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

REGRID_API_KEY = os.getenv("REGRID_API_KEY")

async def test_regrid():
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        test_queries = [
            "500 Capitol Mall Sacramento CA",
            "1600 Amphitheatre Parkway Mountain View CA",
            "350 5th Avenue New York NY",  # Empire State Building
            "1 Microsoft Way Redmond WA",
        ]
        
        for query in test_queries:
            print(f"\n=== Typeahead: {query} ===")
            url = "https://app.regrid.com/api/v1/typeahead"
            params = {"query": query, "token": REGRID_API_KEY}
            response = await client.get(url, params=params)
            data = response.json()
            print(f"Found {len(data)} results")
            
            if data:
                item = data[0]
                ll_uuid = item.get('ll_uuid')
                print(f"First result: {item.get('address')} | {item.get('context')}")
                print(f"UUID: {ll_uuid}")
                
                # Try to fetch the parcel geometry
                if ll_uuid:
                    # Try fetching via parcel path
                    path = item.get('path', '')
                    if path:
                        print(f"\n  Fetching parcel via path: {path}")
                        url2 = f"https://app.regrid.com/api/v1{path}.geojson"
                        params2 = {"token": REGRID_API_KEY}
                        response2 = await client.get(url2, params=params2)
                        print(f"  Status: {response2.status_code}")
                        if response2.status_code == 200:
                            text = response2.text
                            if "geometry" in text:
                                print(f"  ✅ Found geometry!")
                                print(f"  Response: {text[:300]}...")
                            else:
                                print(f"  Response: {text[:200]}...")
                        else:
                            print(f"  Response: {response2.text[:200]}")

asyncio.run(test_regrid())

