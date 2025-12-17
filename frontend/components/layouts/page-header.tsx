import { ReactNode } from 'react'
import { ArrowLeft, LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface PageHeaderProps {
  title: string | ReactNode
  description?: string
  icon?: LucideIcon
  iconColor?: string
  iconBgColor?: string
  actions?: ReactNode
  onBack?: () => void
  backLabel?: string
  className?: string
}

export function PageHeader({ 
  title, 
  description,
  icon: Icon,
  iconColor = 'text-white',
  iconBgColor = 'bg-gradient-to-br from-orange-500 to-orange-600',
  actions, 
  onBack, 
  backLabel = 'Back',
  className,
}: PageHeaderProps) {
  return (
    <header className={cn('border-b border-border bg-background flex-shrink-0', className)}>
      <div className="px-6 py-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          {onBack && (
            <button
              onClick={onBack}
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>{backLabel}</span>
            </button>
          )}
          
          {Icon && (
            <div className={cn('p-2 rounded-xl', iconBgColor)}>
              <Icon className={cn('h-5 w-5', iconColor)} />
            </div>
          )}
          
          <div>
            {typeof title === 'string' ? (
              <h1 className="text-xl font-semibold text-foreground">
                {title}
              </h1>
            ) : (
              title
            )}
            {description && (
              <p className="text-sm text-muted-foreground mt-0.5">
                {description}
              </p>
            )}
          </div>
        </div>
        
        {actions && (
          <div className="flex items-center gap-2">
            {actions}
          </div>
        )}
      </div>
    </header>
  )
}


