# Architecture Overview

## Parking Lot-First Approach

### Core Philosophy

Instead of finding businesses and checking if they have parking lots, we find ALL parking lots in an area first, evaluate their condition, then associate them with businesses for contact data.

---

## Complete Backend Flow

### 1. Receive User Input

User selects geographic area:
- ZIP code
- County
- Custom polygon (GeoJSON)

Backend converts selection to GeoJSON polygon (`area_poly`).

---

### 2. Collect Parking Lots (Maximum Coverage)

Query multiple data sources in parallel:

**INRIX Off-Street Parking API:**
- Commercial parking facilities
- Operator names and addresses
- Centroid coordinates

**HERE Off-Street Parking API:**
- Global parking lot database
- Polygon geometries
- Detailed metadata

**OpenStreetMap Overpass API:**
- `amenity=parking` polygons
- Community-mapped data
- Surface type tags

**Result:** 90-95% coverage of all parking lots in area

---

### 3. Normalize + Deduplicate Parking Lots

Using PostGIS spatial operations:

```sql
-- Combine overlapping polygons
ST_Union(geometry)

-- Compute centroids
ST_Centroid(geometry)

-- Calculate area
ST_Area(geography)

-- Find duplicates
ST_DWithin(geom1, geom2, 20) -- within 20 meters
```

**Process:**
1. Merge overlapping polygons from different sources
2. Pick best geometry (prefer HERE/OSM polygons over INRIX points)
3. Compute accurate centroid and area
4. Store unified records in `parking_lots` table

---

### 4. Fetch Imagery for Each Parking Lot

For each parking lot polygon:

**Maxar/Nearmap/Planet API:**
- Request high-resolution satellite imagery (30-50cm/pixel)
- Clip image to polygon bounds + buffer (10-20m)
- Store in object storage (Supabase Storage or S3)

**Image specifications:**
- Resolution: 30-50cm per pixel
- Format: GeoTIFF or JPEG with georeferencing
- Bounds: Parking lot polygon + 20m buffer

---

### 5. Run Computer Vision Scoring

For each parking lot image:

**Detection Models:**
- YOLOv8/YOLOv9 for crack detection
- Mask R-CNN for pothole detection
- Custom models for line fading detection

**Output Metrics:**
```json
{
  "condition_score": 45,        // 0-100 (lower = worse)
  "crack_density": 12.5,        // percentage
  "pothole_score": 8,           // 0-10 severity
  "line_fading_score": 6,       // 0-10 severity
  "degradation_areas": [...]    // polygon coordinates
}
```

Store CV outputs in `parking_lots` table.

---

### 6. Load Business Contact Records

Query businesses within `area_poly`:

**Infobel PRO API:**
- 200M+ global businesses
- Phone, email, website, address

**SafeGraph Places API:**
- 10M+ US POIs
- Detailed business info
- Foot traffic data

**Google Places API (fallback):**
- Business name, address, phone
- Place ID for additional details

Store in `businesses` table with geometry (point or polygon).

---

### 7. Associate Parking Lots with Businesses

For each parking lot, find the best matching business:

**Step 1: Spatial Query**
```sql
SELECT * FROM businesses
WHERE ST_DWithin(
  business_geometry,
  parking_lot_centroid,
  80  -- 80 meter radius
)
```

**Step 2: Category Filtering**
Filter by relevant categories:
- Retail stores
- Restaurants
- Apartment complexes
- Office buildings
- Churches
- Schools
- Medical centers
- Hotels/motels

**Step 3: Match Scoring**
```python
def calculate_match_score(parking_lot, business):
    score = 0
    
    # Distance (40 points)
    distance = calculate_distance(parking_lot.centroid, business.location)
    if distance < 20m: score += 40
    elif distance < 40m: score += 30
    elif distance < 60m: score += 20
    elif distance < 80m: score += 10
    
    # Category relevance (30 points)
    if business.category in HIGH_PRIORITY_CATEGORIES:
        score += 30
    elif business.category in MEDIUM_PRIORITY_CATEGORIES:
        score += 20
    
    # Name similarity if INRIX/HERE has operator (20 points)
    if parking_lot.operator_name:
        similarity = fuzzy_match(parking_lot.operator_name, business.name)
        score += similarity * 20
    
    # Building footprint adjacency (10 points)
    if business.building_polygon:
        if parking_lot.polygon.touches(business.building_polygon):
            score += 10
    
    return score
```

