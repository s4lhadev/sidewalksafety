"""Test OSM building footprints for Suncountry Owners Association"""
import httpx
import json

lat, lng = 38.4756607, -121.4160123

overpass_query = f"""
[out:json][timeout:25];
(
  way["building"](around:300,{lat},{lng});
);
out geom;
"""

print(f"Querying OSM for buildings near ({lat}, {lng})...")
response = httpx.post('https://overpass-api.de/api/interpreter', data={'data': overpass_query}, timeout=30)
data = response.json()

elements = data.get("elements", [])
print(f"Found {len(elements)} buildings")

for elem in elements[:15]:
    tags = elem.get("tags", {})
    geom = elem.get("geometry", [])
    name = tags.get("name", "unnamed")
    building_type = tags.get("building", "yes")
    print(f"  - {name} | type: {building_type} | {len(geom)} vertices")

