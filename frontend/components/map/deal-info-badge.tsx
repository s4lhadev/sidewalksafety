'use client'

import { DealMapResponse } from '@/types'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { X, MapPin, TrendingUp, DollarSign } from 'lucide-react'
import { cn, getStatusColor, getDamageSeverityColor, formatCurrency } from '@/lib/utils'

interface DealInfoBadgeProps {
  deal: DealMapResponse
  onClose: () => void
  onViewDetails: () => void
  className?: string
}

export function DealInfoBadge({
  deal,
  onClose,
  onViewDetails,
  className,
}: DealInfoBadgeProps) {
  return (
    <div
      className={cn(
        'bg-card/95 backdrop-blur-xl border border-border/40 rounded-lg shadow-2xl',
        'p-4 min-w-[280px] max-w-[320px]',
        'animate-in fade-in slide-in-from-top-2 duration-200',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-base mb-1 truncate">{deal.business_name}</h3>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <MapPin className="h-3 w-3 flex-shrink-0" />
            <span className="truncate">{deal.address}</span>
          </div>
        </div>

        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          className="h-6 w-6 flex-shrink-0 -mt-0.5 -mr-0.5"
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Status & Score */}
      <div className="flex items-center gap-2 mb-3">
        <Badge className={getStatusColor(deal.status)}>
          {deal.status}
        </Badge>
        {deal.deal_score !== null && deal.deal_score !== undefined && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <TrendingUp className="h-3 w-3" />
            <span className="font-medium">{deal.deal_score.toFixed(1)}/10</span>
          </div>
        )}
        {deal.damage_severity && (
          <Badge className={getDamageSeverityColor(deal.damage_severity)}>
            {deal.damage_severity}
          </Badge>
        )}
      </div>

      {/* Value Info */}
      {deal.estimated_job_value && (
        <div className="flex items-center gap-2 mb-3 text-xs">
          <DollarSign className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-muted-foreground">Est. Value:</span>
          <span className="font-semibold">{formatCurrency(deal.estimated_job_value)}</span>
        </div>
      )}

      {/* Action Button */}
      <Button onClick={onViewDetails} className="w-full h-8" size="sm">
        View Details
      </Button>
    </div>
  )
}

