'use client'

import { 
  AreaChart, 
  Area, 
  BarChart as RechartsBarChart,
  Bar,
  XAxis, 
  YAxis, 
  Tooltip, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts'
import { cn } from '@/lib/utils'

/**
 * AreaSparkline - Minimal area chart without axes
 */
interface AreaSparklineProps {
  data: { value: number; label?: string }[]
  height?: number
  className?: string
  color?: string
}

export function AreaSparkline({ data, height = 80, className, color = 'hsl(var(--foreground))' }: AreaSparklineProps) {
  const chartData = data.map((d, i) => ({ name: d.label || i, value: d.value }))
  
  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.15} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area 
            type="monotone" 
            dataKey="value" 
            stroke={color}
            strokeWidth={1.5}
            fill="url(#areaGradient)" 
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

/**
 * MiniBarChart - Compact bar chart with minimal styling
 */
interface MiniBarChartProps {
  data: { value: number; label: string }[]
  height?: number
  className?: string
}

export function MiniBarChart({ data, height = 120, className }: MiniBarChartProps) {
  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RechartsBarChart data={data} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
          <XAxis 
            dataKey="label" 
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
            interval="preserveStartEnd"
          />
          <Tooltip 
            cursor={{ fill: 'hsl(var(--muted))', opacity: 0.5 }}
            contentStyle={{ 
              background: 'hsl(var(--card))', 
              border: '1px solid hsl(var(--border))',
              borderRadius: 6,
              fontSize: 12,
              padding: '6px 10px'
            }}
            labelStyle={{ color: 'hsl(var(--foreground))', fontWeight: 500 }}
          />
          <Bar 
            dataKey="value" 
            fill="hsl(var(--foreground))"
            radius={[2, 2, 0, 0]}
            maxBarSize={24}
          />
        </RechartsBarChart>
      </ResponsiveContainer>
    </div>
  )
}

/**
 * MiniDonut - Small donut/pie chart
 */
interface MiniDonutProps {
  data: { name: string; value: number; color?: string }[]
  size?: number
  className?: string
}

const COLORS = [
  'hsl(var(--foreground))',
  'hsl(var(--muted-foreground))',
  'hsl(220 9% 70%)',
  'hsl(220 9% 80%)',
  'hsl(220 9% 90%)',
]

export function MiniDonut({ data, size = 64, className }: MiniDonutProps) {
  return (
    <div className={cn('flex-shrink-0', className)} style={{ width: size, height: size }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={size * 0.3}
            outerRadius={size * 0.45}
            paddingAngle={2}
            dataKey="value"
            strokeWidth={0}
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color || COLORS[index % COLORS.length]} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

/**
 * TrendLine - Tiny inline sparkline
 */
interface TrendLineProps {
  data: number[]
  width?: number
  height?: number
  color?: string
  className?: string
}

export function TrendLine({ data, width = 60, height = 20, color = 'hsl(var(--foreground))', className }: TrendLineProps) {
  const chartData = data.map((v, i) => ({ value: v }))
  
  return (
    <div className={cn('inline-flex', className)} style={{ width, height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 2, right: 0, left: 0, bottom: 2 }}>
          <Area 
            type="monotone" 
            dataKey="value" 
            stroke={color}
            strokeWidth={1}
            fill="none"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}


