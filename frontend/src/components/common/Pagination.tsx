import React from 'react'
import { Button } from './Button'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { formatNumber } from '@/lib/utils'

interface PaginationProps {
  currentPage: number
  totalPages: number
  totalItems: number
  pageSize: number
  onPageChange: (page: number) => void
  onPageSizeChange?: (size: number) => void
  disabled?: boolean
}

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
  onPageSizeChange,
  disabled = false,
}) => {
  const startItem = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1
  const endItem = Math.min(currentPage * pageSize, totalItems)

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 px-4 py-3 border-t border-navy-800/80 bg-navy-950/40 text-xs text-slate-400">
      <div className="flex items-center gap-3">
        <span>
          Showing <span className="font-medium text-slate-200">{startItem}</span> to{' '}
          <span className="font-medium text-slate-200">{endItem}</span> of{' '}
          <span className="font-medium text-slate-200">{formatNumber(totalItems)}</span> records
        </span>

        {onPageSizeChange && (
          <div className="flex items-center gap-1.5 ml-2">
            <span>Per page:</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              disabled={disabled}
              className="bg-navy-900 border border-navy-700 text-slate-200 rounded px-2 py-0.5 text-xs focus:outline-none focus:border-cyan-500"
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2">
        <span className="mr-2">
          Page <span className="font-medium text-slate-200">{currentPage}</span> of{' '}
          <span className="font-medium text-slate-200">{Math.max(1, totalPages)}</span>
        </span>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={disabled || currentPage <= 1}
          leftIcon={<ChevronLeft className="w-3.5 h-3.5" />}
        >
          Prev
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={disabled || currentPage >= totalPages || totalPages === 0}
          rightIcon={<ChevronRight className="w-3.5 h-3.5" />}
        >
          Next
        </Button>
      </div>
    </div>
  )
}
