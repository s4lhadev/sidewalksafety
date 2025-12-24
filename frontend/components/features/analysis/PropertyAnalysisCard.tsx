'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Loader2, AlertTriangle, CheckCircle2, Clock, Maximize2, Eye, Layers } from 'lucide-react'
import type { PropertyAnalysis } from '@/types'
import { cn } from '@/lib/utils'

interface PropertyAnalysisCardProps {
  analysis: PropertyAnalysis
  onViewFullScreen?: () => void
  className?: string
}

type ImageType = 'segmentation' | 'property_boundary' | 'condition_analysis'

export function PropertyAnalysisCard({ 
  analysis, 
  onViewFullScreen,
  className 
}: PropertyAnalysisCardProps) {
  const [activeImage, setActiveImage] = useState<ImageType>('condition_analysis')
  const [showOriginal, setShowOriginal] = useState(false)

  const getStatusBadge = () => {
    switch (analysis.status) {
      case 'pending':
        return (
          <Badge variant="secondary" className="gap-1">
            <Clock className="h-3 w-3" />
            Pending
          </Badge>
        )
      case 'processing':
        return (
          <Badge variant="secondary" className="gap-1 bg-blue-100 text-blue-700">
            <Loader2 className="h-3 w-3 animate-spin" />
            Processing
          </Badge>
        )
      case 'completed':
        return (
          <Badge variant="secondary" className="gap-1 bg-green-100 text-green-700">
            <CheckCircle2 className="h-3 w-3" />
            Completed
          </Badge>
        )
      case 'failed':
        return (
          <Badge variant="destructive" className="gap-1">
            <AlertTriangle className="h-3 w-3" />
            Failed
          </Badge>
        )
      default:
        return null
    }
  }

  const getConditionColor = (score?: number) => {
    if (!score) return 'text-gray-500'
    if (score < 40) return 'text-red-500'
    if (score < 70) return 'text-yellow-500'
    return 'text-green-500'
  }

  const getConditionLabel = (score?: number) => {
    if (!score) return 'N/A'
    if (score < 40) return 'Poor'
    if (score < 70) return 'Fair'
    return 'Good'
  }

  // Convert base64 to data URL
  const toDataUrl = (base64: string | undefined): string | undefined => {
    if (!base64) return undefined
    if (base64.startsWith('http') || base64.startsWith('data:')) return base64
    return `data:image/jpeg;base64,${base64}`
  }

  const getCurrentImageSrc = () => {
    // If showing original, return wide satellite
    if (showOriginal) {
      return toDataUrl(analysis.images.wide_satellite)
    }
    
    // Otherwise show the selected analysis image
    const imageMap: Record<ImageType, string | undefined> = {
      segmentation: analysis.images.segmentation,
      property_boundary: analysis.images.property_boundary,
      condition_analysis: analysis.images.condition_analysis,
    }
    return toDataUrl(imageMap[activeImage])
  }

  const imageSrc = getCurrentImageSrc()
  const hasOriginal = !!analysis.images.wide_satellite

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">CV Analysis</CardTitle>
          {getStatusBadge()}
        </div>
      </CardHeader>
      
      <CardContent className="p-0">
        {/* Image Viewer */}
        {analysis.status === 'completed' && imageSrc ? (
          <div className="relative">
            {/* Main Image */}
            <div className="relative aspect-video bg-gray-900">
              {/* Using img tag for base64 data URLs */}
              <img
                src={imageSrc}
                alt={showOriginal ? 'Original satellite' : `Property ${activeImage} analysis`}
                className="absolute inset-0 w-full h-full object-contain"
              />
              
              {/* Top Controls */}
              <div className="absolute top-2 left-2 right-2 flex items-center justify-between">
                {/* Original/Analysis Toggle */}
                {hasOriginal && (
                  <div className="flex items-center gap-2 bg-black/60 backdrop-blur-sm rounded-lg px-3 py-1.5">
                    <Layers className="h-4 w-4 text-white" />
                    <Label htmlFor="show-original" className="text-xs text-white cursor-pointer">
                      {showOriginal ? 'Original' : 'Analysis'}
                    </Label>
                    <Switch
                      id="show-original"
                      checked={!showOriginal}
                      onCheckedChange={(checked) => setShowOriginal(!checked)}
                      className="data-[state=checked]:bg-blue-500"
                    />
                  </div>
                )}
                
                {/* Fullscreen Button */}
                {onViewFullScreen && (
                  <Button
                    size="icon"
                    variant="secondary"
                    className="h-8 w-8 ml-auto"
                    onClick={onViewFullScreen}
                  >
                    <Maximize2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
            
            {/* Image Type Tabs - only show when not viewing original */}
            {!showOriginal && (
              <div className="p-2 bg-gray-50 border-t">
                <Tabs value={activeImage} onValueChange={(v) => setActiveImage(v as ImageType)}>
                  <TabsList className="w-full grid grid-cols-3">
                    <TabsTrigger value="segmentation" className="text-xs">
                      Segmentation
                    </TabsTrigger>
                    <TabsTrigger value="property_boundary" className="text-xs">
                      Property
                    </TabsTrigger>
                    <TabsTrigger value="condition_analysis" className="text-xs">
                      Condition
                    </TabsTrigger>
                  </TabsList>
                </Tabs>
              </div>
            )}
          </div>
        ) : analysis.status === 'processing' || analysis.status === 'pending' ? (
          <div className="aspect-video bg-gray-100 flex items-center justify-center">
            <div className="text-center">
              <Loader2 className="h-8 w-8 animate-spin text-blue-500 mx-auto mb-2" />
              <p className="text-sm text-gray-500">Analyzing property...</p>
            </div>
          </div>
        ) : analysis.status === 'failed' ? (
          <div className="aspect-video bg-red-50 flex items-center justify-center">
            <div className="text-center">
              <AlertTriangle className="h-8 w-8 text-red-500 mx-auto mb-2" />
              <p className="text-sm text-red-600">Analysis failed</p>
              {analysis.error_message && (
                <p className="text-xs text-red-500 mt-1">{analysis.error_message}</p>
              )}
            </div>
          </div>
        ) : null}

        {/* Metrics */}
        {analysis.status === 'completed' && (
          <div className="p-4 grid grid-cols-3 gap-4 text-center border-t">
            <div>
              <div className="text-xl font-bold text-blue-600">
                {analysis.total_asphalt_area_m2 
                  ? `${analysis.total_asphalt_area_m2.toLocaleString(undefined, { maximumFractionDigits: 0 })} m²`
                  : 'N/A'}
              </div>
              <div className="text-xs text-gray-500">Total Asphalt</div>
            </div>
            <div>
              <div className={cn(
                "text-xl font-bold",
                getConditionColor(analysis.weighted_condition_score)
              )}>
                {analysis.weighted_condition_score 
                  ? `${analysis.weighted_condition_score.toFixed(0)}/100`
                  : 'N/A'}
              </div>
              <div className="text-xs text-gray-500">
                Condition ({getConditionLabel(analysis.weighted_condition_score)})
              </div>
            </div>
            <div>
              <div className="text-xl font-bold text-purple-600">
                {analysis.asphalt_areas?.filter(a => a.is_associated).length || '-'}
              </div>
              <div className="text-xs text-gray-500">Areas</div>
            </div>
          </div>
        )}

        {/* Damage Summary */}
        {analysis.status === 'completed' && (analysis.total_crack_count || analysis.total_pothole_count) && (
          <div className="px-4 pb-4 flex gap-4 text-sm">
            {analysis.total_crack_count !== undefined && analysis.total_crack_count > 0 && (
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded-full bg-yellow-500" />
                <span>{analysis.total_crack_count} cracks</span>
              </div>
            )}
            {analysis.total_pothole_count !== undefined && analysis.total_pothole_count > 0 && (
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded-full bg-red-500" />
                <span>{analysis.total_pothole_count} potholes</span>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

