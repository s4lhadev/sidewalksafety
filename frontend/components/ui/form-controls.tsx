import { cn } from '@/lib/utils'
import { ChevronDown, RefreshCw } from 'lucide-react'
import { ButtonHTMLAttributes, SelectHTMLAttributes, forwardRef } from 'react'

/**
 * Select - Compact dropdown select
 */
interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  options: { value: string | number; label: string }[]
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ options, className, ...props }, ref) => {
    return (
      <div className="relative">
        <select
          ref={ref}
          className={cn(
            'appearance-none h-8 pl-3 pr-7 text-xs font-medium',
            'bg-background border border-border rounded-md',
            'focus:outline-none focus:ring-1 focus:ring-ring cursor-pointer',
            className
          )}
          {...props}
        >
          {options.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground pointer-events-none" />
      </div>
    )
  }
)
Select.displayName = 'Select'

/**
 * IconButton - Square icon button
 */
interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: React.ReactNode
  loading?: boolean
}

export function IconButton({ icon, loading, className, disabled, ...props }: IconButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      className={cn(
        'h-8 w-8 flex items-center justify-center',
        'border border-border rounded-md',
        'hover:bg-muted transition-colors',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        className
      )}
      {...props}
    >
      {loading ? (
        <RefreshCw className="h-3.5 w-3.5 text-muted-foreground animate-spin" />
      ) : (
        icon
      )}
    </button>
  )
}

/**
 * TextInput - Compact text input
 */
interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean
}

export const TextInput = forwardRef<HTMLInputElement, TextInputProps>(
  ({ className, error, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn(
          'h-8 px-3 text-sm',
          'bg-background border rounded-md',
          'focus:outline-none focus:ring-1',
          error 
            ? 'border-destructive focus:ring-destructive' 
            : 'border-border focus:ring-ring',
          className
        )}
        {...props}
      />
    )
  }
)
TextInput.displayName = 'TextInput'



