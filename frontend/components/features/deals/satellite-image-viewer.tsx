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
      <Card className={className}>
        <CardHeader>
          <CardTitle>Satellite Image</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-64 bg-muted/20 rounded-lg">
            <p className="text-sm text-muted-foreground">No satellite image available</p>
          </div>
        </CardContent>
      </Card>
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
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Satellite Image</CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              onClick={handleZoomOut}
              disabled={zoom <= 0.5}
              className="h-7 w-7"
            >
              <ZoomOut className="h-3.5 w-3.5" />
            </Button>
            <span className="text-xs text-muted-foreground min-w-[3rem] text-center">
              {Math.round(zoom * 100)}%
            </span>
            <Button
              variant="outline"
              size="icon"
              onClick={handleZoomIn}
              disabled={zoom >= 3}
              className="h-7 w-7"
            >
              <ZoomIn className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={handleRotate}
              className="h-7 w-7"
            >
              <RotateCw className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={handleDownload}
              className="h-7 w-7"
            >
              <Download className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="relative w-full h-96 bg-muted/20 rounded-lg overflow-hidden border border-border/40">
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
        {crackDetections && crackDetections.length > 0 && (
          <p className="text-xs text-muted-foreground mt-2">
            {crackDetections.length} crack detection{crackDetections.length !== 1 ? 's' : ''} identified
          </p>
        )}
      </CardContent>
    </Card>
  )
}

