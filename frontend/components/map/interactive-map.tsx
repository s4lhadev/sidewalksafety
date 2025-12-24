'use client'

import { useMemo, useCallback, useEffect, useState, useRef } from 'react'
import { APIProvider, Map, Marker, useMap, InfoWindow } from '@vis.gl/react-google-maps'
import { MarkerClusterer, GridAlgorithm } from '@googlemaps/markerclusterer'
import { DealMapResponse } from '@/types'
import { MapPin, ExternalLink, Satellite, Map as MapIcon, X, CheckCircle2, Clock, Target, Building2, Phone, Globe, AlertTriangle } from 'lucide-react'
import { StatusChip, IconChip } from '@/components/ui'
import { cn } from '@/lib/utils'
import { parkingLotsApi } from '@/lib/api/parking-lots'

interface InteractiveMapProps {
  deals: DealMapResponse[]
  selectedDeal: DealMapResponse | null
  onDealSelect: (deal: DealMapResponse | null) => void
  onViewDetails: (dealId: string) => void
  onBoundsChange?: (bounds: { minLat: number; maxLat: number; minLng: number; maxLng: number }) => void
  onMapClick?: (lat: number, lng: number) => void
  clickedLocation?: { lat: number; lng: number } | null
}

// Clean, modern map style with subtle colors
const mapStyles: google.maps.MapTypeStyle[] = [
  // Base landscape - warm cream/beige
  {
    featureType: 'landscape',
    elementType: 'geometry.fill',
    stylers: [{ color: '#f5f3ef' }],
  },
  {
    featureType: 'landscape.man_made',
    elementType: 'geometry.fill',
    stylers: [{ color: '#f0ede8' }],
  },
  // Water - soft blue
  {
    featureType: 'water',
    elementType: 'geometry.fill',
    stylers: [{ color: '#d4e4ed' }],
  },
  {
    featureType: 'water',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#7da0b8' }],
  },
  // Parks and green areas - muted sage
  {
    featureType: 'poi.park',
    elementType: 'geometry.fill',
    stylers: [{ color: '#dce8dc' }],
  },
  {
    featureType: 'poi.park',
    elementType: 'labels',
    stylers: [{ visibility: 'off' }],
  },
  // Hide other POIs
  {
    featureType: 'poi',
    elementType: 'labels',
    stylers: [{ visibility: 'off' }],
  },
  {
    featureType: 'poi.business',
    stylers: [{ visibility: 'off' }],
  },
  // Roads - clean hierarchy
  {
    featureType: 'road.highway',
    elementType: 'geometry.fill',
    stylers: [{ color: '#ffffff' }],
  },
  {
    featureType: 'road.highway',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#e0ddd8' }, { weight: 1 }],
  },
  {
    featureType: 'road.highway',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#6b6b6b' }],
  },
  {
    featureType: 'road.arterial',
    elementType: 'geometry.fill',
    stylers: [{ color: '#ffffff' }],
  },
  {
    featureType: 'road.arterial',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#e8e5e0' }, { weight: 0.5 }],
  },
  {
    featureType: 'road.arterial',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#8a8a8a' }],
  },
  {
    featureType: 'road.local',
    elementType: 'geometry.fill',
    stylers: [{ color: '#fafafa' }],
  },
  {
    featureType: 'road.local',
    elementType: 'labels',
    stylers: [{ visibility: 'simplified' }],
  },
  {
    featureType: 'road.local',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#b0b0b0' }],
  },
  // Transit - hide
  {
    featureType: 'transit',
    stylers: [{ visibility: 'off' }],
  },
  // Administrative boundaries
  {
    featureType: 'administrative',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#c8c5c0' }, { weight: 0.8 }],
  },
  {
    featureType: 'administrative.locality',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#555555' }],
  },
  {
    featureType: 'administrative.neighborhood',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#999999' }],
  },
  // Buildings - subtle
  {
    featureType: 'landscape.man_made',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#e5e2dd' }, { weight: 0.5 }],
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

function CenterMapController({
  selectedDeal,
}: {
  selectedDeal: DealMapResponse | null
}) {
  const map = useMap()

  useEffect(() => {
    if (!map || !selectedDeal || !selectedDeal.latitude || !selectedDeal.longitude) return

    // Center the map on the selected parking lot with smooth pan
    const currentZoom = map.getZoom() || 13
    const targetZoom = currentZoom < 15 ? 15 : currentZoom // Zoom in if too far out
    
    map.panTo({
      lat: selectedDeal.latitude,
      lng: selectedDeal.longitude,
    })
    
    // Adjust zoom if needed (smooth zoom)
    if (currentZoom < 15) {
      map.setZoom(15)
    }
  }, [map, selectedDeal])

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
          minZoom={3}
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
          <CenterMapController selectedDeal={selectedDeal} />

          <MarkerClustererComponent
            deals={dealsWithLocation}
            selectedDeal={selectedDeal}
            onDealSelect={onDealSelect}
          />

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
                scaledSize: new google.maps.Size(48, 48),
                anchor: new google.maps.Point(24, 24),
              }}
            />
          )}


          {/* Parking lot info window */}
          {selectedDeal && selectedDeal.latitude && selectedDeal.longitude && (
            <InfoWindow
              position={{ lat: selectedDeal.latitude, lng: selectedDeal.longitude }}
              onCloseClick={() => onDealSelect(null)}
              pixelOffset={[0, -30]}
              headerDisabled
            >
              <div className="-m-3">
                <ParkingLotPopup 
                  deal={selectedDeal} 
                  onViewDetails={() => onViewDetails(selectedDeal.id)}
                  onClose={() => onDealSelect(null)}
                />
              </div>
            </InfoWindow>
          )}
        </Map>
      </APIProvider>
    </div>
  )
}

