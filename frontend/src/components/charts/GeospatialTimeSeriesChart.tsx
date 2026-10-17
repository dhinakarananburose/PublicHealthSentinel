import React from 'react'
import * as echarts from 'echarts'
import { EChartWrapper } from '@/components/charts/EChartWrapper'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import type { GeospatialTimeSeriesPoint, MobilityOverlayPoint } from '@/types/api'
import { Activity, AlertTriangle, Layers, TrendingUp } from 'lucide-react'

interface GeospatialTimeSeriesChartProps {
  timeSeriesPoints: GeospatialTimeSeriesPoint[]
  mobilityPoints?: MobilityOverlayPoint[]
  regionId: string
  regionName: string
  syndrome: string
  mobilityMetricName?: string
  showMobilityOverlay: boolean
  onToggleMobilityOverlay: (show: boolean) => void
  selectedAnomalyDate?: string | null
  onSelectAnomalyDate?: (date: string) => void
}

export const GeospatialTimeSeriesChart: React.FC<GeospatialTimeSeriesChartProps> = ({
  timeSeriesPoints,
  mobilityPoints = [],
  regionId,
  regionName,
  syndrome,
  mobilityMetricName = 'transit_station_pct_change',
  showMobilityOverlay,
  onToggleMobilityOverlay,
  selectedAnomalyDate,
  onSelectAnomalyDate,
}) => {
  const dates = timeSeriesPoints.map((p) => p.observation_date)
  const reportCounts = timeSeriesPoints.map((p) => p.report_count)
  const baselines = timeSeriesPoints.map((p) => (p.expected_baseline != null ? Math.round(p.expected_baseline * 10) / 10 : null))
  const thresholds = timeSeriesPoints.map((p) => (p.detection_threshold != null ? Math.round(p.detection_threshold * 10) / 10 : null))

  // Scatter points for flagged anomalies
  const anomalyScatterData = timeSeriesPoints
    .filter((p) => p.is_anomaly)
    .map((p) => ({
      name: `Anomaly: ${p.observation_date}`,
      dateStr: p.observation_date,
      countVal: p.report_count,
      score: p.anomaly_score,
      method: p.detection_method,
    }))

  // Map mobility points by date
  const mobMap = new Map<string, number | null>()
  mobilityPoints.forEach((m) => {
    mobMap.set(m.observation_date, m.mobility_value)
  })
  const mobilityValues = dates.map((d) => mobMap.get(d) ?? null)

  const series: echarts.SeriesOption[] = [
    {
      name: `${syndrome} Daily Cases`,
      type: 'line',
      yAxisIndex: 0,
      data: reportCounts,
      smooth: true,
      lineStyle: {
        color: '#22d3ee', // Cyan
        width: 2.5,
      },
      itemStyle: {
        color: '#22d3ee',
      },
      showSymbol: false,
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(34, 211, 238, 0.25)' },
          { offset: 1, color: 'rgba(34, 211, 238, 0.00)' },
        ]),
      },
      markPoint: {
        symbol: 'pin',
        symbolSize: 32,
        data: anomalyScatterData.map((a) => ({
          name: a.name,
          coord: [a.dateStr, a.countVal] as [string, number],
          value: '!',
          itemStyle: {
            color: '#f43f5e', // Rose
            borderColor: '#ffe4e6',
            borderWidth: 1.5,
          },
        })),
      },
    },
    {
      name: 'Expected Baseline',
      type: 'line',
      yAxisIndex: 0,
      data: baselines,
      smooth: true,
      lineStyle: {
        color: '#94a3b8',
        type: 'dashed',
        width: 1.5,
      },
      showSymbol: false,
    },
    {
      name: 'Surge Threshold',
      type: 'line',
      yAxisIndex: 0,
      data: thresholds,
      smooth: true,
      lineStyle: {
        color: '#f59e0b', // Amber
        type: 'dotted',
        width: 1.5,
      },
      showSymbol: false,
    },
  ]

  if (showMobilityOverlay && mobilityPoints.length > 0) {
    series.push({
      name: `Mobility (% Dev)`,
      type: 'line',
      yAxisIndex: 1,
      data: mobilityValues,
      smooth: true,
      lineStyle: {
        color: '#a855f7', // Purple
        width: 2,
        type: 'solid',
      },
      itemStyle: {
        color: '#a855f7',
      },
      showSymbol: false,
    })
  }

  const options: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0a0f1d',
      borderColor: '#1e293b',
      borderWidth: 1,
      textStyle: {
        color: '#e2e8f0',
        fontSize: 12,
      },
      axisPointer: {
        type: 'cross',
        crossStyle: {
          color: '#475569',
        },
      },
      formatter: (params: any) => {
        if (!Array.isArray(params) || params.length === 0) return ''
        const dateStr = params[0].axisValue
        let html = `<div class="p-1 font-mono">`
        html += `<div class="font-bold text-slate-200 border-b border-navy-800 pb-1 mb-1">${dateStr} (${regionId})</div>`

        // Check if anomaly on this date
        const isAnom = anomalyScatterData.some((a) => a.dateStr === dateStr)
        if (isAnom) {
          html += `<div class="text-rose-400 font-bold flex items-center gap-1 mb-1">⚠️ Flagged Statistical Anomaly</div>`
        }

        params.forEach((item: any) => {
          if (item.value != null) {
            const val = typeof item.value === 'number' ? item.value.toFixed(1) : item.value
            html += `<div class="flex items-center justify-between gap-3 text-xs">`
            html += `<span style="color:${item.color}">${item.seriesName}:</span>`
            html += `<strong class="text-slate-100">${val}</strong>`
            html += `</div>`
          }
        })
        html += `</div>`
        return html
      },
    },
    legend: {
      data: [
        `${syndrome} Daily Cases`,
        'Expected Baseline',
        'Surge Threshold',
        ...(showMobilityOverlay ? ['Mobility (% Dev)'] : []),
      ],
      textStyle: {
        color: '#94a3b8',
        fontSize: 11,
      },
      top: 0,
      right: 10,
    },
    grid: {
      left: '3%',
      right: showMobilityOverlay ? '5%' : '3%',
      bottom: '15%',
      top: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      splitLine: { show: false },
    },
    yAxis: [
      {
        type: 'value' as const,
        name: 'Report Count',
        nameTextStyle: { color: '#94a3b8', fontSize: 11 },
        axisLine: { lineStyle: { color: '#334155' } },
        axisLabel: { color: '#94a3b8', fontSize: 10 },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      ...(showMobilityOverlay
        ? [
            {
              type: 'value' as const,
              name: 'Mobility (% Dev)',
              nameTextStyle: { color: '#a855f7', fontSize: 11 },
              axisLine: { lineStyle: { color: '#a855f7' } },
              axisLabel: {
                color: '#a855f7',
                fontSize: 10,
                formatter: '{value}%',
              },
              splitLine: { show: false },
            },
          ]
        : []),
    ],
    dataZoom: [
      {
        type: 'slider',
        show: true,
        bottom: 5,
        height: 20,
        borderColor: '#1e293b',
        fillerColor: 'rgba(34, 211, 238, 0.15)',
        textStyle: { color: '#94a3b8', fontSize: 10 },
        start: 0,
        end: 100,
      },
      {
        type: 'inside',
      },
    ],
    series,
  }

  const handleChartClick = (params: any) => {
    if (params && params.name && onSelectAnomalyDate) {
      const clickedDate = params.name.replace('Anomaly: ', '')
      onSelectAnomalyDate(clickedDate)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              Time-Series Anomaly & Mobility Explorer ({regionId})
            </CardTitle>
            <CardDescription>
              {regionName} — Daily {syndrome} counts, rolling statistical baseline, threshold limit, and surge markers.
            </CardDescription>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onToggleMobilityOverlay(!showMobilityOverlay)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
                showMobilityOverlay
                  ? 'bg-purple-950/80 border-purple-500 text-purple-200'
                  : 'bg-navy-950 border-navy-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-3.5 h-3.5 text-purple-400" />
              <span>{showMobilityOverlay ? 'Hide Mobility Overlay' : 'Overlay Mobility Indicator'}</span>
            </button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-6 pt-0 space-y-3">
        <EChartWrapper
          options={options}
          height={340}
          onChartClick={handleChartClick}
        />

        <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-navy-800">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-cyan-400" />
              Observed Count
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 border-b border-dashed border-slate-400" />
              Baseline (MAD)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 border-b border-dotted border-amber-400" />
              Threshold
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
              Flagged Anomaly ({anomalyScatterData.length})
            </span>
            {showMobilityOverlay && (
              <span className="flex items-center gap-1.5 text-purple-300">
                <span className="w-3 h-0.5 bg-purple-400" />
                Mobility Deviation %
              </span>
            )}
          </div>
          <span className="text-[10px] text-slate-500 font-mono">
            Pan & zoom with slider below
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
