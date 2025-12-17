/**
 * SidewalkSafety Design Tokens
 * Brand colors and design system constants
 */

// Official SidewalkSafety brand colors
export const SIDEWALKSAFETY_BRAND = {
  orange: '#F97316',  // Primary orange
  orangeDark: '#EA580C',
  slate: '#0F172A',   // Dark slate
  gradient: {
    start: '#F97316',  // Orange
    end: '#DC2626',    // Red-orange
  },
} as const

export const designTokens = {
  // Brand colors
  colors: {
    brand: {
      primary: SIDEWALKSAFETY_BRAND.orange,
      primaryDark: SIDEWALKSAFETY_BRAND.orangeDark,
      gradient: `linear-gradient(135deg, ${SIDEWALKSAFETY_BRAND.gradient.start} 0%, ${SIDEWALKSAFETY_BRAND.gradient.end} 100%)`,
    },
    
    // Semantic colors
    semantic: {
      success: '#10B981',
      warning: '#F59E0B',
      error: '#EF4444',
      info: '#3B82F6',
    },
    
    // Condition score colors
    condition: {
      excellent: '#10B981',  // 80-100
      good: '#84CC16',       // 60-79
      fair: '#F59E0B',       // 40-59
      poor: '#F97316',       // 20-39
      critical: '#EF4444',   // 0-19
    },
    
    // Business tier colors
    tier: {
      premium: '#F59E0B',    // Amber
      high: '#8B5CF6',       // Purple
      standard: '#64748B',   // Slate
    },
  },

  // Typography
  typography: {
    fontFamily: {
      sans: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      mono: 'JetBrains Mono, Menlo, Monaco, Consolas, monospace',
    },
    
    fontSize: {
      xs: '0.75rem',     // 12px
      sm: '0.875rem',    // 14px
      base: '1rem',      // 16px
      lg: '1.125rem',    // 18px
      xl: '1.25rem',     // 20px
      '2xl': '1.5rem',   // 24px
      '3xl': '1.875rem', // 30px
    },
    
    fontWeight: {
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
  },

  // Spacing scale (4px base)
  spacing: {
    0: '0',
    1: '0.25rem',   // 4px
    2: '0.5rem',    // 8px
    3: '0.75rem',   // 12px
    4: '1rem',      // 16px
    5: '1.25rem',   // 20px
    6: '1.5rem',    // 24px
    8: '2rem',      // 32px
  },

  // Border radius
  radius: {
    sm: '0.375rem',   // 6px
    md: '0.5rem',     // 8px
    lg: '0.75rem',    // 12px
    xl: '1rem',       // 16px
    '2xl': '1.5rem',  // 24px
    full: '9999px',
  },
} as const

export type DesignTokens = typeof designTokens

// Helper to get condition color
export function getConditionColor(score: number): string {
  if (score >= 80) return designTokens.colors.condition.excellent
  if (score >= 60) return designTokens.colors.condition.good
  if (score >= 40) return designTokens.colors.condition.fair
  if (score >= 20) return designTokens.colors.condition.poor
  return designTokens.colors.condition.critical
}

// Helper to get condition label
export function getConditionLabel(score: number): string {
  if (score >= 80) return 'Excellent'
  if (score >= 60) return 'Good'
  if (score >= 40) return 'Fair'
  if (score >= 20) return 'Poor'
  return 'Critical'
}


