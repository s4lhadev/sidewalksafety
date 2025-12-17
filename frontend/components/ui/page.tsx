import { cn } from '@/lib/utils'
import { ReactNode } from 'react'

/**
 * Page - Main page wrapper with consistent max-width and padding
 */
interface PageProps {
  children: ReactNode
  className?: string
  size?: 'sm' | 'md' | 'lg' | 'full'
}

const sizes = {
  sm: 'max-w-2xl',   // 672px - forms, settings
  md: 'max-w-4xl',   // 896px - dashboards, tables
  lg: 'max-w-6xl',   // 1152px - complex layouts
  full: 'max-w-full', // full width
}

export function Page({ children, className, size = 'md' }: PageProps) {
  return (
    <div className={cn('min-h-screen bg-background', className)}>
      <div className={cn(sizes[size], 'mx-auto px-6 py-8')}>
        {children}
      </div>
    </div>
  )
}

/**
 * PageHeader - Consistent page title and actions
 */
interface PageHeaderProps {
  title: string
  description?: string
  actions?: ReactNode
  className?: string
}

export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  return (
    <div className={cn('flex items-center justify-between mb-8', className)}>
      <div>
        <h1 className="text-lg font-semibold text-foreground">{title}</h1>
        {description && (
          <p className="text-sm text-muted-foreground mt-0.5">{description}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}

/**
 * Section - Grouped content with optional title
 */
interface SectionProps {
  title?: string
  children: ReactNode
  className?: string
}

export function Section({ title, children, className }: SectionProps) {
  return (
    <section className={className}>
      {title && (
        <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
          {title}
        </h2>
      )}
      {children}
    </section>
  )
}


