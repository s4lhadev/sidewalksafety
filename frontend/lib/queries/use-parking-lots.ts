import { useQuery } from '@tanstack/react-query'
import { parkingLotsApi } from '../api/parking-lots'

export function useParkingLot(id: string) {
  return useQuery({
    queryKey: ['parking-lots', id],
    queryFn: () => parkingLotsApi.getParkingLot(id),
    enabled: !!id,
  })
}

export function useParkingLotBusinesses(id: string) {
  return useQuery({
    queryKey: ['parking-lots', id, 'businesses'],
    queryFn: () => parkingLotsApi.getParkingLotBusinesses(id),
    enabled: !!id,
  })
}

