'use client'

import { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface ListContainerProps {
  children: ReactNode
  className?: string
}

export function ListContainer({ children, className }: ListContainerProps) {
  return (
    <div className={cn('border rounded-lg divide-y bg-card', className)}>
      {children}
    </div>
  )
}


