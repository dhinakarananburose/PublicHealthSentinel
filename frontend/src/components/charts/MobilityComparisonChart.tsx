import React, { useMemo } from 'react'
import { EChartWrapper } from './EChartWrapper'
import type { MobilityIndicator } from '@/types/api'
import type { EChartsOption } from 'echarts'

interface MobilityComparisonChartProps {
  data: MobilityIndicator[]
  height?: number | string
}

export const MobilityComparisonChart: React.FC<MobilityComparisonChartProps> = ({
  data,
  height = 320,
}) => {
  const options = useMemo<EChartsOption>(() => {
    if (!data || data.length === 0) {
      return {
        title: {
          text: 'No mobility indicator records available',
          left: 'center',
          top: 'center',
          textStyle: { color: '#64748b', fontSize: 13 },
        },
      }
    }

    const dates = Array.from(new Set(data.map((d) => d.observation_date))).sort()
    const regions = Array.from(new Set(data.map((d) => d.region_id))).sort()
    const metric = data[0]?.mobility_metric || 'Mobility Value'

    const colors = ['#22d3ee', '#34d399', '#fbbf24', '#f87171', '#c084fc']

    const series = regions.map((region, idx) => {
      const valueByDate = new Map<string, number>()
      data
        .filter((d) => d.region_id === region)
        .forEach((d) => valueByDate.set(d.observation_date, d.mobility_value))

      const seriesData = dates.map((date) => valueByDate.get(date) ?? null)

      return {
        name: region,
        type: 'line' as const,
        smooth: true,
        showSymbol: false,
        data: seriesData,
        itemStyle: { color: colors[idx % colors.length] },
        lineStyle: { width: 2 },
      }
    })

    return {
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#0d1629',
        borderColor: '#24355c',
        textStyle: { color: '#e2e8f0', fontSize: 12 },
      },
      legend: {
        data: regions,
        top: 0,
        textStyle: { color: '#94a3b8', fontSize: 11 },
      },
      grid: {
        top: 35,
        left: 45,
        right: 25,
        bottom: 50,
      },
      xAxis: {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: '#24355c' } },
        axisLabel: {
          color: '#64748b',
          fontSize: 10,
          formatter: (val: string) => {
            const p = val.split('-')
            return p.length >= 3 ? `${p[1]}/${p[2]}` : val
          },
        },
      },
      yAxis: {
        type: 'value',
        name: `${metric} (%)`,
        nameTextStyle: { color: '#64748b', fontSize: 10, align: 'right' },
        axisLine: { show: false },
        axisLabel: { color: '#64748b', fontSize: 10 },
        splitLine: { lineStyle: { color: '#131e36', type: 'dashed' } },
      },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        {
          type: 'slider',
          show: true,
          bottom: 5,
          height: 18,
          borderColor: '#1e293b',
          fillerColor: 'rgba(20, 184, 166, 0.15)',
          handleStyle: { color: '#14b8a6' },
          textStyle: { color: '#64748b', fontSize: 9 },
        },
      ],
      series,
    }
  }, [data])

  return <EChartWrapper options={options} height={height} />
}