function MarkerClustererComponent({
  deals,
  selectedDeal,
  onDealSelect,
}: {
  deals: DealMapResponse[]
  selectedDeal: DealMapResponse | null
  onDealSelect: (deal: DealMapResponse | null) => void
}) {
  const map = useMap()
  const clustererRef = useRef<MarkerClusterer | null>(null)
  const markersRef = useRef<google.maps.Marker[]>([])

  useEffect(() => {
    if (!map || deals.length === 0) return

    // Clean up existing clusterer
    if (clustererRef.current) {
      clustererRef.current.clearMarkers()
      clustererRef.current = null
    }

    // Create markers for each deal
    const markers: google.maps.Marker[] = deals.map((deal) => {
      const marker = new google.maps.Marker({
        position: { lat: deal.latitude!, lng: deal.longitude! },
        icon: getMarkerIcon(deal, selectedDeal?.id === deal.id),
        map: null, // Don't add to map directly, clusterer will handle it
      })

      // Add click handler
      marker.addListener('click', () => {
        onDealSelect(deal)
      })

      return marker
    })

    markersRef.current = markers

    // Create custom cluster renderer - elegant, smooth, minimalist
    const customRenderer = {
      render: (cluster: any) => {
        const count = cluster.count
        const position = cluster.position

        // Subtle size scaling - more refined
        const size = count < 10 ? 36 : count < 50 ? 42 : count < 100 ? 48 : 54
        const fontSize = count < 10 ? 13 : count < 50 ? 14 : count < 100 ? 15 : 16
        const fontWeight = 500 // Lighter, more elegant weight
        
        // Soft, refined color palette - subtle orange with transparency
        const bgColor = count < 10 ? '#f97316' : count < 50 ? '#ea580c' : '#c2410c'
        const textColor = '#ffffff'
        const borderColor = '#ffffff'
        const borderWidth = 1.5 // Thinner, more refined border

        // Create cluster marker with elegant styling
        const clusterMarker = new google.maps.Marker({
          position,
          icon: {
            url: `data:image/svg+xml,${encodeURIComponent(`
              <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
                <defs>
                  <!-- Subtle, soft shadow -->
                  <filter id="soft-shadow-${count}" x="-50%" y="-50%" width="200%" height="200%">
                    <feGaussianBlur in="SourceAlpha" stdDeviation="1.5"/>
                    <feOffset dx="0" dy="1" result="offsetblur"/>
                    <feComponentTransfer>
                      <feFuncA type="linear" slope="0.2"/>
                    </feComponentTransfer>
                    <feMerge>
                      <feMergeNode/>
                      <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                  </filter>
                  <!-- Smooth gradient for depth -->
                  <linearGradient id="gradient-${count}" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:${bgColor};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:${bgColor};stop-opacity:0.9" />
                  </linearGradient>
                </defs>
                <!-- Main circle with gradient -->
                <circle 
                  cx="${size / 2}" 
                  cy="${size / 2}" 
                  r="${size / 2 - borderWidth}" 
                  fill="url(#gradient-${count})" 
                  stroke="${borderColor}" 
                  stroke-width="${borderWidth}"
                  stroke-opacity="0.95"
                  filter="url(#soft-shadow-${count})"
                />
                <!-- Elegant text -->
                <text 
                  x="${size / 2}" 
                  y="${size / 2}" 
                  font-family="-apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif" 
                  font-size="${fontSize}" 
                  font-weight="${fontWeight}" 
                  fill="${textColor}" 
                  text-anchor="middle" 
                  dominant-baseline="central"
                  font-variant-numeric="tabular-nums"
                  letter-spacing="-0.01em"
                  opacity="0.98"
                >${count}</text>
              </svg>
            `)}`,
            scaledSize: new google.maps.Size(size, size),
            anchor: new google.maps.Point(size / 2, size / 2),
          },
          zIndex: Number(google.maps.Marker.MAX_ZINDEX) + count,
        })

        // Smooth zoom on click
        clusterMarker.addListener('click', () => {
          const bounds = new google.maps.LatLngBounds()
          cluster.markers.forEach((m: any) => {
            const pos = m.getPosition?.() || m.position
            if (pos) {
              if (pos instanceof google.maps.LatLng) {
                bounds.extend(pos)
              } else if (pos.lat && pos.lng) {
                bounds.extend(new google.maps.LatLng(pos.lat, pos.lng))
              }
            }
          })
          map.fitBounds(bounds, { top: 60, right: 60, bottom: 60, left: 60 })
        })

        return clusterMarker
      },
    }

    // Create clusterer with custom renderer
    const clusterer = new MarkerClusterer({
      map,
      markers,
      algorithm: new GridAlgorithm({ gridSize: 60 }),
      renderer: customRenderer,
    })

    clustererRef.current = clusterer

    // Cleanup
    return () => {
      if (clustererRef.current) {
        try {
          // Check if map is still valid before clearing markers
          if (map && map.getDiv()) {
            clustererRef.current.clearMarkers()
          }
        } catch (error) {
          // Map might be destroyed, just clean up markers individually
          console.warn('Error clearing clusterer markers:', error)
        }
        clustererRef.current = null
      }
      markers.forEach((marker) => {
        try {
          google.maps.event.clearInstanceListeners(marker)
          marker.setMap(null)
        } catch (error) {
          // Marker might already be cleaned up
        }
      })
    }
  }, [map, deals, selectedDeal, onDealSelect])

  // Update marker icons when selection changes
  useEffect(() => {
    if (!map || markersRef.current.length === 0) return

    markersRef.current.forEach((marker, index) => {
      const deal = deals[index]
      if (deal) {
        marker.setIcon(getMarkerIcon(deal, selectedDeal?.id === deal.id))
      }
    })
  }, [map, deals, selectedDeal])

  return null
}

