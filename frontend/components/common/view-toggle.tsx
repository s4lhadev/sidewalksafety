'use client'

import { Button } from '@/components/ui/button'
import { LayoutGrid, Map } from 'lucide-react'
import { cn } from '@/lib/utils'

type ViewType = 'map' | 'list'

interface ViewToggleProps {
  view: ViewType
  onViewChange: (view: ViewType) => void
  className?: string
}

export function ViewToggle({ view, onViewChange, className }: ViewToggleProps) {
  return (
    <div className={cn('inline-flex items-center rounded-lg border border-border/40 bg-card p-1', className)}>
      <Button
        variant={view === 'map' ? 'default' : 'ghost'}
        size="sm"
        onClick={() => onViewChange('map')}
        className={cn(
          'h-7 px-3 text-xs',
          view === 'map' && 'shadow-sm'
        )}
      >
        <Map className="h-3.5 w-3.5 mr-1.5" />
        Map
      </Button>
      <Button
        variant={view === 'list' ? 'default' : 'ghost'}
        size="sm"
        onClick={() => onViewChange('list')}
        className={cn(
          'h-7 px-3 text-xs',
          view === 'list' && 'shadow-sm'
        )}
      >
        <LayoutGrid className="h-3.5 w-3.5 mr-1.5" />
        List
      </Button>
    </div>
  )
}

