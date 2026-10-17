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
import { MobilityComparisonChart } from '@/components/charts/MobilityComparisonChart'
import { formatScore } from '@/lib/utils'
import {
  BarChart3,
  GitCommit,
  Navigation,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  X,
} from 'lucide-react'

export const MobilityPage: React.FC = () => {
  const [page, setPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(25)
  const [regionFilter, setRegionFilter] = useState<string>('')
  const [metricFilter, setMetricFilter] = useState<string>('')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['mobility_analytics', { page, pageSize, regionFilter, metricFilter, startDate, endDate }],
    queryFn: () =>
      api.getMobility({
        page,
        page_size: pageSize,
        region_id: regionFilter || undefined,
        mobility_metric: metricFilter || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      }),
  })

  // Full dataset for chart
  const chartQuery = useQuery({
    queryKey: ['mobility_chart', { regionFilter, metricFilter }],
    queryFn: () =>
      api.getMobility({
        page_size: 200,
        region_id: regionFilter || undefined,
        mobility_metric: metricFilter || undefined,
      }),
  })

  // Real Phase 4 Empirical Evaluation Report
  const evalQuery = useQuery({
    queryKey: ['mobility_evaluation'],
    queryFn: () => api.getMobilityEvaluation(),
  })

  const resetFilters = () => {
    setRegionFilter('')
    setMetricFilter('')
    setStartDate('')
    setEndDate('')
    setPage(1)
  }

  const hasActiveFilters = Boolean(regionFilter || metricFilter || startDate || endDate)

  return (
    <div className="space-y-6">
      {/* Scope and Filter Card */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Navigation className="w-4 h-4 text-teal-400" />
              Population Mobility Analytics
            </CardTitle>
            <CardDescription>
              Investigate aggregated mobility indicators and statistical cross-correlation with syndromic surge patterns.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                refetch()
                chartQuery.refetch()
                evalQuery.refetch()
              }}
              isLoading={isFetching || chartQuery.isFetching || evalQuery.isFetching}
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isFetching || evalQuery.isFetching ? 'animate-spin' : ''}`} />}
            >
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {/* Jurisdiction */}
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

            {/* Metric */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Mobility Metric</label>
              <select
                value={metricFilter}
                onChange={(e) => {
                  setMetricFilter(e.target.value)
                  setPage(1)
                }}
                className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="">All Mobility Metrics</option>
                <option value="transit_station_pct_change">transit_station_pct_change (Transit Stations)</option>
                <option value="residential_pct_change">residential_pct_change (Residential Areas)</option>
                <option value="workplace_pct_change">workplace_pct_change (Workplaces)</option>
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
                Filtered mobility scope: Showing {data?.total ?? 0} matching records.
              </span>
              <button
                onClick={resetFilters}
                className="text-teal-400 hover:text-teal-300 flex items-center gap-1 font-medium"
              >
                <X className="w-3.5 h-3.5" />
                Reset Mobility Scope
              </button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Mobility Trend Chart */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-teal-400" />
              Population Transit Mobility Trends (% Change from Baseline)
            </CardTitle>
            <CardDescription>
              Time-series tracking of population transit volume shifts across monitored administrative zones.
            </CardDescription>
          </div>
          <Badge variant="info">Phase 4 Predictive Alignment</Badge>
        </CardHeader>
        <CardContent className="pt-2">
          {chartQuery.isLoading ? (
            <LoadingSpinner text="Plotting mobility series across regions..." />
          ) : (
            <MobilityComparisonChart
              data={chartQuery.data?.items || []}
              height={300}
            />
          )}
        </CardContent>
      </Card>

      {/* Predictive Lag Findings Summary Card */}
      <Card className="border-teal-800/40 bg-navy-900/90">
        <CardHeader>
          <div>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <GitCommit className="w-4 h-4 text-teal-400" />
              Phase 4 Benchmark Predictive Evaluation Findings
            </CardTitle>
            <CardDescription>
              Empirical evaluation comparing surveillance-only baseline vs mobility-augmented anomaly forecasting.
            </CardDescription>
          </div>
          <Badge variant="success">Empirical Stored Report</Badge>
        </CardHeader>
        <CardContent>
          {evalQuery.isLoading ? (
            <div className="py-6">
              <LoadingSpinner text="Loading empirical Phase 4 predictive evaluation results..." />
            </div>
          ) : evalQuery.isError ? (
            <div className="py-4">
              <ErrorState
                message={(evalQuery.error as any)?.message || 'Mobility evaluation report is not available.'}
                onRetry={() => evalQuery.refetch()}
              />
            </div>
          ) : evalQuery.data ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                {/* Baseline */}
                <div className="p-3.5 rounded-xl bg-navy-950/70 border border-navy-800">
                  <span className="text-slate-400 font-medium">Baseline Model (Surv Only):</span>
                  <p className="text-base font-bold text-slate-100 font-mono mt-1">
                    F1 Score: {evalQuery.data.baseline_model.f1_score.toFixed(4)}
                  </p>
                  <div className="mt-2 text-[11px] text-slate-400 space-y-0.5">
                    <div>Precision: {evalQuery.data.baseline_model.precision.toFixed(4)}</div>
                    <div>Recall: {evalQuery.data.baseline_model.recall.toFixed(4)}</div>
                    <div>Specificity: {evalQuery.data.baseline_model.specificity.toFixed(4)}</div>
                    <div>Accuracy: {evalQuery.data.baseline_model.accuracy.toFixed(4)}</div>
                    <div className="text-[10px] text-slate-500 font-mono pt-1">
                      TN: {evalQuery.data.baseline_model.confusion_matrix.tn} | FP: {evalQuery.data.baseline_model.confusion_matrix.fp} | FN: {evalQuery.data.baseline_model.confusion_matrix.fn} | TP: {evalQuery.data.baseline_model.confusion_matrix.tp}
                    </div>
                  </div>
                </div>

                {/* Augmented */}
                <div className="p-3.5 rounded-xl bg-navy-950/70 border border-teal-800/40">
                  <span className="text-teal-400 font-medium">Augmented Model (+Mobility):</span>
                  <p className="text-base font-bold text-teal-300 font-mono mt-1">
                    F1 Score: {evalQuery.data.augmented_model.f1_score.toFixed(4)}
                  </p>
                  <div className="mt-2 text-[11px] text-slate-400 space-y-0.5">
                    <div>Precision: {evalQuery.data.augmented_model.precision.toFixed(4)}</div>
                    <div>Recall: {evalQuery.data.augmented_model.recall.toFixed(4)}</div>
                    <div>Specificity: {evalQuery.data.augmented_model.specificity.toFixed(4)}</div>
                    <div>Accuracy: {evalQuery.data.augmented_model.accuracy.toFixed(4)}</div>
                    <div className="text-[10px] text-teal-500/80 font-mono pt-1">
                      TN: {evalQuery.data.augmented_model.confusion_matrix.tn} | FP: {evalQuery.data.augmented_model.confusion_matrix.fp} | FN: {evalQuery.data.augmented_model.confusion_matrix.fn} | TP: {evalQuery.data.augmented_model.confusion_matrix.tp}
                    </div>
                  </div>
                </div>

                {/* Verdict & Delta */}
                <div className="p-3.5 rounded-xl bg-navy-950/70 border border-navy-800">
                  <span className="text-slate-400 font-medium">Empirical Finding & Delta:</span>
                  <p className="text-sm font-semibold text-teal-300 mt-1">
                    Positive Improvement (ΔF1 = +{evalQuery.data.delta_f1.toFixed(4)})
                  </p>
                  <p className="mt-1 text-[11px] text-slate-400 leading-relaxed">
                    {evalQuery.data.performance_verdict}
                  </p>
                  <div className="mt-2 text-[10px] text-slate-500 font-mono flex gap-2">
                    <span>ΔPrec: +{evalQuery.data.delta_precision.toFixed(4)}</span>
                    <span>ΔRec: +{evalQuery.data.delta_recall.toFixed(4)}</span>
                    <span>ΔSpec: +{evalQuery.data.delta_specificity.toFixed(4)}</span>
                  </div>
                </div>
              </div>

              {/* Protocol Specs */}
              <div className="p-3 rounded-lg bg-navy-950/40 border border-navy-800/60 text-[11px] text-slate-400 flex flex-col md:flex-row md:items-center justify-between gap-2">
                <div>
                  <span className="font-semibold text-slate-300">Target:</span> {evalQuery.data.target_definition}
                </div>
                <div className="text-slate-400 font-mono text-[10px]">
                  Train: {evalQuery.data.train_date_range[0]} → {evalQuery.data.train_date_range[1]} ({evalQuery.data.baseline_model.train_sample_size} obs) | Test: {evalQuery.data.test_date_range[0]} → {evalQuery.data.test_date_range[1]} ({evalQuery.data.baseline_model.test_sample_size} obs)
                </div>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* Mobility Records Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <LoadingSpinner text="Retrieving mobility indicators from database..." />
          ) : isError ? (
            <div className="p-6">
              <ErrorState
                message={(error as any)?.message || 'Failed to query mobility indicators.'}
                onRetry={() => refetch()}
              />
            </div>
          ) : !data || data.items.length === 0 ? (
            <div className="p-6">
              <EmptyState
                icon={<Navigation className="w-6 h-6 text-slate-400" />}
                title="No mobility indicators found"
                description="Try clearing or adjusting date range filters."
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
                    <th className="px-4 py-3 font-semibold">Jurisdiction</th>
                    <th className="px-4 py-3 font-semibold">Mobility Metric</th>
                    <th className="px-4 py-3 font-semibold">Relative Value</th>
                    <th className="px-4 py-3 font-semibold">Data Source</th>
                    <th className="px-4 py-3 font-semibold">Data Status</th>
                    <th className="px-5 py-3 font-semibold text-right">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-navy-800/60 text-slate-200">
                  {data.items.map((mob) => (
                    <tr key={mob.id} className="hover:bg-navy-850/60 transition-colors">
                      <td className="px-5 py-3 font-mono font-medium text-slate-300">
                        {mob.observation_date}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline">{mob.region_id}</Badge>
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-300">
                        {mob.mobility_metric}
                      </td>
                      <td className="px-4 py-3 font-mono font-semibold">
                        <span
                          className={`inline-flex items-center gap-1 ${
                            mob.mobility_value >= 0 ? 'text-teal-400' : 'text-amber-400'
                          }`}
                        >
                          {mob.mobility_value >= 0 ? (
                            <TrendingUp className="w-3.5 h-3.5" />
                          ) : (
                            <TrendingDown className="w-3.5 h-3.5" />
                          )}
                          {mob.mobility_value > 0 ? `+${mob.mobility_value.toFixed(1)}%` : `${mob.mobility_value.toFixed(1)}%`}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-400 font-mono text-[11px]">
                        {mob.data_source}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="info" size="sm">
                          {mob.data_status}
                        </Badge>
                      </td>
                      <td className="px-5 py-3 font-mono text-slate-500 text-right text-[11px]">
                        {mob.ingestion_timestamp.split('T')[0]}
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
    </div>
  )
}
