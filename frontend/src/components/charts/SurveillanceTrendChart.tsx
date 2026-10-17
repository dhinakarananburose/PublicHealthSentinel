import React, { useMemo } from 'react'
import { EChartWrapper } from './EChartWrapper'
import type { SurveillanceObservation } from '@/types/api'
import type { EChartsOption } from 'echarts'

interface SurveillanceTrendChartProps {
  data: SurveillanceObservation[]
  height?: number | string
  onPointClick?: (date: string, syndrome: string) => void
}

export const SurveillanceTrendChart: React.FC<SurveillanceTrendChartProps> = ({
  data,
  height = 340,
  onPointClick,
}) => {
  const options = useMemo<EChartsOption>(() => {
    if (!data || data.length === 0) {
      return {
        title: {
          text: 'No surveillance records available',
          left: 'center',
          top: 'center',
          textStyle: { color: '#64748b', fontSize: 13 },
        },
      }
    }

    // Extract unique dates and syndromes
    const dates = Array.from(new Set(data.map((d) => d.observation_date))).sort()
    const syndromes = Array.from(new Set(data.map((d) => d.syndrome))).sort()

    const colors = ['#06b6d4', '#14b8a6', '#f59e0b', '#f43f5e', '#a855f7', '#3b82f6']

    const series = syndromes.map((syndrome, idx) => {
      // Build a map of date -> sum of report_count across regions
      const countByDate = new Map<string, number>()
      data
        .filter((d) => d.syndrome === syndrome)
        .forEach((d) => {
          const current = countByDate.get(d.observation_date) || 0
          countByDate.set(d.observation_date, current + d.report_count)
        })

      const seriesData = dates.map((date) => countByDate.get(date) || 0)

      return {
        name: syndrome,
        type: 'line' as const,
        smooth: true,
        showSymbol: false,
        symbolSize: 6,
        data: seriesData,
        itemStyle: { color: colors[idx % colors.length] },
        lineStyle: { width: 2 },
        areaStyle: {
          color: {
            type: 'linear' as const,
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: `${colors[idx % colors.length]}33` },
              { offset: 1, color: `${colors[idx % colors.length]}00` },
            ],
          },
        },
      }
    })

    return {
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#0d1629',
        borderColor: '#24355c',
        textStyle: { color: '#e2e8f0', fontSize: 12 },
        axisPointer: {
          type: 'cross',
          label: { backgroundColor: '#1e293b' },
          lineStyle: { color: '#334155', type: 'dashed' },
        },
      },
      legend: {
        data: syndromes,
        top: 0,
        textStyle: { color: '#94a3b8', fontSize: 11 },
        itemWidth: 12,
        itemHeight: 8,
      },
      grid: {
        top: 40,
        left: 45,
        right: 25,
        bottom: 55,
      },
      xAxis: {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: '#24355c' } },
        axisLabel: {
          color: '#64748b',
          fontSize: 10,
          formatter: (value: string) => {
            const parts = value.split('-')
            return parts.length >= 3 ? `${parts[1]}/${parts[2]}` : value
          },
        },
      },
      yAxis: {
        type: 'value',
        name: 'Report Count',
        nameTextStyle: { color: '#64748b', fontSize: 10, align: 'right' },
        axisLine: { show: false },
        axisLabel: { color: '#64748b', fontSize: 10 },
        splitLine: { lineStyle: { color: '#131e36', type: 'dashed' } },
      },
      dataZoom: [
        {
          type: 'inside',
          start: 0,
          end: 100,
        },
        {
          type: 'slider',
          show: true,
          bottom: 5,
          height: 18,
          borderColor: '#1e293b',
          fillerColor: 'rgba(6, 182, 212, 0.15)',
          handleStyle: { color: '#06b6d4' },
          textStyle: { color: '#64748b', fontSize: 9 },
        },
      ],
      series,
    }
  }, [data])

  return (
    <EChartWrapper
      options={options}
      height={height}
      onChartClick={(params) => {
        if (onPointClick && params.name && params.seriesName) {
          onPointClick(params.name, params.seriesName)
        }
      }}
    />
  )
}
