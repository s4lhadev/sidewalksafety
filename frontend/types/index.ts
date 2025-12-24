
export interface User {
  id: string
  email: string
  company_name: string
  phone?: string
  is_active: boolean
  created_at: string
}

export interface BusinessInfo {
  id: string
  name: string
  phone?: string
  email?: string
  website?: string
  address?: string
  category?: string
}

export interface Deal {
  id: string
  user_id: string
  business_name: string
  address: string
  city?: string
  state?: string
  zip?: string
  county?: string
  phone?: string
  email?: string
  website?: string
  category?: string
  latitude?: number
  longitude?: number
  places_id?: string
  apollo_id?: string
  status: DealStatus
  score?: number
  satellite_url?: string
  has_property_verified?: boolean
  property_verification_method?: string
  property_type?: string
  created_at: string
  updated_at?: string
  // Business association
  business?: BusinessInfo
  has_business: boolean
  match_score?: number
  distance_meters?: number
  // Business-first discovery fields
  business_type_tier?: 'premium' | 'high' | 'standard'
  discovery_mode?: 'business_first' | 'parking_first'
}

export type DealStatus = 'pending' | 'evaluating' | 'evaluated' | 'archived'

export interface DealMapResponse {
  id: string
  business_name: string
  address: string
  latitude?: number
  longitude?: number
  status: DealStatus
  score?: number
  deal_score?: number
  estimated_job_value?: number
  damage_severity?: DamageSeverity
  satellite_url?: string
  condition_score?: number
  crack_density?: number
  // Business-first discovery fields
  business_type_tier?: 'premium' | 'high' | 'standard'
  business?: BusinessInfo
  has_business?: boolean
}

export type DamageSeverity = 'low' | 'medium' | 'high' | 'critical'

export interface Evaluation {
  id: string
  deal_id: string
  deal_score?: number
  parking_lot_area_sqft?: number
  crack_density_percent?: number
  damage_severity?: DamageSeverity
  estimated_repair_cost?: number
  estimated_job_value?: number
  satellite_image_url?: string
  parking_lot_mask?: Record<string, any>
  crack_detections?: Array<Record<string, any>>
  evaluation_metadata?: Record<string, any>
  evaluated_at: string
}

// Property Analysis Summary (embedded in parking lot/deal response)
export interface PropertyAnalysisSummary {
  id: string
  status: string
  total_asphalt_area_m2?: number
  weighted_condition_score?: number
  total_crack_count: number
  total_pothole_count: number
  images: PropertyAnalysisImages
  analyzed_at?: string
  // Regrid property boundary info
  property_boundary?: PropertyBoundaryInfo
}

export interface DealWithEvaluation extends Deal {
  evaluation?: Evaluation
  property_analysis?: PropertyAnalysisSummary
}

export interface GeographicSearchRequest {
  area_type: 'zip' | 'county'
  value: string
  state?: string
  max_deals?: number
  business_type_ids?: string[]
  tiers?: ('premium' | 'high' | 'standard')[]
}

export interface GeographicSearchResponse {
  job_id: string
  status: string
  message: string
}

export interface BatchEvaluateRequest {
  deal_ids: string[]
}

export interface BatchEvaluateResponse {
  evaluated: number
  failed: number
  message: string
}

export interface ApiError {
  detail: string
}

export interface Token {
  access_token: string
  token_type: string
  user: User
}

export interface UserCreate {
  email: string
  password: string
  company_name: string
  phone?: string
}

export interface UserLogin {
  email: string
  password: string
}

// Property Analysis Types
export interface AsphaltArea {
  id: string
  area_type?: string
  area_m2?: number
  is_associated: boolean
  association_reason?: string
  distance_to_building_m?: number
  condition_score?: number
  crack_count?: number
  pothole_count?: number
  crack_density?: number
}

export interface PropertyAnalysisImages {
  wide_satellite?: string
  segmentation?: string
  property_boundary?: string
  condition_analysis?: string
}

// Property boundary info from Regrid
export interface PropertyBoundaryInfo {
  source: 'regrid' | 'osm' | 'estimated'
  parcel_id?: string
  owner?: string
  apn?: string  // Assessor Parcel Number
  land_use?: string
  zoning?: string
  // GeoJSON polygon (for map display)
  polygon?: GeoJSONPolygon
}

export interface GeoJSONPolygon {
  type: 'Polygon'
  coordinates: number[][][]
}

export interface PropertyAnalysis {
  id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  latitude?: number
  longitude?: number
  total_asphalt_area_m2?: number
  weighted_condition_score?: number
  total_crack_count?: number
  total_pothole_count?: number
  images: PropertyAnalysisImages
  asphalt_areas: AsphaltArea[]
  business_id?: string
  parking_lot_id?: string
  analyzed_at?: string
  created_at?: string
  error_message?: string
  // Regrid property boundary data
  property_boundary?: PropertyBoundaryInfo
}

export interface PropertyAnalysisRequest {
  latitude: number
  longitude: number
  business_id?: string
  parking_lot_id?: string
}

export interface PropertyAnalysisJobResponse {
  job_id: string
  analysis_id: string
  status: string
  message: string
}

export interface PropertyAnalysisListResponse {
  total: number
  limit: number
  offset: number
  results: PropertyAnalysis[]
}

