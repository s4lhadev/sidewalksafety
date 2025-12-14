'use client'

import { useState, useCallback, useRef } from 'react'
import { useDeals, useDealsForMap, useScrapeDeals } from '@/lib/queries/use-deals'
import { InteractiveMap } from '@/components/map/interactive-map'
import { DiscoveryCard } from '@/components/map/discovery-card'
import { DealMapResponse } from '@/types'
import { useRouter } from 'next/navigation'
import { 
  X,
  ChevronRight,
  MapPin,
  TrendingDown,
  Clock,
  CheckCircle2,
  Radar,
  Building2,
  AlertCircle,
  Trophy,
  Star,
  Phone,
  Globe
} from 'lucide-react'

export default function DashboardPage() {
  const router = useRouter()
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const [selectedDeal, setSelectedDeal] = useState<DealMapResponse | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [clickedLocation, setClickedLocation] = useState<{ lat: number; lng: number } | null>(null)
  const [mapBounds, setMapBounds] = useState<{
    minLat: number
    maxLat: number
    minLng: number
    maxLng: number
  } | null>(null)

  const hasMapLoadedOnce = useRef(false)
  const scrapeDeals = useScrapeDeals()

  const { data: dealsData, isLoading } = useDeals(statusFilter)
  const deals = Array.isArray(dealsData) ? dealsData : []
  
  // Always show all deals on map, not filtered by bounds
  // This ensures markers stay visible when zooming or panning
  const { data: mapDealsData, isLoading: isLoadingMap } = useDealsForMap(
    { status: statusFilter }
  )
  const mapDeals = Array.isArray(mapDealsData) ? mapDealsData : []
  
  if (mapDealsData && !hasMapLoadedOnce.current) {
    hasMapLoadedOnce.current = true
  }
  
  const showMapLoading = isLoadingMap && !hasMapLoadedOnce.current

  const handleViewDetails = (dealId: string) => {
    router.push(`/parking-lots/${dealId}`)
  }

  const handleBoundsChange = useCallback(
    (bounds: { minLat: number; maxLat: number; minLng: number; maxLng: number }) => {
      // Store bounds but don't use them to filter deals
      // This allows other features to use bounds if needed
      setMapBounds(bounds)
    },
    []
  )

  const handleMapClick = useCallback((lat: number, lng: number) => {
    // Close deal selection if open
    setSelectedDeal(null)
    // Open discovery card
    setClickedLocation({ lat, lng })
  }, [])

  const handleDiscover = (type: 'zip' | 'county', value: string, state?: string, businessTypeIds?: string[]) => {
    scrapeDeals.mutate(
      {
        area_type: type,
        value,
        state: type === 'county' ? state : undefined,
        max_deals: type === 'zip' ? 10 : 30,
        business_type_ids: businessTypeIds,
      },
      {
        onSuccess: () => {
          setClickedLocation(null)
          // Keep boundary visible during discovery
        },
      }
    )
  }

  const statusTabs = [
    { value: undefined, label: 'All', icon: Radar },
    { value: 'pending', label: 'Pending', icon: Clock },
    { value: 'evaluated', label: 'Analyzed', icon: CheckCircle2 },
  ]

  const getStatusCount = (status?: string) => {
    if (!status) return deals.length
    return deals.filter(d => d.status === status).length
  }

  return (
    <div className="relative h-full">
      {/* Full-screen Map */}
      <div className="absolute inset-0">
        {showMapLoading ? (
          <div className="h-full flex items-center justify-center bg-slate-100">
            <div className="text-center">
              <div className="animate-spin rounded-full h-10 w-10 border-2 border-orange-500 border-t-transparent mx-auto mb-3" />
              <p className="text-sm text-slate-500">Loading map...</p>
            </div>
          </div>
        ) : (
          <InteractiveMap
            deals={mapDeals}
            selectedDeal={selectedDeal}
            onDealSelect={(deal) => {
              setSelectedDeal(deal)
              setClickedLocation(null)
            }}
            onViewDetails={handleViewDetails}
            onBoundsChange={handleBoundsChange}
            onMapClick={handleMapClick}
            clickedLocation={clickedLocation}
          />
        )}
      </div>

      {/* Discovery Card - Top Right */}
      {clickedLocation && (
        <div className="absolute top-4 right-4 z-30">
          <DiscoveryCard
            lat={clickedLocation.lat}
            lng={clickedLocation.lng}
            onDiscover={handleDiscover}
            onClose={() => setClickedLocation(null)}
            isDiscovering={scrapeDeals.isPending}
          />
        </div>
      )}

      {/* Floating Sidebar Panel */}
      <div 
        className={`
          absolute top-4 left-4 bottom-4 z-20 transition-all duration-300 ease-out
          ${sidebarOpen ? 'w-96' : 'w-0 overflow-hidden'}
        `}
      >
        {sidebarOpen && (
          <div className="h-full bg-white/95 backdrop-blur-sm border border-slate-200 rounded-2xl shadow-xl overflow-hidden flex flex-col animate-slide-in">
            {/* Sidebar Header */}
            <div className="p-4 border-b border-slate-100">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-semibold text-slate-900">Parking Lots</h2>
                <button
                  onClick={() => setSidebarOpen(false)}
                  className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors text-slate-400 hover:text-slate-600"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Status Filter */}
              <div className="flex gap-1.5">
                {statusTabs.map((tab) => {
                  const Icon = tab.icon
                  const count = getStatusCount(tab.value)
                  return (
                    <button
                      key={tab.label}
                      onClick={() => setStatusFilter(tab.value)}
                      className={`
                        flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all
                        ${statusFilter === tab.value
                          ? 'bg-orange-500 text-white shadow-sm'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }
                      `}
                    >
                      <Icon className="h-3 w-3" />
                      {tab.label}
                      <span className="opacity-70">({count})</span>
                    </button>
                  )
                })}
        </div>
      </div>

            {/* Deals List */}
            <div className="flex-1 overflow-y-auto">
              {isLoading ? (
                <div className="p-4 space-y-3">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />
                  ))}
                  </div>
              ) : deals.length > 0 ? (
                <div className="p-3 space-y-2">
                  {deals.map((deal) => (
                    <DealCard
                      key={deal.id}
                      deal={deal}
                      isSelected={selectedDeal?.id === deal.id}
                      onClick={() => {
                        setSelectedDeal(deal as any)
                        setClickedLocation(null)
                      }}
                      onViewDetails={() => handleViewDetails(deal.id)}
                    />
                  ))}
                </div>
              ) : (
                <EmptyState />
              )}
            </div>

            {/* Summary Footer */}
            {deals.length > 0 && (
              <div className="p-4 border-t border-slate-100 bg-slate-50/80">
                <div className="grid grid-cols-4 gap-2 text-center">
                  <div>
                    <p className="text-lg font-bold text-slate-900">{deals.length}</p>
                    <p className="text-[10px] text-slate-500 uppercase tracking-wide">Total</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold text-blue-500">
                      {deals.filter((d: any) => d.has_business || d.business).length}
                    </p>
                    <p className="text-[10px] text-slate-500 uppercase tracking-wide">W/ Business</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold text-red-500">
                      {deals.filter(d => d.status === 'evaluated' && d.score && d.score < 50).length}
                    </p>
                    <p className="text-[10px] text-slate-500 uppercase tracking-wide">Leads</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold text-green-500">
                      {deals.filter(d => d.status === 'evaluated').length}
                    </p>
                    <p className="text-[10px] text-slate-500 uppercase tracking-wide">Analyzed</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Sidebar Toggle (when closed) */}
      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          className="absolute top-4 left-4 z-30 h-10 w-10 bg-white border border-slate-200 rounded-xl shadow-lg flex items-center justify-center hover:bg-slate-50 transition-colors"
        >
          <ChevronRight className="h-4 w-4 text-slate-600" />
        </button>
      )}

      {/* Zoom Controls - Bottom Right */}
      <div className="absolute bottom-6 right-4 z-10 flex flex-col gap-1">
        <button className="h-9 w-9 bg-white border border-slate-200 rounded-lg shadow-md flex items-center justify-center hover:bg-slate-50 transition-colors text-slate-600 text-lg font-light">
          +
        </button>
        <button className="h-9 w-9 bg-white border border-slate-200 rounded-lg shadow-md flex items-center justify-center hover:bg-slate-50 transition-colors text-slate-600 text-lg font-light">
          −
        </button>
      </div>

      {/* Stats Bar - Bottom Center */}
      {deals.length > 0 && !clickedLocation && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10">
          <div className="flex items-center gap-4 px-5 py-2.5 bg-white/95 backdrop-blur-sm border border-slate-200 rounded-full shadow-lg">
            <Stat label="Total" value={deals.length} />
            <div className="h-4 w-px bg-slate-200" />
            <Stat label="Analyzed" value={deals.filter(d => d.status === 'evaluated').length} color="text-green-500" />
            <div className="h-4 w-px bg-slate-200" />
            <Stat label="Leads" value={deals.filter(d => d.score && d.score < 50).length} color="text-red-500" />
          </div>
        </div>
      )}
    </div>
  )
}

