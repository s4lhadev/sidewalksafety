import { Button } from '@/components/ui/button'
import { LucideIcon, Plus } from 'lucide-react'

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description: string
  action?: {
    label: string
    onClick: () => void
    icon?: LucideIcon
  }
  compact?: boolean
}

export function EmptyState({ icon: Icon, title, description, action, compact }: EmptyStateProps) {
  return (
    <div className={`flex items-center justify-center ${compact ? 'py-12' : 'min-h-[60vh]'}`}>
      <div className="text-center space-y-6 max-w-sm px-4">
        {/* Icon with dashed border */}
        {Icon && (
          <div className={`mx-auto ${compact ? 'w-16 h-16' : 'w-24 h-24'} rounded-2xl border-2 border-dashed border-border flex items-center justify-center`}>
            <Icon className={`${compact ? 'h-7 w-7' : 'h-10 w-10'} text-muted-foreground/30`} strokeWidth={1.5} />
          </div>
        )}
        
        {/* Text */}
        <div className="space-y-2">
          <h3 className="text-base font-medium text-foreground">
            {title}
          </h3>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {description}
          </p>
        </div>
        
        {/* Action Button with dashed separator */}
        {action && (
          <div className="relative pt-4">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-16 border-t border-dashed border-border/50" />
            
            <Button 
              onClick={action.onClick} 
              variant="gradient"
              className="gap-2 mt-2"
            >
              {action.icon ? <action.icon className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
              {action.label}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
