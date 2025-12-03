/**
 * Free boundary fetching using Google Geocoding API
 * Gets approximate bounds for ZIP codes and counties
 */

export interface BoundaryData {
  bounds: {
    north: number
    south: number
    east: number
    west: number
  }
  viewport?: {
    northeast: { lat: number; lng: number }
    southwest: { lat: number; lng: number }
  }
  center: { lat: number; lng: number }
  type: 'zip' | 'county'
  radius?: number // For county circles
}

export async function fetchZipBoundary(zip: string): Promise<BoundaryData | null> {
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
  if (!apiKey) return null

  try {
    // Geocode ZIP code
    const response = await fetch(
      `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(zip)}&key=${apiKey}`
    )
    const data = await response.json()

    if (data.status !== 'OK' || !data.results?.[0]) {
      return null
    }

    const result = data.results[0]
    const geometry = result.geometry

    // Prefer viewport for ZIP codes (tighter, more accurate)
    if (geometry.viewport) {
      return {
        bounds: {
          north: geometry.viewport.northeast.lat,
          south: geometry.viewport.southwest.lat,
          east: geometry.viewport.northeast.lng,
          west: geometry.viewport.southwest.lng,
        },
        viewport: geometry.viewport,
        center: {
          lat: geometry.location.lat,
          lng: geometry.location.lng,
        },
        type: 'zip',
      }
    }

    // Fallback to bounds if viewport not available
    if (geometry.bounds) {
      return {
        bounds: {
          north: geometry.bounds.northeast.lat,
          south: geometry.bounds.southwest.lat,
          east: geometry.bounds.northeast.lng,
          west: geometry.bounds.southwest.lng,
        },
        viewport: geometry.viewport,
        center: {
          lat: geometry.location.lat,
          lng: geometry.location.lng,
        },
        type: 'zip',
      }
    }

    // Fallback to viewport if bounds not available
    if (geometry.viewport) {
      return {
        bounds: {
          north: geometry.viewport.northeast.lat,
          south: geometry.viewport.southwest.lat,
          east: geometry.viewport.northeast.lng,
          west: geometry.viewport.southwest.lng,
        },
        viewport: geometry.viewport,
        center: {
          lat: geometry.location.lat,
          lng: geometry.location.lng,
        },
        type: 'zip',
      }
    }

    return null
  } catch (error) {
    console.error('Error fetching ZIP boundary:', error)
    return null
  }
}

export async function fetchCountyBoundary(
  county: string,
  state: string
): Promise<BoundaryData | null> {
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
  if (!apiKey) return null

  try {
    // Geocode county
    const query = `${county} County, ${state}`
    const response = await fetch(
      `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(query)}&key=${apiKey}`
    )
    const data = await response.json()

    if (data.status !== 'OK' || !data.results?.[0]) {
      return null
    }

    const result = data.results[0]
    const geometry = result.geometry
    const center = {
      lat: geometry.location.lat,
      lng: geometry.location.lng,
    }

    // For counties, use viewport (tighter) or create a reasonable circle
    // Instead of huge bounding box, use viewport which is usually more reasonable
    if (geometry.viewport) {
      return {
        bounds: {
          north: geometry.viewport.northeast.lat,
          south: geometry.viewport.southwest.lat,
          east: geometry.viewport.northeast.lng,
          west: geometry.viewport.southwest.lng,
        },
        viewport: geometry.viewport,
        center,
        type: 'county',
      }
    }

    // Fallback: Create a reasonable circle around center (30km radius)
    // This gives a ~60km diameter circle which is reasonable for most counties
    const radiusKm = 30
    const latDelta = radiusKm / 111 // ~111km per degree latitude
    const lngDelta = radiusKm / (111 * Math.cos(center.lat * Math.PI / 180))

    return {
      bounds: {
        north: center.lat + latDelta,
        south: center.lat - latDelta,
        east: center.lng + lngDelta,
        west: center.lng - lngDelta,
      },
      viewport: {
        northeast: { lat: center.lat + latDelta, lng: center.lng + lngDelta },
        southwest: { lat: center.lat - latDelta, lng: center.lng - lngDelta },
      },
      center,
      type: 'county',
      radius: radiusKm,
    }
  } catch (error) {
    console.error('Error fetching county boundary:', error)
    return null
  }
}

