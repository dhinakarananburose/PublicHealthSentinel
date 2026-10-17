import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import type { RegionalSurveillanceSummary } from '@/types/api'
import { AlertCircle, CheckCircle2, Globe, MapPin, ShieldAlert, Sparkles, Users } from 'lucide-react'

interface GeospatialMapChartProps {
  regions: RegionalSurveillanceSummary[]
  selectedRegionId: string
  onSelectRegion: (regionId: string) => void
  metricType: 'cases' | 'rate'
  onMetricTypeChange: (metric: 'cases' | 'rate') => void
}

export const GeospatialMapChart: React.FC<GeospatialMapChartProps> = ({
  regions,
  selectedRegionId,
  onSelectRegion,
  metricType,
  onMetricTypeChange,
}) => {
  // Find maximum values for relative color shading
  const maxCases = Math.max(...regions.map((r) => r.total_cases), 1)
  const maxRate = Math.max(...regions.map((r) => r.crude_rate_per_100k ?? 0), 1)

  // Sector geometric positions on a 3x3 synthetic surveillance grid
  // Col 0: West (-73.5°), Col 1: Central (-72.5°), Col 2: East (-71.5°)
  // Row 0: North (42.5°), Row 1: Central (41.5°), Row 2: South (40.5°)
  const gridPositions: Record<string, { col: number; row: number; label: string; coords: string }> = {
    REGION_A: { col: 0, row: 0, label: 'Sector Alpha (Northwest)', coords: '42.50° N, -73.50° W' },
    REGION_B: { col: 2, row: 0, label: 'Sector Beta (Northeast)', coords: '42.50° N, -71.50° W' },
    REGION_C: { col: 1, row: 1, label: 'Sector Gamma (Central Metro)', coords: '41.50° N, -72.50° W' },
    REGION_D: { col: 0, row: 2, label: 'Sector Delta (Southwest)', coords: '40.50° N, -73.50° W' },
    REGION_E: { col: 2, row: 2, label: 'Sector Epsilon (Southeast Coastal)', coords: '40.50° N, -71.50° W' },
  }

  const getIntensityColor = (region: RegionalSurveillanceSummary, isSelected: boolean) => {
    const val = metricType === 'cases' ? region.total_cases : (region.crude_rate_per_100k ?? 0)
    const maxVal = metricType === 'cases' ? maxCases : maxRate
    const ratio = Math.min(Math.max(val / maxVal, 0.15), 1.0)

    if (isSelected) {
      return 'border-cyan-400 bg-cyan-950/90 ring-2 ring-cyan-400/80 shadow-lg shadow-cyan-500/20'
    }

    if (region.recent_anomaly_detected) {
      return 'border-rose-800/80 bg-navy-900/90 hover:border-rose-500 hover:bg-rose-950/30'
    }

    if (ratio > 0.7) {
      return 'border-cyan-800 bg-navy-900/90 hover:border-cyan-500/80 hover:bg-navy-850'
    }
    return 'border-navy-800 bg-navy-950/90 hover:border-navy-700 hover:bg-navy-900'
  }

  return (
    <Card className="flex flex-col justify-between">
      <CardHeader>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Globe className="w-4 h-4 text-cyan-400" />
              Regional Surveillance Grid Map
            </CardTitle>
            <CardDescription>
              Interactive synthetic spatial sectors. Click a sector to focus surveillance, anomaly, and mobility analytics.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-400">Color Shading:</span>
            <div className="flex rounded-lg bg-navy-950 border border-navy-800 p-0.5 text-xs">
              <button
                type="button"
                onClick={() => onMetricTypeChange('cases')}
                className={`px-2.5 py-1 rounded text-[11px] font-medium transition-all ${
                  metricType === 'cases'
                    ? 'bg-cyan-500 text-navy-950 font-semibold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Total Cases
              </button>
              <button
                type="button"
                onClick={() => onMetricTypeChange('rate')}
                className={`px-2.5 py-1 rounded text-[11px] font-medium transition-all ${
                  metricType === 'rate'
                    ? 'bg-cyan-500 text-navy-950 font-semibold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Rate / 100k
              </button>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-6 pt-0 space-y-4">
        {/* Synthetic Geography Notice */}
        <div className="p-2.5 rounded-lg bg-navy-950 border border-navy-800 flex items-center justify-between text-[11px] text-slate-400">
          <div className="flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
            <span>
              <strong>Synthetic Geographic Grid:</strong> Sectors represent abstract benchmark geometries (Alpha–Epsilon).
            </span>
          </div>
          <Badge variant="outline" size="sm" className="text-[10px] uppercase font-mono">
            Simulated Space
          </Badge>
        </div>

        {/* 3x3 Schematic Spatial Grid */}
        <div className="grid grid-cols-3 gap-3 p-4 rounded-xl bg-navy-950/70 border border-navy-800/80 min-h-[380px] relative">
          {/* Compass Rose Header */}
          <div className="absolute top-2 right-3 text-[10px] font-mono text-slate-500 flex flex-col items-center">
            <span>N ↑</span>
            <span>W ← → E</span>
            <span>S ↓</span>
          </div>

          {/* Render 5 Regions mapped to their geographic positions */}
          {regions.map((region) => {
            const pos = gridPositions[region.region_id] || { col: 1, row: 1, label: region.region_name, coords: '' }
            const isSelected = selectedRegionId === region.region_id

            // Calculate grid placement
            // Grid styles: row-start-(1,2,3), col-start-(1,2,3)
            const rowClass = pos.row === 0 ? 'row-start-1' : pos.row === 1 ? 'row-start-2' : 'row-start-3'
            const colClass = pos.col === 0 ? 'col-start-1' : pos.col === 1 ? 'col-start-2' : 'col-start-3'

            return (
              <div
                key={region.region_id}
                onClick={() => onSelectRegion(region.region_id)}
                className={`${rowClass} ${colClass} p-4 rounded-xl border cursor-pointer transition-all flex flex-col justify-between ${getIntensityColor(
                  region,
                  isSelected
                )}`}
              >
                <div>
                  <div className="flex items-start justify-between gap-1 mb-1.5">
                    <div className="flex items-center gap-1.5">
                      <MapPin className={`w-3.5 h-3.5 ${isSelected ? 'text-cyan-400' : 'text-slate-400'}`} />
                      <span className="font-bold text-xs text-slate-100">{region.region_id}</span>
                    </div>
                    {region.recent_anomaly_detected ? (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-300 border border-rose-700 animate-pulse">
                        <ShieldAlert className="w-3 h-3 text-rose-400" />
                        {region.anomaly_count} Anom
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] text-emerald-400 bg-emerald-950/60 border border-emerald-800/60">
                        <CheckCircle2 className="w-3 h-3" />
                        Normal
                      </span>
                    )}
                  </div>

                  <p className="text-[11px] font-medium text-slate-300 leading-snug">{pos.label}</p>
                  <p className="text-[10px] font-mono text-slate-500 mt-0.5">{pos.coords}</p>
                </div>

                <div className="mt-3 pt-2.5 border-t border-navy-800/80 space-y-1 text-[11px]">
                  <div className="flex items-center justify-between text-slate-300">
                    <span>Total Cases:</span>
                    <strong className="font-mono text-cyan-300">{region.total_cases.toLocaleString()}</strong>
                  </div>
                  <div className="flex items-center justify-between text-slate-400 text-[10px]">
                    <span>Crude Rate:</span>
                    <span className="font-mono text-slate-200">
                      {region.crude_rate_per_100k != null ? `${region.crude_rate_per_100k.toFixed(1)}/100k` : 'N/A'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-slate-400 text-[10px]">
                    <span>Population:</span>
                    <span className="font-mono text-slate-300">{region.population.toLocaleString()}</span>
                  </div>
                </div>
              </div>
            )
          })}

          {/* Central Buffer Cell (Row 1, Col 0 & Col 2) */}
          <div className="row-start-2 col-start-1 p-2 border border-dashed border-navy-800/40 rounded-xl flex items-center justify-center text-slate-600 text-[10px] font-mono">
            West Transit Corridor
          </div>
          <div className="row-start-2 col-start-3 p-2 border border-dashed border-navy-800/40 rounded-xl flex items-center justify-center text-slate-600 text-[10px] font-mono">
            East Transit Corridor
          </div>
          <div className="row-start-1 col-start-2 p-2 border border-dashed border-navy-800/40 rounded-xl flex items-center justify-center text-slate-600 text-[10px] font-mono">
            Northern Watershed
          </div>
          <div className="row-start-3 col-start-2 p-2 border border-dashed border-navy-800/40 rounded-xl flex items-center justify-center text-slate-600 text-[10px] font-mono">
            Southern Maritime Buffer
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center justify-between flex-wrap gap-2 pt-2 text-[11px] text-slate-400">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-cyan-950 border border-cyan-400" />
              Selected Sector
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-rose-950 border border-rose-600" />
              Active Statistical Anomaly
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-navy-950 border border-navy-800" />
              Baseline Surveillance
            </span>
          </div>
          <span className="text-[10px] text-slate-500 font-mono">
            Click any sector to focus analysis
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
