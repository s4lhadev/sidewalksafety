import { cn } from '@/lib/utils'
import { LucideIcon } from 'lucide-react'
import { ReactNode } from 'react'

/**
 * DataList - Bordered list container
 */
interface DataListProps {
  children: ReactNode
  className?: string
}

export function DataList({ children, className }: DataListProps) {
  return (
    <div className={cn('border border-border rounded-lg divide-y divide-border', className)}>
      {children}
    </div>
  )
}

/**
 * DataListItem - Row in a data list
 */
interface DataListItemProps {
  label: string
  value: string | number
  sub?: string
  icon?: LucideIcon
  onClick?: () => void
  className?: string
}

export function DataListItem({ label, value, sub, icon: Icon, onClick, className }: DataListItemProps) {
  const Comp = onClick ? 'button' : 'div'
  
  return (
    <Comp 
      onClick={onClick}
      className={cn(
        'flex items-center justify-between px-4 py-3 w-full text-left',
        onClick && 'hover:bg-muted/50 transition-colors cursor-pointer',
        className
      )}
    >
      <div className="flex items-center gap-2.5">
        {Icon && <Icon className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />}
        <span className="text-sm text-foreground">{label}</span>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-sm font-medium tabular-nums">{value}</span>
        {sub && <span className="text-xs text-muted-foreground w-16 text-right">{sub}</span>}
      </div>
    </Comp>
  )
}

/**
 * DataListHeader - Optional header row
 */
interface DataListHeaderProps {
  left: string
  right?: string
  sub?: string
}

export function DataListHeader({ left, right, sub }: DataListHeaderProps) {
  return (
    <div className="flex items-center justify-between px-4 py-2 bg-muted/30">
      <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{left}</span>
      <div className="flex items-center gap-4">
        {right && <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{right}</span>}
        {sub && <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider w-16 text-right">{sub}</span>}
      </div>
    </div>
  )
}


