import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { dealsApi } from '../api/deals'
import { GeographicSearchRequest } from '@/types'
import { toast } from '@/hooks/use-toast'

export function useDeals(status?: string) {
  return useQuery({
    queryKey: ['deals', status],
    queryFn: () => dealsApi.getDeals(status),
    refetchInterval: 10000, // Refetch every 10s to get new discoveries
  })
}

export function useDeal(id: string) {
  return useQuery({
    queryKey: ['deals', id],
    queryFn: () => dealsApi.getDeal(id),
    enabled: !!id,
  })
}

export function useDealsForMap(params?: {
  min_lat?: number
  max_lat?: number
  min_lng?: number
  max_lng?: number
  status?: string
}) {
  return useQuery({
    queryKey: ['deals', 'map', params],
    queryFn: () => dealsApi.getDealsForMap(params),
    refetchInterval: 10000, // Refetch every 10s to get new discoveries
  })
}

export function useScrapeDeals() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: GeographicSearchRequest) => dealsApi.discover(request),
    onSuccess: (data) => {
      // Invalidate after a short delay to allow backend to process
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['deals'] })
      }, 3000)
      
      toast({
        title: 'Discovery Started',
        description: `Job started. Parking lots will appear on the map as they are discovered.`,
      })
    },
    onError: (error: any) => {
      toast({
        variant: 'destructive',
        title: 'Discovery failed',
        description: error.response?.data?.detail || 'Failed to start discovery',
      })
    },
  })
}