function DealCard({ 
  deal, 
  isSelected, 
  onClick,
  onViewDetails 
}: { 
  deal: any
  isSelected: boolean
  onClick: () => void
  onViewDetails: () => void
}) {
  const getScoreColor = (score: number | null) => {
    if (!score) return 'text-slate-400'
    if (score < 30) return 'text-red-500'
    if (score < 50) return 'text-orange-500'
    if (score < 70) return 'text-yellow-600'
    return 'text-green-500'
  }

  const getTierBadge = (tier: string | undefined) => {
    switch (tier) {
      case 'premium':
        return (
          <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-amber-100 text-amber-800 flex items-center gap-1">
            <Trophy className="h-2.5 w-2.5" />
            Premium
          </span>
        )
      case 'high':
        return (
          <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-purple-100 text-purple-800 flex items-center gap-1">
            <Star className="h-2.5 w-2.5" />
            High
          </span>
        )
      default:
        return null
    }
  }

  const isHighPriority = deal.score !== null && deal.score !== undefined && deal.score < 50
  const hasBusiness = deal.has_business || deal.business
  const tier = deal.business_type_tier

  return (
    <div
      onClick={onClick}
      className={`
        p-3 rounded-xl border cursor-pointer transition-all group
        ${isSelected 
          ? 'border-orange-400 bg-orange-50 shadow-sm' 
          : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
        }
        ${isHighPriority ? 'ring-1 ring-red-200' : ''}
        ${tier === 'premium' ? 'border-l-2 border-l-amber-400' : ''}
        ${tier === 'high' ? 'border-l-2 border-l-purple-400' : ''}
      `}
    >
      <div className="flex items-start gap-3">
        {/* Status Indicator */}
        <div className={`
          mt-0.5 w-2 h-2 rounded-full flex-shrink-0
          ${deal.status === 'evaluated' 
            ? isHighPriority ? 'bg-red-500' : 'bg-green-500'
            : deal.status === 'evaluating' 
            ? 'bg-blue-500 animate-pulse' 
            : 'bg-orange-500'
          }
        `} />

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1">
            <div className="flex items-center gap-2">
              <h3 className="font-medium text-sm text-slate-900 line-clamp-1 leading-tight">
                {deal.business_name || deal.address}
              </h3>
              {getTierBadge(tier)}
            </div>
            {deal.score !== null && deal.score !== undefined && (
              <span className={`text-sm font-bold flex-shrink-0 ${getScoreColor(deal.score)}`}>
                {Math.round(deal.score)}%
              </span>
            )}
          </div>

          {deal.address && deal.business_name && (
            <p className="text-xs text-slate-500 mb-1.5 line-clamp-1">{deal.address}</p>
          )}

          {/* Business Association Badge */}
          <div className="flex items-center gap-1.5 flex-wrap mb-2">
            {hasBusiness ? (
              <>
                <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-blue-50 text-blue-700 flex items-center gap-1">
                  <Building2 className="h-2.5 w-2.5" />
                  {deal.business?.category || 'Business'}
                </span>
                {deal.business?.phone && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-green-50 text-green-700 flex items-center gap-1">
                    <Phone className="h-2.5 w-2.5" />
                    Has Phone
                  </span>
                )}
                {deal.business?.website && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-cyan-50 text-cyan-700 flex items-center gap-1">
                    <Globe className="h-2.5 w-2.5" />
                    Website
                  </span>
                )}
              </>
            ) : (
              <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-amber-50 text-amber-700 flex items-center gap-1">
                <AlertCircle className="h-2.5 w-2.5" />
                No Business Data
              </span>
            )}
          </div>

          {/* Score Bar */}
          {deal.score !== null && deal.score !== undefined && (
            <div className="h-1 bg-slate-100 rounded-full overflow-hidden mb-2">
              <div 
                className="h-full rounded-full transition-all"
                style={{ 
                  width: `${deal.score}%`,
                  background: deal.score < 50 
                    ? 'linear-gradient(90deg, #ef4444, #f97316)' 
                    : 'linear-gradient(90deg, #22c55e, #84cc16)'
                }}
              />
            </div>
          )}

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className={`
                text-[10px] px-1.5 py-0.5 rounded font-medium uppercase tracking-wide
                ${deal.status === 'evaluated' 
                  ? 'bg-green-100 text-green-700' 
                  : deal.status === 'evaluating'
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-orange-100 text-orange-700'
                }
              `}>
                {deal.status}
              </span>
              {isHighPriority && (
                <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-red-100 text-red-700 flex items-center gap-0.5">
                  <TrendingDown className="h-2.5 w-2.5" />
                  Lead
                </span>
              )}
            </div>
            <button 
              onClick={(e) => { e.stopPropagation(); onViewDetails(); }}
              className="text-[11px] font-medium text-orange-600 hover:text-orange-700 opacity-0 group-hover:opacity-100 transition-opacity"
            >
              Details →
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-8">
      <div className="w-16 h-16 rounded-2xl bg-orange-50 flex items-center justify-center mb-4">
        <MapPin className="h-8 w-8 text-orange-300" />
      </div>
      <h3 className="font-semibold text-slate-900 mb-1">No parking lots yet</h3>
      <p className="text-sm text-slate-500 max-w-[220px]">
        Click anywhere on the map to discover parking lots in that area
      </p>
    </div>
  )
}

function Stat({ 
  label, 
  value, 
  color = 'text-slate-900' 
}: { 
  label: string
  value: number
  color?: string
}) {
  return (
    <div className="text-center">
      <p className={`text-lg font-semibold ${color}`}>{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  )
}
