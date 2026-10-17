import React, { useEffect, useRef } from 'react'
import * as echarts from 'echarts'
import { cn } from '@/lib/utils'

interface EChartWrapperProps {
  options: echarts.EChartsOption
  className?: string
  height?: string | number
  onChartClick?: (params: any) => void
}

export const EChartWrapper: React.FC<EChartWrapperProps> = ({
  options,
  className,
  height = 320,
  onChartClick,
}) => {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!chartRef.current) return

    // Initialize chart instance with dark theme options
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, 'dark', {
        renderer: 'canvas',
      })

      if (onChartClick) {
        chartInstance.current.on('click', onChartClick)
      }
    }

    // Apply baseline default enterprise theme settings
    const themeOptions: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      textStyle: {
        fontFamily: 'Inter, sans-serif',
      },
      ...options,
    }

    chartInstance.current.setOption(themeOptions, true)

    // Window and container resize observer
    const handleResize = () => {
      chartInstance.current?.resize()
    }

    const resizeObserver = new ResizeObserver(() => {
      chartInstance.current?.resize()
    })

    resizeObserver.observe(chartRef.current)
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      resizeObserver.disconnect()
      if (chartInstance.current) {
        chartInstance.current.dispose()
        chartInstance.current = null
      }
    }
  }, [options, onChartClick])

  return (
    <div
      ref={chartRef}
      style={{ height, width: '100%' }}
      className={cn("w-full transition-opacity duration-300", className)}
    />
  )
}
