import { cn } from '@/lib/utils'
import { HTMLAttributes } from 'react'

interface HeadingProps extends HTMLAttributes<HTMLHeadingElement> {
  children: React.ReactNode
}

export function H1({ className, children, ...props }: HeadingProps) {
  return (
    <h1
      className={cn(
        'text-3xl font-bold tracking-tight text-foreground sm:text-4xl',
        className
      )}
      {...props}
    >
      {children}
    </h1>
  )
}

export function H2({ className, children, ...props }: HeadingProps) {
  return (
    <h2
      className={cn(
        'text-2xl font-semibold tracking-tight text-foreground',
        className
      )}
      {...props}
    >
      {children}
    </h2>
  )
}

export function H3({ className, children, ...props }: HeadingProps) {
  return (
    <h3
      className={cn(
        'text-xl font-semibold tracking-tight text-foreground',
        className
      )}
      {...props}
    >
      {children}
    </h3>
  )
}

export function H4({ className, children, ...props }: HeadingProps) {
  return (
    <h4
      className={cn(
        'text-lg font-semibold text-foreground',
        className
      )}
      {...props}
    >
      {children}
    </h4>
  )
}


