import React from 'react'
import {
  Activity,
  AlertTriangle,
  Bot,
  FileText,
  FlaskConical,
  Globe,
  HeartPulse,
  LayoutDashboard,
  Navigation,
  Settings,
  Shield,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export type NavItemKey =
  | 'command-center'
  | 'geospatial'
  | 'surveillance'
  | 'anomalies'
  | 'mobility'
  | 'evidence'
  | 'assistant'
  | 'pipeline'
  | 'health'
  | 'settings'

interface SidebarProps {
  currentRoute: NavItemKey
  onNavigate: (route: NavItemKey) => void
  isMobileOpen?: boolean
  onCloseMobile?: () => void
}

interface NavItemDef {
  key: NavItemKey
  label: string
  icon: React.ReactNode
  badge?: string
  badgeVariant?: 'cyan' | 'slate' | 'amber'
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentRoute,
  onNavigate,
  isMobileOpen = false,
  onCloseMobile,
}) => {
  const navItems: NavItemDef[] = [
    {
      key: 'command-center',
      label: 'Command Center',
      icon: <LayoutDashboard className="w-4 h-4" />,
    },
    {
      key: 'geospatial',
      label: 'Geospatial Intelligence',
      icon: <Globe className="w-4 h-4" />,
      badge: 'Phase 7',
      badgeVariant: 'cyan',
    },
    {
      key: 'surveillance',
      label: 'Surveillance Explorer',
      icon: <Activity className="w-4 h-4" />,
    },
    {
      key: 'anomalies',
      label: 'Anomaly Intelligence',
      icon: <AlertTriangle className="w-4 h-4" />,
    },
    {
      key: 'mobility',
      label: 'Mobility Analytics',
      icon: <Navigation className="w-4 h-4" />,
    },
    {
      key: 'evidence',
      label: 'Evidence Library',
      icon: <FileText className="w-4 h-4" />,
      badge: 'Phase 6A',
      badgeVariant: 'cyan',
    },
    {
      key: 'assistant',
      label: 'AI Intelligence Assistant',
      icon: <Bot className="w-4 h-4" />,
      badge: 'Preview',
      badgeVariant: 'slate',
    },
    {
      key: 'pipeline',
      label: 'Pipeline Lab',
      icon: <FlaskConical className="w-4 h-4" />,
    },
    {
      key: 'health',
      label: 'System Health',
      icon: <HeartPulse className="w-4 h-4" />,
    },
    {
      key: 'settings',
      label: 'Settings',
      icon: <Settings className="w-4 h-4" />,
    },
  ]

  const handleSelect = (key: NavItemKey) => {
    onNavigate(key)
    if (onCloseMobile) onCloseMobile()
  }

  return (
    <>
      {/* Mobile overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden backdrop-blur-xs"
          onClick={onCloseMobile}
        />
      )}

      <aside
        className={cn(
          "fixed top-0 bottom-0 left-0 z-40 w-64 bg-navy-950 border-r border-navy-800/80 flex flex-col transition-transform duration-200 lg:static lg:translate-x-0",
          isMobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Brand */}
        <div className="h-16 px-6 border-b border-navy-800/80 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-teal-600 flex items-center justify-center text-white shadow-md shadow-cyan-950/40">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight text-slate-100 font-sans">
                Sentinel<span className="text-cyan-400 font-normal">Ops</span>
              </h1>
              <p className="text-[10px] text-slate-400 tracking-wider uppercase font-mono">
                Public Health AI
              </p>
            </div>
          </div>
        </div>

        {/* Navigation list */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <div className="px-3 pb-2 text-[10px] font-semibold text-slate-400 tracking-wider uppercase">
            Surveillance & Analysis
          </div>
          {navItems.slice(0, 5).map((item) => {
            const isActive = currentRoute === item.key
            return (
              <button
                key={item.key}
                onClick={() => handleSelect(item.key)}
                className={cn(
                  "w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all group text-left",
                  isActive
                    ? "bg-navy-850 text-cyan-300 font-semibold border border-cyan-500/30 shadow-sm shadow-black/20"
                    : "text-slate-400 hover:text-slate-200 hover:bg-navy-900"
                )}
              >
                <div className="flex items-center gap-3">
                  <span
                    className={cn(
                      "transition-colors",
                      isActive ? "text-cyan-400" : "text-slate-400 group-hover:text-slate-300"
                    )}
                  >
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span
                    className={cn(
                      "text-[10px] px-1.5 py-0.5 rounded font-mono uppercase",
                      item.badgeVariant === 'cyan'
                        ? "bg-cyan-950 text-cyan-400 border border-cyan-800/60"
                        : "bg-navy-800 text-slate-400 border border-navy-700"
                    )}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            )
          })}

          <div className="pt-4 px-3 pb-2 text-[10px] font-semibold text-slate-400 tracking-wider uppercase">
            Operations & Lab
          </div>
          {navItems.slice(5).map((item) => {
            const isActive = currentRoute === item.key
            return (
              <button
                key={item.key}
                onClick={() => handleSelect(item.key)}
                className={cn(
                  "w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all group text-left",
                  isActive
                    ? "bg-navy-850 text-cyan-300 font-semibold border border-cyan-500/30 shadow-sm shadow-black/20"
                    : "text-slate-400 hover:text-slate-200 hover:bg-navy-900"
                )}
              >
                <div className="flex items-center gap-3">
                  <span
                    className={cn(
                      "transition-colors",
                      isActive ? "text-cyan-400" : "text-slate-400 group-hover:text-slate-300"
                    )}
                  >
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span
                    className={cn(
                      "text-[10px] px-1.5 py-0.5 rounded font-mono uppercase",
                      item.badgeVariant === 'cyan'
                        ? "bg-cyan-950 text-cyan-400 border border-cyan-800/60"
                        : "bg-navy-800 text-slate-400 border border-navy-700"
                    )}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            )
          })}
        </nav>

        {/* System footer indicator */}
        <div className="p-4 border-t border-navy-800/80 bg-navy-950/60">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span>FastAPI Backend</span>
            </span>
            <span className="font-mono text-[11px] text-slate-400">v1 (REST)</span>
          </div>
        </div>
      </aside>
    </>
  )
}
