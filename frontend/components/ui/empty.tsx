import { cn } from '@/lib/utils'
import { LucideIcon } from 'lucide-react'
import { Button } from './button'

/**
 * Empty - Empty state with dashed border
 */
interface EmptyProps {
  icon?: LucideIcon
  title: string
  description?: string
  action?: {
    label: string
    onClick: () => void
  }
  className?: string
}

export function Empty({ icon: Icon, title, description, action, className }: EmptyProps) {
  return (
    <div className={cn(
      'text-center py-16 border border-dashed border-border rounded-lg',
      className
    )}>
      {Icon && (
        <Icon className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" strokeWidth={1.5} />
      )}
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description && (
        <p className="text-xs text-muted-foreground mt-1">{description}</p>
      )}
      {action && (
        <Button 
          variant="outline" 
          size="sm" 
          onClick={action.onClick}
          className="mt-4"
        >
          {action.label}
        </Button>
      )}
    </div>
  )
}

/**
 * Loading - Simple spinner
 */
interface LoadingProps {
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

const spinnerSizes = {
  sm: 'h-4 w-4',
  md: 'h-5 w-5',
  lg: 'h-6 w-6',
}

export function Loading({ className, size = 'md' }: LoadingProps) {
  return (
    <div className={cn('flex items-center justify-center py-20', className)}>
      <div className={cn(
        'border-2 border-muted-foreground/30 border-t-foreground rounded-full animate-spin',
        spinnerSizes[size]
      )} />
    </div>
  )
}



