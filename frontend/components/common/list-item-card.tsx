'use client'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { LucideIcon, Edit2, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ReactNode } from 'react'

export interface ListItemBadge {
  label: string
  variant?: 'default' | 'secondary' | 'destructive' | 'outline'
  className?: string
}

export interface ListItemAction {
  icon?: LucideIcon
  label: string
  onClick: () => void
  variant?: 'default' | 'ghost' | 'outline' | 'destructive'
  disabled?: boolean
  loading?: boolean
}

interface ListItemCardProps {
  title: string
  badges?: ListItemBadge[]
  actions?: ListItemAction[]
  description?: string
  className?: string
  titleClassName?: string
  children?: ReactNode
  icon?: ReactNode
  onClick?: () => void
}

export function ListItemCard({
  title,
  badges = [],
  actions = [],
  description,
  className,
  titleClassName,
  children,
  icon,
  onClick,
}: ListItemCardProps) {
  return (
    <div
      onClick={onClick}
      className={cn(
        'py-4 px-4 flex items-start justify-between gap-4 hover:bg-muted/30 transition-colors last:border-b-0 group',
        onClick && 'cursor-pointer',
        className
      )}
    >
      {/* Left: Content */}
      <div className="flex-1 min-w-0 flex flex-col gap-2">
        {/* Title Row */}
        <div className="flex items-center gap-2">
          {icon && (
            <div className="flex-shrink-0">
              {icon}
            </div>
          )}
          <h4 className={cn('text-sm font-semibold text-foreground', titleClassName)}>{title}</h4>
        </div>

        {/* Badges Row */}
        {badges.length > 0 && (
          <div className="flex flex-wrap gap-1.5 items-center">
            {badges.map((badge, index) => (
              <Badge
                key={index}
                variant={badge.variant || 'secondary'}
                className={cn('text-xs h-fit', badge.className)}
              >
                {badge.label}
              </Badge>
            ))}
          </div>
        )}

        {/* Description */}
        {description && (
          <p className="text-xs text-muted-foreground line-clamp-2">{description}</p>
        )}

        {/* Children (e.g., progress bars) */}
        {children}
      </div>

      {/* Right: Actions */}
      {actions.length > 0 && (
        <div className="flex gap-1 flex-shrink-0">
          {actions.map((action, index) => {
            const Icon = action.icon || (action.variant === 'destructive' ? Trash2 : Edit2)
            const isDestructive = action.variant === 'destructive'
            
            return (
              <Button
                key={index}
                variant={isDestructive ? 'ghost' : (action.variant || 'ghost')}
                size="sm"
                onClick={(e) => {
                  e.stopPropagation()
                  action.onClick()
                }}
                disabled={action.disabled || action.loading}
                className={cn(
                  'gap-1.5 text-xs',
                  isDestructive &&
                    'text-destructive hover:text-destructive hover:bg-destructive/10'
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {action.label}
              </Button>
            )
          })}
        </div>
      )}
    </div>
  )
}


