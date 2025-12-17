import { cn } from '@/lib/utils'
import { HTMLAttributes } from 'react'

type TextProps = HTMLAttributes<HTMLElement>

/**
 * Title - Page/section titles
 */
export function Title({ className, children, ...props }: TextProps) {
  return (
    <h1 className={cn('text-lg font-semibold text-foreground', className)} {...props}>
      {children}
    </h1>
  )
}

/**
 * Subtitle - Secondary headings
 */
export function Subtitle({ className, children, ...props }: TextProps) {
  return (
    <h2 className={cn('text-sm font-medium text-foreground', className)} {...props}>
      {children}
    </h2>
  )
}

/**
 * Label - Small uppercase labels
 */
export function Label({ className, children, ...props }: TextProps) {
  return (
    <span className={cn('text-[11px] font-medium text-muted-foreground uppercase tracking-wider', className)} {...props}>
      {children}
    </span>
  )
}

/**
 * Text - Body text
 */
export function Text({ className, children, ...props }: TextProps) {
  return (
    <p className={cn('text-sm text-foreground', className)} {...props}>
      {children}
    </p>
  )
}

/**
 * Muted - Secondary/muted text
 */
export function Muted({ className, children, ...props }: TextProps) {
  return (
    <p className={cn('text-sm text-muted-foreground', className)} {...props}>
      {children}
    </p>
  )
}

/**
 * Small - Fine print
 */
export function Small({ className, children, ...props }: TextProps) {
  return (
    <p className={cn('text-xs text-muted-foreground', className)} {...props}>
      {children}
    </p>
  )
}

/**
 * Mono - Monospace text (for code, IDs, etc.)
 */
export function Mono({ className, children, ...props }: TextProps) {
  return (
    <code className={cn('text-xs font-mono text-foreground bg-muted px-1 py-0.5 rounded', className)} {...props}>
      {children}
    </code>
  )
}

/**
 * Tabular - Numbers with tabular alignment
 */
export function Tabular({ className, children, ...props }: TextProps) {
  return (
    <span className={cn('tabular-nums', className)} {...props}>
      {children}
    </span>
  )
}


