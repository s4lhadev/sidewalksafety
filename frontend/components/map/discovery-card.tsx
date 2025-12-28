'use client'

import { useState, useEffect } from 'react'
import { 
  X, 
  Loader2, 
  MapPin, 
  CheckCircle2, 
  AlertCircle, 
  Hash, 
  Map as MapIcon,
  Trophy,
  Star,
  ChevronDown,
  ChevronUp,
  Building2,
  Settings2
} from 'lucide-react'

interface LocationInfo {
  zip?: string
  city?: string
  county?: string
  state?: string
}

interface BusinessType {
  id: string
  label: string
  queries: string[]
}

interface Tier {
  id: string
  label: string
  icon: string
  description: string
  types: BusinessType[]
}

interface DiscoveryCardProps {
  lat: number
  lng: number
  onDiscover: (type: 'zip' | 'county', value: string, state?: string, businessTypeIds?: string[], maxResults?: number) => void
  onClose: () => void
  isDiscovering: boolean
}

// Business type options (matches backend)
const BUSINESS_TIERS: Tier[] = [
  {
    id: 'premium',
    label: 'Premium',
    icon: 'trophy',
    description: 'Residential with large parking & roads',
    types: [
      { id: 'apartments', label: 'Apartment Complexes', queries: [] },
      { id: 'condos', label: 'Condo Buildings', queries: [] },
      { id: 'townhomes', label: 'Townhome Communities', queries: [] },
      { id: 'mobile_home', label: 'Mobile Home Parks', queries: [] },
    ],
  },
  {
    id: 'high',
    label: 'High Priority',
    icon: 'star',
    description: 'Commercial with large parking',
    types: [
      { id: 'shopping', label: 'Shopping Centers / Malls', queries: [] },
      { id: 'hotels', label: 'Hotels / Motels', queries: [] },
      { id: 'offices', label: 'Office Parks / Complexes', queries: [] },
      { id: 'warehouses', label: 'Warehouses / Industrial', queries: [] },
    ],
  },
  {
    id: 'standard',
    label: 'Standard',
    icon: 'map-pin',
    description: 'Other businesses',
    types: [
      { id: 'churches', label: 'Churches', queries: [] },
      { id: 'schools', label: 'Schools', queries: [] },
      { id: 'hospitals', label: 'Hospitals / Medical', queries: [] },
      { id: 'gyms', label: 'Gyms / Fitness', queries: [] },
      { id: 'grocery', label: 'Grocery Stores', queries: [] },
      { id: 'car_dealers', label: 'Car Dealerships', queries: [] },
    ],
  },
]

// Default selected types (premium tier)
const DEFAULT_SELECTED = ['apartments', 'condos', 'townhomes', 'mobile_home']

