import React from 'react'
import { cn } from '@/lib/utils'

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'outline' | 'anomaly'
  size?: 'sm' | 'md'
}

export const Badge: React.FC<BadgeProps> = ({
  className,
  variant = 'default',
  size = 'md',
  children,
  ...props
}) => {
  const base = "inline-flex items-center font-medium rounded-full tracking-wide transition-colors"
  
  const sizeStyles = {
    sm: "px-2 py-0.5 text-xs",
    md: "px-2.5 py-1 text-xs",
  }

  const variantStyles = {
    default: "bg-navy-800 text-slate-300 border border-navy-700",
    success: "bg-emerald-950/80 text-emerald-400 border border-emerald-800/60",
    warning: "bg-amber-950/80 text-amber-400 border border-amber-800/60",
    danger: "bg-rose-950/80 text-rose-400 border border-rose-800/60",
    info: "bg-cyan-950/80 text-cyan-400 border border-cyan-800/60",
    outline: "border border-slate-700 text-slate-400 bg-transparent",
    anomaly: "bg-rose-900/40 text-rose-300 border border-rose-600/60 animate-pulse font-semibold",
  }

  return (
    <span
      className={cn(base, sizeStyles[size], variantStyles[variant], className)}
      {...props}
    >
      {children}
    </span>
  )
}
