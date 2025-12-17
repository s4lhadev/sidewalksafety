'use client'

import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { LucideIcon } from 'lucide-react'

interface MetricCardProps {
  label: string
  value: string | number
  icon: LucideIcon
  iconBgColor?: string
  iconColor?: string
  subtitle?: string
  loading?: boolean
  onClick?: () => void
}

export function MetricCard({
  label,
  value,
  icon: Icon,
  iconBgColor = 'bg-primary/10',
  iconColor = 'text-primary',
  subtitle,
  loading,
  onClick,
}: MetricCardProps) {
  if (loading) {
    return (
      <Card className="p-4 flex items-center gap-4">
        <div className="h-10 w-10 rounded-lg bg-muted animate-pulse" />
        <div className="space-y-2">
          <div className="h-3 w-16 bg-muted animate-pulse rounded" />
          <div className="h-6 w-10 bg-muted animate-pulse rounded" />
        </div>
      </Card>
    )
  }

  return (
    <Card
      className={cn(
        'p-4 flex items-center gap-4 transition-all duration-200',
        onClick && 'cursor-pointer hover:shadow-md hover:border-primary/20'
      )}
      onClick={onClick}
    >
      <div className={cn('p-2.5 rounded-lg', iconBgColor)}>
        <Icon className={cn('h-5 w-5', iconColor)} />
      </div>
      <div>
        <p className="text-xs text-muted-foreground font-medium">{label}</p>
        <p className="text-xl font-bold">{value}</p>
        {subtitle && (
          <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>
        )}
      </div>
    </Card>
  )
}


