import React from 'react'
import { AlertCircle } from 'lucide-react'

export const NoticeBanner: React.FC = () => {
  return (
    <div className="bg-navy-900/90 border-b border-navy-800/80 px-4 py-2 text-xs text-slate-300 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2 overflow-hidden">
        <AlertCircle className="w-4 h-4 text-cyan-400 shrink-0" />
        <span className="truncate">
          <strong className="text-cyan-300 font-semibold uppercase tracking-wider text-[11px] mr-1">
            Research Prototype:
          </strong>
          All surveillance observations, mobility indicators, and anomaly detection results are synthetic mathematical simulations. Anomalies indicate statistical surge deviations and do not constitute confirmed epidemiological diagnoses.
        </span>
      </div>
      <div className="hidden sm:flex items-center gap-2 shrink-0 text-[11px] text-slate-400">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
        <span>Synthetic Benchmark Environment</span>
      </div>
    </div>
  )
}
