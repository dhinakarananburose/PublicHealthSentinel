import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { GeospatialMapChart } from '@/components/charts/GeospatialMapChart'
import { GeospatialTimeSeriesChart } from '@/components/charts/GeospatialTimeSeriesChart'
import { GeospatialLagCorrelationChart } from '@/components/charts/GeospatialLagCorrelationChart'
import { api } from '@/lib/api-client'
import {
  Activity,
  AlertCircle,
  Calendar,
  CheckCircle2,
  Compass,
  Filter,
  Globe,
  Layers,
  MapPin,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
} from 'lucide-react'

export const GeospatialPage: React.FC = () => {
  const [selectedRegionId, setSelectedRegionId] = useState<string>('REGION_A')
  const [selectedSyndrome, setSelectedSyndrome] = useState<string>('Respiratory')
  const [selectedMobilityMetric, setSelectedMobilityMetric] = useState<string>('transit_station_pct_change')
  const [metricShading, setMetricShading] = useState<'cases' | 'rate'>('cases')
  const [showMobilityOverlay, setShowMobilityOverlay] = useState<boolean>(true)
  const [dateRangePreset, setDateRangePreset] = useState<'all' | '60d' | '30d'>('all')
  const [selectedAnomalyDate, setSelectedAnomalyDate] = useState<string | null>(null)

  // Compute date filter strings
  const getDates = () => {
    if (dateRangePreset === '30d') return { start: '2026-05-30', end: '2026-06-29' }
    if (dateRangePreset === '60d') return { start: '2026-04-30', end: '2026-06-29' }
    return { start: '2026-01-01', end: '2026-06-29' }
  }
  const { start: startDate, end: endDate } = getDates()

  // 1. Fetch Regional Surveillance Summaries
  const {
    data: survSummary,
    isLoading: isSurvLoading,
    refetch: refetchSurv,
  } = useQuery({
    queryKey: ['geospatial_surveillance', startDate, endDate, selectedSyndrome],
    queryFn: () =>
      api.getGeospatialSurveillance({
        start_date: startDate,
        end_date: endDate,
        syndrome: selectedSyndrome === 'All' ? undefined : selectedSyndrome,
      }),
  })

  // 2. Fetch Time Series for Selected Region
  const {
    data: timeSeriesData,
    isLoading: isTSLoading,
    refetch: refetchTS,
  } = useQuery({
    queryKey: ['geospatial_timeseries', selectedRegionId, selectedSyndrome, startDate, endDate],
    queryFn: () =>
      api.getGeospatialTimeSeries({
        region_id: selectedRegionId,
        syndrome: selectedSyndrome === 'All' ? 'Respiratory' : selectedSyndrome,
        start_date: startDate,
        end_date: endDate,
      }),
  })

  // 3. Fetch Mobility Overlay Points
  const { data: mobilityData, isLoading: isMobLoading } = useQuery({
    queryKey: ['geospatial_mobility', selectedRegionId, selectedSyndrome, selectedMobilityMetric, startDate, endDate],
    queryFn: () =>
      api.getGeospatialMobility({
        region_id: selectedRegionId,
        syndrome: selectedSyndrome === 'All' ? 'Respiratory' : selectedSyndrome,
        mobility_metric: selectedMobilityMetric,
        start_date: startDate,
        end_date: endDate,
      }),
    enabled: showMobilityOverlay,
  })

  // 4. Fetch Lagged Cross-Correlations
  const {
    data: correlationData,
    isLoading: isCorrLoading,
    refetch: refetchCorr,
  } = useQuery({
    queryKey: ['geospatial_correlations', selectedRegionId, selectedSyndrome, selectedMobilityMetric],
    queryFn: () =>
      api.getGeospatialCorrelations({
        region_id: selectedRegionId,
        syndrome: selectedSyndrome === 'All' ? 'Respiratory' : selectedSyndrome,
        mobility_metric: selectedMobilityMetric,
        min_lag: -7,
        max_lag: 14,
      }),
  })

  const handleRefreshAll = () => {
    refetchSurv()
    refetchTS()
    refetchCorr()
  }

  const selectedRegionSummary = survSummary?.regions.find((r) => r.region_id === selectedRegionId)

  // Extract anomaly points from time series for the anomaly ledger
  const anomalyRows = timeSeriesData?.points.filter((p) => p.is_anomaly) || []

  return (
    <div className="space-y-6">
      {/* Top Protocol & Synthetic Geography Banner */}
      <div className="p-4 rounded-xl border border-navy-800 bg-navy-900/90 text-xs text-slate-200 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-lg bg-cyan-950 border border-cyan-800 flex items-center justify-center text-cyan-400 shrink-0">
            <Globe className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-sm font-semibold text-slate-100">
                Phase 7: Geospatial Intelligence & Surveillance Mapping
              </h2>
              <Badge variant="info">Synthetic Territory Grid</Badge>
              <Badge variant="outline">
                {survSummary?.total_surveillance_cases.toLocaleString() ?? '229,544'} Total Cases
              </Badge>
              <Badge variant="anomaly">
                {survSummary?.total_anomalies_flagged ?? 64} Flagged Anomalies
              </Badge>
            </div>
            <p className="mt-1 text-slate-400 leading-relaxed max-w-3xl">
              Geographic surveillance aggregation across five synthetic public-health sectors (Alpha–Epsilon). Integrates spatial case density, algorithmic anomaly detection limits, and dual-axis population mobility lagged cross-correlations.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end md:self-auto shrink-0">
          <Button
            size="sm"
            variant="outline"
            onClick={handleRefreshAll}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Global Filter Bar */}
      <Card>
        <CardContent className="p-4 flex flex-wrap items-center justify-between gap-4 text-xs">
          {/* Region Buttons */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="font-semibold text-slate-400 mr-1 flex items-center gap-1">
              <MapPin className="w-3.5 h-3.5 text-cyan-400" />
              Focus Sector:
            </span>
            {['REGION_A', 'REGION_B', 'REGION_C', 'REGION_D', 'REGION_E'].map((rId) => (
              <button
                key={rId}
                onClick={() => setSelectedRegionId(rId)}
                className={`px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all ${
                  selectedRegionId === rId
                    ? 'bg-cyan-500 text-navy-950 border-cyan-400 font-bold shadow-md shadow-cyan-500/20'
                    : 'bg-navy-950 border-navy-800 text-slate-300 hover:border-navy-700 hover:bg-navy-900'
                }`}
              >
                {rId.replace('REGION_', 'Sector ')}
              </button>
            ))}
          </div>

          {/* Controls: Syndrome, Date, Metric */}
          <div className="flex items-center gap-3 flex-wrap">
            {/* Syndrome Selector */}
            <div className="flex items-center gap-1.5">
              <span className="text-slate-400">Syndrome:</span>
              <select
                value={selectedSyndrome}
                onChange={(e) => setSelectedSyndrome(e.target.value)}
                className="px-2.5 py-1.5 rounded-lg bg-navy-950 border border-navy-700 text-slate-200 text-xs focus:outline-none focus:border-cyan-500"
              >
                <option value="Respiratory">Respiratory</option>
                <option value="Gastrointestinal">Gastrointestinal</option>
                <option value="Febrile">Febrile</option>
                <option value="All">All Syndromes</option>
              </select>
            </div>

            {/* Date Preset */}
            <div className="flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-slate-400" />
              <select
                value={dateRangePreset}
                onChange={(e) => setDateRangePreset(e.target.value as any)}
                className="px-2.5 py-1.5 rounded-lg bg-navy-950 border border-navy-700 text-slate-200 text-xs focus:outline-none focus:border-cyan-500"
              >
                <option value="all">Full 180 Days (Jan-Jun 2026)</option>
                <option value="60d">Last 60 Days</option>
                <option value="30d">Last 30 Days</option>
              </select>
            </div>

            {/* Mobility Metric */}
            <div className="flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-purple-400" />
              <select
                value={selectedMobilityMetric}
                onChange={(e) => setSelectedMobilityMetric(e.target.value)}
                className="px-2.5 py-1.5 rounded-lg bg-navy-950 border border-navy-700 text-slate-200 text-xs focus:outline-none focus:border-cyan-500"
              >
                <option value="transit_station_pct_change">Transit Station Mobility</option>
                <option value="workplace_pct_change">Workplace Presence</option>
                <option value="residential_pct_change">Residential Shifts</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Geospatial Map & Region Summary Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Schematic Geospatial Sector Map */}
        <div className="lg:col-span-2">
          {isSurvLoading ? (
            <Card className="min-h-[440px] flex items-center justify-center">
              <LoadingSpinner size="lg" />
            </Card>
          ) : (
            <GeospatialMapChart
              regions={survSummary?.regions || []}
              selectedRegionId={selectedRegionId}
              onSelectRegion={setSelectedRegionId}
              metricType={metricShading}
              onMetricTypeChange={setMetricShading}
            />
          )}
        </div>

        {/* Right Col: Focused Sector Metadata Card */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                  Selected Sector Profile
                </CardTitle>
                <Badge variant="outline" className="font-mono text-[10px]">
                  {selectedRegionId}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 p-5 pt-0 text-xs">
              <div>
                <h3 className="text-sm font-bold text-slate-100">
                  {selectedRegionSummary?.region_name || selectedRegionId}
                </h3>
                <p className="text-[11px] font-mono text-slate-400 mt-0.5">
                  Centroid: {selectedRegionSummary?.centroid_lat.toFixed(2)}° N,{' '}
                  {selectedRegionSummary?.centroid_lon.toFixed(2)}° W
                </p>
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div className="p-3 rounded-lg bg-navy-950 border border-navy-800 space-y-1">
                  <span className="text-[10px] text-slate-400 flex items-center gap-1">
                    <Users className="w-3 h-3 text-cyan-400" /> Population
                  </span>
                  <div className="text-sm font-mono font-bold text-slate-100">
                    {selectedRegionSummary?.population.toLocaleString()}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-navy-950 border border-navy-800 space-y-1">
                  <span className="text-[10px] text-slate-400 flex items-center gap-1">
                    <Activity className="w-3 h-3 text-emerald-400" /> Facilities
                  </span>
                  <div className="text-sm font-mono font-bold text-slate-100">
                    {selectedRegionSummary?.facility_count} Sentinel Sites
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-navy-950 border border-navy-800 space-y-1">
                  <span className="text-[10px] text-slate-400">Total Cases</span>
                  <div className="text-sm font-mono font-bold text-cyan-300">
                    {selectedRegionSummary?.total_cases.toLocaleString()}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-navy-950 border border-navy-800 space-y-1">
                  <span className="text-[10px] text-slate-400">Crude Rate</span>
                  <div className="text-sm font-mono font-bold text-slate-200">
                    {selectedRegionSummary?.crude_rate_per_100k != null
                      ? `${selectedRegionSummary.crude_rate_per_100k.toFixed(1)} / 100k`
                      : 'N/A'}
                  </div>
                </div>
              </div>

              {/* Anomaly Badge */}
              <div
                className={`p-3 rounded-lg border text-xs flex items-center justify-between ${
                  selectedRegionSummary?.recent_anomaly_detected
                    ? 'bg-rose-950/40 border-rose-800/80 text-rose-200'
                    : 'bg-emerald-950/40 border-emerald-800/60 text-emerald-200'
                }`}
              >
                <div className="flex items-center gap-2">
                  {selectedRegionSummary?.recent_anomaly_detected ? (
                    <ShieldAlert className="w-4 h-4 text-rose-400" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  )}
                  <span>
                    {selectedRegionSummary?.recent_anomaly_detected
                      ? `${selectedRegionSummary.anomaly_count} Anomalies Detected`
                      : 'No Statistical Surges'}
                  </span>
                </div>
                <Badge variant={selectedRegionSummary?.recent_anomaly_detected ? 'anomaly' : 'success'} size="sm">
                  {selectedRegionSummary?.recent_anomaly_detected ? 'Review Ledger' : 'Stable'}
                </Badge>
              </div>

              {/* Syndromic Breakdown */}
              {selectedRegionSummary && (
                <div className="space-y-2 pt-1 border-t border-navy-800 text-[11px]">
                  <span className="text-slate-400 font-semibold block">Syndromic Distribution:</span>
                  <div className="space-y-1">
                    {Object.entries(selectedRegionSummary.syndromic_breakdown).map(([synd, count]) => {
                      const pct = Math.round((count / selectedRegionSummary.total_cases) * 100)
                      return (
                        <div key={synd} className="space-y-0.5">
                          <div className="flex items-center justify-between text-slate-300">
                            <span>{synd}</span>
                            <span className="font-mono text-slate-400">
                              {count.toLocaleString()} ({pct}%)
                            </span>
                          </div>
                          <div className="w-full h-1.5 rounded-full bg-navy-800 overflow-hidden">
                            <div
                              className="h-full bg-cyan-500 rounded-full"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Time Series Explorer with Dual-Axis Mobility Overlay */}
      <div>
        {isTSLoading ? (
          <Card className="min-h-[380px] flex items-center justify-center">
            <LoadingSpinner size="lg" />
          </Card>
        ) : (
          <GeospatialTimeSeriesChart
            timeSeriesPoints={timeSeriesData?.points || []}
            mobilityPoints={mobilityData?.points || []}
            regionId={selectedRegionId}
            regionName={selectedRegionSummary?.region_name || selectedRegionId}
            syndrome={selectedSyndrome === 'All' ? 'Respiratory' : selectedSyndrome}
            mobilityMetricName={selectedMobilityMetric}
            showMobilityOverlay={showMobilityOverlay}
            onToggleMobilityOverlay={setShowMobilityOverlay}
            selectedAnomalyDate={selectedAnomalyDate}
            onSelectAnomalyDate={setSelectedAnomalyDate}
          />
        )}
      </div>

      {/* Lagged Cross-Correlation & Anomaly Ledger Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Lagged Correlation Profile */}
        <div>
          {isCorrLoading ? (
            <Card className="min-h-[360px] flex items-center justify-center">
              <LoadingSpinner size="lg" />
            </Card>
          ) : (
            <GeospatialLagCorrelationChart correlationData={correlationData || null} />
          )}
        </div>

        {/* Flagged Anomaly Ledger Table */}
        <div>
          <Card className="min-h-[360px] flex flex-col justify-between">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-rose-400" />
                    Flagged Anomaly Ledger ({selectedRegionId})
                  </CardTitle>
                  <CardDescription>
                    Statistical baseline deviations flagged by rolling MAD (threshold &ge; 3.0).
                  </CardDescription>
                </div>
                <Badge variant="anomaly" size="sm">
                  {anomalyRows.length} Events
                </Badge>
              </div>
            </CardHeader>

            <CardContent className="p-6 pt-0 space-y-3 flex-1 flex flex-col justify-between">
              {anomalyRows.length === 0 ? (
                <div className="text-center py-12 text-slate-500 text-xs">
                  No statistical anomalies flagged for {selectedRegionId} in this time period.
                </div>
              ) : (
                <div className="overflow-x-auto max-h-[280px] overflow-y-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-navy-800 text-[11px] text-slate-400 font-semibold uppercase tracking-wider">
                        <th className="py-2 px-2.5">Date</th>
                        <th className="py-2 px-2.5">Observed</th>
                        <th className="py-2 px-2.5">Baseline</th>
                        <th className="py-2 px-2.5">Threshold</th>
                        <th className="py-2 px-2.5">MAD Score</th>
                        <th className="py-2 px-2.5">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-navy-900 font-mono text-[11px]">
                      {anomalyRows.slice(0, 10).map((anom) => (
                        <tr
                          key={anom.observation_date}
                          onClick={() => setSelectedAnomalyDate(anom.observation_date)}
                          className={`cursor-pointer transition-colors ${
                            selectedAnomalyDate === anom.observation_date
                              ? 'bg-rose-950/60 text-rose-200'
                              : 'hover:bg-navy-900/60 text-slate-300'
                          }`}
                        >
                          <td className="py-2 px-2.5 font-bold text-slate-200">{anom.observation_date}</td>
                          <td className="py-2 px-2.5 text-cyan-300 font-bold">{anom.report_count}</td>
                          <td className="py-2 px-2.5 text-slate-400">
                            {anom.expected_baseline != null ? anom.expected_baseline.toFixed(1) : 'N/A'}
                          </td>
                          <td className="py-2 px-2.5 text-amber-300">
                            {anom.detection_threshold != null ? anom.detection_threshold.toFixed(1) : 'N/A'}
                          </td>
                          <td className="py-2 px-2.5 text-rose-300 font-bold">
                            {anom.anomaly_score != null ? anom.anomaly_score.toFixed(2) : 'N/A'}
                          </td>
                          <td className="py-2 px-2.5">
                            <span className="px-1.5 py-0.5 rounded text-[10px] bg-rose-950 text-rose-300 border border-rose-800">
                              Surge Alert
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Non-Diagnostic Disclaimer */}
              <div className="p-2.5 rounded-lg bg-navy-950 border border-navy-800 text-[11px] text-slate-400 flex items-center justify-between">
                <span>
                  <strong>Surveillance Principle:</strong> Statistical surge alerts indicate anomalous divergence from empirical baselines; they are <em>not confirmed real-world outbreak diagnoses</em>.
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
