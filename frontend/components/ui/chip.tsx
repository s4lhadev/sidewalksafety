import { cn } from '@/lib/utils'
import { LucideIcon } from 'lucide-react'
import { forwardRef, ButtonHTMLAttributes } from 'react'

/**
 * Chip - Minimal, elegant selectable chip component
 */
interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean
  icon?: LucideIcon
  count?: number
  size?: 'sm' | 'md'
  variant?: 'default' | 'outline'
}

export const Chip = forwardRef<HTMLButtonElement, ChipProps>(({
  children,
  active,
  icon: Icon,
  count,
  size = 'md',
  variant = 'default',
  className,
  ...props
}, ref) => {
  return (
    <button
      ref={ref}
      className={cn(
        'inline-flex items-center gap-1.5 font-medium transition-all duration-150',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1',
        // Size
        size === 'sm' && 'h-6 px-2 text-[11px] rounded',
        size === 'md' && 'h-7 px-2.5 text-xs rounded-md',
        // Variant + Active state
        variant === 'default' && [
          active
            ? 'bg-muted text-foreground border border-border'
            : 'bg-transparent text-muted-foreground hover:text-foreground hover:bg-muted/50'
        ],
        variant === 'outline' && [
          'border',
          active
            ? 'border-border bg-muted text-foreground'
            : 'border-border text-muted-foreground hover:text-foreground hover:bg-muted/50'
        ],
        className
      )}
      {...props}
    >
      {Icon && <Icon className={cn(size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5')} />}
      <span>{children}</span>
      {count !== undefined && (
        <span className={cn(
          'tabular-nums',
          active ? 'opacity-70' : 'opacity-50'
        )}>
          {count}
        </span>
      )}
    </button>
  )
})
Chip.displayName = 'Chip'

/**
 * ChipGroup - Container for multiple chips
 */
interface ChipGroupProps {
  children: React.ReactNode
  className?: string
}

export function ChipGroup({ children, className }: ChipGroupProps) {
  return (
    <div className={cn('inline-flex items-center gap-1', className)}>
      {children}
    </div>
  )
}

/**
 * StatusChip - Pre-styled status indicator chip
 */
interface StatusChipProps {
  status: 'success' | 'warning' | 'error' | 'info' | 'neutral'
  icon?: LucideIcon
  children: React.ReactNode
  size?: 'sm' | 'md'
  className?: string
}

const statusStyles = {
  success: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  warning: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  error: 'bg-red-500/10 text-red-600 dark:text-red-400',
  info: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  neutral: 'bg-muted text-muted-foreground',
}

export function StatusChip({ status, icon: Icon, children, size = 'sm', className }: StatusChipProps) {
  return (
    <span className={cn(
      'inline-flex items-center gap-1 font-medium',
      size === 'sm' && 'h-5 px-1.5 text-[10px] rounded',
      size === 'md' && 'h-6 px-2 text-[11px] rounded-md',
      statusStyles[status],
      className
    )}>
      {Icon && <Icon className={cn(size === 'sm' ? 'h-2.5 w-2.5' : 'h-3 w-3')} />}
      {children}
    </span>
  )
}

/**
 * IconChip - Small chip with just an icon (for compact displays)
 */
interface IconChipProps {
  icon: LucideIcon
  tooltip?: string
  variant?: 'default' | 'success' | 'warning' | 'error'
  className?: string
}

const iconChipStyles = {
  default: 'bg-muted text-muted-foreground',
  success: 'bg-emerald-500/10 text-emerald-600',
  warning: 'bg-amber-500/10 text-amber-600',
  error: 'bg-red-500/10 text-red-600',
}

export function IconChip({ icon: Icon, tooltip, variant = 'default', className }: IconChipProps) {
  return (
    <span 
      className={cn(
        'inline-flex items-center justify-center h-5 w-5 rounded',
        iconChipStyles[variant],
        className
      )}
      title={tooltip}
    >
      <Icon className="h-2.5 w-2.5" />
    </span>
  )
}

