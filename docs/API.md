# API Reference

## Authentication

### `POST /api/v1/auth/register`
Register new parking lot repair company.

**Request:**
```json
{
  "email": "company@example.com",
  "password": "securepassword",
  "company_name": "ABC Parking Repair",
  "phone": "+1234567890"
}
```

**Response:**
```json
{
  "access_token": "jwt_token",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "company@example.com",
    "company_name": "ABC Parking Repair"
  }
}
```

### `POST /api/v1/auth/login`
Login and get JWT token.

**Request:**
```json
{
  "email": "company@example.com",
  "password": "securepassword"
}
```

### `GET /api/v1/auth/me`
Get current user info (requires auth).

---

## Parking Lot Discovery

### `POST /api/v1/parking-lots/discover`
Start parking lot discovery process (requires auth).

**Request:**
```json
{
  "area_type": "zip" | "county" | "polygon",
  "value": "90210",
  "state": "CA",  // Required if area_type is "county"
  "polygon": {...},  // Required if area_type is "polygon" (GeoJSON)
  "filters": {
    "min_area_m2": 500,
    "max_condition_score": 60,
    "min_match_score": 70
  }
}
```

**Response:**
```json
{
  "job_id": "uuid",
  "status": "processing",
  "message": "Discovery started. This may take 2-5 minutes.",
  "estimated_completion": "2024-01-15T10:35:00Z"
}
```

### `GET /api/v1/parking-lots/discover/{job_id}`
Check discovery job status (requires auth).

**Response (processing):**
```json
{
  "job_id": "uuid",
  "status": "processing",
  "progress": {
    "current_step": "fetching_imagery",
    "steps_completed": 3,
    "total_steps": 5,
    "parking_lots_found": 150,
    "parking_lots_evaluated": 45
  }
}
```

**Response (completed):**
```json
{
  "job_id": "uuid",
  "status": "completed",
  "results": {
    "parking_lots_found": 180,
    "parking_lots_evaluated": 180,
    "high_value_leads": 42,
    "businesses_matched": 40
  },
  "message": "Found 180 parking lots. 42 high-value leads identified."
}
```

---

## Parking Lots

### `GET /api/v1/parking-lots`
List parking lots with filters (requires auth).

**Query Params:**
- `min_area_m2` (optional): Minimum lot area in square meters
- `max_condition_score` (optional): Maximum condition score (0-100, lower = worse)
- `min_match_score` (optional): Minimum business match score (0-100)
- `has_business` (optional): Filter by business association (true/false)
- `limit` (optional): Results limit (default: 50, max: 200)
- `offset` (optional): Pagination offset

**Response:**
```json
{
  "total": 180,
  "limit": 50,
  "offset": 0,
  "results": [
    {
      "id": "uuid",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[...]]
      },
      "centroid": {"lat": 34.0522, "lng": -118.2437},
      "area_m2": 1250.5,
      "area_sqft": 13459.2,
      "condition_score": 45,
      "crack_density": 12.5,
      "pothole_score": 8,
      "line_fading_score": 6,
      "satellite_image_url": "https://...",
      "data_sources": ["HERE", "OSM"],
      "business": {
        "id": "uuid",
        "name": "ABC Shopping Center",
        "phone": "+1-555-0123",
        "match_score": 85
      },
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### `GET /api/v1/parking-lots/{id}`
Get single parking lot details (requires auth).

**Response:**
```json
{
  "id": "uuid",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[...]]
  },
  "centroid": {"lat": 34.0522, "lng": -118.2437},
  "area_m2": 1250.5,
  "area_sqft": 13459.2,
  
  "condition_score": 45,
  "crack_density": 12.5,
  "pothole_score": 8,
  "line_fading_score": 6,
  "degradation_areas": [...],
  
  "satellite_image_url": "https://...",
  "image_captured_at": "2024-01-10T14:20:00Z",
  
  "inrix_id": "inrix_12345",
  "here_id": "here_67890",
  "osm_id": "123456789",
  "data_sources": ["INRIX", "HERE", "OSM"],
  
  "operator_name": "ABC Parking Corp",
  "surface_type": "asphalt",
  
  "businesses": [
    {
      "id": "uuid",
      "name": "ABC Shopping Center",
      "phone": "+1-555-0123",
      "email": "manager@abcshopping.com",
      "website": "https://abcshopping.com",
      "address": "123 Main St, Los Angeles, CA 90001",
      "category": "shopping_mall",
      "match_score": 85,
      "distance_meters": 25.3,
      "is_primary": true
    }
  ],
  
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:35:00Z"
}
```

### `GET /api/v1/parking-lots/map`
Get parking lots for map display (requires auth).

**Query Params:**
- `min_lat`, `max_lat`, `min_lng`, `max_lng` (optional): Bounding box
- `min_condition_score`, `max_condition_score` (optional): Condition filter
- `has_business` (optional): Filter by business association

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [-118.2437, 34.0522]
      },
      "properties": {
        "id": "uuid",
        "area_m2": 1250.5,
        "condition_score": 45,
        "business_name": "ABC Shopping Center",
        "has_business": true
      }
    }
  ]
}
```