function getMarkerIcon(deal: DealMapResponse, isSelected: boolean) {
  let color = '#f97316'
  
  if (deal.status === 'evaluated') {
    // Inverted: low score (bad condition) = green (opportunity)
    if (deal.score !== null && deal.score !== undefined) {
      if (deal.score <= 30) color = '#10b981' // emerald
      else if (deal.score <= 50) color = '#84cc16' // lime
      else if (deal.score <= 70) color = '#f59e0b' // amber
      else color = '#ef4444' // red (good condition = not interesting)
    } else {
      color = '#22c55e'
    }
  } else if (deal.status === 'evaluating') {
    color = '#3b82f6'
  }

  const scale = isSelected ? 1.2 : 1
  const size = 28 * scale
  const borderWidth = 1.5

  return {
    url: `data:image/svg+xml,${encodeURIComponent(`
      <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
        <defs>
          <!-- Subtle, soft shadow -->
          <filter id="marker-shadow-${deal.id}" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceAlpha" stdDeviation="1"/>
            <feOffset dx="0" dy="0.5" result="offsetblur"/>
            <feComponentTransfer>
              <feFuncA type="linear" slope="0.25"/>
            </feComponentTransfer>
            <feMerge>
              <feMergeNode/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
          <!-- Smooth gradient -->
          <linearGradient id="marker-gradient-${deal.id}" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" style="stop-color:${color};stop-opacity:1" />
            <stop offset="100%" style="stop-color:${color};stop-opacity:0.92" />
          </linearGradient>
        </defs>
        <!-- Outer circle with gradient -->
        <circle 
          cx="${size / 2}" 
          cy="${size / 2}" 
          r="${size / 2 - borderWidth}" 
          fill="url(#marker-gradient-${deal.id})" 
          stroke="white" 
          stroke-width="${borderWidth}"
          stroke-opacity="0.95"
          filter="url(#marker-shadow-${deal.id})"
        />
        <!-- Inner dot - smaller and more refined -->
        <circle 
          cx="${size / 2}" 
          cy="${size / 2}" 
          r="${size / 6}" 
          fill="white" 
          opacity="0.98"
        />
      </svg>
    `)}`,
    scaledSize: new google.maps.Size(size, size),
    anchor: new google.maps.Point(size / 2, size / 2),
  }
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
  const [satelliteImage, setSatelliteImage] = useState<string | null>(null)
  const [imageLoading, setImageLoading] = useState(true)

  // Reset and lazy load the satellite image when deal changes
  useEffect(() => {
    // Reset state immediately when deal changes
    setSatelliteImage(null)
    setImageLoading(true)
    
    const fetchImage = async () => {
      try {
        const data = await parkingLotsApi.getParkingLot(deal.id)
        const wideSatellite = data.property_analysis?.images?.wide_satellite
        if (wideSatellite) {
          // Convert base64 to data URL if needed
          const imageUrl = wideSatellite.startsWith('data:') 
            ? wideSatellite 
            : `data:image/jpeg;base64,${wideSatellite}`
          setSatelliteImage(imageUrl)
        }
      } catch (error) {
        console.error('Failed to load satellite image:', error)
      } finally {
        setImageLoading(false)
      }
    }
    fetchImage()
  }, [deal.id])

  const getScoreColor = (score: number | null | undefined) => {
    if (score === null || score === undefined) {
      return { bg: 'bg-muted', text: 'text-muted-foreground' }
    }
    // Inverted logic: Low score (bad condition) = Green (opportunity!)
    if (score <= 30) return { bg: 'bg-emerald-100 dark:bg-emerald-950', text: 'text-emerald-700 dark:text-emerald-400' }
    if (score <= 50) return { bg: 'bg-lime-100 dark:bg-lime-950', text: 'text-lime-700 dark:text-lime-400' }
    if (score <= 70) return { bg: 'bg-amber-100 dark:bg-amber-950', text: 'text-amber-700 dark:text-amber-400' }
    // High score (good condition) = Red/Muted (not interesting)
    return { bg: 'bg-red-100 dark:bg-red-950', text: 'text-red-700 dark:text-red-400' }
  }

  const hasBusiness = deal.has_business || deal.business
  const isLead = deal.score !== null && deal.score !== undefined && deal.score < 50
  const scoreStyle = getScoreColor(deal.score)

  return (
    <div className="w-72 bg-card border border-border rounded-lg shadow-xl overflow-hidden">
      {/* Close Button - positioned over image */}
      <button
        onClick={onClose}
        className="absolute top-1.5 right-1.5 z-10 h-6 w-6 flex items-center justify-center rounded-md bg-black/40 backdrop-blur-sm hover:bg-black/60 transition-colors"
      >
        <X className="h-3.5 w-3.5 text-white" />
      </button>

      {/* Satellite Image */}
      <div className="relative h-36 bg-gradient-to-br from-slate-800 to-slate-900 overflow-hidden">
        {satelliteImage ? (
          <img 
            src={satelliteImage} 
            alt="Satellite view"
            className="w-full h-full object-cover"
          />
        ) : imageLoading ? (
          <div className="w-full h-full flex items-center justify-center">
            <div className="animate-pulse flex flex-col items-center">
              <Satellite className="h-8 w-8 text-white/40 mb-1" />
              <p className="text-[10px] text-white/50">Loading...</p>
            </div>
          </div>
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-center">
              <Satellite className="h-8 w-8 text-white/40 mx-auto mb-1" />
              <p className="text-[10px] text-white/50 uppercase tracking-wider">No image</p>
            </div>
          </div>
        )}
        {/* Score badge overlay */}
        {deal.score !== null && deal.score !== undefined && (
          <div className={cn(
            'absolute top-2 left-2 px-2 py-1 rounded text-xs font-bold shadow-lg',
            scoreStyle.bg, scoreStyle.text
          )}>
            {Math.round(deal.score)}/100
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-3 space-y-2">
        {/* Title & Address */}
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-foreground truncate mb-0.5">
            {deal.business?.name || deal.business_name || 'Unknown Location'}
          </h3>
          <div className="flex items-start gap-1 text-xs text-muted-foreground">
            <MapPin className="h-3 w-3 flex-shrink-0 mt-0.5" />
            <span className="line-clamp-2">{deal.address}</span>
          </div>
        </div>

        {/* Tags */}
        <div className="flex items-center gap-1 flex-wrap">
          {/* Status */}
          <StatusChip 
            status={deal.status === 'evaluated' ? 'success' : deal.status === 'evaluating' ? 'info' : 'warning'}
            icon={deal.status === 'evaluated' ? CheckCircle2 : Clock}
          >
            {deal.status === 'evaluated' ? 'Analyzed' : deal.status === 'evaluating' ? 'Evaluating' : 'Pending'}
          </StatusChip>

          {/* Lead indicator */}
          {isLead && (
            <StatusChip status="success" icon={Target}>Lead</StatusChip>
          )}

          {/* Business info */}
          {hasBusiness ? (
            <>
              <StatusChip status="neutral" icon={Building2}>
                {deal.business?.category || 'Business'}
              </StatusChip>
              {deal.business?.phone && <IconChip icon={Phone} tooltip="Has phone" />}
              {deal.business?.website && <IconChip icon={Globe} tooltip="Has website" />}
            </>
          ) : (
            <StatusChip status="warning" icon={AlertTriangle}>No business</StatusChip>
          )}
        </div>

        {/* Action Button */}
        <button
          onClick={onViewDetails}
          className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-foreground bg-muted hover:bg-muted/80 border border-border rounded-md transition-colors"
        >
          View Details
          <ExternalLink className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
