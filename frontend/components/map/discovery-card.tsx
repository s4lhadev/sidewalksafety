'use client'

import { useState, useEffect } from 'react'
import { X, Loader2, MapPin, CheckCircle2, AlertCircle, Hash, Map as MapIcon } from 'lucide-react'

interface LocationInfo {
  zip?: string
  city?: string
  county?: string
  state?: string
}

interface DiscoveryCardProps {
  lat: number
  lng: number
  onDiscover: (type: 'zip' | 'county', value: string, state?: string) => void
  onClose: () => void
  isDiscovering: boolean
}

export function DiscoveryCard({ lat, lng, onDiscover, onClose, isDiscovering }: DiscoveryCardProps) {
  const [locationInfo, setLocationInfo] = useState<LocationInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pendingAction, setPendingAction] = useState<'zip' | 'county' | null>(null)

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
    
    if (pendingAction === 'zip' && locationInfo.zip) {
      onDiscover('zip', locationInfo.zip)
    } else if (pendingAction === 'county' && locationInfo.county && locationInfo.state) {
      onDiscover('county', locationInfo.county, locationInfo.state)
    }
  }

  const handleCancel = () => {
    setPendingAction(null)
  }

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
            {/* Location Display - Elegant */}
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

            {/* Confirmation State */}
            {pendingAction ? (
              <div className="space-y-3">
                <div className="flex items-start gap-3 p-3 bg-orange-50 rounded-lg border border-orange-200">
                  <AlertCircle className="h-5 w-5 text-orange-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-900 mb-1">
                      Confirm Discovery
                    </p>
                    <p className="text-xs text-slate-600">
                      {pendingAction === 'zip' 
                        ? `Discover parking lots in ZIP code ${locationInfo.zip}?`
                        : `Discover parking lots in ${locationInfo.county} County?`
                      }
                    </p>
                    <p className="text-xs text-slate-500 mt-1.5">
                      This will start discovering parking lots in the selected area
                    </p>
                  </div>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={handleCancel}
                    className="flex-1 px-3 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-all text-sm font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleConfirm}
                    disabled={isDiscovering}
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
                        Confirm
                      </>
                    )}
                  </button>
                </div>
              </div>
            ) : (
              /* Action Buttons */
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
