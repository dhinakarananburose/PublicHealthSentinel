import React from 'react'
import { cn } from '@/lib/utils'
import { Loader2 } from 'lucide-react'

interface LoadingSpinnerProps {
  className?: string
  text?: string
  size?: 'sm' | 'md' | 'lg'
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  className,
  text = 'Loading intelligence data...',
  size = 'md',
}) => {
  const sizeMap = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  }

  return (
    <div className={cn("flex flex-col items-center justify-center py-12 px-4 gap-3", className)}>
      <Loader2 className={cn("animate-spin text-cyan-400", sizeMap[size])} />
      {text && <p className="text-xs text-slate-400 animate-pulse">{text}</p>}
    </div>
  )
}
