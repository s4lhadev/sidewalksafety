'use client'

import { useEffect, useRef } from 'react'
import { useMap } from '@vis.gl/react-google-maps'
import { DealMapResponse } from '@/types'
import { cn } from '@/lib/utils'
import { createRoot, Root } from 'react-dom/client'
import { getStatusColor, getDamageSeverityColor } from '@/lib/utils'

interface DealMarkerProps {
  deal: DealMapResponse
  position: { lat: number; lng: number }
  isSelected: boolean
  onClick: () => void
}

function getMarkerColor(deal: DealMapResponse): string {
  if (deal.deal_score !== null && deal.deal_score !== undefined) {
    if (deal.deal_score >= 7) return '#10B981' // green
    if (deal.deal_score >= 4) return '#F59E0B' // yellow
    return '#EF4444' // red
  }
  
  if (deal.damage_severity) {
    switch (deal.damage_severity) {
      case 'critical':
        return '#EF4444'
      case 'high':
        return '#F97316'
      case 'medium':
        return '#F59E0B'
      case 'low':
        return '#10B981'
    }
  }

  switch (deal.status) {
    case 'evaluated':
      return '#10B981'
    case 'evaluating':
      return '#F59E0B'
    case 'pending':
      return '#6B7280'
    default:
      return '#6B7280'
  }
}

export function DealMarker({ deal, position, isSelected, onClick }: DealMarkerProps) {
  const map = useMap()
  const overlayRef = useRef<google.maps.OverlayView | null>(null)
  const rootRef = useRef<Root | null>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!map || typeof window === 'undefined' || !window.google?.maps) return

    const markerColor = getMarkerColor(deal)

    class CustomOverlay extends window.google.maps.OverlayView {
      position: google.maps.LatLng
      containerDiv: HTMLDivElement | null = null

      constructor(position: google.maps.LatLng) {
        super()
        this.position = position
      }

      onAdd() {
        this.containerDiv = document.createElement('div')
        this.containerDiv.style.position = 'absolute'
        this.containerDiv.style.cursor = 'pointer'
        this.containerDiv.style.zIndex = isSelected ? '1000' : '100'

        containerRef.current = this.containerDiv
        rootRef.current = createRoot(this.containerDiv)
        this.updateContent()

        const panes = this.getPanes()
        panes?.overlayMouseTarget.appendChild(this.containerDiv)
      }

      draw() {
        if (!this.containerDiv) return

        const overlayProjection = this.getProjection()
        const point = overlayProjection.fromLatLngToDivPixel(this.position)

        if (point) {
          this.containerDiv.style.left = point.x + 'px'
          this.containerDiv.style.top = point.y + 'px'
          this.containerDiv.style.transform = 'translate(-50%, -100%)'
        }
      }

      updateContent() {
        if (!rootRef.current) return

        rootRef.current.render(
          <div
            className={cn(
              'flex flex-col items-center gap-1.5 transition-all duration-200 cursor-pointer group',
              isSelected && 'scale-110'
            )}
            onClick={onClick}
          >
            {/* Marker Dot */}
            <div
              className={cn(
                'relative rounded-full shadow-lg transition-all duration-200',
                'group-hover:scale-110 group-hover:shadow-xl',
                isSelected && 'ring-2 ring-primary ring-offset-2 ring-offset-background'
              )}
              style={{
                width: isSelected ? '20px' : '16px',
                height: isSelected ? '20px' : '16px',
                backgroundColor: markerColor,
              }}
            >
              {isSelected && (
                <div
                  className="absolute inset-0 rounded-full animate-ping opacity-75"
                  style={{ backgroundColor: markerColor }}
                />
              )}
            </div>

            {/* Deal Name Badge */}
            <div
              className={cn(
                'bg-card/95 backdrop-blur-sm border border-border/40 rounded-md px-2 py-1',
                'shadow-lg max-w-[140px] transition-all duration-200',
                isSelected && 'bg-primary/10 border-primary/40'
              )}
            >
              <p className="text-[11px] font-medium text-foreground truncate text-center">
                {deal.business_name}
              </p>
              {deal.deal_score !== null && deal.deal_score !== undefined && (
                <p className="text-[10px] text-muted-foreground text-center mt-0.5">
                  Score: {deal.deal_score.toFixed(1)}
                </p>
              )}
            </div>
          </div>
        )
      }

      onRemove() {
        if (this.containerDiv && this.containerDiv.parentElement) {
          const rootToUnmount = rootRef.current
          if (rootToUnmount) {
            setTimeout(() => {
              try {
                rootToUnmount.unmount()
              } catch (error) {
                // Ignore errors
              }
            }, 0)
            rootRef.current = null
          }
          this.containerDiv.parentElement.removeChild(this.containerDiv)
          this.containerDiv = null
        }
      }
    }

    const overlay = new CustomOverlay(
      new window.google.maps.LatLng(position.lat, position.lng)
    )
    overlay.setMap(map)
    overlayRef.current = overlay

    return () => {
      if (overlayRef.current) {
        overlayRef.current.setMap(null)
        overlayRef.current = null
      }
      const rootToUnmount = rootRef.current
      if (rootToUnmount) {
        setTimeout(() => {
          try {
            rootToUnmount.unmount()
          } catch (error) {
            // Ignore errors
          }
        }, 0)
        rootRef.current = null
      }
    }
  }, [map, position.lat, position.lng, deal, isSelected, onClick])

  useEffect(() => {
    if (overlayRef.current && 'updateContent' in overlayRef.current) {
      ;(overlayRef.current as any).updateContent()
    }
  }, [isSelected, deal, onClick])

  return null
}

