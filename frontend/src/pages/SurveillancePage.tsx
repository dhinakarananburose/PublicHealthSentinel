import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Pagination } from '@/components/common/Pagination'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'
import { Modal } from '@/components/common/Modal'
import { formatNumber } from '@/lib/utils'
import type { SurveillanceObservation } from '@/types/api'
import {
  Activity,
  Calendar,
  Eye,
  Filter,
  RefreshCw,
  Search,
  X,
} from 'lucide-react'

export const SurveillancePage: React.FC = () => {
  const [page, setPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(25)
  const [regionFilter, setRegionFilter] = useState<string>('')
  const [syndromeFilter, setSyndromeFilter] = useState<string>('')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [searchTerm, setSearchTerm] = useState<string>('')
  const [selectedRecord, setSelectedRecord] = useState<SurveillanceObservation | null>(null)

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['surveillance_explorer', { page, pageSize, regionFilter, syndromeFilter, startDate, endDate }],
    queryFn: () =>
      api.getSurveillance({
        page,
        page_size: pageSize,
        region_id: regionFilter || undefined,
        syndrome: syndromeFilter || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      }),
  })

  const resetFilters = () => {
    setRegionFilter('')
    setSyndromeFilter('')
    setStartDate('')
    setEndDate('')
    setSearchTerm('')
    setPage(1)
  }

  const hasActiveFilters = Boolean(
    regionFilter || syndromeFilter || startDate || endDate || searchTerm
  )

  // Filter items in-memory by search term (for region or syndrome substring)
  const filteredItems = (data?.items || []).filter((item) => {
    if (!searchTerm) return true
    const term = searchTerm.toLowerCase()
    return (
      item.region_id.toLowerCase().includes(term) ||
      item.syndrome.toLowerCase().includes(term) ||
      item.data_source.toLowerCase().includes(term)
    )
  })

  return (
    <div className="space-y-6">
      {/* Header card with filters */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              Surveillance Observations Explorer
            </CardTitle>
            <CardDescription>
              Explore, filter, and inspect aggregated daily symptom reports across jurisdictions.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => refetch()}
              isLoading={isFetching}
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />}
            >
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Filter row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {/* Search */}
            <div className="relative">
              <label className="block text-xs font-medium text-slate-300 mb-1">Search Scope</label>
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
                <input
                  type="text"
                  placeholder="Region, syndrome, source..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            {/* Region select */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Jurisdiction</label>
              <select
                value={regionFilter}
                onChange={(e) => {
                  setRegionFilter(e.target.value)
                  setPage(1)
                }}
                className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="">All Regions</option>
                <option value="REGION_A">REGION_A</option>
                <option value="REGION_B">REGION_B</option>
                <option value="REGION_C">REGION_C</option>
                <option value="REGION_D">REGION_D</option>
                <option value="REGION_E">REGION_E</option>
              </select>
            </div>

            {/* Syndrome select */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Syndrome Cluster</label>
              <select
                value={syndromeFilter}
                onChange={(e) => {
                  setSyndromeFilter(e.target.value)
                  setPage(1)
                }}
                className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="">All Syndromes</option>
                <option value="Respiratory">Respiratory</option>
                <option value="Gastrointestinal">Gastrointestinal</option>
                <option value="Febrile">Febrile</option>
              </select>
            </div>

            {/* Date Range Start */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Earliest Date</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => {
                  setStartDate(e.target.value)
                  setPage(1)
                }}
                className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-200 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* Date Range End */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Latest Date</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => {
                  setEndDate(e.target.value)
                  setPage(1)
                }}
                className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-200 focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>

          {hasActiveFilters && (
            <div className="flex items-center justify-between pt-2 border-t border-navy-800 text-xs">
              <span className="text-slate-400">
                Active filter query applied to surveillance observations database.
              </span>
              <button
                onClick={resetFilters}
                className="text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-medium"
              >
                <X className="w-3.5 h-3.5" />
                Clear All Filters
              </button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Observations Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <LoadingSpinner text="Retrieving surveillance records from database..." />
          ) : isError ? (
            <div className="p-6">
              <ErrorState
                message={(error as any)?.message || 'Failed to query surveillance observations.'}
                onRetry={() => refetch()}
              />
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="p-6">
              <EmptyState
                icon={<Activity className="w-6 h-6 text-slate-400" />}
                title="No surveillance observations found"
                description="Try adjusting your date range, syndrome filter, or clearing search criteria."
                actionLabel={hasActiveFilters ? 'Reset Filters' : undefined}
                onAction={resetFilters}
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-navy-950/70 border-b border-navy-800 text-slate-400 uppercase tracking-wider font-mono text-[11px]">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Date</th>
                    <th className="px-4 py-3 font-semibold">Region</th>
                    <th className="px-4 py-3 font-semibold">Syndrome</th>
                    <th className="px-4 py-3 font-semibold">Report Count</th>
                    <th className="px-4 py-3 font-semibold">Crude Incidence (/100k)</th>
                    <th className="px-4 py-3 font-semibold">Facilities</th>
                    <th className="px-4 py-3 font-semibold">Source</th>
                    <th className="px-5 py-3 font-semibold text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-navy-800/60 text-slate-200">
                  {filteredItems.map((obs) => (
                    <tr
                      key={obs.id}
                      onClick={() => setSelectedRecord(obs)}
                      className="hover:bg-navy-850/60 transition-colors cursor-pointer group"
                    >
                      <td className="px-5 py-3 font-mono font-medium text-slate-300">
                        {obs.observation_date}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline">{obs.region_id}</Badge>
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-200">
                        {obs.syndrome}
                      </td>
                      <td className="px-4 py-3 font-mono font-semibold text-cyan-400">
                        {formatNumber(obs.report_count)}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-300">
                        {obs.crude_incidence_per_100k !== null
                          ? `${obs.crude_incidence_per_100k} / 100k`
                          : '—'}
                      </td>
                      <td className="px-4 py-3 text-slate-400 font-mono">
                        {obs.reporting_facility_count ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-slate-400 font-mono text-[11px]">
                        {obs.data_source}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setSelectedRecord(obs)
                          }}
                          className="text-cyan-400 hover:text-cyan-300 p-1 rounded hover:bg-navy-800 focus:outline-none focus:ring-1 focus:ring-cyan-400"
                          title="Inspect Observation"
                          aria-label={`Inspect observation ${obs.id} for ${obs.region_id}`}
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data && data.total > 0 && (
            <Pagination
              currentPage={page}
              totalPages={data.total_pages}
              totalItems={data.total}
              pageSize={pageSize}
              onPageChange={(newPage) => setPage(newPage)}
              onPageSizeChange={(newSize) => {
                setPageSize(newSize)
                setPage(1)
              }}
              disabled={isFetching}
            />
          )}
        </CardContent>
      </Card>

      {/* Observation Detail Modal */}
      {selectedRecord && (
        <Modal
          isOpen={!!selectedRecord}
          onClose={() => setSelectedRecord(null)}
          title={`Surveillance Record #${selectedRecord.id}`}
          subtitle={`${selectedRecord.region_id} • ${selectedRecord.syndrome} • ${selectedRecord.observation_date}`}
          maxWidth="md"
        >
          <div className="space-y-4 text-xs">
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800">
                <span className="text-slate-400">Clinical Report Count:</span>
                <p className="text-xl font-bold text-cyan-400 font-mono mt-0.5">
                  {formatNumber(selectedRecord.report_count)}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800">
                <span className="text-slate-400">Crude Incidence Rate:</span>
                <p className="text-xl font-bold text-slate-200 font-mono mt-0.5">
                  {selectedRecord.crude_incidence_per_100k
                    ? `${selectedRecord.crude_incidence_per_100k} / 100k`
                    : 'N/A'}
                </p>
              </div>
            </div>

            <div className="space-y-2 pt-2 border-t border-navy-800">
              <div className="flex justify-between py-1.5 border-b border-navy-800/40">
                <span className="text-slate-400">Observation Date:</span>
                <span className="font-mono text-slate-200">{selectedRecord.observation_date}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-navy-800/40">
                <span className="text-slate-400">Region Identifier:</span>
                <Badge variant="outline">{selectedRecord.region_id}</Badge>
              </div>
              <div className="flex justify-between py-1.5 border-b border-navy-800/40">
                <span className="text-slate-400">Syndrome Cluster:</span>
                <span className="font-semibold text-slate-200">{selectedRecord.syndrome}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-navy-800/40">
                <span className="text-slate-400">Reporting Facilities:</span>
                <span className="font-mono text-slate-200">{selectedRecord.reporting_facility_count ?? 'Not Reported'}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-navy-800/40">
                <span className="text-slate-400">Population Denominator:</span>
                <span className="font-mono text-slate-200">{formatNumber(selectedRecord.population_denominator) ?? 'Unspecified'}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-navy-800/40">
                <span className="text-slate-400">Data Source:</span>
                <span className="font-mono text-slate-300">{selectedRecord.data_source}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-navy-800/40">
                <span className="text-slate-400">Data Provenance:</span>
                <Badge variant="info">{selectedRecord.data_status}</Badge>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="text-slate-400">Ingestion Timestamp:</span>
                <span className="font-mono text-slate-400 text-[11px]">{selectedRecord.ingestion_timestamp}</span>
              </div>
            </div>

            <div className="flex justify-end pt-3">
              <Button size="sm" variant="secondary" onClick={() => setSelectedRecord(null)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