**Step 4: Store Association**
```python
# Store in parking_lot_business_associations table
{
  "parking_lot_id": uuid,
  "business_id": uuid,
  "match_score": 85,
  "distance_meters": 25.3,
  "association_method": "spatial_proximity"
}
```

---

### 8. Filter High-Value Leads

Apply filtering criteria:

```python
high_value_leads = parking_lots.filter(
    lot_area_m2 > 500,           # Minimum 500 m² (5,382 sqft)
    condition_score < 60,         # Poor condition (0-100 scale)
    match_score > 70,             # High confidence business match
    has_business_contact = True   # Must have contact data
)
```

**Configurable thresholds:**
- Minimum lot area
- Maximum condition score (lower = worse = better lead)
- Minimum match score
- Required contact fields (phone/email/website)

---

### 9. Return Output to Frontend

For each high-value lead:

```json
{
  "parking_lot": {
    "id": "uuid",
    "geometry": {
      "type": "Polygon",
      "coordinates": [[...]]
    },
    "area_m2": 1250.5,
    "area_sqft": 13459.2,
    "centroid": {"lat": 34.0522, "lng": -118.2437},
    "condition_score": 45,
    "crack_density": 12.5,
    "pothole_score": 8,
    "line_fading_score": 6,
    "satellite_image_url": "https://...",
    "data_sources": ["HERE", "OSM"]
  },
  "business": {
    "id": "uuid",
    "name": "ABC Shopping Center",
    "phone": "+1-555-0123",
    "email": "manager@abcshopping.com",
    "website": "https://abcshopping.com",
    "address": "123 Main St, Los Angeles, CA 90001",
    "category": "shopping_mall"
  },
  "association": {
    "match_score": 85,
    "distance_meters": 25.3,
    "confidence": "high"
  },
  "estimated_job_value": 15000.00,
  "priority_score": 92
}
```

---

## Data Models

### ParkingLot
```python
class ParkingLot(Base):
    id = UUID (primary key)
    user_id = UUID (foreign key)
    geometry = Geography(Polygon)  # PostGIS
    centroid = Geography(Point)
    area_m2 = Numeric
    area_sqft = Numeric
    
    # Data sources
    inrix_id = String (nullable)
    here_id = String (nullable)
    osm_id = String (nullable)
    data_sources = JSON  # ["INRIX", "HERE", "OSM"]
    
    # Condition metrics
    condition_score = Numeric  # 0-100
    crack_density = Numeric  # percentage
    pothole_score = Numeric  # 0-10
    line_fading_score = Numeric  # 0-10
    degradation_areas = JSON  # polygon coordinates
    
    # Imagery
    satellite_image_url = String
    image_captured_at = DateTime
    
    # Metadata
    surface_type = String  # asphalt, concrete
    operator_name = String (nullable)
    created_at = DateTime
    updated_at = DateTime
```

### Business
```python
class Business(Base):
    id = UUID (primary key)
    name = String
    phone = String (nullable)
    email = String (nullable)
    website = String (nullable)
    address = String
    city = String
    state = String
    zip = String
    category = String
    
    # Location
    geometry = Geography(Point)  # PostGIS
    building_polygon = Geography(Polygon) (nullable)
    
    # Data sources
    infobel_id = String (nullable)
    safegraph_id = String (nullable)
    places_id = String (nullable)
    data_source = String  # "infobel", "safegraph", "google_places"
    
    created_at = DateTime
    updated_at = DateTime
```

### ParkingLotBusinessAssociation
```python
class ParkingLotBusinessAssociation(Base):
    id = UUID (primary key)
    parking_lot_id = UUID (foreign key)
    business_id = UUID (foreign key)
    
    # Match scoring
    match_score = Numeric  # 0-100
    distance_meters = Numeric
    association_method = String  # "spatial_proximity", "operator_match"
    
    # Priority
    is_primary = Boolean  # True for best match
    
    created_at = DateTime
```

### Deal (Simplified)
```python
class Deal(Base):
    id = UUID (primary key)
    user_id = UUID (foreign key)
    parking_lot_id = UUID (foreign key)
    business_id = UUID (foreign key)
    
    status = String  # "pending", "contacted", "quoted", "won", "lost"
    estimated_job_value = Numeric
    priority_score = Numeric
    
    notes = Text (nullable)
    created_at = DateTime
    updated_at = DateTime
```

