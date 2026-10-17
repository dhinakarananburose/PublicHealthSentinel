import React, { useMemo } from 'react'
import { EChartWrapper } from './EChartWrapper'
import type { AnomalyResult } from '@/types/api'
import type { EChartsOption } from 'echarts'

interface AnomalyScoreChartProps {
  data: AnomalyResult[]
  height?: number | string
  onAnomalyClick?: (anomaly: AnomalyResult) => void
}

export const AnomalyScoreChart: React.FC<AnomalyScoreChartProps> = ({
  data,
  height = 320,
  onAnomalyClick,
}) => {
  const options = useMemo<EChartsOption>(() => {
    if (!data || data.length === 0) {
      return {
        title: {
          text: 'No anomaly records available',
          left: 'center',
          top: 'center',
          textStyle: { color: '#64748b', fontSize: 13 },
        },
      }
    }

    // Sort chronologically
    const sorted = [...data].sort(
      (a, b) => new Date(a.observation_date).getTime() - new Date(b.observation_date).getTime()
    )

    const categories = sorted.map(
      (d) => `${d.observation_date} (${d.region_id}/${d.syndrome})`
    )

    const normalData: any[] = []
    const anomalyData: any[] = []

    sorted.forEach((d, idx) => {
      const score = d.anomaly_score ?? 0
      const point = {
        value: [idx, score],
        rawRecord: d,
        itemStyle: {
          color: d.is_anomaly ? '#f43f5e' : '#0891b2',
        },
      }
      if (d.is_anomaly) {
        anomalyData.push(point)
      } else {
        normalData.push(point)
      }
    })

    const threshold = sorted[0]?.detection_threshold ?? 3.0

    return {
      tooltip: {
        trigger: 'item',
        backgroundColor: '#0d1629',
        borderColor: '#24355c',
        textStyle: { color: '#e2e8f0', fontSize: 12 },
        formatter: (params: any) => {
          const rec: AnomalyResult = params.data?.rawRecord
          if (!rec) return ''
          return `
            <div style="font-weight: 600; margin-bottom: 4px; color: ${rec.is_anomaly ? '#f43f5e' : '#38bdf8'}">
              ${rec.is_anomaly ? '⚠️ STATISTICAL SURGE ANOMALY' : '✓ Normal Observation'}
            </div>
            <div><strong>Date:</strong> ${rec.observation_date}</div>
            <div><strong>Region:</strong> ${rec.region_id}</div>
            <div><strong>Syndrome:</strong> ${rec.syndrome}</div>
            <div><strong>Observed:</strong> ${rec.observed_count} (Exp: ${rec.expected_baseline?.toFixed(1) ?? '—'})</div>
            <div><strong>Anomaly Score:</strong> ${rec.anomaly_score?.toFixed(2)} (Threshold: ${rec.detection_threshold})</div>
            <div><strong>Method:</strong> ${rec.detection_method}</div>
          `
        },
      },
      legend: {
        data: ['Normal Score', 'Surge Anomaly', 'Threshold'],
        top: 0,
        textStyle: { color: '#94a3b8', fontSize: 11 },
      },
      grid: {
        top: 35,
        left: 45,
        right: 25,
        bottom: 40,
      },
      xAxis: {
        type: 'category',
        data: categories,
        axisLine: { lineStyle: { color: '#24355c' } },
        axisLabel: {
          show: false, // Too dense for text labels; tooltip provides full context
        },
      },
      yAxis: {
        type: 'value',
        name: 'Anomaly Score (MAD / Z-score)',
        nameTextStyle: { color: '#64748b', fontSize: 10, align: 'right' },
        axisLine: { show: false },
        axisLabel: { color: '#64748b', fontSize: 10 },
        splitLine: { lineStyle: { color: '#131e36', type: 'dashed' } },
      },
      series: [
        {
          name: 'Normal Score',
          type: 'scatter',
          symbolSize: 6,
          data: normalData,
          itemStyle: { color: '#0891b2', opacity: 0.6 },
        },
        {
          name: 'Surge Anomaly',
          type: 'scatter',
          symbolSize: 10,
          data: anomalyData,
          itemStyle: { color: '#f43f5e' },
          markLine: {
            silent: true,
            lineStyle: { color: '#f59e0b', type: 'dashed', width: 1.5 },
            data: [
              {
                yAxis: threshold,
                name: `Threshold (${threshold})`,
                label: {
                  formatter: `Threshold ${threshold}`,
                  color: '#f59e0b',
                  fontSize: 10,
                  position: 'end',
                },
              },
            ],
          },
        },
      ],
    }
  }, [data])

  return (
    <EChartWrapper
      options={options}
      height={height}
      onChartClick={(params) => {
        const raw: AnomalyResult = params.data?.rawRecord
        if (raw && onAnomalyClick) {
          onAnomalyClick(raw)
        }
      }}
    />
  )
}
