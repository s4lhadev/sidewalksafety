'use client'

import { useState, useCallback } from 'react'
import { useDeals, useDealsForMap } from '@/lib/queries/use-deals'
import { DealList } from '@/components/features/deals/deal-list'
import { MapScrapeForm } from '@/components/features/deals/map-scrape-form'
import { InteractiveMap } from '@/components/map/interactive-map'
import { ViewToggle } from '@/components/common/view-toggle'
import { useEvaluateDeal } from '@/lib/queries/use-evaluations'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { DealMapResponse } from '@/types'
import { useRouter } from 'next/navigation'

type ViewType = 'map' | 'list'

export default function DashboardPage() {
  const router = useRouter()
  const [view, setView] = useState<ViewType>('map')
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const [selectedDeal, setSelectedDeal] = useState<DealMapResponse | null>(null)
  const [mapBounds, setMapBounds] = useState<{
    minLat: number
    maxLat: number
    minLng: number
    maxLng: number
  } | null>(null)

  const { data: deals, isLoading } = useDeals(statusFilter)
  const { data: mapDeals, isLoading: isLoadingMap } = useDealsForMap(
    mapBounds
      ? {
          min_lat: mapBounds.minLat,
          max_lat: mapBounds.maxLat,
          min_lng: mapBounds.minLng,
          max_lng: mapBounds.maxLng,
          status: statusFilter,
        }
      : { status: statusFilter }
  )

  const evaluateDeal = useEvaluateDeal()

  const handleEvaluate = (dealId: string) => {
    evaluateDeal.mutate(dealId)
  }

  const handleViewDetails = (dealId: string) => {
    router.push(`/deals/${dealId}`)
  }

  const handleBoundsChange = useCallback(
    (bounds: { minLat: number; maxLat: number; minLng: number; maxLng: number }) => {
      setMapBounds(bounds)
    },
    []
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Deals</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Manage and evaluate parking lot deals
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ViewToggle view={view} onViewChange={setView} />
          <MapScrapeForm />
        </div>
      </div>

      <Tabs defaultValue="all" onValueChange={(value) => setStatusFilter(value === 'all' ? undefined : value)}>
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="pending">Pending</TabsTrigger>
          <TabsTrigger value="evaluating">Evaluating</TabsTrigger>
          <TabsTrigger value="evaluated">Evaluated</TabsTrigger>
        </TabsList>
        <TabsContent value={statusFilter || 'all'} className="mt-4">
          {view === 'map' ? (
            <div className="h-[calc(100vh-280px)] min-h-[600px] rounded-lg overflow-hidden border border-border/40 bg-muted/20">
              {isLoadingMap ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
                    <p className="text-sm text-muted-foreground">Loading map...</p>
                  </div>
                </div>
              ) : (
                <InteractiveMap
                  deals={mapDeals || []}
                  selectedDeal={selectedDeal}
                  onDealSelect={setSelectedDeal}
                  onViewDetails={handleViewDetails}
                  onBoundsChange={handleBoundsChange}
                />
              )}
            </div>
          ) : (
            <DealList
              deals={deals || []}
              isLoading={isLoading}
              onEvaluate={handleEvaluate}
            />
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

