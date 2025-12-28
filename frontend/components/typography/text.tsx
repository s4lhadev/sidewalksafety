import { cn } from '@/lib/utils'
import { HTMLAttributes } from 'react'

interface TextProps extends HTMLAttributes<HTMLParagraphElement> {
  children: React.ReactNode
}

export function Body({ className, children, ...props }: TextProps) {
  return (
    <p
      className={cn('text-base text-foreground leading-relaxed', className)}
      {...props}
    >
      {children}
    </p>
  )
}

export function BodyMuted({ className, children, ...props }: TextProps) {
  return (
    <p
      className={cn('text-base text-muted-foreground leading-relaxed', className)}
      {...props}
    >
      {children}
    </p>
  )
}

export function Caption({ className, children, ...props }: TextProps) {
  return (
    <p
      className={cn('text-sm text-muted-foreground', className)}
      {...props}
    >
      {children}
    </p>
  )
}

export function Small({ className, children, ...props }: TextProps) {
  return (
    <p
      className={cn('text-xs text-muted-foreground', className)}
      {...props}
    >
      {children}
    </p>
  )
}

export function Lead({ className, children, ...props }: TextProps) {
  return (
    <p
      className={cn('text-lg text-muted-foreground leading-relaxed', className)}
      {...props}
    >
      {children}
    </p>
  )
}



