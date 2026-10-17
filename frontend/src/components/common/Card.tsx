import React from 'react'
import { cn } from '@/lib/utils'

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  elevated?: boolean
}

export const Card: React.FC<CardProps> = ({
  className,
  elevated = false,
  children,
  ...props
}) => {
  return (
    <div
      className={cn(
        "rounded-xl border transition-all duration-200",
        elevated
          ? "bg-navy-900 border-navy-700/80 shadow-lg shadow-black/40"
          : "bg-navy-900/90 border-navy-800/80 hover:border-navy-700/80",
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <div
      className={cn(
        "px-5 py-4 border-b border-navy-800/80 flex items-center justify-between gap-4",
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export const CardTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <h3
      className={cn("text-base font-semibold text-slate-100 tracking-tight", className)}
      {...props}
    >
      {children}
    </h3>
  )
}

export const CardDescription: React.FC<React.HTMLAttributes<HTMLParagraphElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <p
      className={cn("text-xs text-slate-400 mt-0.5 leading-relaxed", className)}
      {...props}
    >
      {children}
    </p>
  )
}

export const CardContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <div className={cn("p-5", className)} {...props}>
      {children}
    </div>
  )
}

export const CardFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <div
      className={cn("px-5 py-3 border-t border-navy-800/80 bg-navy-950/40 rounded-b-xl", className)}
      {...props}
    >
      {children}
    </div>
  )
}
