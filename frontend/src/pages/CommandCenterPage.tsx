import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { SurveillanceTrendChart } from '@/components/charts/SurveillanceTrendChart'
import { AnomalyScoreChart } from '@/components/charts/AnomalyScoreChart'
import { Modal } from '@/components/common/Modal'
import { formatNumber, formatScore } from '@/lib/utils'
import type { AnomalyResult } from '@/types/api'
import type { NavItemKey } from '@/components/layout/Sidebar'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Database,
  Eye,
  Filter,
  MapPin,
  RefreshCw,
  TrendingUp,
} from 'lucide-react'

interface CommandCenterPageProps {
  onNavigate: (route: NavItemKey) => void
}

export const CommandCenterPage: React.FC<CommandCenterPageProps> = ({ onNavigate }) => {
  const [selectedRegion, setSelectedRegion] = useState<string>('')
  const [selectedSyndrome, setSelectedSyndrome] = useState<string>('')
  const [selectedAnomaly, setSelectedAnomaly] = useState<AnomalyResult | null>(null)

  // Fetch surveillance records for charts and KPIs
  const surveillanceQuery = useQuery({
    queryKey: ['surveillance', { region: selectedRegion, syndrome: selectedSyndrome, pageSize: 200 }],
    queryFn: () =>
      api.getSurveillance({
        region_id: selectedRegion || undefined,
        syndrome: selectedSyndrome || undefined,
        page_size: 200,
      }),
  })

  // Fetch anomaly records (flagged anomalies)
  const anomaliesQuery = useQuery({
    queryKey: ['anomalies_flagged', { region: selectedRegion, syndrome: selectedSyndrome }],
    queryFn: () =>
      api.getAnomalies({
        region_id: selectedRegion || undefined,
        syndrome: selectedSyndrome || undefined,
        is_anomaly: true,
        page_size: 50,
      }),
  })

  // Fetch all recent anomaly evaluations
  const evaluationsQuery = useQuery({
    queryKey: ['anomalies_all', { region: selectedRegion, syndrome: selectedSyndrome }],
    queryFn: () =>
      api.getAnomalies({
        region_id: selectedRegion || undefined,
        syndrome: selectedSyndrome || undefined,
        page_size: 100,
      }),
  })

  // System Health
  const healthQuery = useQuery({
    queryKey: ['system_health'],
    queryFn: () => api.getHealth(),
  })

  const isLoading =
    surveillanceQuery.isLoading || anomaliesQuery.isLoading || evaluationsQuery.isLoading
  const isError = surveillanceQuery.isError || anomaliesQuery.isError

  const refetchAll = () => {
    surveillanceQuery.refetch()
    anomaliesQuery.refetch()
    evaluationsQuery.refetch()
    healthQuery.refetch()
  }

  // Calculate high-level summary KPIs
  const totalAnomalies = anomaliesQuery.data?.total ?? 0
  const totalObservations = surveillanceQuery.data?.total ?? 0
  const uniqueRegions = Array.from(
    new Set((surveillanceQuery.data?.items || []).map((i) => i.region_id))
  )
  const uniqueSyndromes = Array.from(
    new Set((surveillanceQuery.data?.items || []).map((i) => i.syndrome))
  )

  return (
    <div className="space-y-6">
      {/* Filters & Actions Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-navy-900/60 border border-navy-800">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Filter className="w-3.5 h-3.5 text-cyan-400" />
            <span>Scope Filter:</span>
          </div>

          <select
            value={selectedRegion}
            onChange={(e) => setSelectedRegion(e.target.value)}
            className="bg-navy-950 border border-navy-700 text-slate-200 text-xs rounded-lg px-2.5 py-1.5 focus:border-cyan-500 focus:outline-none"
          >
            <option value="">All Jurisdictions (5 Regions)</option>
            <option value="REGION_A">Region A (Metro Core)</option>
            <option value="REGION_B">Region B (North County)</option>
            <option value="REGION_C">Region C (Eastern Valley)</option>
            <option value="REGION_D">Region D (Coastal District)</option>
            <option value="REGION_E">Region E (Southern Plains)</option>
          </select>

          <select
            value={selectedSyndrome}
            onChange={(e) => setSelectedSyndrome(e.target.value)}
            className="bg-navy-950 border border-navy-700 text-slate-200 text-xs rounded-lg px-2.5 py-1.5 focus:border-cyan-500 focus:outline-none"
          >
            <option value="">All Syndromes (3 Clusters)</option>
            <option value="Respiratory">Respiratory</option>
            <option value="Gastrointestinal">Gastrointestinal</option>
            <option value="Febrile">Febrile</option>
          </select>

          {(selectedRegion || selectedSyndrome) && (
            <button
              onClick={() => {
                setSelectedRegion('')
                setSelectedSyndrome('')
              }}
              className="text-xs text-cyan-400 hover:text-cyan-300 underline underline-offset-2 ml-1"
            >
              Reset Filters
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="secondary"
            onClick={refetchAll}
            isLoading={isLoading}
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />}
          >
            Refresh Data
          </Button>
          <Button
            size="sm"
            variant="teal"
            onClick={() => onNavigate('pipeline')}
            leftIcon={<TrendingUp className="w-3.5 h-3.5" />}
          >
            Execute Detection
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Active Anomalies */}
        <Card
          className="cursor-pointer hover:border-rose-500/50 group"
          onClick={() => onNavigate('anomalies')}
        >
          <CardContent className="p-5 flex items-start justify-between">
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                Flagged Surge Anomalies
              </p>
              <h3 className="text-2xl font-bold text-rose-400 mt-1 font-mono">
                {isLoading ? '...' : formatNumber(totalAnomalies)}
              </h3>
              <p className="text-[11px] text-slate-400 mt-1 flex items-center gap-1 group-hover:text-cyan-400 transition-colors">
                <span>Investigate anomalies</span>
                <ArrowRight className="w-3 h-3" />
              </p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-rose-950/60 border border-rose-800/80 flex items-center justify-center text-rose-400 shadow-inner">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>

        {/* Card 2: Monitored Observations */}
        <Card
          className="cursor-pointer hover:border-cyan-500/50 group"
          onClick={() => onNavigate('surveillance')}
        >
          <CardContent className="p-5 flex items-start justify-between">
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                Surveillance Records
              </p>
              <h3 className="text-2xl font-bold text-cyan-400 mt-1 font-mono">
                {isLoading ? '...' : formatNumber(totalObservations)}
              </h3>
              <p className="text-[11px] text-slate-400 mt-1 flex items-center gap-1 group-hover:text-cyan-400 transition-colors">
                <span>Explore observations</span>
                <ArrowRight className="w-3 h-3" />
              </p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-cyan-950/60 border border-cyan-800/80 flex items-center justify-center text-cyan-400 shadow-inner">
              <Activity className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>

        {/* Card 3: Jurisdictions & Syndromes */}
        <Card className="hover:border-navy-700">
          <CardContent className="p-5 flex items-start justify-between">
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                Active Monitoring Matrix
              </p>
              <h3 className="text-2xl font-bold text-slate-100 mt-1 font-mono">
                {selectedRegion ? 1 : uniqueRegions.length || 5}{' '}
                <span className="text-xs font-normal text-slate-400">Regions</span> /{' '}
                {selectedSyndrome ? 1 : uniqueSyndromes.length || 3}{' '}
                <span className="text-xs font-normal text-slate-400">Syndromes</span>
              </h3>
              <p className="text-[11px] text-slate-400 mt-1">
                {selectedRegion || selectedSyndrome ? 'Filtered monitoring subset' : 'Complete surveillance scope'}
              </p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-navy-800 border border-navy-700 flex items-center justify-center text-slate-300 shadow-inner">
              <MapPin className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>

        {/* Card 4: Database Health */}
        <Card
          className="cursor-pointer hover:border-teal-500/50 group"
          onClick={() => onNavigate('health')}
        >
          <CardContent className="p-5 flex items-start justify-between">
            <div>
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                Database Engine Status
              </p>
              <div className="flex items-center gap-2 mt-1">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <h3 className="text-lg font-bold text-emerald-400 font-mono">
                  {healthQuery.data?.database_connected ? 'CONNECTED' : 'STANDBY'}
                </h3>
              </div>
              <p className="text-[11px] text-slate-400 mt-1 flex items-center gap-1 group-hover:text-teal-400 transition-colors">
                <span>View system diagnostics</span>
                <ArrowRight className="w-3 h-3" />
              </p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-teal-950/60 border border-teal-800/80 flex items-center justify-center text-teal-400 shadow-inner">
              <Database className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Charts Row */}
      {isError ? (
        <ErrorState
          message="Failed to connect to surveillance backend API. Please ensure FastAPI server is running."
          onRetry={refetchAll}
        />
      ) : isLoading ? (
        <Card>
          <CardContent>
            <LoadingSpinner text="Rendering syndromic surveillance time series..." />
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Surveillance Trend Chart */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <div>
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-cyan-400" />
                  Syndromic Surveillance Volume by Syndrome Cluster
                </CardTitle>
                <CardDescription>
                  Aggregated daily clinical report counts over time across monitored jurisdictions.
                </CardDescription>
              </div>
              <Badge variant="info">Interactive Timeline</Badge>
            </CardHeader>
            <CardContent className="pt-2">
              <SurveillanceTrendChart
                data={surveillanceQuery.data?.items || []}
                height={320}
              />
            </CardContent>
          </Card>

          {/* Anomaly Distribution & Anomaly Score Scatter */}
          <Card>
            <CardHeader>
              <div>
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                  Anomaly Evaluation Scores
                </CardTitle>
                <CardDescription>
                  Statistical deviation scores against baseline threshold (3.0σ).
                </CardDescription>
              </div>
              <Badge variant="anomaly">
                {anomaliesQuery.data?.total || 0} Surges
              </Badge>
            </CardHeader>
            <CardContent className="pt-2">
              <AnomalyScoreChart
                data={evaluationsQuery.data?.items || []}
                height={320}
                onAnomalyClick={(a) => setSelectedAnomaly(a)}
              />
            </CardContent>
          </Card>
        </div>
      )}

      {/* Recent Flagged Anomalies Table */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400" />
              Latest Flagged Anomaly Surges
            </CardTitle>
            <CardDescription>
              Statistical threshold exceedances requiring epidemiological review.
            </CardDescription>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onNavigate('anomalies')}
            rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
          >
            View All ({totalAnomalies})
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-navy-950/70 border-b border-navy-800 text-slate-400 uppercase tracking-wider font-mono text-[11px]">
                <tr>
                  <th className="px-5 py-3 font-semibold">Date</th>
                  <th className="px-4 py-3 font-semibold">Jurisdiction</th>
                  <th className="px-4 py-3 font-semibold">Syndrome</th>
                  <th className="px-4 py-3 font-semibold">Observed / Expected</th>
                  <th className="px-4 py-3 font-semibold">Anomaly Score</th>
                  <th className="px-4 py-3 font-semibold">Algorithm</th>
                  <th className="px-5 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-800/60 text-slate-200">
                {anomaliesQuery.data?.items && anomaliesQuery.data.items.length > 0 ? (
                  anomaliesQuery.data.items.slice(0, 5).map((a) => (
                    <tr
                      key={a.id}
                      className="hover:bg-navy-850/60 transition-colors cursor-pointer"
                      onClick={() => setSelectedAnomaly(a)}
                    >
                      <td className="px-5 py-3 font-mono font-medium text-slate-300">
                        {a.observation_date}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline">{a.region_id}</Badge>
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-200">
                        {a.syndrome}
                      </td>
                      <td className="px-4 py-3 font-mono">
                        <span className="text-rose-400 font-semibold">{a.observed_count}</span>{' '}
                        <span className="text-slate-500">/</span>{' '}
                        <span className="text-slate-400">
                          {a.expected_baseline ? formatScore(a.expected_baseline) : '—'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="danger" size="sm" className="font-mono">
                          {formatScore(a.anomaly_score)}σ
                        </Badge>
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-400">
                        {a.detection_method}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setSelectedAnomaly(a)
                          }}
                          className="text-cyan-400 hover:text-cyan-300 p-1 rounded hover:bg-navy-800 focus:outline-none focus:ring-1 focus:ring-cyan-400"
                          title="Inspect Details"
                          aria-label={`Inspect details for anomaly ${a.id} in ${a.region_id}`}
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="px-6 py-8 text-center text-slate-400">
                      No anomaly surges flagged under current scope filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Anomaly Inspection Modal */}
      {selectedAnomaly && (
        <Modal
          isOpen={!!selectedAnomaly}
          onClose={() => setSelectedAnomaly(null)}
          title={`Statistical Surge Anomaly #${selectedAnomaly.id}`}
          subtitle={`${selectedAnomaly.region_id} • ${selectedAnomaly.syndrome} • ${selectedAnomaly.observation_date}`}
          maxWidth="lg"
        >
          <div className="space-y-4">
            <div className="p-3.5 rounded-lg bg-rose-950/40 border border-rose-800/60 text-xs text-rose-300 flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <strong>Statistical Flag Disclaimer:</strong>
                <p className="mt-1 text-rose-300/90 leading-relaxed">
                  {selectedAnomaly.interpretation_disclaimer}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800">
                <span className="text-slate-400">Observed Report Count:</span>
                <p className="text-lg font-bold text-rose-400 font-mono mt-0.5">
                  {selectedAnomaly.observed_count}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800">
                <span className="text-slate-400">Expected Baseline:</span>
                <p className="text-lg font-bold text-slate-200 font-mono mt-0.5">
                  {selectedAnomaly.expected_baseline
                    ? formatScore(selectedAnomaly.expected_baseline)
                    : '—'}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800">
                <span className="text-slate-400">Anomaly Deviation Score:</span>
                <p className="text-lg font-bold text-cyan-400 font-mono mt-0.5">
                  {formatScore(selectedAnomaly.anomaly_score)}σ
                </p>
              </div>
              <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800">
                <span className="text-slate-400">Detection Threshold:</span>
                <p className="text-lg font-bold text-slate-200 font-mono mt-0.5">
                  {selectedAnomaly.detection_threshold}σ
                </p>
              </div>
            </div>

            <div className="text-xs space-y-1.5 pt-2 border-t border-navy-800">
              <div className="flex justify-between py-1 border-b border-navy-800/40">
                <span className="text-slate-400">Algorithm:</span>
                <span className="font-mono text-slate-200">{selectedAnomaly.detection_method}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-navy-800/40">
                <span className="text-slate-400">Historical History Count:</span>
                <span className="font-mono text-slate-200">{selectedAnomaly.history_count} days</span>
              </div>
              <div className="flex justify-between py-1 border-b border-navy-800/40">
                <span className="text-slate-400">Evaluation Status:</span>
                <Badge variant="success" size="sm">{selectedAnomaly.evaluation_status}</Badge>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-400">Data Status:</span>
                <span className="font-mono text-cyan-400">{selectedAnomaly.data_status}</span>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSelectedAnomaly(null)}
              >
                Close
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  setSelectedAnomaly(null)
                  onNavigate('anomalies')
                }}
              >
                Open in Anomaly Intelligence
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
