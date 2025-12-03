'use client'

import { useMemo, useCallback, useEffect, useState } from 'react'
import { APIProvider, Map, Marker, useMap, InfoWindow } from '@vis.gl/react-google-maps'
import { DealMapResponse } from '@/types'
import { MapPin, ExternalLink, Satellite, Map as MapIcon } from 'lucide-react'

interface InteractiveMapProps {
  deals: DealMapResponse[]
  selectedDeal: DealMapResponse | null
  onDealSelect: (deal: DealMapResponse | null) => void
  onViewDetails: (dealId: string) => void
  onBoundsChange?: (bounds: { minLat: number; maxLat: number; minLng: number; maxLng: number }) => void
  onMapClick?: (lat: number, lng: number) => void
  clickedLocation?: { lat: number; lng: number } | null
}

// Clean, minimal light map style
const mapStyles: google.maps.MapTypeStyle[] = [
  {
    featureType: 'all',
    elementType: 'geometry',
    stylers: [{ color: '#f5f5f5' }],
  },
  {
    featureType: 'water',
    elementType: 'geometry',
    stylers: [{ color: '#e9e9e9' }],
  },
  {
    featureType: 'water',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#9e9e9e' }],
  },
  {
    featureType: 'road',
    elementType: 'geometry',
    stylers: [{ color: '#ffffff' }],
  },
  {
    featureType: 'road.arterial',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#757575' }],
  },
  {
    featureType: 'road.highway',
    elementType: 'geometry',
    stylers: [{ color: '#dadada' }],
  },
  {
    featureType: 'road.highway',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#616161' }],
  },
  {
    featureType: 'road.local',
    elementType: 'labels',
    stylers: [{ visibility: 'off' }],
  },
  {
    featureType: 'poi',
    stylers: [{ visibility: 'off' }],
  },
  {
    featureType: 'poi.park',
    elementType: 'geometry',
    stylers: [{ visibility: 'on' }, { color: '#e5e5e5' }],
  },
  {
    featureType: 'transit',
    stylers: [{ visibility: 'off' }],
  },
  {
    featureType: 'administrative',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#c9c9c9' }],
  },
  {
    featureType: 'administrative.locality',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#484848' }],
  },
  {
    featureType: 'administrative.neighborhood',
    stylers: [{ visibility: 'off' }],
  },
]

function MapController({
  onBoundsChange,
  onMapClick,
}: {
  onBoundsChange?: (bounds: { minLat: number; maxLat: number; minLng: number; maxLng: number }) => void
  onMapClick?: (lat: number, lng: number) => void
}) {
  const map = useMap()

  useEffect(() => {
    if (!map) return

    const handleIdle = () => {
      const bounds = map.getBounds()
      if (bounds && onBoundsChange) {
        const ne = bounds.getNorthEast()
        const sw = bounds.getSouthWest()
        onBoundsChange({
          minLat: sw.lat(),
          maxLat: ne.lat(),
          minLng: sw.lng(),
          maxLng: ne.lng(),
        })
      }
    }

    const handleClick = (e: google.maps.MapMouseEvent) => {
      if (e.latLng && onMapClick) {
        onMapClick(e.latLng.lat(), e.latLng.lng())
      }
    }

    map.addListener('idle', handleIdle)
    map.addListener('click', handleClick)
    handleIdle()

    return () => {
      google.maps.event.clearListeners(map, 'idle')
      google.maps.event.clearListeners(map, 'click')
    }
  }, [map, onBoundsChange, onMapClick])

  return null
}

function MapTypeController({
  mapType,
  onMapTypeChange,
}: {
  mapType: 'roadmap' | 'hybrid'
  onMapTypeChange: (type: 'roadmap' | 'hybrid') => void
}) {
  const map = useMap()

  useEffect(() => {
    if (!map) return
    map.setMapTypeId(mapType)
  }, [map, mapType])

  return null
}

