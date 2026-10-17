import React, { lazy, Suspense, useState } from 'react'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api-client'
import { NoticeBanner } from '@/components/layout/NoticeBanner'
import { Header } from '@/components/layout/Header'
import { Sidebar, type NavItemKey } from '@/components/layout/Sidebar'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

const CommandCenterPage = lazy(() =>
  import('@/pages/CommandCenterPage').then((m) => ({ default: m.CommandCenterPage }))
)
const GeospatialPage = lazy(() =>
  import('@/pages/GeospatialPage').then((m) => ({ default: m.GeospatialPage }))
)
const SurveillancePage = lazy(() =>
  import('@/pages/SurveillancePage').then((m) => ({ default: m.SurveillancePage }))
)
const AnomaliesPage = lazy(() =>
  import('@/pages/AnomaliesPage').then((m) => ({ default: m.AnomaliesPage }))
)
const MobilityPage = lazy(() =>
  import('@/pages/MobilityPage').then((m) => ({ default: m.MobilityPage }))
)
const EvidenceLibraryPage = lazy(() =>
  import('@/pages/EvidenceLibraryPage').then((m) => ({ default: m.EvidenceLibraryPage }))
)
const AIAssistantPage = lazy(() =>
  import('@/pages/AIAssistantPage').then((m) => ({ default: m.AIAssistantPage }))
)
const PipelineLabPage = lazy(() =>
  import('@/pages/PipelineLabPage').then((m) => ({ default: m.PipelineLabPage }))
)
const SystemHealthPage = lazy(() =>
  import('@/pages/SystemHealthPage').then((m) => ({ default: m.SystemHealthPage }))
)
const SettingsPage = lazy(() =>
  import('@/pages/SettingsPage').then((m) => ({ default: m.SettingsPage }))
)

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 3, // 3 minutes cache for performance
      retry: 1,
    },
  },
})

const AppContent: React.FC = () => {
  const [currentRoute, setCurrentRoute] = useState<NavItemKey>('command-center')
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState<boolean>(false)
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date())

  // Global Health Probe
  const { data: healthData, isFetching: isHealthFetching, refetch: refetchHealth } = useQuery({
    queryKey: ['global_health_probe'],
    queryFn: () => api.getHealth(),
    refetchInterval: 30000,
  })

  const isHealthy = healthData?.status === 'healthy' && healthData?.database_connected

  const handleGlobalRefresh = () => {
    queryClient.invalidateQueries()
    refetchHealth()
    setLastRefreshed(new Date())
  }

  const pageMeta: Record<NavItemKey, { title: string; subtitle: string }> = {
    'command-center': {
      title: 'Surveillance Command Center',
      subtitle: 'Real-time overview of syndromic surveillance trends and statistical surge anomalies.',
    },
    geospatial: {
      title: 'Geospatial Intelligence & Surveillance Mapping',
      subtitle: 'Regional case intensity, algorithmic anomaly mapping, and population mobility cross-correlations.',
    },
    surveillance: {
      title: 'Surveillance Explorer',
      subtitle: 'Paginated examination of raw and standardized clinical symptom reports.',
    },
    anomalies: {
      title: 'Anomaly Intelligence',
      subtitle: 'Statistical baseline evaluation and outbreak surge detection across algorithms.',
    },
    mobility: {
      title: 'Mobility Analytics',
      subtitle: 'Investigation of population transit shifts and predictive lead correlations.',
    },
    evidence: {
      title: 'Evidence & Protocol Library',
      subtitle: 'Phase 6A cryptographic document repository for verified public health protocols.',
    },
    assistant: {
      title: 'AI Intelligence Assistant',
      subtitle: 'Phase 6B preview of evidence-grounded public health assistant.',
    },
    pipeline: {
      title: 'Detection Pipeline Lab',
      subtitle: 'Execute and benchmark Rolling MAD, EWMA, and rolling Z-score detection pipelines.',
    },
    health: {
      title: 'System Health & Diagnostics',
      subtitle: 'Backend API latency probes, database connection checks, and table telemetry.',
    },
    settings: {
      title: 'Platform Settings',
      subtitle: 'Configure gateway URLs, manage client cache, and review synthetic data protocol.',
    },
  }

  return (
    <div className="min-h-screen bg-navy-950 text-slate-100 flex flex-col font-sans">
      {/* Top Research Disclaimer Banner */}
      <NoticeBanner />

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar Navigation */}
        <Sidebar
          currentRoute={currentRoute}
          onNavigate={(route) => setCurrentRoute(route)}
          isMobileOpen={isMobileMenuOpen}
          onCloseMobile={() => setIsMobileMenuOpen(false)}
        />

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
          {/* Header */}
          <Header
            title={pageMeta[currentRoute].title}
            subtitle={pageMeta[currentRoute].subtitle}
            lastUpdated={lastRefreshed}
            isHealthy={Boolean(isHealthy)}
            isLoading={isHealthFetching}
            onRefresh={handleGlobalRefresh}
            onToggleMobileMenu={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          />

          {/* Page Body */}
          <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
            <Suspense
              fallback={
                <div className="py-20 flex justify-center">
                  <LoadingSpinner text="Loading analytical view..." />
                </div>
              }
            >
              {currentRoute === 'command-center' && (
                <CommandCenterPage onNavigate={(route) => setCurrentRoute(route)} />
              )}
              {currentRoute === 'geospatial' && <GeospatialPage />}
              {currentRoute === 'surveillance' && <SurveillancePage />}
              {currentRoute === 'anomalies' && <AnomaliesPage />}
              {currentRoute === 'mobility' && <MobilityPage />}
              {currentRoute === 'evidence' && <EvidenceLibraryPage />}
              {currentRoute === 'assistant' && <AIAssistantPage />}
              {currentRoute === 'pipeline' && (
                <PipelineLabPage onNavigate={(route) => setCurrentRoute(route)} />
              )}
              {currentRoute === 'health' && <SystemHealthPage />}
              {currentRoute === 'settings' && <SettingsPage />}
            </Suspense>
          </main>
        </div>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  )
}
