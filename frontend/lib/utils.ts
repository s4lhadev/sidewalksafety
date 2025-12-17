import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(amount: string | number): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount
  if (isNaN(num)) return '$0.00'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(num)
}

export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(d)
}

export function formatDateTime(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(d)
}

export function formatNumber(num: number, decimals: number = 0): string {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(num)
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'evaluated':
      return 'bg-green-500/10 text-green-600 dark:text-green-400'
    case 'evaluating':
      return 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400'
    case 'pending':
      return 'bg-gray-500/10 text-gray-600 dark:text-gray-400'
    case 'archived':
      return 'bg-gray-500/10 text-gray-500 dark:text-gray-500'
    default:
      return 'bg-gray-500/10 text-gray-600 dark:text-gray-400'
  }
}

export function getDamageSeverityColor(severity?: string): string {
  switch (severity) {
    case 'critical':
      return 'bg-red-500/10 text-red-600 dark:text-red-400'
    case 'high':
      return 'bg-orange-500/10 text-orange-600 dark:text-orange-400'
    case 'medium':
      return 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400'
    case 'low':
      return 'bg-green-500/10 text-green-600 dark:text-green-400'
    default:
      return 'bg-gray-500/10 text-gray-600 dark:text-gray-400'
  }
}

/**
 * Format relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(date: string | Date): string {
  const now = new Date()
  const then = typeof date === 'string' ? new Date(date) : date
  const seconds = Math.floor((now.getTime() - then.getTime()) / 1000)
  
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`
  
  return formatDate(then)
}

/**
 * Format bytes to human readable string
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

/**
 * Get condition score color class
 */
export function getConditionColor(score: number | null | undefined): string {
  if (score === null || score === undefined) return 'text-muted-foreground'
  if (score >= 80) return 'text-emerald-500'
  if (score >= 60) return 'text-lime-500'
  if (score >= 40) return 'text-yellow-500'
  if (score >= 20) return 'text-orange-500'
  return 'text-red-500'
}

/**
 * Get condition score background class
 */
export function getConditionBgColor(score: number | null | undefined): string {
  if (score === null || score === undefined) return 'bg-muted'
  if (score >= 80) return 'bg-emerald-500/10'
  if (score >= 60) return 'bg-lime-500/10'
  if (score >= 40) return 'bg-yellow-500/10'
  if (score >= 20) return 'bg-orange-500/10'
  return 'bg-red-500/10'
}

/**
 * Get tier badge color
 */
export function getTierColor(tier?: string): { bg: string; text: string } {
  switch (tier) {
    case 'premium':
      return { bg: 'bg-amber-100 dark:bg-amber-950/50', text: 'text-amber-700 dark:text-amber-400' }
    case 'high':
      return { bg: 'bg-purple-100 dark:bg-purple-950/50', text: 'text-purple-700 dark:text-purple-400' }
    default:
      return { bg: 'bg-slate-100 dark:bg-slate-800', text: 'text-slate-600 dark:text-slate-400' }
  }
}

/**
 * Safely extract error message from error object
 */
export function getErrorMessage(error: any, fallback: string = 'An error occurred'): string {
  const detail = error?.response?.data?.detail
  
  if (typeof detail === 'string') return detail
  
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (typeof item?.msg === 'string') return item.msg
        return JSON.stringify(item)
      })
      .filter(Boolean)
      .join(' ') || fallback
  }
  
  if (error?.response?.data?.message) return error.response.data.message
  if (error?.message) return error.message
  
  return fallback
}