export function InteractiveMap({
  deals,
  selectedDeal,
  onDealSelect,
  onViewDetails,
  onBoundsChange,
  onMapClick,
  clickedLocation,
}: InteractiveMapProps) {
  const [mapType, setMapType] = useState<'roadmap' | 'hybrid'>('roadmap')
  
  const dealsWithLocation = useMemo(
    () => deals.filter((deal) => deal.latitude && deal.longitude),
    [deals]
  )

  const defaultCenter = useMemo(() => {
    if (dealsWithLocation.length === 0) {
      return { lat: 37.7749, lng: -122.4194 }
    }

    const lats = dealsWithLocation.map((d) => d.latitude!).filter(Boolean)
    const lngs = dealsWithLocation.map((d) => d.longitude!).filter(Boolean)

    return {
      lat: lats.reduce((a, b) => a + b, 0) / lats.length,
      lng: lngs.reduce((a, b) => a + b, 0) / lngs.length,
    }
  }, [dealsWithLocation])

  const handleMarkerClick = useCallback((deal: DealMapResponse) => {
    onDealSelect(deal)
  }, [onDealSelect])

  const toggleMapType = useCallback(() => {
    setMapType((prev) => (prev === 'roadmap' ? 'hybrid' : 'roadmap'))
  }, [])

  if (!process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY) {
    return (
      <div className="flex items-center justify-center h-full bg-slate-50">
        <div className="text-center">
          <MapPin className="h-12 w-12 text-slate-300 mx-auto mb-3" />
          <p className="text-sm text-slate-500">
            Google Maps API key not configured
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="relative w-full h-full cursor-crosshair">
      {/* Map Type Toggle Button */}
      <button
        onClick={toggleMapType}
        className="absolute top-4 right-4 z-10 flex items-center gap-2 px-3 py-2 bg-white rounded-lg shadow-lg hover:shadow-xl transition-all hover:scale-105 border border-slate-200"
        title={mapType === 'roadmap' ? 'Switch to Satellite' : 'Switch to Map'}
      >
        {mapType === 'roadmap' ? (
          <>
            <Satellite className="h-4 w-4 text-slate-700" />
            <span className="text-sm font-medium text-slate-700">Satellite</span>
          </>
        ) : (
          <>
            <MapIcon className="h-4 w-4 text-slate-700" />
            <span className="text-sm font-medium text-slate-700">Map</span>
          </>
        )}
      </button>

      <APIProvider apiKey={process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY}>
        <Map
          defaultCenter={defaultCenter}
          defaultZoom={dealsWithLocation.length > 0 ? 13 : 10}
          gestureHandling="greedy"
          disableDefaultUI={true}
          zoomControl={false}
          mapTypeControl={false}
          fullscreenControl={false}
          streetViewControl={false}
          clickableIcons={false}
          styles={mapType === 'roadmap' ? mapStyles : undefined}
          className="w-full h-full"
        >
          <MapController onBoundsChange={onBoundsChange} onMapClick={onMapClick} />
          <MapTypeController mapType={mapType} onMapTypeChange={setMapType} />

          {dealsWithLocation.map((deal) => (
            <ParkingLotMarker
              key={deal.id}
              deal={deal}
              isSelected={selectedDeal?.id === deal.id}
              onClick={() => handleMarkerClick(deal)}
            />
          ))}

          {/* Selected location marker */}
          {clickedLocation && (
            <Marker
              position={clickedLocation}
              icon={{
                url: `data:image/svg+xml,${encodeURIComponent(`
                  <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
                    <circle cx="24" cy="24" r="20" fill="none" stroke="#f97316" stroke-width="3" opacity="0.3">
                      <animate attributeName="r" from="12" to="22" dur="1.5s" repeatCount="indefinite"/>
                      <animate attributeName="opacity" from="0.6" to="0" dur="1.5s" repeatCount="indefinite"/>
                    </circle>
                    <circle cx="24" cy="24" r="12" fill="#f97316" stroke="white" stroke-width="3"/>
                    <circle cx="24" cy="24" r="4" fill="white"/>
                  </svg>
                `)}`,
                scaledSize: { width: 48, height: 48 },
                anchor: { x: 24, y: 24 },
              }}
            />
          )}


          {/* Parking lot info window */}
          {selectedDeal && selectedDeal.latitude && selectedDeal.longitude && (
            <InfoWindow
              position={{ lat: selectedDeal.latitude, lng: selectedDeal.longitude }}
              onCloseClick={() => onDealSelect(null)}
              pixelOffset={[0, -40]}
            >
              <ParkingLotPopup 
                deal={selectedDeal} 
                onViewDetails={() => onViewDetails(selectedDeal.id)}
                onClose={() => onDealSelect(null)}
              />
            </InfoWindow>
          )}
        </Map>
      </APIProvider>
    </div>
  )
}

function ParkingLotMarker({ 
  deal, 
  isSelected, 
  onClick 
}: { 
  deal: DealMapResponse
  isSelected: boolean
  onClick: () => void 
}) {
  const getMarkerIcon = () => {
    let color = '#f97316'
    
    if (deal.status === 'evaluated') {
      color = deal.score && deal.score < 50 ? '#ef4444' : '#22c55e'
    } else if (deal.status === 'evaluating') {
      color = '#3b82f6'
    }

    const scale = isSelected ? 1.3 : 1
    const size = 32 * scale

    return {
      url: `data:image/svg+xml,${encodeURIComponent(`
        <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10" fill="${color}" stroke="white" stroke-width="2"/>
          <circle cx="12" cy="12" r="4" fill="white"/>
        </svg>
      `)}`,
      scaledSize: { width: size, height: size },
      anchor: { x: size / 2, y: size / 2 },
    }
  }

  return (
    <Marker
      position={{ lat: deal.latitude!, lng: deal.longitude! }}
      onClick={onClick}
      icon={getMarkerIcon()}
    />
  )
}

function ParkingLotPopup({ 
  deal, 
  onViewDetails,
  onClose 
}: { 
  deal: DealMapResponse
  onViewDetails: () => void
  onClose: () => void
}) {
  const getScoreColor = (score: number) => {
    if (score < 30) return 'text-red-500'
    if (score < 50) return 'text-orange-500'
    if (score < 70) return 'text-yellow-600'
    return 'text-green-500'
  }

  const getScoreLabel = (score: number) => {
    if (score < 30) return 'Poor - High Priority Lead'
    if (score < 50) return 'Fair - Good Lead'
    if (score < 70) return 'Good - Moderate Lead'
    return 'Excellent - Low Priority'
  }

  return (
    <div className="w-72 p-0 -m-2">
      {/* Satellite Image */}
      {deal.satellite_url ? (
        <div className="relative h-36 bg-slate-100 rounded-t-lg overflow-hidden">
          <img 
            src={deal.satellite_url} 
            alt="Satellite view"
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
          <div className="absolute bottom-2 left-2 right-2">
            <p className="text-white text-xs font-medium truncate">{deal.address || deal.business_name}</p>
          </div>
        </div>
      ) : (
        <div className="h-24 bg-slate-100 rounded-t-lg flex items-center justify-center">
          <MapPin className="h-8 w-8 text-slate-300" />
        </div>
      )}

      {/* Content */}
      <div className="p-3 space-y-3">
        {/* Score */}
        {deal.score !== null && deal.score !== undefined && (
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">Condition Score</span>
              <span className={`text-lg font-bold ${getScoreColor(deal.score)}`}>
                {Math.round(deal.score)}%
              </span>
            </div>
            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
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
            <p className="text-xs text-slate-500">{getScoreLabel(deal.score)}</p>
          </div>
        )}

        {/* Status Badge */}
        <div className="flex items-center justify-between">
          <span className={`
            text-xs px-2 py-1 rounded-full font-medium
            ${deal.status === 'evaluated' 
              ? 'bg-green-100 text-green-700' 
              : deal.status === 'evaluating'
              ? 'bg-blue-100 text-blue-700'
              : 'bg-orange-100 text-orange-700'
            }
          `}>
            {deal.status.charAt(0).toUpperCase() + deal.status.slice(1)}
          </span>
          <button
            onClick={onViewDetails}
            className="text-xs font-medium text-orange-600 hover:text-orange-700 flex items-center gap-1"
          >
            View Details
            <ExternalLink className="h-3 w-3" />
          </button>
        </div>
      </div>
    </div>
  )
}
