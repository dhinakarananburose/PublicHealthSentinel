import React from 'react'
import { cn } from '@/lib/utils'
import { AlertTriangle, RotateCcw } from 'lucide-react'
import { Button } from './Button'

interface ErrorStateProps {
  className?: string
  title?: string
  message: string
  onRetry?: () => void
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  className,
  title = 'Failed to load intelligence data',
  message,
  onRetry,
}) => {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-12 px-6 text-center rounded-xl border border-rose-900/50 bg-rose-950/20",
        className
      )}
    >
      <div className="w-12 h-12 rounded-xl bg-rose-950/60 border border-rose-800/80 flex items-center justify-center text-rose-400 mb-4 shadow-inner">
        <AlertTriangle className="w-6 h-6" />
      </div>
      <h4 className="text-sm font-semibold text-rose-200">{title}</h4>
      <p className="text-xs text-rose-300/80 mt-1.5 max-w-md font-mono break-words leading-relaxed">
        {message}
      </p>
      {onRetry && (
        <Button
          size="sm"
          variant="secondary"
          onClick={onRetry}
          leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
          className="mt-4 border-rose-800/60 hover:border-rose-700"
        >
          Retry Request
        </Button>
      )}
    </div>
  )
}