---

## Deals

### `POST /api/v1/deals`
Create deal from parking lot (requires auth).

**Request:**
```json
{
  "parking_lot_id": "uuid",
  "business_id": "uuid",
  "estimated_job_value": 15000.00,
  "notes": "Large shopping center parking lot with extensive cracking"
}
```

**Response:**
```json
{
  "id": "uuid",
  "parking_lot_id": "uuid",
  "business_id": "uuid",
  "status": "pending",
  "estimated_job_value": 15000.00,
  "priority_score": 92,
  "notes": "Large shopping center parking lot with extensive cracking",
  "created_at": "2024-01-15T10:40:00Z"
}
```

### `GET /api/v1/deals`
List deals (requires auth).

**Query Params:**
- `status` (optional): Filter by status (pending/contacted/quoted/won/lost)
- `min_priority_score` (optional): Minimum priority score
- `limit` (optional): Results limit
- `offset` (optional): Pagination offset

**Response:**
```json
{
  "total": 25,
  "results": [
    {
      "id": "uuid",
      "status": "pending",
      "estimated_job_value": 15000.00,
      "priority_score": 92,
      "parking_lot": {
        "id": "uuid",
        "area_sqft": 13459.2,
        "condition_score": 45,
        "centroid": {"lat": 34.0522, "lng": -118.2437}
      },
      "business": {
        "id": "uuid",
        "name": "ABC Shopping Center",
        "phone": "+1-555-0123",
        "email": "manager@abcshopping.com"
      },
      "created_at": "2024-01-15T10:40:00Z"
    }
  ]
}
```

### `GET /api/v1/deals/{id}`
Get deal details (requires auth).

### `PATCH /api/v1/deals/{id}`
Update deal status (requires auth).

**Request:**
```json
{
  "status": "contacted",
  "notes": "Spoke with property manager, sending quote"
}
```

### `DELETE /api/v1/deals/{id}`
Delete deal (requires auth).

---

## Businesses

### `GET /api/v1/businesses/{id}`
Get business details (requires auth).

**Response:**
```json
{
  "id": "uuid",
  "name": "ABC Shopping Center",
  "phone": "+1-555-0123",
  "email": "manager@abcshopping.com",
  "website": "https://abcshopping.com",
  "address": "123 Main St, Los Angeles, CA 90001",
  "city": "Los Angeles",
  "state": "CA",
  "zip": "90001",
  "category": "shopping_mall",
  "geometry": {
    "type": "Point",
    "coordinates": [-118.2437, 34.0522]
  },
  "data_source": "infobel",
  "parking_lots": [
    {
      "id": "uuid",
      "area_sqft": 13459.2,
      "condition_score": 45,
      "match_score": 85
    }
  ]
}
```

---

## Authentication

All endpoints except `/auth/register` and `/auth/login` require authentication.

Include JWT token in Authorization header:
```
Authorization: Bearer <token>
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid area_type. Must be 'zip', 'county', or 'polygon'"
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 404 Not Found
```json
{
  "detail": "Parking lot not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error"
}
```

---

## Rate Limits

- **Discovery endpoint**: 10 requests per hour per user
- **Other endpoints**: 1000 requests per hour per user

Rate limit headers:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642248000
```
