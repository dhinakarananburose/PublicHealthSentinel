import React, { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { getApiBaseUrl, setApiBaseUrl, api } from '@/lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import {
  CheckCircle2,
  Database,
  Globe,
  HardDrive,
  Info,
  RefreshCw,
  RotateCcw,
  Settings,
  Shield,
  Trash2,
} from 'lucide-react'

export const SettingsPage: React.FC = () => {
  const queryClient = useQueryClient()
  const [apiUrl, setApiUrl] = useState<string>(getApiBaseUrl())
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false)
  const [testResult, setTestResult] = useState<{
    status: 'success' | 'error'
    message: string
  } | null>(null)
  const [isTesting, setIsTesting] = useState<boolean>(false)

  const handleSaveUrl = (e: React.FormEvent) => {
    e.preventDefault()
    setApiBaseUrl(apiUrl)
    setSaveSuccess(true)
    setTimeout(() => setSaveSuccess(false), 3000)
    queryClient.invalidateQueries()
  }

  const handleTestConnection = async () => {
    setIsTesting(true)
    setTestResult(null)
    try {
      const res = await api.getHealth()
      setTestResult({
        status: 'success',
        message: `Successfully connected to ${res.app_name} (${res.environment})! Database: ${res.database_connected ? 'Connected' : 'Degraded'}.`,
      })
    } catch (err: any) {
      setTestResult({
        status: 'error',
        message: err.message || 'Connection test failed. Verify backend is running on target URL.',
      })
    } finally {
      setIsTesting(false)
    }
  }

  const handleClearCache = () => {
    queryClient.clear()
    queryClient.invalidateQueries()
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Settings className="w-4 h-4 text-cyan-400" />
              Platform Settings & Gateway Configuration
            </CardTitle>
            <CardDescription>
              Configure backend service endpoints, manage client caching, and review scientific research disclosures.
            </CardDescription>
          </div>
        </CardHeader>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Backend API Configuration */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Globe className="w-4 h-4 text-cyan-400" />
              FastAPI Gateway Connection
            </CardTitle>
            <Badge variant="outline">REST Service</Badge>
          </CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={handleSaveUrl} className="space-y-4">
              <div>
                <Input
                  label="API Server Base URL"
                  placeholder="e.g. http://127.0.0.1:8000 (leave empty for Vite proxy default)"
                  value={apiUrl}
                  onChange={(e) => setApiUrl(e.target.value)}
                  helperText="Default empty value routes through Vite proxy (http://127.0.0.1:8000)."
                />
              </div>

              {saveSuccess && (
                <div className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-800 text-xs text-emerald-300 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>Gateway configuration updated in local storage.</span>
                </div>
              )}

              {testResult && (
                <div
                  className={`p-3 rounded-lg border text-xs flex items-start gap-2 ${
                    testResult.status === 'success'
                      ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300'
                      : 'bg-rose-950/40 border-rose-800 text-rose-300'
                  }`}
                >
                  <Info className="w-4 h-4 shrink-0 mt-0.5" />
                  <div>
                    <strong>{testResult.status === 'success' ? 'Probe Succeeded' : 'Probe Error'}:</strong>{' '}
                    {testResult.message}
                  </div>
                </div>
              )}

              <div className="flex gap-2 justify-end">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={handleTestConnection}
                  isLoading={isTesting}
                  leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isTesting ? 'animate-spin' : ''}`} />}
                >
                  Test Connection
                </Button>
                <Button type="submit" variant="primary" size="sm">
                  Save Changes
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {/* Cache & Local State Management */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <HardDrive className="w-4 h-4 text-teal-400" />
              Client Cache & Query State
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-xs">
            <p className="text-slate-300 leading-relaxed">
              PublicHealthSentinel caches API responses in memory using TanStack Query to reduce unnecessary network roundtrips on an 8 GB RAM laptop.
            </p>

            <div className="p-3 rounded-lg bg-navy-950 border border-navy-800 space-y-2">
              <div className="flex justify-between">
                <span className="text-slate-400">Query Cache Lifetime:</span>
                <span className="font-mono text-slate-200">5 minutes (staleTime)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Automatic Invalidation:</span>
                <span className="font-mono text-teal-400">On Pipeline Detection</span>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleClearCache}
                leftIcon={<Trash2 className="w-3.5 h-3.5 text-rose-400" />}
              >
                Flush In-Memory Cache
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Scientific Compliance & Synthetic Data Protocol */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Shield className="w-4 h-4 text-cyan-400" />
              Scientific Compliance & Synthetic Data Protocol
            </CardTitle>
            <Badge variant="info">Institutional Governance</Badge>
          </CardHeader>
          <CardContent className="space-y-3 text-xs text-slate-300 leading-relaxed">
            <p>
              <strong>1. Simulated Provenance:</strong> PublicHealthSentinel is developed strictly as a methodological anomaly detection research prototype. All observations and mobility indicators are mathematically simulated. Under no circumstances should these records be interpreted as genuine patient records or clinical outbreaks.
            </p>
            <p>
              <strong>2. Statistical Surge vs. Clinical Diagnosis:</strong> Statistical anomalies indicate that an observed count has exceeded historical baselines (via Rolling MAD, EWMA, or Z-Score). Outlier detection algorithms flag numerical surges only and cannot diagnose diseases or establish epidemiological causality.
            </p>
            <p>
              <strong>3. Cryptographic Verification:</strong> Document reference ingestion (Phase 6A) enforces cryptographic SHA-256 validation and strict filename sanitization to prevent path traversal and ensure immutable provenance before future RAG integration.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
