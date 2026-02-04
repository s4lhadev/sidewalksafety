/**
 * Discovery API Client
 * 
 * Two discovery modes:
 * 1. Places Discovery: Google Places -> Regrid Tiles (business-focused)
 * 2. Area Discovery: Regrid Tiles directly (size-based)
 * 
 * Tiles are free (200k/month), records are limited (2k/month).
 */

import { apiClient } from './client'

// ============ Parcel Types (Area-based discovery) ============

export interface DiscoveryParcel {
  id: string
  address: string
  acreage: number
  apn: string
  regrid_id: string
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon
  centroid: { lat: number; lng: number }
  owner?: string | null
  selected?: boolean  // Client-side selection state
}

export interface DiscoveryQueryRequest {
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon
  min_acres?: number
  max_acres?: number
  limit?: number
}

export interface DiscoveryQueryResponse {
  success: boolean
  parcels: DiscoveryParcel[]
  total_count: number
  error?: string
}

// ============ Places Types (Business-focused discovery) ============

export interface PlaceWithParcel {
  // Place info (from Google Places)
  place_id: string
  name: string
  address: string
  lat: number
  lng: number
  types: string[]
  primary_type?: string | null
  rating?: number | null
  user_ratings_count?: number | null
  website?: string | null
  phone?: string | null
  
  // Parcel info (from Regrid Tiles)
  parcel_id?: string | null
  parcel_address?: string | null
  parcel_acreage?: number | null
  parcel_apn?: string | null
  parcel_owner?: string | null
  parcel_geometry?: GeoJSON.Polygon | GeoJSON.MultiPolygon | null
  parcel_centroid?: { lat: number; lng: number } | null
  
  // Client-side state
  selected?: boolean
}

export interface PlacesDiscoveryRequest {
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon
  property_type: string  // Natural language (e.g., "big restaurants")
  included_type?: string  // Optional Google Places type
  max_results?: number  // Max 60
}

export interface PlacesDiscoveryResponse {
  success: boolean
  places: PlaceWithParcel[]
  total_places: number
  places_with_parcels: number
  error?: string
}

// ============ Processing Types ============

export interface ProcessParcelsRequest {
  parcels: DiscoveryParcel[]
}

export interface ProcessParcelsResponse {
  success: boolean
  message: string
  job_id?: string
}

export interface EnrichedContact {
  name?: string | null
  first_name?: string | null
  last_name?: string | null
  email?: string | null
  phone?: string | null
  title?: string | null
  company?: string | null
  website?: string | null
  confidence: number
}

export interface ProcessedPlace {
  place_id: string
  name: string
  address: string
  property_id?: string | null
  contact?: EnrichedContact | null
  enrichment_status: 'pending' | 'success' | 'not_found' | 'error'
  enrichment_steps?: string[] | null
  error?: string | null
}

export interface ProcessPlacesResponse {
  success: boolean
  message: string
  processed: ProcessedPlace[]
  total: number
  with_contacts: number
}

export interface ProcessingProgress {
  type: 'start' | 'processing' | 'property_found' | 'property_created' | 'enriching' | 'contact_found' | 'no_contact' | 'error' | 'complete'
  message: string
  current?: number
  total?: number
  place_id?: string
  property_id?: string
  contact?: EnrichedContact
  error?: string
  with_contacts?: number
  results?: ProcessedPlace[]
}

// API Client
export const discoveryApi = {
  /**
   * Discover businesses by type and get their parcel geometries.
   * 
   * Flow: Google Places search -> Regrid tile lookup for parcels
   * Max 60 results (Google's limit per query).
   */
  discoverPlaces: async (request: PlacesDiscoveryRequest): Promise<PlacesDiscoveryResponse> => {
    const { data } = await apiClient.post<PlacesDiscoveryResponse>('/discover/places', {
      geometry: request.geometry,
      property_type: request.property_type,
      included_type: request.included_type,
      max_results: request.max_results || 60,
    }, {
      timeout: 60000, // 1 minute (Google Places + tile lookups)
    })
    return data
  },

  /**
   * Query parcels within a given area with optional size filter.
   * Uses Regrid Tileserver MVT - real geometries, unlimited requests!
   * Note: Uses longer timeout (120s) due to processing many parcels
   */
  queryParcels: async (request: DiscoveryQueryRequest): Promise<DiscoveryQueryResponse> => {
    const { data } = await apiClient.post<DiscoveryQueryResponse>('/discover/parcels', {
      geometry: request.geometry,
      min_acres: request.min_acres,
      max_acres: request.max_acres,
      limit: request.limit || 500,
    }, {
      timeout: 120000, // 2 minutes for large areas
    })
    return data
  },

  /**
   * Process selected parcels for LLM enrichment to find contact information.
   * @deprecated Use processPlacesStream for the new discovery flow
   */
  processParcels: async (request: ProcessParcelsRequest): Promise<ProcessParcelsResponse> => {
    const { data } = await apiClient.post<ProcessParcelsResponse>('/discover/process', {
      parcels: request.parcels,
    })
    return data
  },

  /**
   * Process selected places for LLM enrichment with SSE streaming.
   * Returns an EventSource that streams progress updates.
   */
  processPlacesStream: (
    places: PlaceWithParcel[],
    onProgress: (progress: ProcessingProgress) => void,
    onComplete: (results: ProcessedPlace[]) => void,
    onError: (error: string) => void,
  ): AbortController => {
    const controller = new AbortController()
    
    const processStream = async () => {
      try {
        const response = await fetch(`${apiClient.defaults.baseURL}/discover/process/places/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': apiClient.defaults.headers.common?.['Authorization'] as string || '',
          },
          body: JSON.stringify({ places }),
          signal: controller.signal,
        })
        
        if (!response.ok) {
          const error = await response.json()
          onError(error.detail || 'Processing failed')
          return
        }
        
        const reader = response.body?.getReader()
        if (!reader) {
          onError('No response stream')
          return
        }
        
        const decoder = new TextDecoder()
        let buffer = ''
        
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n\n')
          buffer = lines.pop() || ''
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6)) as ProcessingProgress
                onProgress(data)
                
                if (data.type === 'complete' && data.results) {
                  onComplete(data.results)
                }
              } catch (e) {
                console.error('Failed to parse SSE data:', e)
              }
            }
          }
        }
      } catch (e) {
        if ((e as Error).name !== 'AbortError') {
          onError((e as Error).message || 'Processing failed')
        }
      }
    }
    
    processStream()
    return controller
  },

  /**
   * Process selected places for LLM enrichment (non-streaming).
   * For progress updates, use processPlacesStream instead.
   */
  processPlaces: async (places: PlaceWithParcel[]): Promise<ProcessPlacesResponse> => {
    const { data } = await apiClient.post<ProcessPlacesResponse>('/discover/process/places', {
      places,
    }, {
      timeout: 300000, // 5 minutes for batch processing
    })
    return data
  },
}

export default discoveryApi
