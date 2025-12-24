'use client'

import { useParkingLot, useParkingLotBusinesses } from '@/lib/queries/use-parking-lots'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusChip, IconChip, Switch, Label } from '@/components/ui'
import { formatNumber, cn } from '@/lib/utils'
import { 
  MapPin, 
  Building2, 
  ArrowLeft,
  Phone,
  Globe,
  ExternalLink,
  CheckCircle2,
  Clock,
  Calendar,
  Copy,
  Share2,
  Download,
  AlertCircle,
  Target,
  AlertTriangle,
  Ruler,
  MapPinned,
  Layers,
  ZoomIn,
  ZoomOut,
  RotateCcw
} from 'lucide-react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { useState, useRef, useCallback } from 'react'

export default function ParkingLotDetailPage() {
  const params = useParams()
  const router = useRouter()
  const parkingLotId = params.id as string
  const { data: parkingLot, isLoading, error } = useParkingLot(parkingLotId)
  const { data: businesses } = useParkingLotBusinesses(parkingLotId)
  const [copied, setCopied] = useState(false)
  const [showOriginal, setShowOriginal] = useState(false)
  const [activeImageType, setActiveImageType] = useState<'segmentation' | 'property_boundary' | 'condition_analysis'>('condition_analysis')
  const [zoom, setZoom] = useState(100)
  
  // Image pan/drag state
  const [isDragging, setIsDragging] = useState(false)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const imageContainerRef = useRef<HTMLDivElement>(null)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (zoom <= 100) return // Only allow dragging when zoomed in
    setIsDragging(true)
    setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y })
  }, [zoom, position])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging) return
    const newX = e.clientX - dragStart.x
    const newY = e.clientY - dragStart.y
    setPosition({ x: newX, y: newY })
  }, [isDragging, dragStart])

  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
  }, [])

  const resetView = useCallback(() => {
    setZoom(100)
    setPosition({ x: 0, y: 0 })
  }, [])

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Inverted score colors: bad condition = green (opportunity)
  const getScoreStyle = (score: number | null | undefined) => {
    if (score === null || score === undefined) {
      return { bg: 'bg-muted', text: 'text-muted-foreground', label: 'Not evaluated' }
    }
    if (score <= 30) return { bg: 'bg-emerald-100 dark:bg-emerald-950', text: 'text-emerald-700 dark:text-emerald-400', label: 'Critical - High Priority' }
    if (score <= 50) return { bg: 'bg-lime-100 dark:bg-lime-950', text: 'text-lime-700 dark:text-lime-400', label: 'Poor - Good Opportunity' }
    if (score <= 70) return { bg: 'bg-amber-100 dark:bg-amber-950', text: 'text-amber-700 dark:text-amber-400', label: 'Fair - Moderate' }
    return { bg: 'bg-red-100 dark:bg-red-950', text: 'text-red-700 dark:text-red-400', label: 'Good Condition' }
  }

  if (isLoading) {
    return (
      <div className="h-full bg-background">
        <div className="max-w-5xl mx-auto px-6 py-6 space-y-4">
          <Skeleton className="h-6 w-48" />
          <div className="grid gap-6 lg:grid-cols-2">
            <Skeleton className="h-80" />
            <div className="space-y-3">
              <Skeleton className="h-20" />
              <Skeleton className="h-32" />
              <Skeleton className="h-24" />
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (error || !parkingLot) {
    return (
      <div className="h-full bg-background flex items-center justify-center p-4">
        <div className="text-center space-y-3">
          <div className="w-14 h-14 rounded-xl border-2 border-dashed border-border flex items-center justify-center mx-auto">
            <AlertCircle className="h-6 w-6 text-muted-foreground/30" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground">Parking Lot Not Found</h2>
            <p className="text-sm text-muted-foreground mt-1">
              The parking lot doesn't exist or you don't have access.
            </p>
          </div>
          <Link href="/dashboard">
            <Button variant="outline" size="sm" className="mt-2">
              <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
              Back to Dashboard
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  const primaryBusiness = parkingLot.business || businesses?.find(b => b.is_primary) || businesses?.[0]
  const hasBusinessData = !!primaryBusiness || (businesses && businesses.length > 0)
  const displayName = primaryBusiness?.name || parkingLot.operator_name || 'Parking Lot'
  const displayAddress = parkingLot.address || 'Address not available'
  const conditionScore = parkingLot.condition_score ?? null
  const isLead = conditionScore !== null && conditionScore < 50
  const scoreStyle = getScoreStyle(conditionScore)

  return (
    <div className="h-full bg-background overflow-auto">
      <div className="max-w-5xl mx-auto px-6 py-4">
        {/* Header */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <Link href="/dashboard">
              <Button variant="ghost" size="sm" className="h-7 px-2 -ml-2 text-xs text-muted-foreground hover:text-foreground">
                <ArrowLeft className="h-3 w-3 mr-1" />
                Back
              </Button>
            </Link>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                onClick={handleCopyLink}
              >
                {copied ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
              </Button>
              <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                <Share2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>

          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <h1 className="text-lg font-semibold text-foreground mb-1 truncate">{displayName}</h1>
              <div className="text-xs text-muted-foreground flex items-center gap-1.5">
                <MapPin className="h-3 w-3 flex-shrink-0" />
                <span className="truncate">{displayAddress}</span>
              </div>
            </div>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              {isLead && (
                <StatusChip status="success" icon={Target}>Lead</StatusChip>
              )}
              {hasBusinessData ? (
                <StatusChip status="info" icon={Building2}>Business</StatusChip>
              ) : (
                <StatusChip status="warning" icon={AlertTriangle}>No business</StatusChip>
              )}
              {parkingLot.is_evaluated ? (
                <StatusChip status="success" icon={CheckCircle2}>Analyzed</StatusChip>
              ) : (
                <StatusChip status="warning" icon={Clock}>Pending</StatusChip>
              )}
            </div>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
          {/* Left Column - CV Analysis Images */}
          <div className="space-y-4">
            <div className="border border-border rounded-lg overflow-hidden bg-card">
              <div className="px-3 py-2 border-b border-border flex items-center justify-between">
                <span className="text-xs font-medium text-foreground">CV Analysis</span>
                {parkingLot.property_analysis?.images?.wide_satellite && (
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-muted-foreground">
                      {showOriginal ? 'Original' : 'Analysis'}
                    </span>
                    <Switch
                      checked={!showOriginal}
                      onCheckedChange={(checked) => setShowOriginal(!checked)}
                    />
                  </div>
                )}
              </div>
              <div className="relative">
                {(() => {
                  const images = parkingLot.property_analysis?.images
                  const toDataUrl = (b64: string | undefined) => 
                    b64 ? (b64.startsWith('data:') ? b64 : `data:image/jpeg;base64,${b64}`) : null
                  
                  const currentImage = showOriginal 
                    ? toDataUrl(images?.wide_satellite)
                    : toDataUrl(images?.[activeImageType])
                  
                  if (currentImage) {
                    return (
                      <>
                        {/* Large Image Container with Pan/Drag */}
                        <div 
                          ref={imageContainerRef}
                          className={cn(
                            "relative h-[500px] bg-gray-900 overflow-hidden select-none",
                            zoom > 100 ? "cursor-grab" : "cursor-default",
                            isDragging && "cursor-grabbing"
                          )}
                          onMouseDown={handleMouseDown}
                          onMouseMove={handleMouseMove}
                          onMouseUp={handleMouseUp}
                          onMouseLeave={handleMouseUp}
                        >
                          <img
                            src={currentImage}
                            alt={showOriginal ? 'Original satellite' : `CV ${activeImageType}`}
                            className="w-full h-full object-contain transition-transform pointer-events-none"
                            style={{ 
                              transform: `scale(${zoom / 100}) translate(${position.x / (zoom / 100)}px, ${position.y / (zoom / 100)}px)`,
                            }}
                            draggable={false}
                          />
                          
                          {/* Drag hint when zoomed */}
                          {zoom > 100 && !isDragging && (
                            <div className="absolute bottom-3 left-1/2 -translate-x-1/2 bg-black/60 text-white text-[10px] px-2 py-1 rounded">
                              Drag to pan
                            </div>
                          )}
                        </div>
                        
                        {/* Image Controls */}
                        <div className="absolute top-3 right-3 flex items-center gap-1 bg-black/50 backdrop-blur-sm rounded-lg p-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-8 w-8 p-0 text-white hover:bg-white/20"
                            onClick={() => {
                              setZoom(z => Math.max(50, z - 25))
                              if (zoom <= 100) setPosition({ x: 0, y: 0 })
                            }}
                          >
                            <ZoomOut className="h-4 w-4" />
                          </Button>
                          <span className="text-xs text-white px-2 min-w-[50px] text-center font-medium">
                            {zoom}%
                          </span>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-8 w-8 p-0 text-white hover:bg-white/20"
                            onClick={() => setZoom(z => Math.min(300, z + 25))}
                          >
                            <ZoomIn className="h-4 w-4" />
                          </Button>
                          <div className="w-px h-5 bg-white/30 mx-1" />
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-8 w-8 p-0 text-white hover:bg-white/20"
                            onClick={resetView}
                          >
                            <RotateCcw className="h-4 w-4" />
                          </Button>
                        </div>
                        
                        {/* Image Type Tabs - only show when not viewing original */}
                        {!showOriginal && (
                          <div className="p-2 bg-muted/50 border-t border-border">
                            <div className="flex gap-1">
                              {(['segmentation', 'property_boundary', 'condition_analysis'] as const).map((type) => (
                                <button
                                  key={type}
                                  onClick={() => {
                                    setActiveImageType(type)
                                    resetView()
                                  }}
                                  className={cn(
                                    'flex-1 px-3 py-2 text-xs font-medium rounded transition-colors',
                                    activeImageType === type
                                      ? 'bg-primary text-primary-foreground'
                                      : 'bg-background hover:bg-muted text-muted-foreground'
                                  )}
                                >
                                  {type === 'segmentation' && 'Segmentation'}
                                  {type === 'property_boundary' && 'Property'}
                                  {type === 'condition_analysis' && 'Condition'}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )
                  }
                  
                  return (
                    <div className="flex items-center justify-center h-[500px] bg-muted/50 rounded">
                      <div className="text-center">
                        <MapPinned className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
                        <p className="text-sm text-muted-foreground">No CV analysis available</p>
                        <p className="text-xs text-muted-foreground mt-1">Run discovery to generate images</p>
                      </div>
                    </div>
                  )
                })()}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" className="h-8 text-xs">
                <Download className="h-3.5 w-3.5 mr-1.5" />
                Export Report
              </Button>
            </div>
          </div>

          {/* Right Column - Details */}
          <div className="space-y-4">
            {/* Score Card */}
            <div className="border border-border rounded-lg p-3 bg-card">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className={cn(
                    'text-lg font-semibold tabular-nums',
                    conditionScore !== null ? scoreStyle.text : 'text-muted-foreground'
                  )}>
                    {conditionScore !== null ? Math.round(conditionScore) : '—'}
                  </span>
                  <div>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Condition</p>
                    <p className="text-xs text-foreground">{scoreStyle.label}</p>
                  </div>
                </div>
                {isLead && (
                  <StatusChip status="success" icon={Target}>Lead</StatusChip>
                )}
              </div>
              {conditionScore !== null && (
                <div className="mt-2 h-1 bg-muted rounded-full overflow-hidden">
                  <div 
                    className={cn('h-full rounded-full transition-all', scoreStyle.text.replace('text-', 'bg-').replace('-700', '-500').replace('-400', '-500'))}
                    style={{ width: `${conditionScore}%` }}
                  />
                </div>
              )}
            </div>

            {/* Details Grid */}
            <div className="grid grid-cols-2 gap-3">
              {parkingLot.area_sqft && (
                <div className="border border-border rounded-lg p-3 bg-card">
                  <div className="flex items-center gap-1.5 text-muted-foreground mb-1">
                    <Ruler className="h-3 w-3" />
                    <span className="text-[10px] uppercase tracking-wider">Area</span>
                  </div>
                  <p className="text-sm font-semibold tabular-nums">{formatNumber(parkingLot.area_sqft, 0)} <span className="text-xs font-normal text-muted-foreground">sq ft</span></p>
                </div>
              )}
              {parkingLot.evaluated_at && (
                <div className="border border-border rounded-lg p-3 bg-card">
                  <div className="flex items-center gap-1.5 text-muted-foreground mb-1">
                    <Calendar className="h-3 w-3" />
                    <span className="text-[10px] uppercase tracking-wider">Evaluated</span>
                  </div>
                  <p className="text-sm font-semibold">{new Date(parkingLot.evaluated_at).toLocaleDateString()}</p>
                </div>
              )}
            </div>

            {/* Location */}
            <div className="border border-border rounded-lg bg-card">
              <div className="px-3 py-2 border-b border-border">
                <span className="text-xs font-medium text-foreground">Location</span>
              </div>
              <div className="p-3 space-y-2.5 text-xs">
                <div>
                  <span className="text-muted-foreground">Address</span>
                  <p className="text-foreground mt-0.5">{displayAddress}</p>
                </div>
                {parkingLot.centroid && (
                  <div>
                    <span className="text-muted-foreground">Coordinates</span>
                    <p className="text-foreground font-mono text-[11px] mt-0.5">
                      {parkingLot.centroid.lat.toFixed(6)}, {parkingLot.centroid.lng.toFixed(6)}
                    </p>
                  </div>
                )}
                {parkingLot.surface_type && (
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Surface</span>
                    <Badge variant="outline" className="text-[10px] capitalize h-5">{parkingLot.surface_type}</Badge>
                  </div>
                )}
              </div>
            </div>

            {/* Business Card - Complete */}
            <div className={cn(
              'border rounded-lg bg-card',
              hasBusinessData ? 'border-blue-500/30' : 'border-border'
            )}>
              <div className="px-3 py-2 border-b border-border flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Building2 className={cn('h-4 w-4', hasBusinessData ? 'text-blue-500' : 'text-muted-foreground')} />
                  <span className="text-xs font-medium text-foreground">Business</span>
                </div>
                {hasBusinessData && <CheckCircle2 className="h-3.5 w-3.5 text-blue-500" />}
              </div>
              <div className="p-4">
                {hasBusinessData && primaryBusiness ? (
                  <div className="space-y-4">
                    {/* Business Name & Category */}
                    <div>
                      <h3 className="text-base font-semibold text-foreground">{primaryBusiness.name}</h3>
                      {primaryBusiness.category && (
                        <Badge variant="outline" className="text-[10px] h-5 mt-1.5">{primaryBusiness.category}</Badge>
                      )}
                    </div>
                    
                    {/* Address */}
                    {primaryBusiness.address && (
                      <div className="flex items-start gap-2 text-sm">
                        <MapPin className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5" />
                        <span className="text-muted-foreground">{primaryBusiness.address}</span>
                      </div>
                    )}
                    
                    {/* Contact Info */}
                    <div className="space-y-2">
                      {primaryBusiness.phone && (
                        <a
                          href={`tel:${primaryBusiness.phone}`}
                          className="flex items-center gap-2 text-sm text-foreground hover:text-blue-600 transition-colors"
                        >
                          <Phone className="h-4 w-4 text-muted-foreground" />
                          <span>{primaryBusiness.phone}</span>
                        </a>
                      )}
                      {primaryBusiness.email && (
                        <a
                          href={`mailto:${primaryBusiness.email}`}
                          className="flex items-center gap-2 text-sm text-foreground hover:text-blue-600 transition-colors"
                        >
                          <svg className="h-4 w-4 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                          </svg>
                          <span>{primaryBusiness.email}</span>
                        </a>
                      )}
                      {primaryBusiness.website && (
                        <a
                          href={primaryBusiness.website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 text-sm text-foreground hover:text-blue-600 transition-colors"
                        >
                          <Globe className="h-4 w-4 text-muted-foreground" />
                          <span className="truncate">{primaryBusiness.website.replace(/^https?:\/\//, '')}</span>
                          <ExternalLink className="h-3 w-3 text-muted-foreground" />
                        </a>
                      )}
                    </div>
                    
                    {/* Match Score - if from associated businesses */}
                    {businesses?.[0]?.match_score && (
                      <div className="pt-3 border-t border-border flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">Match Confidence</span>
                        <div className="flex items-center gap-2">
                          <div className="w-24 h-1.5 bg-muted rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-blue-500 rounded-full"
                              style={{ width: `${businesses[0].match_score}%` }}
                            />
                          </div>
                          <span className="text-xs font-medium text-foreground">
                            {Math.round(businesses[0].match_score)}%
                          </span>
                        </div>
                      </div>
                    )}
                    
                    {/* Quick Actions */}
                    <div className="pt-3 border-t border-border flex gap-2">
                      {primaryBusiness.phone && (
                        <Button 
                          variant="outline" 
                          size="sm" 
                          className="flex-1 h-9 text-xs"
                          onClick={() => window.open(`tel:${primaryBusiness.phone}`)}
                        >
                          <Phone className="h-3.5 w-3.5 mr-1.5" />
                          Call
                        </Button>
                      )}
                      {primaryBusiness.website && (
                        <Button 
                          variant="outline" 
                          size="sm" 
                          className="flex-1 h-9 text-xs"
                          onClick={() => window.open(primaryBusiness.website, '_blank')}
                        >
                          <Globe className="h-3.5 w-3.5 mr-1.5" />
                          Website
                        </Button>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-6">
                    <AlertTriangle className="h-8 w-8 text-muted-foreground/30 mx-auto mb-2" />
                    <p className="text-sm text-muted-foreground">No business data</p>
                    <p className="text-xs text-muted-foreground mt-1">Business information not available</p>
                  </div>
                )}
              </div>
            </div>

            {/* Property Boundary Info (from Regrid) */}
            {parkingLot.property_analysis?.property_boundary && (
              <div className={cn(
                'border rounded-lg bg-card',
                parkingLot.property_analysis.property_boundary.source === 'regrid' 
                  ? 'border-purple-500/30' 
                  : 'border-border'
              )}>
                <div className="px-3 py-2 border-b border-border flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Layers className={cn(
                      'h-4 w-4', 
                      parkingLot.property_analysis.property_boundary.source === 'regrid' 
                        ? 'text-purple-500' 
                        : 'text-muted-foreground'
                    )} />
                    <span className="text-xs font-medium text-foreground">Property Boundary</span>
                  </div>
                  <Badge 
                    variant="outline" 
                    className={cn(
                      'text-[10px] h-5 capitalize',
                      parkingLot.property_analysis.property_boundary.source === 'regrid' && 'border-purple-500/50 text-purple-600'
                    )}
                  >
                    {parkingLot.property_analysis.property_boundary.source}
                  </Badge>
                </div>
                <div className="p-3 space-y-2 text-xs">
                  {parkingLot.property_analysis.property_boundary.owner && (
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-muted-foreground flex-shrink-0">Owner</span>
                      <span className="text-foreground text-right truncate">
                        {parkingLot.property_analysis.property_boundary.owner}
                      </span>
                    </div>
                  )}
                  {parkingLot.property_analysis.property_boundary.apn && (
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-muted-foreground">APN</span>
                      <span className="text-foreground font-mono text-[11px]">
                        {parkingLot.property_analysis.property_boundary.apn}
                      </span>
                    </div>
                  )}
                  {parkingLot.property_analysis.property_boundary.land_use && (
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-muted-foreground">Land Use</span>
                      <Badge variant="outline" className="text-[10px] h-5">
                        {parkingLot.property_analysis.property_boundary.land_use}
                      </Badge>
                    </div>
                  )}
                  {parkingLot.property_analysis.property_boundary.zoning && (
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-muted-foreground">Zoning</span>
                      <Badge variant="outline" className="text-[10px] h-5">
                        {parkingLot.property_analysis.property_boundary.zoning}
                      </Badge>
                    </div>
                  )}
                  {parkingLot.property_analysis.property_boundary.parcel_id && (
                    <div className="flex items-center justify-between gap-2 pt-2 border-t border-border mt-2">
                      <span className="text-muted-foreground">Parcel ID</span>
                      <span className="text-foreground font-mono text-[10px] truncate max-w-[150px]">
                        {parkingLot.property_analysis.property_boundary.parcel_id}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Evaluation Error */}
            {parkingLot.evaluation_error && (
              <div className="border border-red-500/30 rounded-lg p-3 bg-red-500/5">
                <div className="flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-medium text-red-700 dark:text-red-400">Evaluation Error</p>
                    <p className="text-xs text-red-600 dark:text-red-300 mt-0.5">{parkingLot.evaluation_error}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}
