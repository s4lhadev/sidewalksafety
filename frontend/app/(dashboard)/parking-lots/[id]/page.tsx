'use client'

import { useParkingLot, useParkingLotBusinesses } from '@/lib/queries/use-parking-lots'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusChip, IconChip } from '@/components/ui'
import { SatelliteImageViewer } from '@/components/features/deals/satellite-image-viewer'
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
  MapPinned
} from 'lucide-react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { useState } from 'react'

export default function ParkingLotDetailPage() {
  const params = useParams()
  const router = useRouter()
  const parkingLotId = params.id as string
  const { data: parkingLot, isLoading, error } = useParkingLot(parkingLotId)
  const { data: businesses } = useParkingLotBusinesses(parkingLotId)
  const [copied, setCopied] = useState(false)

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
          {/* Left Column - Satellite Image */}
          <div className="space-y-4">
            <div className="border border-border rounded-lg overflow-hidden bg-card">
              <div className="px-3 py-2 border-b border-border">
                <span className="text-xs font-medium text-foreground">Satellite Imagery</span>
              </div>
              <div className="p-2">
                {parkingLot.satellite_image_url ? (
                  <SatelliteImageViewer
                    imageUrl={parkingLot.satellite_image_url}
                    parkingLotMask={undefined}
                    crackDetections={parkingLot.degradation_areas}
                  />
                ) : (
                  <div className="flex items-center justify-center h-80 bg-muted/50 rounded">
                    <div className="text-center">
                      <MapPinned className="h-8 w-8 text-muted-foreground/30 mx-auto mb-2" />
                      <p className="text-xs text-muted-foreground">No satellite image</p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" className="h-8 text-xs">
                <Download className="h-3.5 w-3.5 mr-1.5" />
                Export Report
              </Button>
              {parkingLot.satellite_image_url && (
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="h-8 text-xs"
                  onClick={() => {
                    const link = document.createElement('a')
                    link.href = parkingLot.satellite_image_url!
                    link.download = `parking-lot-${parkingLotId}.jpg`
                    link.click()
                  }}
                >
                  <Download className="h-3.5 w-3.5 mr-1.5" />
                  Download Image
                </Button>
              )}
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

            {/* Business */}
            <div className={cn(
              'border rounded-lg bg-card',
              hasBusinessData ? 'border-blue-500/30' : 'border-border'
            )}>
              <div className="px-3 py-2 border-b border-border flex items-center justify-between">
                <span className="text-xs font-medium text-foreground">Business</span>
                {hasBusinessData && <CheckCircle2 className="h-3.5 w-3.5 text-blue-500" />}
              </div>
              <div className="p-3">
                {hasBusinessData && primaryBusiness ? (
                  <div className="space-y-2.5 text-xs">
                    <div>
                      <span className="text-muted-foreground">Name</span>
                      <p className="text-foreground font-medium mt-0.5">{primaryBusiness.name}</p>
                    </div>
                    {primaryBusiness.category && (
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Category</span>
                        <Badge variant="outline" className="text-[10px] h-5">{primaryBusiness.category}</Badge>
                      </div>
                    )}
                    <div className="flex flex-wrap gap-1.5 pt-2 border-t border-border">
                      {primaryBusiness.phone && (
                        <a
                          href={`tel:${primaryBusiness.phone}`}
                          className="inline-flex items-center gap-1 px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted rounded-md border border-border transition-colors"
                        >
                          <Phone className="h-3 w-3" />
                          {primaryBusiness.phone}
                        </a>
                      )}
                      {primaryBusiness.website && (
                        <a
                          href={primaryBusiness.website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted rounded-md border border-border transition-colors"
                        >
                          <Globe className="h-3 w-3" />
                          Website
                          <ExternalLink className="h-2.5 w-2.5" />
                        </a>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-4">
                    <AlertTriangle className="h-5 w-5 text-muted-foreground/30 mx-auto mb-1.5" />
                    <p className="text-xs text-muted-foreground">No business data</p>
                  </div>
                )}
              </div>
            </div>

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

        {/* Associated Businesses */}
        {businesses && businesses.length > 0 && (
          <div className="mt-6">
            <div className="border border-border rounded-lg bg-card">
              <div className="px-3 py-2 border-b border-border flex items-center gap-2">
                <span className="text-xs font-medium text-foreground">Associated Businesses</span>
                <Badge variant="outline" className="text-[10px] h-5">{businesses.length}</Badge>
              </div>
              <div className="divide-y divide-border">
                {businesses.map((business) => (
                  <div key={business.id} className="p-3 flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Building2 className={cn('h-3.5 w-3.5', business.is_primary ? 'text-blue-500' : 'text-muted-foreground')} />
                        <span className="text-sm font-medium text-foreground truncate">{business.name}</span>
                        {business.is_primary && (
                          <Badge className="bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20 text-[10px] h-5">Primary</Badge>
                        )}
                      </div>
                      {business.address && (
                        <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                          <MapPin className="h-3 w-3 flex-shrink-0" />
                          {business.address}
                        </p>
                      )}
                      {business.category && (
                        <Badge variant="outline" className="text-[10px] h-5 mb-2">{business.category}</Badge>
                      )}
                      <div className="flex flex-wrap gap-1.5">
                        {business.phone && (
                          <a
                            href={`tel:${business.phone}`}
                            className="inline-flex items-center gap-1 px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted rounded-md border border-border transition-colors"
                          >
                            <Phone className="h-3 w-3" />
                            {business.phone}
                          </a>
                        )}
                        {business.website && (
                          <a
                            href={business.website}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted rounded-md border border-border transition-colors"
                          >
                            <Globe className="h-3 w-3" />
                            Website
                            <ExternalLink className="h-2.5 w-2.5" />
                          </a>
                        )}
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className="text-[10px] text-muted-foreground mb-0.5">Match</div>
                      <div className="text-base font-semibold tabular-nums text-foreground">{Math.round(business.match_score)}%</div>
                      <div className="text-[10px] text-muted-foreground">{formatNumber(business.distance_meters, 0)}m</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
