'use client'

import { useParkingLot, useParkingLotBusinesses } from '@/lib/queries/use-parking-lots'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { SatelliteImageViewer } from '@/components/features/deals/satellite-image-viewer'
import { formatNumber } from '@/lib/utils'
import { 
  MapPin, 
  Building2, 
  ArrowLeft,
  Phone,
  Mail,
  Globe,
  ExternalLink,
  CheckCircle2,
  XCircle,
  Calendar,
  Copy,
  Share2,
  Download,
  AlertCircle,
  ChevronRight
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

  if (isLoading) {
    return (
      <div className="min-h-screen bg-white">
        <div className="max-w-6xl mx-auto px-4 py-6 space-y-4">
          <Skeleton className="h-8 w-64" />
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2 space-y-4">
              <Skeleton className="h-48" />
              <Skeleton className="h-64" />
            </div>
            <div className="space-y-4">
              <Skeleton className="h-32" />
              <Skeleton className="h-32" />
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (error || !parkingLot) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center p-4">
        <Card className="max-w-md w-full border-0 shadow-sm">
          <CardContent className="pt-6">
            <div className="text-center space-y-3">
              <XCircle className="h-8 w-8 text-slate-400 mx-auto" />
              <div>
                <h2 className="text-lg font-medium text-slate-900">Parking Lot Not Found</h2>
                <p className="text-sm text-slate-500 mt-1">
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
          </CardContent>
        </Card>
      </div>
    )
  }

  const primaryBusiness = parkingLot.business || businesses?.find(b => b.is_primary) || businesses?.[0]
  const hasBusinessData = !!primaryBusiness || (businesses && businesses.length > 0)
  const displayName = primaryBusiness?.name || parkingLot.operator_name || 'Parking Lot'
  const displayAddress = parkingLot.address || 'Address not available'
  const conditionScore = parkingLot.condition_score ?? null

  const getConditionColor = (score: number | null) => {
    if (!score) return { text: 'text-slate-400', bg: 'bg-slate-50', border: 'border-slate-200' }
    if (score < 30) return { text: 'text-red-600', bg: 'bg-red-50', border: 'border-red-200' }
    if (score < 50) return { text: 'text-orange-600', bg: 'bg-orange-50', border: 'border-orange-200' }
    if (score < 70) return { text: 'text-yellow-600', bg: 'bg-yellow-50', border: 'border-yellow-200' }
    return { text: 'text-green-600', bg: 'bg-green-50', border: 'border-green-200' }
  }

  const conditionColors = getConditionColor(conditionScore)

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-7xl mx-auto px-6 py-4">
        {/* Header */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-3">
            <Link href="/dashboard">
              <Button variant="ghost" size="sm" className="h-7 px-2 -ml-2 text-xs">
                <ArrowLeft className="h-3 w-3 mr-1" />
                Back
              </Button>
            </Link>
            <div className="flex items-center gap-0.5">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                onClick={handleCopyLink}
              >
                {copied ? <CheckCircle2 className="h-3 w-3 text-green-600" /> : <Copy className="h-3 w-3" />}
              </Button>
              <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                <Share2 className="h-3 w-3" />
              </Button>
            </div>
          </div>

          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <h1 className="text-lg font-semibold text-slate-900 mb-1 truncate">{displayName}</h1>
              <div className="text-xs text-slate-500 flex items-center gap-1.5">
                <MapPin className="h-3 w-3 flex-shrink-0" />
                <span className="truncate">{displayAddress}</span>
              </div>
            </div>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              {hasBusinessData ? (
                <Badge variant="outline" className="border-green-300 text-green-700 bg-green-50/50 text-[10px] px-1.5 py-0.5 h-5">
                  <CheckCircle2 className="h-2.5 w-2.5 mr-0.5" />
                  Business Data
                </Badge>
              ) : (
                <Badge variant="outline" className="border-slate-300 text-slate-600 bg-slate-50 text-[10px] px-1.5 py-0.5 h-5">
                  <XCircle className="h-2.5 w-2.5 mr-0.5" />
                  No Business Data
                </Badge>
              )}
              {parkingLot.is_evaluated ? (
                <Badge variant="outline" className="border-green-300 text-green-700 bg-green-50/50 text-[10px] px-1.5 py-0.5 h-5">
                  Evaluated
                </Badge>
              ) : (
                <Badge variant="outline" className="border-orange-300 text-orange-700 bg-orange-50/50 text-[10px] px-1.5 py-0.5 h-5">
                  Pending
                </Badge>
              )}
            </div>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
          {/* Left Column - Satellite Image */}
          <div className="lg:sticky lg:top-4 lg:self-start">
            {parkingLot.satellite_image_url ? (
              <Card className="border border-slate-200">
                <CardHeader className="pb-2 px-3 pt-3">
                  <CardTitle className="text-xs font-semibold text-slate-900">Satellite Imagery</CardTitle>
                </CardHeader>
                <CardContent className="px-3 pb-3">
                  <SatelliteImageViewer
                    imageUrl={parkingLot.satellite_image_url}
                    parkingLotMask={undefined}
                    crackDetections={parkingLot.degradation_areas}
                  />
                </CardContent>
              </Card>
            ) : (
              <Card className="border border-slate-200">
                <CardHeader className="pb-2 px-3 pt-3">
                  <CardTitle className="text-xs font-semibold text-slate-900">Satellite Imagery</CardTitle>
                </CardHeader>
                <CardContent className="px-3 pb-3">
                  <div className="flex items-center justify-center h-[500px] bg-slate-50 rounded border border-slate-200">
                    <p className="text-[10px] text-slate-500">No satellite image available</p>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right Column - All Data */}
          <div className="space-y-3">
            {/* Condition Score */}
            {conditionScore !== null && (
              <Card className="border border-slate-200">
                <CardContent className="p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">Condition Score</span>
                    <span className={`text-xl font-light ${conditionColors.text}`} style={{ letterSpacing: '-0.03em' }}>
                      {Math.round(conditionScore)}
                    </span>
                  </div>
                  <div className="h-1 bg-slate-100 rounded-full overflow-hidden">
                    <div 
                      className={`h-full ${conditionColors.bg.replace('50', '500')} transition-all`}
                      style={{ width: `${conditionScore}%` }}
                    />
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Metrics Grid */}
            <div className="grid grid-cols-3 gap-2">
              {parkingLot.area_sqft && (
                <Card className="border border-slate-200">
                  <CardContent className="p-2.5">
                    <div className="text-[10px] text-slate-500 mb-0.5">Area</div>
                    <div className="text-xs font-light text-slate-900" style={{ letterSpacing: '-0.01em' }}>
                      {formatNumber(parkingLot.area_sqft, 0)}
                      <span className="text-[10px] font-normal text-slate-500 ml-0.5">sq ft</span>
                    </div>
                  </CardContent>
                </Card>
              )}
              {parkingLot.crack_density !== null && parkingLot.crack_density !== undefined && (
                <Card className="border border-slate-200">
                  <CardContent className="p-2.5">
                    <div className="text-[10px] text-slate-500 mb-0.5">Crack Density</div>
                    <div className="text-xs font-light text-slate-900" style={{ letterSpacing: '-0.01em' }}>
                      {formatNumber(parkingLot.crack_density, 1)}%
                    </div>
                  </CardContent>
                </Card>
              )}
              {parkingLot.pothole_score !== null && parkingLot.pothole_score !== undefined && (
                <Card className="border border-slate-200">
                  <CardContent className="p-2.5">
                    <div className="text-[10px] text-slate-500 mb-0.5">Pothole Score</div>
                    <div className="text-xs font-light text-slate-900" style={{ letterSpacing: '-0.01em' }}>
                      {formatNumber(parkingLot.pothole_score, 1)}/10
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>

            {/* Evaluation Details */}
            {parkingLot.is_evaluated && conditionScore !== null && (
              <Card className="border border-slate-200">
                <CardHeader className="pb-2 px-3 pt-3">
                  <CardTitle className="text-xs font-semibold text-slate-900">Evaluation Details</CardTitle>
                </CardHeader>
                <CardContent className="px-3 pb-3 space-y-2">
                  {parkingLot.crack_density !== null && parkingLot.crack_density !== undefined && (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-600">Crack Density</span>
                      <span className="font-light text-slate-900" style={{ letterSpacing: '-0.01em' }}>{formatNumber(parkingLot.crack_density, 1)}%</span>
                    </div>
                  )}
                  {parkingLot.pothole_score !== null && parkingLot.pothole_score !== undefined && (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-600">Pothole Score</span>
                      <span className="font-light text-slate-900" style={{ letterSpacing: '-0.01em' }}>{formatNumber(parkingLot.pothole_score, 1)}/10</span>
                    </div>
                  )}
                  {parkingLot.line_fading_score !== null && parkingLot.line_fading_score !== undefined && (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-600">Line Fading</span>
                      <span className="font-light text-slate-900" style={{ letterSpacing: '-0.01em' }}>{formatNumber(parkingLot.line_fading_score, 1)}/10</span>
                    </div>
                  )}
                  {parkingLot.evaluated_at && (
                    <div className="flex items-center justify-between text-xs pt-2 border-t border-slate-100">
                      <span className="text-slate-500 flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        Evaluated
                      </span>
                      <span className="text-slate-600">
                        {new Date(parkingLot.evaluated_at).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Evaluation Error */}
            {parkingLot.evaluation_error && (
              <Card className="border border-red-200 bg-red-50/50">
                <CardContent className="p-3">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="h-3.5 w-3.5 text-red-600 flex-shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <p className="text-[10px] font-medium text-red-900 mb-0.5">Evaluation Error</p>
                      <p className="text-[10px] text-red-700 leading-relaxed">{parkingLot.evaluation_error}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Location */}
            <Card className="border border-slate-200">
              <CardHeader className="pb-2 px-3 pt-3">
                <CardTitle className="text-xs font-semibold text-slate-900">Location</CardTitle>
              </CardHeader>
              <CardContent className="px-3 pb-3 space-y-2 text-xs">
                <div>
                  <div className="text-[10px] text-slate-500 mb-0.5">Address</div>
                  <div className="text-slate-900 leading-relaxed">{displayAddress}</div>
                </div>
                {parkingLot.centroid && (
                  <div>
                    <div className="text-[10px] text-slate-500 mb-0.5">Coordinates</div>
                    <div className="text-slate-600 font-mono text-[10px]">
                      {parkingLot.centroid.lat.toFixed(6)}, {parkingLot.centroid.lng.toFixed(6)}
                    </div>
                  </div>
                )}
                {parkingLot.surface_type && (
                  <div>
                    <div className="text-[10px] text-slate-500 mb-0.5">Surface Type</div>
                    <Badge variant="outline" className="text-[10px] capitalize border-slate-200 h-4 px-1.5">
                      {parkingLot.surface_type}
                    </Badge>
                  </div>
                )}
                {parkingLot.data_sources && parkingLot.data_sources.length > 0 && (
                  <div>
                    <div className="text-[10px] text-slate-500 mb-1">Data Sources</div>
                    <div className="flex flex-wrap gap-1">
                      {parkingLot.data_sources.map((source) => (
                        <Badge key={source} variant="outline" className="text-[10px] border-slate-200 h-4 px-1.5">
                          {source}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Business */}
            <Card className={`border ${hasBusinessData ? 'border-green-200 bg-green-50/30' : 'border-slate-200'}`}>
              <CardHeader className="pb-2 px-3 pt-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-xs font-semibold text-slate-900">Business</CardTitle>
                  {hasBusinessData && (
                    <CheckCircle2 className="h-3 w-3 text-green-600" />
                  )}
                </div>
              </CardHeader>
              <CardContent className="px-3 pb-3">
                {hasBusinessData && primaryBusiness ? (
                  <div className="space-y-2 text-xs">
                    <div>
                      <div className="text-[10px] text-slate-500 mb-0.5">Name</div>
                      <div className="font-medium text-slate-900">{primaryBusiness.name}</div>
                    </div>
                    {primaryBusiness.address && (
                      <div>
                        <div className="text-[10px] text-slate-500 mb-0.5">Address</div>
                        <div className="text-slate-600 leading-relaxed">{primaryBusiness.address}</div>
                      </div>
                    )}
                    {primaryBusiness.category && (
                      <div>
                        <div className="text-[10px] text-slate-500 mb-0.5">Category</div>
                        <Badge variant="outline" className="text-[10px] border-slate-200 h-4 px-1.5">
                          {primaryBusiness.category}
                        </Badge>
                      </div>
                    )}
                    <div className="flex flex-wrap gap-1 pt-1.5 border-t border-slate-100">
                      {primaryBusiness.phone && (
                        <a
                          href={`tel:${primaryBusiness.phone}`}
                          className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded border border-slate-200 transition-colors"
                        >
                          <Phone className="h-2.5 w-2.5" />
                          {primaryBusiness.phone}
                        </a>
                      )}
                      {primaryBusiness.email && (
                        <a
                          href={`mailto:${primaryBusiness.email}`}
                          className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded border border-slate-200 transition-colors truncate max-w-[140px]"
                        >
                          <Mail className="h-2.5 w-2.5 flex-shrink-0" />
                          <span className="truncate">{primaryBusiness.email}</span>
                        </a>
                      )}
                      {primaryBusiness.website && (
                        <a
                          href={primaryBusiness.website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded border border-slate-200 transition-colors"
                        >
                          <Globe className="h-2.5 w-2.5" />
                          Website
                          <ExternalLink className="h-2 w-2" />
                        </a>
                      )}
                    </div>
                    {businesses && businesses.length > 1 && (
                      <button
                        onClick={() => {
                          document.getElementById('businesses-section')?.scrollIntoView({ behavior: 'smooth' })
                        }}
                        className="w-full flex items-center justify-between text-[10px] text-slate-600 hover:text-slate-900 pt-1.5 border-t border-slate-100"
                      >
                        <span>View {businesses.length} businesses</span>
                        <ChevronRight className="h-2.5 w-2.5" />
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-3">
                    <AlertCircle className="h-4 w-4 text-slate-400 mx-auto mb-1" />
                    <p className="text-[10px] text-slate-500">No business data available</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Actions */}
            <Card className="border border-slate-200">
              <CardHeader className="pb-2 px-3 pt-3">
                <CardTitle className="text-xs font-semibold text-slate-900">Actions</CardTitle>
              </CardHeader>
              <CardContent className="px-3 pb-3 space-y-1">
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="w-full justify-start h-7 text-[10px] text-slate-600 hover:text-slate-900"
                >
                  <Download className="h-3 w-3 mr-1.5" />
                  Export Report
                </Button>
                {parkingLot.satellite_image_url && (
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="w-full justify-start h-7 text-[10px] text-slate-600 hover:text-slate-900"
                    onClick={() => {
                      const link = document.createElement('a')
                      link.href = parkingLot.satellite_image_url!
                      link.download = `parking-lot-${parkingLotId}-satellite.jpg`
                      link.click()
                    }}
                  >
                    <Download className="h-3 w-3 mr-1.5" />
                    Download Image
                  </Button>
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Associated Businesses */}
        {businesses && businesses.length > 0 && (
          <div id="businesses-section" className="mt-4">
            <Card className="border border-slate-200">
              <CardHeader className="pb-2 px-3 pt-3">
                <CardTitle className="text-xs font-semibold text-slate-900">
                  Associated Businesses
                  <Badge variant="outline" className="ml-1.5 text-[10px] border-slate-200 h-4 px-1.5">
                    {businesses.length}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="px-3 pb-3">
                <div className="space-y-2">
                  {businesses.map((business) => (
                    <div
                      key={business.id}
                      className={`p-2.5 rounded border text-xs transition-colors ${
                        business.is_primary 
                          ? 'border-green-200 bg-green-50/50' 
                          : 'border-slate-200 bg-white'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5 mb-1">
                            <Building2 className={`h-3 w-3 flex-shrink-0 ${business.is_primary ? 'text-green-600' : 'text-slate-400'}`} />
                            <span className="font-medium text-slate-900 truncate">{business.name}</span>
                            {business.is_primary && (
                              <Badge variant="outline" className="text-[10px] border-green-300 text-green-700 bg-green-50/50 px-1 py-0 h-4">
                                Primary
                              </Badge>
                            )}
                          </div>
                          {business.address && (
                            <p className="text-[10px] text-slate-500 mb-1.5 flex items-center gap-1">
                              <MapPin className="h-2.5 w-2.5 flex-shrink-0" />
                              {business.address}
                            </p>
                          )}
                          {business.category && (
                            <Badge variant="outline" className="text-[10px] border-slate-200 mb-1.5 h-4 px-1.5">
                              {business.category}
                            </Badge>
                          )}
                          <div className="flex flex-wrap gap-1 mt-1.5">
                            {business.phone && (
                              <a
                                href={`tel:${business.phone}`}
                                className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded border border-slate-200 transition-colors"
                              >
                                <Phone className="h-2.5 w-2.5" />
                                {business.phone}
                              </a>
                            )}
                            {business.email && (
                              <a
                                href={`mailto:${business.email}`}
                                className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded border border-slate-200 transition-colors truncate max-w-[140px]"
                              >
                                <Mail className="h-2.5 w-2.5 flex-shrink-0" />
                                <span className="truncate">{business.email}</span>
                              </a>
                            )}
                            {business.website && (
                              <a
                                href={business.website}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded border border-slate-200 transition-colors"
                              >
                                <Globe className="h-2.5 w-2.5" />
                                Website
                                <ExternalLink className="h-2 w-2" />
                              </a>
                            )}
                          </div>
                        </div>
                        <div className="text-right flex-shrink-0 ml-3">
                          <div className="text-[10px] text-slate-500 mb-0.5">Match</div>
                          <div className="text-sm font-light text-slate-900" style={{ letterSpacing: '-0.02em' }}>{Math.round(business.match_score)}%</div>
                          <div className="text-[10px] text-slate-400 mt-0.5">
                            {formatNumber(business.distance_meters, 0)}m
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
