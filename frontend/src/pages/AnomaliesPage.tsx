import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Pagination } from '@/components/common/Pagination'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'
import { Modal } from '@/components/common/Modal'
import { formatNumber, formatScore } from '@/lib/utils'
import type { AnomalyResult } from '@/types/api'
import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  Filter,
  RefreshCw,
  Search,
  ShieldAlert,
  X,
} from 'lucide-react'

export const AnomaliesPage: React.FC = () => {
  const [page, setPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(25)
  const [regionFilter, setRegionFilter] = useState<string>('')
  const [syndromeFilter, setSyndromeFilter] = useState<string>('')
  const [methodFilter, setMethodFilter] = useState<string>('')
  const [isAnomalyFilter, setIsAnomalyFilter] = useState<string>('true') // default to flagged anomalies
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [selectedAnomaly, setSelectedAnomaly] = useState<AnomalyResult | null>(null)

  const isAnomalyParam =
    isAnomalyFilter === 'true' ? true : isAnomalyFilter === 'false' ? false : undefined

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: [
      'anomalies_intelligence',
      { page, pageSize, regionFilter, syndromeFilter, methodFilter, isAnomalyFilter, startDate, endDate },
    ],
    queryFn: () =>
      api.getAnomalies({
        page,
        page_size: pageSize,
        region_id: regionFilter || undefined,
        syndrome: syndromeFilter || undefined,
        method: methodFilter || undefined,
        is_anomaly: isAnomalyParam,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      }),
  })

  const resetFilters = () => {
    setRegionFilter('')
    setSyndromeFilter('')
    setMethodFilter('')
    setIsAnomalyFilter('true')
    setStartDate('')
    setEndDate('')
    setPage(1)
  }

  const hasActiveFilters = Boolean(
    regionFilter || syndromeFilter || methodFilter || isAnomalyFilter !== 'true' || startDate || endDate
  )

  return (
    <div className="space-y-6">
      {/* Scope and Filter Card */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-rose-400" />
              Statistical Anomaly Intelligence
            </CardTitle>
            <CardDescription>
              Evaluate baseline departures across surveillance time-series using Rolling MAD, EWMA, and Z-Score algorithms.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => refetch()}
              isLoading={isFetching}
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />}
            >
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3">
            {/* Anomaly Status */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Surge Status</label>
              <select
                value={isAnomalyFilter}
                onChange={(e) => {
                  setIsAnomalyFilter(e.target.value)
                  setPage(1)
                }}
                className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="true">⚠️ Confirmed Outliers Only</option>
                <option value="false">✓ Normal Baseline Evaluated</option>
                <option value="all">All Evaluations</option>
              </select>
            </div>

            {/* Algorithm */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Algorithm Method</label>
              <select
                value={methodFilter}
                onChange={(e) => {
                  setMethodFilter(e.target.value)
                  setPage(1)
                }}
                className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="">All Methods</option>
                <option value="rolling_mad">Rolling MAD (Robust)</option>
                <option value="ewma">EWMA (Smoothed)</option>
                <option value="zscore">Z-Score (Standardized)</option>
              </select>
            </div>

            {/* Region */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Jurisdiction</label>
              <select
                value={regionFilter}
                onChange={(e) => {
                  setRegionFilter(e.target.value)
                  setPage(1)
                }}
                className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="">All Jurisdictions</option>
                <option value="REGION_A">REGION_A</option>
                <option value="REGION_B">REGION_B</option>
                <option value="REGION_C">REGION_C</option>
                <option value="REGION_D">REGION_D</option>
                <option value="REGION_E">REGION_E</option>
              </select>
            </div>

            {/* Syndrome */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Syndrome Cluster</label>
              <select
                value={syndromeFilter}
                onChange={(e) => {
                  setSyndromeFilter(e.target.value)
                  setPage(1)
                }}
                className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="">All Syndromes</option>
                <option value="Respiratory">Respiratory</option>
                <option value="Gastrointestinal">Gastrointestinal</option>
                <option value="Febrile">Febrile</option>
              </select>
            </div>

            {/* Start Date */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">From Date</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => {
                  setStartDate(e.target.value)
                  setPage(1)
                }}
                className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-200 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* End Date */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">To Date</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => {
                  setEndDate(e.target.value)
                  setPage(1)
                }}
                className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-200 focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>

          {hasActiveFilters && (
            <div className="flex items-center justify-between pt-2 border-t border-navy-800 text-xs">
              <span className="text-slate-400">
                Filtered evaluation query: Showing {data?.total ?? 0} matching records.
              </span>
              <button
                onClick={resetFilters}
                className="text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-medium"
              >
                <X className="w-3.5 h-3.5" />
                Reset Scope Filters
              </button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Anomaly Results Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <LoadingSpinner text="Evaluating baseline departures from database..." />
          ) : isError ? (
            <div className="p-6">
              <ErrorState
                message={(error as any)?.message || 'Failed to query anomaly results.'}
                onRetry={() => refetch()}
              />
            </div>
          ) : !data || data.items.length === 0 ? (
            <div className="p-6">
              <EmptyState
                icon={<CheckCircle2 className="w-6 h-6 text-emerald-400" />}
                title="No anomalies match current scope"
                description="No statistical threshold exceedances were detected for the selected filters."
                actionLabel={hasActiveFilters ? 'Reset Filters' : undefined}
                onAction={resetFilters}
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-navy-950/70 border-b border-navy-800 text-slate-400 uppercase tracking-wider font-mono text-[11px]">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Date</th>
                    <th className="px-4 py-3 font-semibold">Status</th>
                    <th className="px-4 py-3 font-semibold">Jurisdiction</th>
                    <th className="px-4 py-3 font-semibold">Syndrome</th>
                    <th className="px-4 py-3 font-semibold">Observed</th>
                    <th className="px-4 py-3 font-semibold">Baseline Exp.</th>
                    <th className="px-4 py-3 font-semibold">Deviation Score</th>
                    <th className="px-4 py-3 font-semibold">Threshold</th>
                    <th className="px-4 py-3 font-semibold">Algorithm</th>
                    <th className="px-5 py-3 font-semibold text-right">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-navy-800/60 text-slate-200">
                  {data.items.map((anom) => (
                    <tr
                      key={anom.id}
                      onClick={() => setSelectedAnomaly(anom)}
                      className="hover:bg-navy-850/60 transition-colors cursor-pointer group"
                    >
                      <td className="px-5 py-3 font-mono font-medium text-slate-300">
                        {anom.observation_date}
                      </td>
                      <td className="px-4 py-3">
                        {anom.is_anomaly ? (
                          <Badge variant="danger" size="sm">
                            SURGE FLAG
                          </Badge>
                        ) : (
                          <Badge variant="outline" size="sm">
                            NORMAL
                          </Badge>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline">{anom.region_id}</Badge>
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-200">
                        {anom.syndrome}
                      </td>
                      <td className="px-4 py-3 font-mono font-semibold text-rose-400">
                        {anom.observed_count ?? '—'}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-400">
                        {anom.expected_baseline !== null ? formatScore(anom.expected_baseline) : '—'}
                      </td>
                      <td className="px-4 py-3 font-mono">
                        <span
                          className={`font-semibold ${
                            anom.is_anomaly ? 'text-rose-400' : 'text-slate-300'
                          }`}
                        >
                          {formatScore(anom.anomaly_score)}σ
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-400">
                        {anom.detection_threshold}σ
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-400 text-[11px]">
                        {anom.detection_method}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setSelectedAnomaly(anom)
                          }}
                          className="text-cyan-400 hover:text-cyan-300 p-1 rounded hover:bg-navy-800 focus:outline-none focus:ring-1 focus:ring-cyan-400"
                          title="Inspect Details"
                          aria-label={`Inspect details for anomaly ${anom.id} in ${anom.region_id}`}
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data && data.total > 0 && (
            <Pagination
              currentPage={page}
              totalPages={data.total_pages}
              totalItems={data.total}
              pageSize={pageSize}
              onPageChange={(newPage) => setPage(newPage)}
              onPageSizeChange={(newSize) => {
                setPageSize(newSize)
                setPage(1)
              }}
              disabled={isFetching}
            />
          )}
        </CardContent>
      </Card>

      {/* Anomaly Detail Modal */}
      {selectedAnomaly && (
        <Modal
          isOpen={!!selectedAnomaly}
          onClose={() => setSelectedAnomaly(null)}
          title={`Anomaly Result #${selectedAnomaly.id}`}
          subtitle={`${selectedAnomaly.region_id} • ${selectedAnomaly.syndrome} • ${selectedAnomaly.observation_date}`}
          maxWidth="lg"
        >
          <div className="space-y-4 text-xs">
            {/* Statistical Warning Banner */}
            <div className="p-3.5 rounded-lg bg-navy-950 border border-rose-800/60 text-xs text-rose-300 flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <strong className="font-semibold text-rose-200">
                  Non-Clinical Interpretation Guardrail:
                </strong>
                <p className="mt-1 leading-relaxed text-slate-300">
                  {selectedAnomaly.interpretation_disclaimer}
                </p>
              </div>
            </div>

            {/* Observed vs Expected Baseline Comparison */}
            <div className="p-4 rounded-xl bg-navy-950/70 border border-navy-800">
              <h4 className="text-xs font-semibold text-slate-300 mb-3 uppercase tracking-wider">
                Observed vs Historical Baseline
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-2.5 rounded-lg bg-navy-900 border border-navy-800">
                  <span className="text-[11px] text-slate-400">Observed Volume:</span>
                  <p className="text-lg font-bold text-rose-400 font-mono mt-0.5">
                    {selectedAnomaly.observed_count}
                  </p>
                </div>
                <div className="p-2.5 rounded-lg bg-navy-900 border border-navy-800">
                  <span className="text-[11px] text-slate-400">Expected Baseline:</span>
                  <p className="text-lg font-bold text-slate-200 font-mono mt-0.5">
                    {selectedAnomaly.expected_baseline ? formatScore(selectedAnomaly.expected_baseline) : '—'}
                  </p>
                </div>
                <div className="p-2.5 rounded-lg bg-navy-900 border border-navy-800">
                  <span className="text-[11px] text-slate-400">Deviation Score:</span>
                  <p className="text-lg font-bold text-cyan-400 font-mono mt-0.5">
                    {formatScore(selectedAnomaly.anomaly_score)}σ
                  </p>
                </div>
                <div className="p-2.5 rounded-lg bg-navy-900 border border-navy-800">
                  <span className="text-[11px] text-slate-400">Surge Threshold:</span>
                  <p className="text-lg font-bold text-slate-300 font-mono mt-0.5">
                    {selectedAnomaly.detection_threshold}σ
                  </p>
                </div>
              </div>
            </div>

            {/* Context and Provenance */}
            <div className="space-y-2 pt-2 border-t border-navy-800">
              <div className="flex justify-between py-1.5 border-b border-navy-800/40">
                <span className="text-slate-400">Algorithm Methodology:</span>
                <span className="font-mono font-medium text-slate-200">
                  {selectedAnomaly.detection_method}
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-navy-800/40">
                <span className="text-slate-400">Lookback History Evaluated:</span>
                <span className="font-mono text-slate-200">
                  {selectedAnomaly.history_count} days
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-navy-800/40">
                <span className="text-slate-400">Evaluation State:</span>
                <Badge variant="success" size="sm">
                  {selectedAnomaly.evaluation_status}
                </Badge>
              </div>
              <div className="flex justify-between py-1.5 border-b border-navy-800/40">
                <span className="text-slate-400">Benchmark Data Status:</span>
                <Badge variant="info" size="sm">
                  {selectedAnomaly.data_status}
                </Badge>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="text-slate-400">Evaluation Timestamp:</span>
                <span className="font-mono text-slate-400 text-[11px]">
                  {selectedAnomaly.created_at}
                </span>
              </div>
            </div>

            <div className="flex justify-end pt-3">
              <Button size="sm" variant="secondary" onClick={() => setSelectedAnomaly(null)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
