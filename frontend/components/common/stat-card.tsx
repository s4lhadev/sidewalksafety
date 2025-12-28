'use client'

import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { TrendingUp, TrendingDown, Minus, LucideIcon } from 'lucide-react'

interface StatCardProps {
  title: string
  value: string | number
  change?: number
  changeLabel?: string
  icon: LucideIcon
  iconColor?: string
  iconBgColor?: string
  loading?: boolean
  onClick?: () => void
}

export function StatCard({
  title,
  value,
  change,
  changeLabel,
  icon: Icon,
  iconColor = 'text-primary',
  iconBgColor = 'bg-primary/10',
  loading,
  onClick,
}: StatCardProps) {
  const changeType = change === undefined || change === 0 
    ? 'neutral' 
    : change > 0 
      ? 'positive' 
      : 'negative'
  
  const ChangeIcon = changeType === 'positive' 
    ? TrendingUp 
    : changeType === 'negative' 
      ? TrendingDown 
      : Minus

  return (
    <Card
      className={cn(
        'transition-all hover:shadow-md',
        onClick && 'cursor-pointer hover:border-primary/20'
      )}
      onClick={onClick}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              {title}
            </p>
            {loading ? (
              <div className="h-8 w-20 bg-muted animate-pulse rounded" />
            ) : (
              <p className="text-2xl font-bold tracking-tight">{value}</p>
            )}
          </div>
          <div className={cn('p-2.5 rounded-lg', iconBgColor)}>
            <Icon className={cn('h-5 w-5', iconColor)} />
          </div>
        </div>
        
        {change !== undefined && !loading && (
          <div className="mt-3 flex items-center gap-1.5">
            <div
              className={cn(
                'flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium',
                changeType === 'positive' && 'text-emerald-600 bg-emerald-50 dark:bg-emerald-950/30',
                changeType === 'negative' && 'text-red-600 bg-red-50 dark:bg-red-950/30',
                changeType === 'neutral' && 'text-muted-foreground bg-muted'
              )}
            >
              <ChangeIcon className="h-3 w-3" />
              <span>{Math.abs(change).toFixed(1)}%</span>
            </div>
            {changeLabel && (
              <span className="text-xs text-muted-foreground">{changeLabel}</span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}



