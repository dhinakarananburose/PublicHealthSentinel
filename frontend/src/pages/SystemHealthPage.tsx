import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { formatDateTime, formatNumber } from '@/lib/utils'
import {
  Activity,
  CheckCircle2,
  Cpu,
  Database,
  FileText,
  HeartPulse,
  RefreshCw,
  Server,
  Shield,
  Zap,
} from 'lucide-react'

export const SystemHealthPage: React.FC = () => {
  const [probeLatency, setProbeLatency] = useState<number | null>(null)

  const healthQuery = useQuery({
    queryKey: ['system_health_telemetry'],
    queryFn: async () => {
      const start = performance.now()
      const res = await api.getHealth()
      const end = performance.now()
      setProbeLatency(Math.round(end - start))
      return res
    },
    refetchInterval: 10000, // Probe every 10 seconds
  })

  // Surveillance counts
  const surveillanceQuery = useQuery({
    queryKey: ['health_counts_surveillance'],
    queryFn: () => api.getSurveillance({ page_size: 1 }),
  })

  // Mobility counts
  const mobilityQuery = useQuery({
    queryKey: ['health_counts_mobility'],
    queryFn: () => api.getMobility({ page_size: 1 }),
  })

  // Anomaly counts
  const anomaliesQuery = useQuery({
    queryKey: ['health_counts_anomalies'],
    queryFn: () => api.getAnomalies({ page_size: 1 }),
  })

  // Document counts
  const documentsQuery = useQuery({
    queryKey: ['health_counts_documents'],
    queryFn: () => api.listDocuments({ page_size: 1 }),
  })

  const refetchAll = () => {
    healthQuery.refetch()
    surveillanceQuery.refetch()
    mobilityQuery.refetch()
    anomaliesQuery.refetch()
    documentsQuery.refetch()
  }

  const isHealthy = healthQuery.data?.status === 'healthy' && healthQuery.data?.database_connected

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <HeartPulse className="w-4 h-4 text-emerald-400" />
              Service Health & Telemetry Diagnostics
            </CardTitle>
            <CardDescription>
              Real-time health probes, database connection validation, and table inventory telemetry.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={refetchAll}
              isLoading={healthQuery.isFetching}
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${healthQuery.isFetching ? 'animate-spin' : ''}`} />}
            >
              Probe Now
            </Button>
          </div>
        </CardHeader>
      </Card>

      {/* Main Status Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* API Status */}
        <Card>
          <CardContent className="p-5 flex items-start justify-between">
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                FastAPI Gateway Status
              </p>
              <div className="flex items-center gap-2 mt-1">
                <span
                  className={`w-2.5 h-2.5 rounded-full ${
                    isHealthy ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
                  }`}
                />
                <h3 className="text-xl font-bold font-mono text-slate-100">
                  {healthQuery.isLoading
                    ? 'Probing...'
                    : healthQuery.data?.status.toUpperCase() || 'OFFLINE'}
                </h3>
              </div>
              <p className="text-[11px] text-slate-400 mt-1 font-mono">
                Port: 8000 • Endpoint: /health
              </p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-navy-800 border border-navy-700 flex items-center justify-center text-cyan-400 shadow-inner">
              <Server className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>

        {/* Database Connectivity */}
        <Card>
          <CardContent className="p-5 flex items-start justify-between">
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                Relational Database
              </p>
              <div className="flex items-center gap-2 mt-1">
                <span
                  className={`w-2.5 h-2.5 rounded-full ${
                    healthQuery.data?.database_connected ? 'bg-emerald-400' : 'bg-rose-400'
                  }`}
                />
                <h3 className="text-xl font-bold font-mono text-slate-100">
                  {healthQuery.data?.database_connected ? 'CONNECTED' : 'UNREACHABLE'}
                </h3>
              </div>
              <p className="text-[11px] text-slate-400 mt-1 font-mono">
                Engine: SQLite / PostgreSQL Ready
              </p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-navy-800 border border-navy-700 flex items-center justify-center text-teal-400 shadow-inner">
              <Database className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>

        {/* Telemetry Probe Latency */}
        <Card>
          <CardContent className="p-5 flex items-start justify-between">
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                Round-Trip Latency
              </p>
              <h3 className="text-xl font-bold font-mono text-cyan-400 mt-1">
                {probeLatency !== null ? `${probeLatency} ms` : '—'}
              </h3>
              <p className="text-[11px] text-slate-400 mt-1">
                Live internal probe via fetch API
              </p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-navy-800 border border-navy-700 flex items-center justify-center text-amber-400 shadow-inner">
              <Zap className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Database Inventory Metrics */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Database className="w-4 h-4 text-cyan-400" />
            Database Entity Inventory & Record Counts
          </CardTitle>
          <CardDescription>
            Live counts across validated tables in the primary surveillance store.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
            {/* Surveillance table */}
            <div className="p-4 rounded-xl bg-navy-950/70 border border-navy-800">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-mono">surveillance_observations</span>
                <Activity className="w-4 h-4 text-cyan-400" />
              </div>
              <p className="text-2xl font-bold text-slate-100 font-mono mt-2">
                {formatNumber(surveillanceQuery.data?.total)}
              </p>
              <span className="text-[11px] text-slate-400 block mt-1">
                Clinical syndromic reports
              </span>
            </div>

            {/* Mobility table */}
            <div className="p-4 rounded-xl bg-navy-950/70 border border-navy-800">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-mono">mobility_indicators</span>
                <Activity className="w-4 h-4 text-teal-400" />
              </div>
              <p className="text-2xl font-bold text-slate-100 font-mono mt-2">
                {formatNumber(mobilityQuery.data?.total)}
              </p>
              <span className="text-[11px] text-slate-400 block mt-1">
                Aggregated transit shifts
              </span>
            </div>

            {/* Anomaly table */}
            <div className="p-4 rounded-xl bg-navy-950/70 border border-navy-800">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-mono">anomaly_detection_results</span>
                <Activity className="w-4 h-4 text-rose-400" />
              </div>
              <p className="text-2xl font-bold text-slate-100 font-mono mt-2">
                {formatNumber(anomaliesQuery.data?.total)}
              </p>
              <span className="text-[11px] text-slate-400 block mt-1">
                Evaluated baseline scores
              </span>
            </div>

            {/* Documents table */}
            <div className="p-4 rounded-xl bg-navy-950/70 border border-navy-800">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-mono">document_metadata</span>
                <FileText className="w-4 h-4 text-amber-400" />
              </div>
              <p className="text-2xl font-bold text-slate-100 font-mono mt-2">
                {formatNumber(documentsQuery.data?.total)}
              </p>
              <span className="text-[11px] text-slate-400 block mt-1">
                Reference evidence documents
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Environment Specification */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Cpu className="w-4 h-4 text-cyan-400" />
            Runtime Environment & Compliance Metadata
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
            <div className="p-3 rounded-lg bg-navy-950 border border-navy-800">
              <span className="text-slate-400 text-[11px] block">App Identifier</span>
              <span className="text-slate-200 font-semibold mt-1 block">
                {healthQuery.data?.app_name || 'PublicHealthSentinel'}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-navy-950 border border-navy-800">
              <span className="text-slate-400 text-[11px] block">API Semantic Version</span>
              <span className="text-cyan-400 font-semibold mt-1 block">
                {healthQuery.data?.api_version || 'v1'}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-navy-950 border border-navy-800">
              <span className="text-slate-400 text-[11px] block">Runtime Mode</span>
              <span className="text-slate-200 font-semibold mt-1 block">
                {healthQuery.data?.environment || 'development'}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-navy-950 border border-navy-800">
              <span className="text-slate-400 text-[11px] block">Backend Server Time</span>
              <span className="text-slate-200 text-[11px] mt-1 block truncate">
                {healthQuery.data?.timestamp ? formatDateTime(healthQuery.data.timestamp) : '—'}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