---

## Tech Stack

### Backend
- **Framework**: FastAPI
- **Database**: PostgreSQL with PostGIS extension
- **ORM**: SQLAlchemy with GeoAlchemy2
- **Hosting**: Supabase (with PostGIS enabled)

### Data Sources
- **INRIX Off-Street Parking API**: Commercial parking facilities
- **HERE Discover API**: Global parking lot database
- **OpenStreetMap Overpass API**: Community-mapped parking lots (free)
- **Google Places API**: Business contact data (name, phone, website, address)

### Imagery & CV
- **Satellite Imagery**: Google Maps Static API
- **Object Storage**: Supabase Storage or AWS S3 (optional)
- **CV Models**: YOLOv8 + OpenCV for crack/pothole detection
- **Processing**: OpenCV, NumPy, Shapely

### Frontend
- **Framework**: Next.js + React
- **Styling**: Tailwind CSS
- **Maps**: Mapbox GL JS or Leaflet
- **State Management**: React Query

---

## API Endpoints

### Discovery
- `POST /api/v1/parking-lots/discover` - Start parking lot discovery
- `GET /api/v1/parking-lots/discover/{job_id}` - Check discovery status

### Parking Lots
- `GET /api/v1/parking-lots` - List parking lots with filters
- `GET /api/v1/parking-lots/{id}` - Get parking lot details
- `GET /api/v1/parking-lots/map` - Get parking lots for map display

### Deals
- `POST /api/v1/deals` - Create deal from parking lot
- `GET /api/v1/deals` - List deals
- `GET /api/v1/deals/{id}` - Get deal details
- `PATCH /api/v1/deals/{id}` - Update deal status

### Authentication
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User login
- `GET /api/v1/auth/me` - Current user info

---

## Authentication

- JWT-based authentication
- All endpoints require auth (except register/login)
- Users can only see their own parking lots and deals

---

## Environment Variables

```env
# Database (PostGIS required)
SUPABASE_DB_URL=postgresql://...

# Parking Lot Data Sources
INRIX_APP_ID=your_app_id           # From INRIX IQ dashboard
INRIX_HASH_TOKEN=your_hash_token   # From INRIX IQ dashboard
HERE_API_KEY=your_key              # From HERE Developer Portal
# OSM Overpass is free (no key needed)

# Google APIs (for business data + satellite imagery)
GOOGLE_PLACES_KEY=your_key         # For business contact data
GOOGLE_MAPS_KEY=your_key           # For satellite imagery

# Object Storage (optional)
SUPABASE_STORAGE_URL=https://...
SUPABASE_STORAGE_KEY=your_key

# Security
SECRET_KEY=your_secret_key

# Environment
ENVIRONMENT=development
```

---

## Advantages Over Business-First Approach

1. **10-15x More Leads**: Find ALL parking lots, not just those attached to well-indexed businesses

2. **Complete Coverage**: 90-95% of parking lots in area vs 20-30% with business-first

3. **Condition-Driven**: Evaluate ALL parking lots, filter by condition, only pursue damaged ones

4. **Accurate Association**: Find the RIGHT business contact (property owner/manager) using spatial matching

5. **Scalable**: Works in any geographic area (ZIP, county, custom polygon)

6. **Future-Proof**: Can expand to other property types (lawns, sidewalks) easily

---

## Implementation Phases

### Phase 1: Infrastructure (Week 1-2)
- Enable PostGIS on Supabase
- Create new database models
- Set up API integrations (INRIX, HERE, Infobel/SafeGraph)
- Configure object storage

### Phase 2: Core Services (Week 3-4)
- Parking lot discovery service
- Normalization and deduplication
- Business data service
- Association service

### Phase 3: CV Pipeline (Week 5-6)
- Imagery fetching service
- CV model integration
- Condition scoring

### Phase 4: API & Frontend (Week 7-8)
- API endpoints
- Frontend integration
- Map visualization
- Deal management UI

### Phase 5: Testing & Optimization (Week 9-10)
- End-to-end testing
- Performance optimization
- User acceptance testing
- Production deployment
