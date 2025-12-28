import { Card } from '@/components/ui/card'
import { LucideIcon } from 'lucide-react'
import { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface DataRowProps {
  children: ReactNode
  onClick?: () => void
  className?: string
}

export function DataRow({ children, onClick, className = '' }: DataRowProps) {
  return (
    <Card 
      className={cn(
        'p-3 hover:border-primary/30 transition-colors',
        onClick && 'cursor-pointer',
        className
      )}
      onClick={onClick}
    >
      <div className="flex items-center gap-4">
        {children}
      </div>
    </Card>
  )
}

interface DataFieldProps {
  icon: LucideIcon
  label?: string
  value: ReactNode
  className?: string
}

export function DataField({ icon: Icon, label, value, className = '' }: DataFieldProps) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <Icon className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
      <div className="flex flex-col min-w-0">
        {label && <span className="text-xs text-muted-foreground">{label}</span>}
        <span className="text-sm font-medium truncate">{value}</span>
      </div>
    </div>
  )
}



