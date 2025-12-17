'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import { 
  Page, 
  PageHeader, 
  Section,
  StatGrid, 
  StatBox, 
  DataList, 
  DataListItem,
  MiniBarChart,
  MiniDonut,
  Empty,
  Loading,
  Select,
  IconButton,
} from '@/components/ui'
import { 
  Activity,
  RefreshCw,
  Zap,
  DollarSign,
  Database,
  Clock,
  TrendingUp,
  Globe,
  MapPin,
  Eye,
  Layers,
  Building,
  Search,
  Cpu,
  Server,
  BarChart3,
  PieChart
} from 'lucide-react'

interface UsageSummary {
  period_days: number
  total_requests: number
  total_cost_usd: number
  total_bytes_processed: number
  by_action: Record<string, { count: number; total_cost: number; bytes_processed: number }>
  by_resource: Record<string, { count: number; total_cost: number }>
}

interface DailyUsage {
  date: string
  request_count: number
  total_cost_usd: number
  bytes_processed: number
}

const RESOURCE_META: Record<string, { label: string; icon: typeof Globe }> = {
  google_places: { label: 'Places API', icon: Building },
  google_maps: { label: 'Static Maps', icon: MapPin },
  roboflow: { label: 'CV Inference', icon: Eye },
  inrix: { label: 'INRIX', icon: Layers },
  here: { label: 'HERE', icon: Globe },
  osm: { label: 'OSM', icon: Globe },
  discovery_pipeline: { label: 'Discovery', icon: Search },
}

const ACTION_META: Record<string, { label: string; icon: typeof Cpu }> = {
  discovery: { label: 'Discovery', icon: Search },
  cv_evaluation: { label: 'CV Analysis', icon: Eye },
  api_call: { label: 'API Calls', icon: Server },
}

const PERIOD_OPTIONS = [
  { value: 7, label: '7d' },
  { value: 14, label: '14d' },
  { value: 30, label: '30d' },
  { value: 90, label: '90d' },
]

export default function UsagePage() {
  const [days, setDays] = useState(30)

  const { data: summary, isLoading, refetch } = useQuery<UsageSummary>({
    queryKey: ['usage-summary', days],
    queryFn: async () => (await apiClient.get(`/usage/summary?days=${days}`)).data,
  })

  const { data: daily } = useQuery<DailyUsage[]>({
    queryKey: ['usage-daily', Math.min(days, 30)],
    queryFn: async () => (await apiClient.get(`/usage/daily?days=${Math.min(days, 30)}`)).data,
  })

  const formatCost = (n: number) => n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`
  const formatBytes = (b: number) => b === 0 ? '0 B' : `${(b / 1024 / 1024).toFixed(1)} MB`

  // Prepare chart data
  const barData = daily?.slice(-14).map(d => ({
    value: d.request_count,
    label: new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  })) || []

  const donutData = summary ? Object.entries(summary.by_action).map(([key, val]) => ({
    name: ACTION_META[key]?.label || key,
    value: val.count
  })) : []

  const totalByAction = donutData.reduce((sum, d) => sum + d.value, 0)

  return (
    <Page size="md">
      <PageHeader
        title="Usage"
        description="API consumption and costs"
        actions={
          <>
            <Select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              options={PERIOD_OPTIONS}
            />
            <IconButton
              icon={<RefreshCw className="h-3.5 w-3.5 text-muted-foreground" />}
              onClick={() => refetch()}
              loading={isLoading}
            />
          </>
        }
      />

      {isLoading ? (
        <Loading />
      ) : !summary || summary.total_requests === 0 ? (
        <Empty
          icon={Activity}
          title="No usage data"
          description="Run a discovery to see metrics"
        />
      ) : (
        <div className="space-y-8">
          {/* Stats */}
          <StatGrid columns={4}>
            <StatBox 
              label="Requests" 
              value={summary.total_requests.toLocaleString()} 
              icon={Zap}
            />
            <StatBox 
              label="Cost" 
              value={formatCost(summary.total_cost_usd)} 
              sub={`${formatCost(summary.total_cost_usd / days)}/day`}
              icon={DollarSign}
            />
            <StatBox 
              label="Data" 
              value={formatBytes(summary.total_bytes_processed)} 
              icon={Database}
            />
            <StatBox 
              label="Period" 
              value={`${days}d`} 
              icon={Clock}
            />
          </StatGrid>

          {/* Charts Row */}
          <div className="grid grid-cols-3 gap-6">
            {/* Bar Chart */}
            <div className="col-span-2 border border-border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Daily Requests</span>
              </div>
              {barData.length > 0 ? (
                <MiniBarChart data={barData} height={140} />
              ) : (
                <div className="h-[140px] flex items-center justify-center text-xs text-muted-foreground">No data</div>
              )}
            </div>

            {/* Donut Chart */}
            <div className="border border-border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-4">
                <PieChart className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">By Type</span>
              </div>
              <div className="flex items-center gap-4">
                <MiniDonut data={donutData} size={80} />
                <div className="space-y-2 flex-1">
                  {donutData.map((d, i) => (
                    <div key={d.name} className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">{d.name}</span>
                      <span className="font-medium tabular-nums">{((d.value / totalByAction) * 100).toFixed(0)}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Breakdown Lists */}
          <div className="grid grid-cols-2 gap-6">
            <Section title="By Action">
              <DataList>
                {Object.entries(summary.by_action).map(([action, data]) => {
                  const meta = ACTION_META[action] || { label: action, icon: Cpu }
                  return (
                    <DataListItem
                      key={action}
                      icon={meta.icon}
                      label={meta.label}
                      value={data.count}
                      sub={formatCost(data.total_cost)}
                    />
                  )
                })}
              </DataList>
            </Section>

            <Section title="By Service">
              <DataList>
                {Object.entries(summary.by_resource)
                  .sort((a, b) => b[1].count - a[1].count)
                  .slice(0, 6)
                  .map(([resource, data]) => {
                    const meta = RESOURCE_META[resource] || { label: resource, icon: Globe }
                    return (
                      <DataListItem
                        key={resource}
                        icon={meta.icon}
                        label={meta.label}
                        value={data.count}
                        sub={formatCost(data.total_cost)}
                      />
                    )
                  })}
              </DataList>
            </Section>
          </div>

          {/* Footer */}
          <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
            <TrendingUp className="h-3 w-3" />
            Costs are estimates. Google Places ~$17/1K, Maps ~$2/1K, Roboflow ~$1/1K.
          </p>
        </div>
      )}
    </Page>
  )
}
