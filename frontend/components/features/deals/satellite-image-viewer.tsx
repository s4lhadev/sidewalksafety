'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ZoomIn, ZoomOut, RotateCw, Download } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SatelliteImageViewerProps {
  imageUrl?: string
  parkingLotMask?: Record<string, any>
  crackDetections?: Array<Record<string, any>>
  className?: string
}

export function SatelliteImageViewer({
  imageUrl,
  parkingLotMask,
  crackDetections,
  className,
}: SatelliteImageViewerProps) {
  const [zoom, setZoom] = useState(1)
  const [rotation, setRotation] = useState(0)
  const [isLoading, setIsLoading] = useState(true)

  if (!imageUrl) {
    return (
      <div className={className}>
        <div className="flex items-center justify-center h-64 bg-slate-50 rounded-lg border border-slate-200">
          <p className="text-xs text-slate-500">No satellite image available</p>
        </div>
      </div>
    )
  }

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 0.25, 3))
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 0.25, 0.5))
  const handleRotate = () => setRotation((prev) => (prev + 90) % 360)
  const handleDownload = () => {
    const link = document.createElement('a')
    link.href = imageUrl
    link.download = 'satellite-image.jpg'
    link.click()
  }

  return (
    <div className={className}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleZoomOut}
            disabled={zoom <= 0.5}
            className="h-7 w-7 p-0"
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </Button>
          <span className="text-xs text-slate-500 min-w-[2.5rem] text-center">
            {Math.round(zoom * 100)}%
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleZoomIn}
            disabled={zoom >= 3}
            className="h-7 w-7 p-0"
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRotate}
            className="h-7 w-7 p-0"
          >
            <RotateCw className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDownload}
            className="h-7 w-7 p-0"
          >
            <Download className="h-3.5 w-3.5" />
          </Button>
        </div>
        {crackDetections && crackDetections.length > 0 && (
          <span className="text-xs text-slate-500">
            {crackDetections.length} detection{crackDetections.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>
      <div className="relative w-full h-[500px] bg-slate-50 rounded border border-slate-200 overflow-hidden">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Skeleton className="w-full h-full" />
          </div>
        )}
        <div
          className={cn(
            'relative w-full h-full transition-transform duration-200',
            isLoading && 'opacity-0'
          )}
          style={{
            transform: `scale(${zoom}) rotate(${rotation}deg)`,
            transformOrigin: 'center center',
          }}
        >
          <img
            src={imageUrl}
            alt="Satellite image of parking lot"
            className="w-full h-full object-contain"
            onLoad={() => setIsLoading(false)}
          />
          {/* Overlay for parking lot mask if available */}
          {parkingLotMask && (
            <div className="absolute inset-0 pointer-events-none">
              {/* Render mask overlay if needed */}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

