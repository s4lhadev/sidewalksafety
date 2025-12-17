import { apiClient } from './client'

export interface ParkingLotCoordinates {
  lat: number
  lng: number
}

export interface ParkingLotGeometry {
  type: 'Polygon'
  coordinates: number[][][]
}

export interface BusinessSummary {
  id: string
  name: string
  phone?: string
  email?: string
  website?: string
  address?: string
  category?: string
}

export interface ParkingLotDetail {
  id: string
  centroid: ParkingLotCoordinates
  geometry?: ParkingLotGeometry
  area_m2?: number
  area_sqft?: number
  operator_name?: string
  address?: string
  surface_type?: string
  condition_score?: number
  crack_density?: number
  pothole_score?: number
  line_fading_score?: number
  satellite_image_url?: string
  is_evaluated: boolean
  data_sources: string[]
  degradation_areas?: Array<Record<string, any>>
  raw_metadata?: Record<string, any>
  evaluation_error?: string
  created_at: string
  evaluated_at?: string
  updated_at?: string
  business?: BusinessSummary
  match_score?: number
  distance_meters?: number
}

export interface ParkingLotBusiness {
  id: string
  name: string
  phone?: string
  email?: string
  website?: string
  address?: string
  category?: string
  match_score: number
  distance_meters: number
  is_primary: boolean
  location: ParkingLotCoordinates
}

export const parkingLotsApi = {
  getParkingLot: async (id: string): Promise<ParkingLotDetail> => {
    const { data } = await apiClient.get<ParkingLotDetail>(`/parking-lots/${id}`)
    return data
  },

  getParkingLotBusinesses: async (id: string): Promise<ParkingLotBusiness[]> => {
    const { data } = await apiClient.get<ParkingLotBusiness[]>(`/parking-lots/${id}/businesses`)
    return data
  },
}


