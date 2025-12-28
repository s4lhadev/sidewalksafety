import { apiClient } from './client'
import type {
  PropertyAnalysis,
  PropertyAnalysisRequest,
  PropertyAnalysisJobResponse,
  PropertyAnalysisListResponse,
} from '@/types'

export const propertyAnalysisApi = {
  /**
   * Start a property analysis for a business location.
   * Returns a job response with analysis_id for polling.
   */
  startAnalysis: async (request: PropertyAnalysisRequest): Promise<PropertyAnalysisJobResponse> => {
    const { data } = await apiClient.post('/property-analysis', request)
    return data
  },

  /**
   * Get property analysis by ID.
   * Includes status, metrics, image URLs, and asphalt areas.
   */
  getAnalysis: async (analysisId: string): Promise<PropertyAnalysis> => {
    const { data } = await apiClient.get(`/property-analysis/${analysisId}`)
    return data
  },

  /**
   * List property analyses for current user.
   */
  listAnalyses: async (params?: {
    limit?: number
    offset?: number
    status?: string
  }): Promise<PropertyAnalysisListResponse> => {
    const { data } = await apiClient.get('/property-analysis', { params })
    return data
  },

  /**
   * Get image URL for a specific analysis image type.
   */
  getImageUrl: (analysisId: string, imageType: 'wide_satellite' | 'segmentation' | 'property_boundary' | 'condition_analysis'): string => {
    return `/api/v1/property-analysis/images/${analysisId}/${imageType}`
  },
}


