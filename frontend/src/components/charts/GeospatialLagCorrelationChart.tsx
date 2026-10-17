import React from 'react'
import * as echarts from 'echarts'
import { EChartWrapper } from '@/components/charts/EChartWrapper'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import type { GeospatialLaggedCorrelationResponse } from '@/types/api'
import { AlertCircle, ArrowRight, GitCommit, Info, Sparkles, TrendingUp } from 'lucide-react'

interface GeospatialLagCorrelationChartProps {
  correlationData: GeospatialLaggedCorrelationResponse | null
  isLoading?: boolean
}

export const GeospatialLagCorrelationChart: React.FC<GeospatialLagCorrelationChartProps> = ({
  correlationData,
  isLoading = false,
}) => {
  if (!correlationData || correlationData.lag_points.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-cyan-400" />
            Lagged Cross-Correlation Explorer
          </CardTitle>
          <CardDescription>
            Temporal association between population mobility shifts and syndromic case reports.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-6 text-center text-xs text-slate-500 py-10">
          No aligned mobility and surveillance data available for this selection.
        </CardContent>
      </Card>
    )
  }

  const lags = correlationData.lag_points.map((p) => (p.lag_days > 0 ? `+${p.lag_days}d` : `${p.lag_days}d`))
  const pearsonR = correlationData.lag_points.map((p) => p.pearson_r)
  const spearmanRho = correlationData.lag_points.map((p) => p.spearman_rho)

  const options: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0a0f1d',
      borderColor: '#1e293b',
      borderWidth: 1,
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: (params: any) => {
        if (!Array.isArray(params) || params.length === 0) return ''
        const idx = params[0].dataIndex
        const pt = correlationData.lag_points[idx]
        let html = `<div class="p-1 font-mono text-xs">`
        html += `<div class="font-bold text-slate-200 border-b border-navy-800 pb-1 mb-1">Lag Offset: ${pt.lag_days} Days</div>`
        html += `<div class="text-[11px] text-slate-400 mb-1.5 italic">${pt.convention_description}</div>`
        html += `<div class="flex items-center justify-between gap-3 text-cyan-300">`
        html += `<span>Pearson r:</span><strong>${pt.pearson_r != null ? pt.pearson_r.toFixed(4) : 'N/A'}</strong>`
        html += `</div>`
        html += `<div class="flex items-center justify-between gap-3 text-purple-300">`
        html += `<span>Spearman ρ:</span><strong>${pt.spearman_rho != null ? pt.spearman_rho.toFixed(4) : 'N/A'}</strong>`
        html += `</div>`
        html += `<div class="flex items-center justify-between gap-3 text-slate-400 text-[10px] pt-1 mt-1 border-t border-navy-800">`
        html += `<span>p-value:</span><span>${pt.pearson_p_value != null ? pt.pearson_p_value.toExponential(2) : 'N/A'}</span>`
        html += `</div>`
        html += `<div class="flex items-center justify-between gap-3 text-slate-400 text-[10px]">`
        html += `<span>Paired N:</span><span>${pt.sample_size_n} days</span>`
        html += `</div>`
        html += `</div>`
        return html
      },
    },
    legend: {
      data: ['Pearson r (Linear)', 'Spearman ρ (Monotonic)'],
      textStyle: { color: '#94a3b8', fontSize: 11 },
      top: 0,
      right: 10,
    },
    grid: {
      left: '3%',
      right: '3%',
      bottom: '10%',
      top: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: lags,
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'Correlation Coefficient',
      min: -1.0,
      max: 1.0,
      nameTextStyle: { color: '#94a3b8', fontSize: 11 },
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      splitLine: { lineStyle: { color: '#1e293b' } },
    },
    series: [
      {
        name: 'Pearson r (Linear)',
        type: 'bar',
        data: pearsonR,
        itemStyle: {
          color: (params: any) => {
            const v = params.value
            return v >= 0 ? '#22d3ee' : '#f43f5e'
          },
          borderRadius: [3, 3, 0, 0],
        },
      },
      {
        name: 'Spearman ρ (Monotonic)',
        type: 'line',
        data: spearmanRho,
        smooth: true,
        lineStyle: { color: '#c084fc', width: 2 },
        itemStyle: { color: '#c084fc' },
        showSymbol: true,
        symbolSize: 6,
      },
    ],
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-cyan-400" />
              Lagged Cross-Correlation Profile (-7 to +14 Days)
            </CardTitle>
            <CardDescription>
              {correlationData.region_name} — {correlationData.syndrome} vs {correlationData.mobility_metric}
            </CardDescription>
          </div>

          <div className="flex items-center gap-2">
            {correlationData.best_positive_lag_days != null && (
              <Badge variant="info" className="font-mono text-xs">
                Peak Lead: +{correlationData.best_positive_lag_days} Days (r ={' '}
                {correlationData.best_positive_lag_pearson_r?.toFixed(3)})
              </Badge>
            )}
            <Badge variant="outline" className="font-mono text-xs">
              N = {correlationData.sample_size} paired dates
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-6 pt-0 space-y-4">
        {/* Lag Convention Definition */}
        <div className="p-2.5 rounded-lg bg-navy-950 border border-navy-800 text-[11px] text-slate-300 space-y-1">
          <div className="font-semibold text-cyan-300 flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5" />
            Lag Sign Convention & Alignment Protocol
          </div>
          <p className="text-slate-400 leading-relaxed">
            {correlationData.lag_convention} A peak at positive lag indicates that mobility reductions statistically preceded symptom surge onset in the benchmark series.
          </p>
        </div>

        {/* EChart */}
        <EChartWrapper options={options} height={280} />

        {/* Epidemiological Non-Causality Disclaimer */}
        <div className="p-3 rounded-lg bg-amber-950/30 border border-amber-800/60 text-[11px] text-amber-200 space-y-1">
          <div className="font-semibold text-amber-300 flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            Epidemiological Principle: Correlation Does Not Establish Causation
          </div>
          <p className="text-amber-200/90 leading-relaxed">
            {correlationData.causality_disclaimer} Macroscopic associations between aggregate transit metrics and syndromic reporting do not prove individual transmission mechanics or clinical incubation timelines.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
