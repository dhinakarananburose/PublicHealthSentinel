import React, { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import { Select } from '@/components/common/Select'
import { formatNumber } from '@/lib/utils'
import type { RunDetectionRequest, RunDetectionResponse } from '@/types/api'
import type { NavItemKey } from '@/components/layout/Sidebar'
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Database,
  FlaskConical,
  Play,
  RotateCcw,
  Sliders,
  TrendingUp,
} from 'lucide-react'

interface PipelineLabPageProps {
  onNavigate: (route: NavItemKey) => void
}

export const PipelineLabPage: React.FC<PipelineLabPageProps> = ({ onNavigate }) => {
  const queryClient = useQueryClient()

  // Form parameter states with validated defaults matching FastAPI backend
  const [method, setMethod] = useState<'all' | 'rolling_mad' | 'ewma' | 'zscore'>('all')
  const [windowSize, setWindowSize] = useState<number>(21)
  const [threshold, setThreshold] = useState<number>(3.0)
  const [minHistory, setMinHistory] = useState<number>(7)
  const [ewmaLambda, setEwmaLambda] = useState<number>(0.2)
  const [persistResults, setPersistResults] = useState<boolean>(true)

  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({})
  const [executionResult, setExecutionResult] = useState<RunDetectionResponse | null>(null)

  // Validation function
  const validateForm = (): boolean => {
    const errors: Record<string, string> = {}
    if (windowSize < 2 || windowSize > 90) {
      errors.windowSize = 'Lookback window must be between 2 and 90 days.'
    }
    if (threshold <= 0 || threshold > 10.0) {
      errors.threshold = 'Threshold must be between 0.1 and 10.0 standard deviations.'
    }
    if (minHistory < 1 || minHistory > 30) {
      errors.minHistory = 'Minimum history must be between 1 and 30 days.'
    }
    if (ewmaLambda <= 0 || ewmaLambda > 1.0) {
      errors.ewmaLambda = 'EWMA lambda must be between 0.01 and 1.0.'
    }
    setValidationErrors(errors)
    return Object.keys(errors).length === 0
  }

  // Mutation triggering POST /api/v1/pipeline/detect
  const runMutation = useMutation({
    mutationFn: (payload: RunDetectionRequest) => api.runDetectionPipeline(payload),
    onSuccess: (data) => {
      setExecutionResult(data)
      // Invalidate relevant anomaly and surveillance queries so other views get fresh data
      queryClient.invalidateQueries({ queryKey: ['anomalies_intelligence'] })
      queryClient.invalidateQueries({ queryKey: ['anomalies_flagged'] })
      queryClient.invalidateQueries({ queryKey: ['anomalies_all'] })
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!validateForm()) return

    const payload: RunDetectionRequest = {
      method,
      window_size: windowSize,
      threshold,
      min_history: minHistory,
      ewma_lambda: ewmaLambda,
      persist_results: persistResults,
    }
    runMutation.mutate(payload)
  }

  const handleResetDefaults = () => {
    setMethod('all')
    setWindowSize(21)
    setThreshold(3.0)
    setMinHistory(7)
    setEwmaLambda(0.2)
    setPersistResults(true)
    setValidationErrors({})
  }

  return (
    <div className="space-y-6">
      {/* Intro Header */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <FlaskConical className="w-4 h-4 text-cyan-400" />
              Statistical Anomaly Detection Pipeline Lab
            </CardTitle>
            <CardDescription>
              Execute real anomaly detection over historical surveillance observations. Configure window size, threshold, and algorithm parameters.
            </CardDescription>
          </div>
          <Badge variant="info">Live Execution Engine</Badge>
        </CardHeader>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Execution Form */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Sliders className="w-4 h-4 text-teal-400" />
                Pipeline Parameters
              </CardTitle>
              <Button
                size="sm"
                variant="ghost"
                onClick={handleResetDefaults}
                leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
              >
                Reset Defaults
              </Button>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Detection Method */}
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Detection Algorithm Method
                  </label>
                  <select
                    value={method}
                    onChange={(e) => setMethod(e.target.value as any)}
                    className="w-full px-3 py-2 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
                  >
                    <option value="all">all — Execute Rolling MAD, EWMA, and Z-Score concurrently</option>
                    <option value="rolling_mad">rolling_mad — Median Absolute Deviation (Robust to Outliers)</option>
                    <option value="ewma">ewma — Exponentially Weighted Moving Average (Fast Drift Detection)</option>
                    <option value="zscore">zscore — Standard Rolling Mean / Std Dev</option>
                  </select>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Selects which analytical algorithms will process the chronological observation window.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Lookback Window */}
                  <div>
                    <Input
                      label="Lookback Window Size (days, 2 to 90)"
                      type="number"
                      min={2}
                      max={90}
                      value={windowSize}
                      onChange={(e) => setWindowSize(Number(e.target.value))}
                      error={validationErrors.windowSize}
                      helperText="Default: 21 days historical rolling baseline."
                    />
                  </div>

                  {/* Threshold */}
                  <div>
                    <Input
                      label="Anomaly Threshold (0.1 to 10.0 σ)"
                      type="number"
                      step={0.1}
                      min={0.1}
                      max={10.0}
                      value={threshold}
                      onChange={(e) => setThreshold(Number(e.target.value))}
                      error={validationErrors.threshold}
                      helperText="Default: 3.0 standard deviations (or MAD scale)."
                    />
                  </div>

                  {/* Minimum History */}
                  <div>
                    <Input
                      label="Minimum History Required (1 to 30 days)"
                      type="number"
                      min={1}
                      max={30}
                      value={minHistory}
                      onChange={(e) => setMinHistory(Number(e.target.value))}
                      error={validationErrors.minHistory}
                      helperText="Minimum past points before starting evaluation."
                    />
                  </div>

                  {/* EWMA Smoothing Factor */}
                  <div>
                    <Input
                      label="EWMA Smoothing Lambda (0.01 to 1.0)"
                      type="number"
                      step={0.05}
                      min={0.01}
                      max={1.0}
                      value={ewmaLambda}
                      onChange={(e) => setEwmaLambda(Number(e.target.value))}
                      error={validationErrors.ewmaLambda}
                      helperText="Weight on recent observations (higher = more reactive)."
                    />
                  </div>
                </div>

                {/* Database Persistence Toggle */}
                <div className="p-3.5 rounded-lg bg-navy-950 border border-navy-800 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold text-slate-200 block">
                      Persist Evaluation Results to Database
                    </span>
                    <span className="text-[11px] text-slate-400">
                      Upserts anomaly flags and scores to the relational database table.
                    </span>
                  </div>
                  <input
                    type="checkbox"
                    checked={persistResults}
                    aria-label="Persist evaluation results to database"
                    onChange={(e) => setPersistResults(e.target.checked)}
                    className="w-4 h-4 rounded border-navy-700 bg-navy-900 text-cyan-500 focus:ring-cyan-500/40 cursor-pointer"
                  />
                </div>

                {runMutation.isError && (
                  <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-800 text-xs text-rose-300 flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                    <div>
                      <strong>Execution Failure:</strong>{' '}
                      {(runMutation.error as any)?.message || 'Pipeline failed during execution.'}
                    </div>
                  </div>
                )}

                <div className="flex justify-end gap-3 pt-2">
                  <Button
                    type="submit"
                    variant="teal"
                    size="md"
                    isLoading={runMutation.isPending}
                    leftIcon={<Play className="w-4 h-4" />}
                    disabled={runMutation.isPending}
                  >
                    Run Detection Pipeline
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Execution Result Summary Panel */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-xs font-semibold flex items-center gap-2 uppercase tracking-wider text-slate-300">
                <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                Pipeline Execution Audit
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 p-4 pt-0 text-xs">
              {executionResult ? (
                <div className="space-y-3">
                  <div className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-800/80 text-emerald-300">
                    <div className="flex items-center gap-2 font-semibold">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <span>Execution {executionResult.status}</span>
                    </div>
                    <p className="text-[11px] font-mono text-emerald-400/90 mt-1">
                      ID: {executionResult.execution_id}
                    </p>
                  </div>

                  <div className="space-y-1.5 pt-1">
                    <div className="flex justify-between py-1 border-b border-navy-800">
                      <span className="text-slate-400">Total Evaluated:</span>
                      <span className="font-mono font-semibold text-slate-100">
                        {formatNumber(executionResult.total_evaluated_observations)} obs
                      </span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-navy-800">
                      <span className="text-slate-400">DB Records Written:</span>
                      <span className="font-mono text-cyan-400 font-semibold">
                        {formatNumber(executionResult.database_records_persisted)}
                      </span>
                    </div>
                  </div>

                  <div>
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1.5">
                      Anomalies Flagged by Method:
                    </span>
                    <div className="space-y-1">
                      {Object.entries(executionResult.anomalies_detected_by_method).map(
                        ([m, count]) => (
                          <div
                            key={m}
                            className="flex items-center justify-between p-2 rounded bg-navy-950 border border-navy-800 font-mono text-xs"
                          >
                            <span className="text-slate-300">{m}:</span>
                            <Badge variant={count > 0 ? 'danger' : 'outline'} size="sm">
                              {count} flagged
                            </Badge>
                          </div>
                        )
                      )}
                    </div>
                  </div>

                  <div className="pt-2">
                    <Button
                      size="sm"
                      variant="primary"
                      className="w-full"
                      onClick={() => onNavigate('anomalies')}
                      rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                    >
                      Inspect Anomalies in Intelligence
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="py-8 text-center text-slate-400 space-y-2">
                  <Database className="w-8 h-8 mx-auto text-slate-600" />
                  <p className="text-xs">
                    No active pipeline execution. Configure parameters and click "Run Detection Pipeline" to start.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
