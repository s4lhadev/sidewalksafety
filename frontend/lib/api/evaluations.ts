import { apiClient } from './client'
import {
  Evaluation,
  DealWithEvaluation,
  BatchEvaluateRequest,
  BatchEvaluateResponse,
} from '@/types'

export const evaluationsApi = {
  evaluateDeal: async (dealId: string): Promise<Evaluation> => {
    const { data } = await apiClient.post<Evaluation>(`/evaluations/${dealId}`)
    return data
  },

  batchEvaluate: async (request: BatchEvaluateRequest): Promise<BatchEvaluateResponse> => {
    const { data } = await apiClient.post<BatchEvaluateResponse>(
      '/evaluations/batch',
      request
    )
    return data
  },

  getDealWithEvaluation: async (dealId: string): Promise<DealWithEvaluation> => {
    // Use parking-lots endpoint which includes property_analysis with images
    const { data } = await apiClient.get<DealWithEvaluation>(`/parking-lots/${dealId}`)
    return data
  },
}

