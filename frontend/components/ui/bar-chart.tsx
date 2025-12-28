import { cn } from '@/lib/utils'

/**
 * BarChart - Simple CSS-only bar chart
 */
interface BarChartProps {
  data: { value: number; label?: string }[]
  height?: number
  className?: string
  highlightLast?: boolean
}

export function BarChart({ data, height = 96, className, highlightLast = true }: BarChartProps) {
  const max = Math.max(...data.map(d => d.value), 1)
  
  return (
    <div className={cn('border border-border rounded-lg p-4', className)}>
      <div className="flex items-end gap-1" style={{ height }}>
        {data.map((d, i) => {
          const h = (d.value / max) * 100
          const isLast = highlightLast && i === data.length - 1
          return (
            <div key={i} className="flex-1 flex flex-col items-center group">
              <div 
                className={cn(
                  'w-full rounded-sm transition-all',
                  isLast ? 'bg-foreground' : 'bg-muted-foreground/20 group-hover:bg-muted-foreground/40'
                )}
                style={{ height: `${Math.max(h, 4)}%` }}
              />
            </div>
          )
        })}
      </div>
      {data.length > 0 && data[0].label && (
        <div className="flex justify-between mt-2 text-[10px] text-muted-foreground">
          <span>{data[0].label}</span>
          <span>{data[data.length - 1].label}</span>
        </div>
      )}
    </div>
  )
}

/**
 * ProgressBar - Horizontal progress indicator
 */
interface ProgressBarProps {
  value: number
  max?: number
  className?: string
  size?: 'sm' | 'md'
}

export function ProgressBar({ value, max = 100, className, size = 'sm' }: ProgressBarProps) {
  const percent = Math.min((value / max) * 100, 100)
  
  return (
    <div className={cn(
      'bg-muted rounded-full overflow-hidden',
      size === 'sm' ? 'h-1' : 'h-2',
      className
    )}>
      <div 
        className="h-full bg-foreground rounded-full transition-all duration-300"
        style={{ width: `${percent}%` }}
      />
    </div>
  )
}



