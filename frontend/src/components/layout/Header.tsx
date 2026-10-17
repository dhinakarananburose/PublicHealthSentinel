import React from 'react'
import { Menu, RefreshCw } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { Badge } from '@/components/common/Badge'
import { formatDateTime } from '@/lib/utils'

interface HeaderProps {
  title: string
  subtitle?: string
  lastUpdated?: Date | null
  isHealthy?: boolean
  isLoading?: boolean
  onRefresh?: () => void
  onToggleMobileMenu?: () => void
}

export const Header: React.FC<HeaderProps> = ({
  title,
  subtitle,
  lastUpdated,
  isHealthy = true,
  isLoading = false,
  onRefresh,
  onToggleMobileMenu,
}) => {
  return (
    <header className="h-16 px-6 border-b border-navy-800/80 bg-navy-950/70 backdrop-blur-md sticky top-0 z-30 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleMobileMenu}
          className="lg:hidden p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-navy-900 focus:outline-none"
          aria-label="Toggle navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div>
          <h2 className="text-base font-semibold text-slate-100 tracking-tight flex items-center gap-2">
            {title}
          </h2>
          {subtitle && (
            <p className="text-xs text-slate-400 hidden sm:block truncate max-w-md">
              {subtitle}
            </p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* System Health Badge */}
        <div className="hidden md:flex items-center gap-2">
          <Badge
            variant={isHealthy ? 'success' : 'danger'}
            size="sm"
            className="gap-1.5"
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isHealthy ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
              }`}
            />
            {isHealthy ? 'API Online' : 'API Degraded'}
          </Badge>
        </div>

        {/* Last update timestamp */}
        {lastUpdated && (
          <span className="text-[11px] text-slate-400 font-mono hidden xl:inline-block">
            Updated: {formatDateTime(lastUpdated.toISOString())}
          </span>
        )}

        {/* Refresh Action */}
        {onRefresh && (
          <Button
            size="sm"
            variant="secondary"
            onClick={onRefresh}
            isLoading={isLoading}
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />}
            className="text-xs"
          >
            Refresh
          </Button>
        )}
      </div>
    </header>
  )
}