export function DiscoveryCard({ lat, lng, onDiscover, onClose, isDiscovering }: DiscoveryCardProps) {
  const [locationInfo, setLocationInfo] = useState<LocationInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pendingAction, setPendingAction] = useState<'zip' | 'county' | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set(DEFAULT_SELECTED))
  const [expandedTiers, setExpandedTiers] = useState<Set<string>>(new Set(['premium']))
  const [maxResults, setMaxResults] = useState<number>(10)

  useEffect(() => {
    const geocode = async () => {
      setIsLoading(true)
      setError(null)
      
      try {
        const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
        const response = await fetch(
          `https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lng}&key=${apiKey}`
        )
        const data = await response.json()
        
        if (data.status !== 'OK' || !data.results?.length) {
          setError('Location not found')
          return
        }

        const components = data.results[0].address_components || []
        const info: LocationInfo = {}

        for (const component of components) {
          if (component.types.includes('postal_code')) {
            info.zip = component.long_name
          }
          if (component.types.includes('locality')) {
            info.city = component.long_name
          }
          if (component.types.includes('administrative_area_level_2')) {
            info.county = component.long_name.replace(' County', '')
          }
          if (component.types.includes('administrative_area_level_1')) {
            info.state = component.short_name
          }
        }

        setLocationInfo(info)
      } catch (err) {
        setError('Failed to load')
      } finally {
        setIsLoading(false)
      }
    }

    geocode()
  }, [lat, lng])

  const handlePreviewZip = () => {
    if (!locationInfo?.zip) return
    setPendingAction('zip')
  }

  const handlePreviewCounty = () => {
    if (!locationInfo?.county || !locationInfo?.state) return
    setPendingAction('county')
  }

  const handleConfirm = () => {
    if (!pendingAction || !locationInfo) return
    
    const typeIds = Array.from(selectedTypes)
    
    if (pendingAction === 'zip' && locationInfo.zip) {
      onDiscover('zip', locationInfo.zip, undefined, typeIds.length > 0 ? typeIds : undefined, maxResults)
    } else if (pendingAction === 'county' && locationInfo.county && locationInfo.state) {
      onDiscover('county', locationInfo.county, locationInfo.state, typeIds.length > 0 ? typeIds : undefined, maxResults)
    }
  }

  const handleCancel = () => {
    setPendingAction(null)
    setShowAdvanced(false)
  }

  const toggleType = (typeId: string) => {
    const newSelected = new Set(selectedTypes)
    if (newSelected.has(typeId)) {
      newSelected.delete(typeId)
    } else {
      newSelected.add(typeId)
    }
    setSelectedTypes(newSelected)
  }

  const toggleTier = (tierId: string) => {
    const tier = BUSINESS_TIERS.find(t => t.id === tierId)
    if (!tier) return
    
    const tierTypeIds = tier.types.map(t => t.id)
    const allSelected = tierTypeIds.every(id => selectedTypes.has(id))
    
    const newSelected = new Set(selectedTypes)
    if (allSelected) {
      tierTypeIds.forEach(id => newSelected.delete(id))
    } else {
      tierTypeIds.forEach(id => newSelected.add(id))
    }
    setSelectedTypes(newSelected)
  }

  const toggleTierExpand = (tierId: string) => {
    const newExpanded = new Set(expandedTiers)
    if (newExpanded.has(tierId)) {
      newExpanded.delete(tierId)
    } else {
      newExpanded.add(tierId)
    }
    setExpandedTiers(newExpanded)
  }

  const getTierIcon = (iconName: string) => {
    switch (iconName) {
      case 'trophy': return <Trophy className="h-4 w-4" />
      case 'star': return <Star className="h-4 w-4" />
      default: return <MapPin className="h-4 w-4" />
    }
  }

  const getTierSelectedCount = (tier: Tier) => {
    return tier.types.filter(t => selectedTypes.has(t.id)).length
  }

  const totalSelected = selectedTypes.size

  return (
    <div className="bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden w-80 animate-slide-in">
      {/* Header */}
      <div className="px-4 py-3 bg-gradient-to-r from-orange-500 to-orange-600 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MapPin className="h-4 w-4 text-white" />
          <span className="text-white font-medium text-sm">Discover Area</span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-lg hover:bg-white/20 transition-colors text-white/80 hover:text-white"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Content */}
      <div className="p-4">
        {isLoading ? (
          <div className="flex items-center justify-center py-6">
            <Loader2 className="h-5 w-5 animate-spin text-orange-500" />
            <span className="ml-2 text-sm text-slate-500">Identifying location...</span>
          </div>
        ) : error ? (
          <div className="text-center py-6">
            <p className="text-sm text-slate-500">{error}</p>
          </div>
        ) : locationInfo ? (
          <div className="space-y-4">
            {/* Location Display */}
            <div className="text-center pb-3 border-b border-slate-100">
              {locationInfo.city && (
                <p className="text-base font-semibold text-slate-900">
                  {locationInfo.city}
                </p>
              )}
              {locationInfo.zip && (
                <p className="text-sm font-medium text-orange-600 mt-1">
                  ZIP: {locationInfo.zip}
                </p>
              )}
              {locationInfo.state && (
                <p className="text-sm text-slate-500 mt-0.5">
                  {locationInfo.state}
                </p>
              )}
              {locationInfo.county && (
                <p className="text-xs text-slate-400 mt-1">
                  {locationInfo.county} County
                </p>
              )}
            </div>

            {/* Confirmation State with Business Type Selection */}
            {pendingAction ? (
              <div className="space-y-3">
                {/* Summary */}
                <div className="flex items-start gap-3 p-3 bg-orange-50 rounded-lg border border-orange-200">
                  <Building2 className="h-5 w-5 text-orange-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-900 mb-1">
                      {pendingAction === 'zip' 
                        ? `ZIP ${locationInfo.zip}`
                        : `${locationInfo.county} County`
                      }
                    </p>
                    <p className="text-xs text-slate-600">
                      {totalSelected} business type{totalSelected !== 1 ? 's' : ''} selected
                    </p>
                  </div>
                </div>

                {/* Max Results Input */}
                <div className="flex items-center gap-3 px-3 py-2 bg-slate-50 rounded-lg">
                  <label htmlFor="maxResults" className="text-sm text-slate-600 whitespace-nowrap">
                    Max businesses:
                  </label>
                  <input
                    id="maxResults"
                    type="number"
                    min={1}
                    max={50}
                    value={maxResults}
                    onChange={(e) => setMaxResults(Math.max(1, Math.min(50, parseInt(e.target.value) || 1)))}
                    className="w-16 px-2 py-1 text-sm border border-slate-200 rounded-md focus:ring-2 focus:ring-orange-500 focus:border-orange-500 text-center"
                  />
                </div>

                {/* Business Type Selection */}
                <div className="space-y-2">
                  <button
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="w-full flex items-center justify-between px-3 py-2 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors text-sm"
                  >
                    <div className="flex items-center gap-2 text-slate-700">
                      <Settings2 className="h-4 w-4" />
                      <span className="font-medium">Business Types</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-500">{totalSelected} selected</span>
                      {showAdvanced ? (
                        <ChevronUp className="h-4 w-4 text-slate-400" />
                      ) : (
                        <ChevronDown className="h-4 w-4 text-slate-400" />
                      )}
                    </div>
                  </button>

                  {showAdvanced && (
                    <div className="max-h-64 overflow-y-auto space-y-2 border border-slate-200 rounded-lg p-2">
                      {BUSINESS_TIERS.map((tier) => {
                        const tierCount = getTierSelectedCount(tier)
                        const allSelected = tierCount === tier.types.length
                        const isExpanded = expandedTiers.has(tier.id)
                        
                        return (
                          <div key={tier.id} className="border border-slate-100 rounded-lg overflow-hidden">
                            {/* Tier Header */}
                            <div 
                              className={`flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-slate-50 ${
                                tier.id === 'premium' ? 'bg-amber-50' : 
                                tier.id === 'high' ? 'bg-purple-50' : 'bg-slate-50'
                              }`}
                            >
                              <button
                                onClick={() => toggleTier(tier.id)}
                                className={`w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center ${
                                  allSelected 
                                    ? 'bg-orange-500 border-orange-500 text-white' 
                                    : tierCount > 0
                                    ? 'bg-orange-200 border-orange-300'
                                    : 'border-slate-300'
                                }`}
                              >
                                {allSelected && <CheckCircle2 className="h-3 w-3" />}
                              </button>
                              
                              <div className="flex-1 flex items-center gap-2" onClick={() => toggleTierExpand(tier.id)}>
                                <span className={`${
                                  tier.id === 'premium' ? 'text-amber-600' : 
                                  tier.id === 'high' ? 'text-purple-600' : 'text-slate-600'
                                }`}>
                                  {getTierIcon(tier.icon)}
                                </span>
                                <span className="text-xs font-medium text-slate-700">{tier.label}</span>
                                <span className="text-[10px] text-slate-400">({tierCount}/{tier.types.length})</span>
                              </div>
                              
                              <button onClick={() => toggleTierExpand(tier.id)}>
                                {isExpanded ? (
                                  <ChevronUp className="h-4 w-4 text-slate-400" />
                                ) : (
                                  <ChevronDown className="h-4 w-4 text-slate-400" />
                                )}
                              </button>
                            </div>
                            
                            {/* Tier Types */}
                            {isExpanded && (
                              <div className="px-3 py-2 space-y-1 bg-white">
                                {tier.types.map((type) => (
                                  <label 
                                    key={type.id}
                                    className="flex items-center gap-2 cursor-pointer hover:bg-slate-50 px-2 py-1 rounded"
                                  >
                                    <input
                                      type="checkbox"
                                      checked={selectedTypes.has(type.id)}
                                      onChange={() => toggleType(type.id)}
                                      className="w-3.5 h-3.5 rounded border-slate-300 text-orange-500 focus:ring-orange-500"
                                    />
                                    <span className="text-xs text-slate-600">{type.label}</span>
                                  </label>
                                ))}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>

                {/* Action Buttons */}
                <div className="flex gap-2">
                  <button
                    onClick={handleCancel}
                    className="flex-1 px-3 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-all text-sm font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleConfirm}
                    disabled={isDiscovering || totalSelected === 0}
                    className="flex-1 px-3 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition-all disabled:opacity-50 text-sm font-medium flex items-center justify-center gap-1.5"
                  >
                    {isDiscovering ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Starting...
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="h-4 w-4" />
                        Discover
                      </>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              /* Initial Action Buttons */
              <div className="flex gap-2">
                {locationInfo.zip && (
                  <button
                    onClick={handlePreviewZip}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 bg-gradient-to-r from-orange-500 to-orange-600 text-white rounded-lg hover:from-orange-600 hover:to-orange-700 transition-all shadow-sm hover:shadow-md"
                  >
                    <Hash className="h-4 w-4" />
                    <span className="font-medium text-sm">ZIP</span>
                  </button>
                )}

                {locationInfo.county && locationInfo.state && (
                  <button
                    onClick={handlePreviewCounty}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-all"
                  >
                    <MapIcon className="h-4 w-4" />
                    <span className="font-medium text-sm">County</span>
                  </button>
                )}
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  )
}
