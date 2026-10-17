import React from 'react'
import { cn } from '@/lib/utils'
import { Inbox } from 'lucide-react'
import { Button } from './Button'

interface EmptyStateProps {
  className?: string
  icon?: React.ReactNode
  title: string
  description?: string
  actionLabel?: string
  onAction?: () => void
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  className,
  icon,
  title,
  description,
  actionLabel,
  onAction,
}) => {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 px-6 text-center rounded-xl border border-navy-800/80 bg-navy-900/40",
        className
      )}
    >
      <div className="w-12 h-12 rounded-xl bg-navy-800/80 border border-navy-700/80 flex items-center justify-center text-slate-400 mb-4 shadow-inner">
        {icon || <Inbox className="w-6 h-6 text-slate-400" />}
      </div>
      <h4 className="text-sm font-semibold text-slate-200">{title}</h4>
      {description && (
        <p className="text-xs text-slate-400 mt-1.5 max-w-sm leading-relaxed">
          {description}
        </p>
      )}
      {actionLabel && onAction && (
        <Button
          size="sm"
          variant="secondary"
          onClick={onAction}
          className="mt-4"
        >
          {actionLabel}
        </Button>
      )}
    </div>
  )
}
