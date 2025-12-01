'use client'

import { useMemo, useCallback, useState, useEffect } from 'react'
import { APIProvider, Map, Marker, useMap } from '@vis.gl/react-google-maps'
import { DealMapResponse } from '@/types'
import { DealMarker } from './deal-marker'
import { DealInfoBadge } from './deal-info-badge'

interface InteractiveMapProps {
  deals: DealMapResponse[]
  selectedDeal: DealMapResponse | null
  onDealSelect: (deal: DealMapResponse | null) => void
  onViewDetails: (dealId: string) => void
  onBoundsChange?: (bounds: { minLat: number; maxLat: number; minLng: number; maxLng: number }) => void
}

// Elegant minimalist map style - Stripe-inspired dark theme
const mapStyles: google.maps.MapTypeStyle[] = [
  {
    featureType: 'all',
    elementType: 'geometry',
    stylers: [{ color: '#0a0a0a' }],
  },
  {
    featureType: 'water',
    elementType: 'geometry',
    stylers: [{ color: '#0d0d0d' }],
  },
  {
    featureType: 'road',
    elementType: 'geometry',
    stylers: [{ color: '#1a1a1a' }],
  },
  {
    featureType: 'road.arterial',
    elementType: 'labels.text.fill',
    stylers: [{ visibility: 'on' }, { color: '#666666' }],
  },
  {
    featureType: 'road.highway',
    elementType: 'labels.text.fill',
    stylers: [{ visibility: 'on' }, { color: '#888888' }],
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
    featureType: 'transit',
    stylers: [{ visibility: 'off' }],
  },
  {
    featureType: 'administrative',
    elementType: 'geometry',
    stylers: [{ color: '#1a1a1a' }],
  },
  {
    featureType: 'administrative.locality',
    elementType: 'labels.text.fill',
    stylers: [{ visibility: 'on' }, { color: '#ffffff' }],
  },
]

function MapLoadHandler({
  onMapLoad,
  onBoundsChange,
}: {
  onMapLoad: (map: google.maps.Map) => void
  onBoundsChange?: (bounds: { minLat: number; maxLat: number; minLng: number; maxLng: number }) => void
}) {
  const map = useMap()

  useEffect(() => {
    if (!map) return

    onMapLoad(map)

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

    map.addListener('idle', handleIdle)
    handleIdle() // Initial bounds

    return () => {
      google.maps.event.clearListeners(map, 'idle')
    }
  }, [map, onMapLoad, onBoundsChange])

  return null
}

export function InteractiveMap({
  deals,
  selectedDeal,
  onDealSelect,
  onViewDetails,
  onBoundsChange,
}: InteractiveMapProps) {
  const [mapInstance, setMapInstance] = useState<google.maps.Map | null>(null)
  const [isMapLoaded, setIsMapLoaded] = useState(false)

  const handleMapLoad = useCallback((map: google.maps.Map) => {
    setMapInstance(map)
    setIsMapLoaded(true)
  }, [])

  const dealsWithLocation = useMemo(
    () => deals.filter((deal) => deal.latitude && deal.longitude),
    [deals]
  )

  const defaultCenter = useMemo(() => {
    if (dealsWithLocation.length === 0) {
      return { lat: 37.7749, lng: -122.4194 } // San Francisco default
    }

    const lats = dealsWithLocation.map((d) => d.latitude!).filter(Boolean)
    const lngs = dealsWithLocation.map((d) => d.longitude!).filter(Boolean)

    return {
      lat: lats.reduce((a, b) => a + b, 0) / lats.length,
      lng: lngs.reduce((a, b) => a + b, 0) / lngs.length,
    }
  }, [dealsWithLocation])

  const handleMarkerClick = useCallback(
    (deal: DealMapResponse) => {
      onDealSelect(deal)
    },
    [onDealSelect]
  )

  const handleMapClick = useCallback(() => {
    onDealSelect(null)
  }, [onDealSelect])

  if (!process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY) {
    return (
      <div className="flex items-center justify-center h-full bg-muted/20 rounded-lg">
        <p className="text-sm text-muted-foreground">
          Google Maps API key not configured
        </p>
      </div>
    )
  }

  return (
    <div className="relative w-full h-full rounded-lg overflow-hidden">
      <APIProvider apiKey={process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY}>
        <Map
          defaultCenter={defaultCenter}
          defaultZoom={dealsWithLocation.length > 0 ? 12 : 10}
          gestureHandling="greedy"
          disableDefaultUI={true}
          zoomControl={true}
          mapTypeControl={false}
          fullscreenControl={false}
          streetViewControl={false}
          clickableIcons={false}
          styles={mapStyles}
          onClick={handleMapClick}
          className="w-full h-full"
        >
          <MapLoadHandler onMapLoad={handleMapLoad} onBoundsChange={onBoundsChange} />

          {isMapLoaded &&
            dealsWithLocation.map((deal) => (
              <DealMarker
                key={deal.id}
                deal={deal}
                position={{ lat: deal.latitude!, lng: deal.longitude! }}
                isSelected={selectedDeal?.id === deal.id}
                onClick={() => handleMarkerClick(deal)}
              />
            ))}
        </Map>
      </APIProvider>

      {selectedDeal && (
        <div className="absolute top-4 left-4 z-10">
          <DealInfoBadge
            deal={selectedDeal}
            onClose={() => onDealSelect(null)}
            onViewDetails={() => onViewDetails(selectedDeal.id)}
          />
        </div>
      )}
    </div>
  )
}

