import React from 'react'
import { cn } from '@/lib/utils'
import { Loader2 } from 'lucide-react'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'ghost' | 'teal'
  size?: 'sm' | 'md' | 'lg'
  isLoading?: boolean
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      leftIcon,
      rightIcon,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const base =
      "inline-flex items-center justify-center font-medium rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-cyan-500/40 disabled:opacity-50 disabled:cursor-not-allowed select-none active:scale-[0.98]"

    const sizeStyles = {
      sm: "px-3 py-1.5 text-xs gap-1.5",
      md: "px-4 py-2 text-sm gap-2",
      lg: "px-5 py-2.5 text-base gap-2.5",
    }

    const variantStyles = {
      primary:
        "bg-cyan-600 hover:bg-cyan-500 text-white shadow-sm shadow-cyan-950/50 border border-cyan-500/50",
      teal:
        "bg-teal-600 hover:bg-teal-500 text-white shadow-sm shadow-teal-950/50 border border-teal-500/50",
      secondary:
        "bg-navy-800 hover:bg-navy-750 text-slate-200 border border-navy-700 hover:border-navy-600",
      outline:
        "border border-navy-700 hover:border-cyan-500/60 text-slate-300 hover:text-cyan-300 bg-transparent",
      danger:
        "bg-rose-700 hover:bg-rose-600 text-white shadow-sm shadow-rose-950/50 border border-rose-600/50",
      ghost:
        "bg-transparent hover:bg-navy-850 text-slate-400 hover:text-slate-200",
    }

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(base, sizeStyles[size], variantStyles[variant], className)}
        {...props}
      >
        {isLoading ? (
          <Loader2 className="w-4 h-4 animate-spin text-current" />
        ) : (
          leftIcon
        )}
        {children}
        {!isLoading && rightIcon}
      </button>
    )
  }
)

Button.displayName = 'Button'
