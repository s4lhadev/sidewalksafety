import { cn } from '@/lib/utils'
import { LucideIcon } from 'lucide-react'

/**
 * StatGrid - Container for stat boxes
 */
interface StatGridProps {
  children: React.ReactNode
  columns?: 2 | 3 | 4 | 5
  className?: string
}

const gridCols = {
  2: 'grid-cols-2',
  3: 'grid-cols-3',
  4: 'grid-cols-4',
  5: 'grid-cols-5',
}

export function StatGrid({ children, columns = 4, className }: StatGridProps) {
  return (
    <div className={cn('grid gap-4', gridCols[columns], className)}>
      {children}
    </div>
  )
}

/**
 * StatBox - Simple stat display
 */
interface StatBoxProps {
  label: string
  value: string | number
  sub?: string
  icon?: LucideIcon
  trend?: 'up' | 'down' | 'neutral'
  className?: string
}

export function StatBox({ label, value, sub, icon: Icon, trend, className }: StatBoxProps) {
  return (
    <div className={cn('border border-border rounded-lg p-4', className)}>
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
          {label}
        </p>
        {Icon && <Icon className="h-3.5 w-3.5 text-muted-foreground" />}
      </div>
      <p className="text-xl font-semibold text-foreground mt-1 tabular-nums">{value}</p>
      {sub && (
        <p className={cn(
          'text-[11px] mt-0.5',
          trend === 'up' && 'text-emerald-600',
          trend === 'down' && 'text-red-600',
          !trend && 'text-muted-foreground'
        )}>
          {sub}
        </p>
      )}
    </div>
  )
}



