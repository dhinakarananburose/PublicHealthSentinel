import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { api, ApiError } from '@/lib/api-client'
import type {
  AssistantAskRequest,
  AssistantAskResponse,
  AssistantStatusResponse,
  RetrievedPassageReference,
} from '@/types/api'
import {
  AlertCircle,
  AlertTriangle,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Compass,
  Info,
  Layers,
  MessageSquare,
  RefreshCw,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Zap,
} from 'lucide-react'

export const AIAssistantPage: React.FC = () => {
  const [queryInput, setQueryInput] = useState<string>('')
  const [topK, setTopK] = useState<number>(5)
  const [minSimilarity, setMinSimilarity] = useState<number>(0.30)
  const [responseMode, setResponseMode] = useState<'concise' | 'detailed'>('detailed')
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0)
  const [error, setError] = useState<string | null>(null)
  const [errorStatus, setErrorStatus] = useState<number | null>(null)
  const [failedQuery, setFailedQuery] = useState<string | null>(null)
  const [assistantResponse, setAssistantResponse] = useState<AssistantAskResponse | null>(null)
  const [statusData, setStatusData] = useState<AssistantStatusResponse | null>(null)
  const [isStatusLoading, setIsStatusLoading] = useState<boolean>(false)
  const [expandedPassage, setExpandedPassage] = useState<string | null>(null)
  const [selectedCitation, setSelectedCitation] = useState<string | null>(null)

  const samplePrompts = [
    {
      title: 'Respiratory Surge Thresholds',
      query: 'What statistical threshold triggers a respiratory surge alert?',
      category: 'Threshold Protocol',
    },
    {
      title: 'Rolling MAD Methodology',
      query: 'How does Rolling Median Absolute Deviation (MAD) calculate dispersion and handle outlier resistance?',
      category: 'Statistical Method',
    },
    {
      title: 'EWMA Smoothing Factor',
      query: 'What is the recommended EWMA smoothing factor lambda for syndromic time-series signals?',
      category: 'Syndromic Signal',
    },
    {
      title: 'Syndromic Anomaly vs Outbreak',
      query: 'Explain why statistical anomaly alerts are not confirmed outbreak diagnoses.',
      category: 'Surveillance Interpretation',
    },
    {
      title: 'Unanswerable / Out-of-Scope Test',
      query: 'What quantum annealing hardware is recommended for hospital emergency room triage?',
      category: 'Negative Refusal Test',
    },
  ]

  const fetchStatus = async () => {
    setIsStatusLoading(true)
    try {
      const data = await api.getAssistantStatus()
      setStatusData(data)
    } catch (err: any) {
      console.warn('Unable to load assistant status:', err)
    } finally {
      setIsStatusLoading(false)
    }
  }

  useEffect(() => {
    let isMounted = true
    setIsStatusLoading(true)
    api.getAssistantStatus()
      .then((data) => {
        if (isMounted) setStatusData(data)
      })
      .catch((err) => {
        console.warn('Unable to load assistant status:', err)
      })
      .finally(() => {
        if (isMounted) setIsStatusLoading(false)
      })
    return () => {
      isMounted = false
    }
  }, [])

  // Dynamic elapsed timer during generation
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null
    if (isLoading) {
      setElapsedSeconds(0)
      const startTime = Date.now()
      interval = setInterval(() => {
        setElapsedSeconds((Date.now() - startTime) / 1000)
      }, 100)
    } else {
      if (interval) clearInterval(interval)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [isLoading])

  const handleAsk = async (questionToAsk?: string, modeOverride?: 'concise' | 'detailed') => {
    // Prevent accidental duplicate submissions
    if (isLoading) return

    const targetMode = modeOverride || responseMode
    const q = (questionToAsk || queryInput).trim()
    if (!q) return

    setIsLoading(true)
    setError(null)
    setErrorStatus(null)
    setSelectedCitation(null)
    setFailedQuery(null)

    const payload: AssistantAskRequest = {
      question: q,
      top_k: topK,
      min_similarity: minSimilarity,
      mode: targetMode,
      fallback_on_timeout: true,
    }

    try {
      const resp = await api.askAssistant(payload)
      setAssistantResponse(resp)
      if (questionToAsk) {
        setQueryInput(questionToAsk)
      }
    } catch (err: any) {
      // Preserve user question on failure
      setFailedQuery(q)
      if (questionToAsk) {
        setQueryInput(questionToAsk)
      }
      if (err instanceof ApiError) {
        setErrorStatus(err.statusCode)
        if (err.statusCode === 503) {
          setError(
            err.message ||
              'Generation provider (Ollama) is unavailable or the specified model is missing. Check Ollama daemon or configure mock generation.'
          )
        } else if (err.statusCode === 504 || err.statusCode === 408) {
          setError(
            err.message ||
              'Answer generation timed out. Local CPU inference on 3B parameters requires ~2.0s per token (~80–85s for 40 tokens). Switch to Concise Mode (~20 tokens budget) or verify that Ollama is pre-warmed in RAM.'
          )
        } else if (err.statusCode === 400) {
          setError(err.message || 'Invalid search parameters or inquiry length.')
        } else {
          setError(err.message || 'An unexpected error occurred during evidence synthesis.')
        }
      } else {
        setError(err.message || 'Network connection failed. Verify that the backend server is reachable.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  const renderGroundedAnswer = (answerText: string) => {
    // Regex matching [E1], [E2], etc.
    const parts = answerText.split(/(\[E\d+\])/g)

    return parts.map((part, index) => {
      const match = part.match(/^\[E(\d+)\]$/)
      if (match) {
        const citationTag = part
        const isSelected = selectedCitation === citationTag
        return (
          <button
            key={index}
            type="button"
            onClick={() => {
              setSelectedCitation(isSelected ? null : citationTag)
              setExpandedPassage(citationTag)
              // Scroll to passage card if available
              const element = document.getElementById(`passage-${citationTag}`)
              if (element) {
                element.scrollIntoView({ behavior: 'smooth', block: 'center' })
              }
            }}
            className={`inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded text-[11px] font-mono font-semibold transition-all border ${
              isSelected
                ? 'bg-cyan-500 text-navy-950 border-cyan-400 ring-2 ring-cyan-400 shadow-md shadow-cyan-500/20'
                : 'bg-cyan-950/80 text-cyan-300 border-cyan-700/80 hover:bg-cyan-900 hover:border-cyan-500 hover:text-cyan-200'
            }`}
            title={`Jump to verified evidence passage ${citationTag}`}
          >
            {part}
          </button>
        )
      }
      return <span key={index}>{part}</span>
    })
  }

  const getSufficiencyBadge = (sufficiency: 'SUFFICIENT' | 'PARTIAL' | 'INSUFFICIENT') => {
    switch (sufficiency) {
      case 'SUFFICIENT':
        return (
          <Badge variant="success" className="flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Evidence Sufficient
          </Badge>
        )
      case 'PARTIAL':
        return (
          <Badge variant="warning" className="flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            Partial Evidence
          </Badge>
        )
      case 'INSUFFICIENT':
      default:
        return (
          <Badge variant="danger" className="flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5" />
            Insufficient Evidence
          </Badge>
        )
    }
  }

  return (
    <div className="space-y-6">
      {/* Provider Status & Subsystem Readiness Banner */}
      <div className="p-4 rounded-xl border border-navy-800 bg-navy-900/90 text-xs text-slate-200 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-lg bg-cyan-950 border border-cyan-800 flex items-center justify-center text-cyan-400 shrink-0">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-sm font-semibold text-slate-100">
                Phase 6C: Evidence-Grounded Public Health Assistant
              </h2>
              {statusData?.provider === 'demo' ? (
                <Badge variant="success" className="flex items-center gap-1 bg-cyan-950/80 text-cyan-300 border-cyan-800">
                  <CheckCircle2 className="w-3 h-3" />
                  Cloud Demo Mode (Evidence-First)
                </Badge>
              ) : statusData?.provider_healthy ? (
                <Badge variant="success" className="flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" />
                  Provider Ready ({statusData.provider})
                </Badge>
              ) : (
                <Badge variant="warning" className="flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />
                  {statusData?.provider === 'ollama' ? 'Ollama Offline' : 'Provider Unavailable'}
                </Badge>
              )}
              <Badge variant="outline">
                Vectors: {statusData?.indexed_passages_count ?? 12} indexed
              </Badge>
            </div>
            <p className="mt-1 text-slate-400 leading-relaxed max-w-2xl">
              Strictly grounded in the Evidence Library. The assistant retrieves local document passages, isolates context against prompt injection, verifies citations against retrieved text, and refuses to fabricate answers when evidence is insufficient.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end md:self-auto shrink-0">
          <Button
            size="sm"
            variant="outline"
            onClick={fetchStatus}
            disabled={isStatusLoading}
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isStatusLoading ? 'animate-spin' : ''}`} />}
          >
            Check Status
          </Button>
        </div>
      </div>

      {/* Cloud Portfolio Demo Mode Banner */}
      {statusData?.provider === 'demo' && (
        <div className="p-4 rounded-xl border border-cyan-800/60 bg-gradient-to-r from-cyan-950/40 via-navy-900/60 to-navy-950/40 text-xs text-cyan-200 flex items-start gap-3 shadow-lg">
          <Sparkles className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold text-cyan-300 flex items-center gap-2">
              <span>Cloud Portfolio Demo Mode Active</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-900/50 border border-cyan-700/60 text-cyan-200">
                512 MB Free-Tier Compliant
              </span>
            </p>
            <p className="text-slate-300 leading-relaxed">
              To operate reliably within Render's free 512 MB RAM limit at a ₹0/month hosting budget, heavyweight local neural synthesis (Ollama / Llama-3.2 3B, requiring ~2.56 GB) is bypassed. The assistant operates in strict <strong>Evidence-First Retrieval Mode</strong>: matching inquiries against indexed public health surveillance guidelines, extracting verified passages, and generating cited evidence cards <code className="px-1 py-0.5 rounded bg-navy-950 border border-navy-800 text-cyan-300 font-mono">[E1]</code> with 0% AI hallucination.
            </p>
            <p className="text-[11px] text-cyan-400/80">
              Note: Full generative LLM synthesis remains fully supported in the local Docker Compose environment.
            </p>
          </div>
        </div>
      )}

      {/* Provider Offline Notice if applicable (only when not in demo mode) */}
      {statusData && !statusData.provider_healthy && statusData.provider !== 'demo' && (
        <div className="p-4 rounded-xl border border-amber-800/60 bg-amber-950/30 text-xs text-amber-200 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold text-amber-300">
              Local Generation Daemon Not Detected ({statusData.provider}: {statusData.model})
            </p>
            <p className="text-amber-200/90 leading-relaxed">
              {statusData.provider_message}
            </p>
            <p className="text-[11px] text-amber-300/80">
              Queries with no matching evidence will correctly return zero-hallucination refusals offline. To enable live neural synthesis, start your local Ollama daemon (<code className="px-1 py-0.5 rounded bg-black/40">ollama serve</code>) or configure the mock generation provider for automated development testing.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chat / Query Canvas */}
        <div className="lg:col-span-2 space-y-4">
          <Card className="min-h-[520px] flex flex-col justify-between">
            <CardHeader>
              <div>
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <Bot className="w-4 h-4 text-cyan-400" />
                  Evidence-Grounded Intelligence Query
                </CardTitle>
                <CardDescription>
                  Inquire across surveillance protocols, anomaly thresholds, and syndromic guidelines.
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline">Strict Evidence Mode</Badge>
              </div>
            </CardHeader>

            <CardContent className="flex-1 flex flex-col justify-start p-6 space-y-4 overflow-y-auto max-h-[680px]">
              {/* Error Notice with Actionable Retries */}
              {error && (
                <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800/80 text-xs text-rose-200 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 font-semibold text-rose-300">
                      <ShieldAlert className="w-4 h-4 shrink-0" />
                      <span>Query Failed {errorStatus ? `(HTTP ${errorStatus})` : ''}</span>
                    </div>
                    {failedQuery && (
                      <span className="text-[10px] text-slate-400 font-mono">
                        Question Preserved
                      </span>
                    )}
                  </div>

                  <p className="leading-relaxed">{error}</p>

                  {failedQuery && (
                    <div className="p-2 rounded bg-navy-950/80 border border-rose-900/60 text-[11px] text-slate-300 font-medium">
                      Inquiry: "{failedQuery}"
                    </div>
                  )}

                  <div className="flex items-center gap-2 flex-wrap pt-1">
                    {(errorStatus === 504 || errorStatus === 408 || error.toLowerCase().includes('time')) ? (
                      <>
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => {
                            setResponseMode('concise')
                            handleAsk(failedQuery || queryInput, 'concise')
                          }}
                          className="bg-cyan-600 hover:bg-cyan-500 text-navy-950 font-semibold"
                          leftIcon={<Zap className="w-3.5 h-3.5" />}
                        >
                          Retry in Concise Mode (~20 tok, ~40-48s)
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setResponseMode('detailed')
                            handleAsk(failedQuery || queryInput, 'detailed')
                          }}
                          className="border-rose-700 hover:bg-rose-900/50 text-rose-200"
                        >
                          Retry in Detailed Mode
                        </Button>
                      </>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleAsk(failedQuery || queryInput)}
                        className="border-rose-700 hover:bg-rose-900/50 text-rose-200"
                        leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
                      >
                        Retry Query
                      </Button>
                    )}
                  </div>
                </div>
              )}

              {/* Loading State with Live Elapsed Time and Stage Feedback */}
              {isLoading && (
                <div className="py-12 flex flex-col items-center justify-center space-y-4">
                  <LoadingSpinner size="lg" />
                  <div className="flex items-center gap-2.5 px-3 py-1 rounded-full bg-cyan-950/80 border border-cyan-700/60 font-mono text-xs text-cyan-300">
                    <Clock className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
                    <span>Elapsed: <strong>{elapsedSeconds.toFixed(1)}s</strong></span>
                    <span className="text-slate-500">|</span>
                    <span className="text-slate-300 font-sans">
                      Mode: <strong className="uppercase text-cyan-300">{responseMode}</strong> ({responseMode === 'concise' ? '~20 tok' : '~40 tok'})
                    </span>
                  </div>
                  <div className="text-center space-y-1 max-w-md">
                    {elapsedSeconds < 2 ? (
                      <p className="text-xs font-semibold text-cyan-300">
                        Encoding inquiry vector & retrieving top-{topK} evidence passages...
                      </p>
                    ) : responseMode === 'concise' ? (
                      <p className="text-xs font-semibold text-cyan-300">
                        {elapsedSeconds < 25
                          ? "Synthesizing concise answer via local CPU LLM (~0.49 tok/s)..."
                          : elapsedSeconds < 45
                          ? "Reconciling evidence citations and validating [E#] tags..."
                          : "Processing tokens. Fallback protection active if gateway deadline is reached..."}
                      </p>
                    ) : (
                      <p className="text-xs font-semibold text-cyan-300">
                        {elapsedSeconds < 35
                          ? "Synthesizing detailed answer via local CPU LLM (~0.49 tok/s)..."
                          : elapsedSeconds < 75
                          ? "Generating grounded response and strictly reconciling citation provenance..."
                          : "Approaching deadline (~90s). Evidence-first fallback ready if exceeded..."}
                      </p>
                    )}
                    <p className="text-[11px] text-slate-400">
                      Measured local CPU generation throughput: ~0.49 tokens/second (~2.0s per token).
                    </p>
                  </div>
                </div>
              )}

              {/* Active Assistant Response */}
              {!isLoading && assistantResponse && (
                <div className="space-y-5">
                  {/* Evidence-First Fallback Banner if LLM timed out */}
                  {assistantResponse.response_type === 'evidence_fallback' && (
                    <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-600/70 text-xs text-amber-200 space-y-2">
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <div className="flex items-center gap-2 font-semibold text-amber-300">
                          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                          <span>Evidence-First Fallback (Direct Source Passages)</span>
                        </div>
                        <Badge variant="warning" size="sm">No AI Generative Summarization</Badge>
                      </div>
                      <p className="leading-relaxed text-slate-200">
                        Language model synthesis timed out on the host CPU. However, <strong>{assistantResponse.retrieved_passages.length} reference passages</strong> were successfully retrieved and verified from the Evidence Library. Authoritative source excerpts are presented verbatim below with citation identifiers and document offsets.
                      </p>
                    </div>
                  )}

                  {/* Warning Notice if generation was truncated or incomplete */}
                  {assistantResponse.warning && assistantResponse.response_type !== 'evidence_fallback' && (
                    <div className="p-3 rounded-lg bg-amber-950/30 border border-amber-800/60 text-[11px] text-amber-300 flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                      <span>{assistantResponse.warning}</span>
                    </div>
                  )}

                  {/* User Inquiry Echo */}
                  <div className="flex items-start gap-3 p-3.5 rounded-xl bg-navy-950 border border-navy-800 text-xs">
                    <div className="w-7 h-7 rounded-full bg-cyan-950 border border-cyan-700 flex items-center justify-center text-cyan-400 shrink-0 font-semibold">
                      U
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-slate-300">Investigator Inquiry</span>
                        <span className="text-[11px] font-mono text-slate-500">
                          {assistantResponse.query_id}
                        </span>
                      </div>
                      <p className="text-slate-100 mt-1 font-medium">{assistantResponse.question}</p>
                    </div>
                  </div>

                  {/* Synthesized / Grounded Answer Card */}
                  <div className="p-5 rounded-xl bg-navy-900/90 border border-cyan-800/40 space-y-4">
                    {/* Header with Sufficiency & Latency */}
                    <div className="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-navy-800 text-xs">
                      <div className="flex items-center gap-2">
                        {getSufficiencyBadge(assistantResponse.evidence_sufficiency)}
                        {assistantResponse.response_type === 'evidence_fallback' ? (
                          <Badge variant="warning">Evidence Fallback</Badge>
                        ) : (
                          <Badge variant="outline" className="uppercase font-mono text-[10px]">
                            {assistantResponse.response_mode || 'detailed'} mode
                          </Badge>
                        )}
                        <span className="text-slate-400 text-[11px]">
                          Provider: <strong className="text-slate-200">{assistantResponse.provider}</strong> ({assistantResponse.model})
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-[11px] text-slate-400 font-mono">
                        <span className="flex items-center gap-1">
                          <Zap className="w-3 h-3 text-amber-400" />
                          {assistantResponse.latency_seconds.toFixed(2)}s round-trip
                        </span>
                        <span>
                          {assistantResponse.citations.length} verified citation{assistantResponse.citations.length === 1 ? '' : 's'}
                        </span>
                      </div>
                    </div>

                    {/* Grounded Answer Body */}
                    <div className="text-xs text-slate-200 leading-relaxed font-sans space-y-2 whitespace-pre-wrap">
                      {renderGroundedAnswer(assistantResponse.answer)}
                    </div>

                    {/* Sufficiency Explanation if insufficient */}
                    {assistantResponse.evidence_sufficiency === 'INSUFFICIENT' && (
                      <div className="p-3 rounded-lg bg-navy-950 border border-amber-900/50 text-[11px] text-amber-300/90 space-y-1">
                        <div className="font-semibold flex items-center gap-1.5">
                          <Info className="w-3.5 h-3.5" />
                          Zero-Hallucination Policy Triggered
                        </div>
                        <p>
                          The indexed reference documents did not contain sufficient evidence meeting the {minSimilarity.toFixed(2)} similarity cutoff. No speculative claims or fabricated sources were generated.
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Verified Citations List */}
                  {assistantResponse.citations.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-semibold text-slate-300 flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4 text-cyan-400" />
                        Verified In-Text Citations ({assistantResponse.citations.length})
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {assistantResponse.citations.map((cit, citIdx) => {
                          const tag = cit.citation_id
                            ? (cit.citation_id.startsWith('[') ? cit.citation_id : `[${cit.citation_id}]`)
                            : (cit.citation_tag || `[E${citIdx + 1}]`)
                          return (
                            <div
                              key={tag + cit.chunk_id}
                              onClick={() => {
                                setSelectedCitation(tag)
                                setExpandedPassage(tag)
                                const element = document.getElementById(`passage-${tag}`)
                                if (element) {
                                  element.scrollIntoView({ behavior: 'smooth', block: 'center' })
                                }
                              }}
                              className={`p-2.5 rounded-lg border text-[11px] cursor-pointer transition-all ${
                                selectedCitation === tag
                                  ? 'bg-cyan-950/80 border-cyan-400 ring-1 ring-cyan-400'
                                  : 'bg-navy-950 border-navy-800 hover:border-navy-700'
                              }`}
                            >
                              <div className="flex items-center justify-between gap-1 mb-1">
                                <span className="font-mono font-bold text-cyan-400">
                                  {tag}
                                </span>
                                <Badge variant="outline" size="sm" className="font-mono text-[10px]">
                                  Score: {cit.similarity_score.toFixed(3)}
                                </Badge>
                              </div>
                              <p className="font-semibold text-slate-200 truncate">{cit.title}</p>
                              <p className="text-slate-400 line-clamp-2 mt-1 italic">
                                "{cit.excerpt}"
                              </p>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Complete Retrieved Evidence Passages */}
                  {assistantResponse.retrieved_passages.length > 0 && (
                    <div className="space-y-3 pt-2 border-t border-navy-800">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-semibold text-slate-300 flex items-center gap-2">
                          <Layers className="w-4 h-4 text-cyan-400" />
                          Retrieved Reference Passages ({assistantResponse.retrieved_passages.length})
                        </h4>
                        <span className="text-[11px] text-slate-500">
                          Sorted by embedding similarity
                        </span>
                      </div>

                      <div className="space-y-2">
                        {assistantResponse.retrieved_passages.map((passage: RetrievedPassageReference) => {
                          const tag = `[E${passage.passage_index}]`
                          const isExpanded = expandedPassage === tag
                          const isSelected = selectedCitation === tag

                          return (
                            <div
                              key={passage.chunk_id}
                              id={`passage-${tag}`}
                              className={`rounded-lg border text-xs transition-all ${
                                isSelected
                                  ? 'bg-navy-900 border-cyan-500/80 ring-1 ring-cyan-500/50'
                                  : 'bg-navy-950 border-navy-800/80'
                              }`}
                            >
                              <div
                                onClick={() => setExpandedPassage(isExpanded ? null : tag)}
                                className="p-3 flex items-center justify-between gap-2 cursor-pointer hover:bg-navy-900/50"
                              >
                                <div className="flex items-center gap-2.5 flex-wrap">
                                  <span className="font-mono font-bold text-cyan-400 bg-cyan-950 px-2 py-0.5 rounded border border-cyan-800 text-[11px]">
                                    {tag}
                                  </span>
                                  <span className="font-semibold text-slate-200 truncate max-w-xs md:max-w-md">
                                    {passage.title}
                                  </span>
                                  {passage.source_publisher && (
                                    <span className="text-[11px] text-slate-400">
                                      ({passage.source_publisher})
                                    </span>
                                  )}
                                </div>

                                <div className="flex items-center gap-2 shrink-0">
                                  <span
                                    className="px-2 py-0.5 rounded bg-navy-800 border border-navy-700 text-[10px] font-mono text-cyan-300"
                                    title="Cosine similarity between question and passage embeddings. This is an indexing metric, not a clinical probability."
                                  >
                                    Retrieval Score: {passage.similarity_score.toFixed(3)}
                                  </span>
                                  {isExpanded ? (
                                    <ChevronUp className="w-4 h-4 text-slate-400" />
                                  ) : (
                                    <ChevronDown className="w-4 h-4 text-slate-400" />
                                  )}
                                </div>
                              </div>

                              {isExpanded && (
                                <div className="px-3 pb-3 pt-1 border-t border-navy-800/60 space-y-2 text-[11px]">
                                  <div className="flex items-center justify-between text-slate-400 font-mono text-[10px]">
                                    <span>Chunk ID: {passage.chunk_id}</span>
                                    <span>Offsets: {passage.char_start} - {passage.char_end}</span>
                                  </div>
                                  <div className="p-2.5 rounded bg-navy-900 border border-navy-800 text-slate-300 leading-relaxed font-mono whitespace-pre-wrap">
                                    {passage.text}
                                  </div>
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Synthetic Notice and Non-Clinical Disclaimer */}
                  <div className="p-3.5 rounded-lg bg-navy-950/80 border border-navy-800 text-[11px] text-slate-400 space-y-1.5">
                    <p className="text-slate-300">
                      <strong>Synthetic Research Notice:</strong> {assistantResponse.synthetic_data_notice}
                    </p>
                    <p className="text-amber-300/80">
                      <strong>Clinical Disclaimer:</strong> {assistantResponse.non_clinical_notice}
                    </p>
                  </div>
                </div>
              )}

              {/* Empty / Initial State */}
              {!isLoading && !assistantResponse && !error && (
                <div className="text-center py-12 space-y-4">
                  <div className="w-14 h-14 rounded-2xl bg-cyan-950/60 border border-cyan-800/80 mx-auto flex items-center justify-center text-cyan-400 shadow-inner">
                    <MessageSquare className="w-7 h-7" />
                  </div>
                  <div className="space-y-1">
                    <h3 className="text-sm font-semibold text-slate-100">
                      Inquire Across Grounded Public Health Guidelines
                    </h3>
                    <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
                      Select a research prompt from the panel on the right or type a custom inquiry regarding outbreak case definitions, anomaly detection statistics, or surge thresholds.
                    </p>
                  </div>

                  <div className="max-w-md mx-auto p-3.5 rounded-xl bg-navy-950 border border-navy-800 text-left text-[11px] space-y-2 text-slate-400">
                    <div className="font-semibold text-slate-200 flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                      Evidence Pipeline Guardrails
                    </div>
                    <ul className="list-disc pl-4 space-y-1">
                      <li>Only indexed reference documents are provided to the model.</li>
                      <li>In-text citations [E#] are validated against retrieved passages.</li>
                      <li>Refuses to speculate when evidence does not meet similarity cutoffs.</li>
                      <li>Prompt injection instructions inside documents are isolated and ignored.</li>
                    </ul>
                  </div>
                </div>
              )}
            </CardContent>

            {/* Input Bar & Config Controls */}
            <div className="p-4 border-t border-navy-800 bg-navy-950/60 rounded-b-xl space-y-3">
              {/* Retrieval Parameter Controls & Response Mode Selector */}
              <div className="flex items-center justify-between text-[11px] text-slate-400 px-1 flex-wrap gap-2">
                <div className="flex items-center gap-3 flex-wrap">
                  {/* Mode Selector */}
                  <div className="flex items-center gap-1 bg-navy-900 border border-navy-700 rounded-lg p-0.5 text-xs">
                    <button
                      type="button"
                      onClick={() => setResponseMode('concise')}
                      disabled={isLoading}
                      className={`px-2.5 py-1 rounded text-[11px] font-medium transition-all ${
                        responseMode === 'concise'
                          ? 'bg-cyan-500 text-navy-950 font-semibold shadow-sm'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                      title="Concise Mode: Generates a direct ~20 token answer for ~40-48s latency budget on warm CPU."
                    >
                      ⚡ Concise (~20 tok)
                    </button>
                    <button
                      type="button"
                      onClick={() => setResponseMode('detailed')}
                      disabled={isLoading}
                      className={`px-2.5 py-1 rounded text-[11px] font-medium transition-all ${
                        responseMode === 'detailed'
                          ? 'bg-cyan-500 text-navy-950 font-semibold shadow-sm'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                      title="Detailed Mode: Standard ~40 token budget (~80-85s latency on CPU) for comprehensive synthesis."
                    >
                      📄 Detailed (~40 tok)
                    </button>
                  </div>

                  <label className="flex items-center gap-1.5">
                    <span>Top-k:</span>
                    <select
                      value={topK}
                      onChange={(e) => setTopK(Number(e.target.value))}
                      disabled={isLoading}
                      className="px-2 py-0.5 rounded bg-navy-900 border border-navy-700 text-slate-200 text-xs focus:outline-none focus:border-cyan-500 disabled:opacity-50"
                    >
                      <option value={3}>3</option>
                      <option value={5}>5 (Standard)</option>
                      <option value={8}>8</option>
                      <option value={10}>10</option>
                    </select>
                  </label>

                  <label className="flex items-center gap-1.5">
                    <span>Min Sim:</span>
                    <select
                      value={minSimilarity}
                      onChange={(e) => setMinSimilarity(Number(e.target.value))}
                      disabled={isLoading}
                      className="px-2 py-0.5 rounded bg-navy-900 border border-navy-700 text-slate-200 text-xs focus:outline-none focus:border-cyan-500 disabled:opacity-50"
                    >
                      <option value={0.20}>0.20</option>
                      <option value={0.30}>0.30 (Standard)</option>
                      <option value={0.45}>0.45 (Strict)</option>
                      <option value={0.60}>0.60</option>
                    </select>
                  </label>
                </div>

                <span className="text-slate-500 font-mono">
                  {queryInput.length}/1000 chars
                </span>
              </div>

              {/* Form Input */}
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  handleAsk()
                }}
                className="flex gap-2"
              >
                <input
                  type="text"
                  placeholder="Ask a question grounded in reference documentation..."
                  aria-label="Ask a question grounded in reference documentation"
                  value={queryInput}
                  maxLength={1000}
                  onChange={(e) => setQueryInput(e.target.value)}
                  disabled={isLoading}
                  className="flex-1 px-3.5 py-2.5 text-xs rounded-lg bg-navy-900 border border-navy-700 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500 disabled:opacity-50"
                />
                <Button
                  size="sm"
                  variant="primary"
                  type="submit"
                  disabled={!queryInput.trim() || isLoading}
                  isLoading={isLoading}
                  rightIcon={<Send className="w-3.5 h-3.5" />}
                >
                  Ask
                </Button>
              </form>
            </div>
          </Card>
        </div>

        {/* Suggested Queries & System Architecture Panel */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-xs font-semibold flex items-center gap-2 uppercase tracking-wider text-slate-300">
                <Compass className="w-3.5 h-3.5 text-cyan-400" />
                Benchmark Research Queries
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 p-4 pt-0">
              {samplePrompts.map((sample, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setQueryInput(sample.query)
                    handleAsk(sample.query)
                  }}
                  disabled={isLoading}
                  className="w-full text-left p-3 rounded-lg bg-navy-950/70 border border-navy-800/80 hover:border-cyan-500/50 hover:bg-navy-900/60 text-xs transition-colors group space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-semibold tracking-wider text-cyan-400 uppercase">
                      {sample.category}
                    </span>
                    <span className="text-[10px] text-slate-500 group-hover:text-cyan-300 font-mono">
                      Run &rarr;
                    </span>
                  </div>
                  <p className="text-slate-200 group-hover:text-cyan-200 leading-snug">
                    "{sample.query}"
                  </p>
                </button>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-xs font-semibold flex items-center gap-2 uppercase tracking-wider text-slate-300">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                Public Health Safety Guardrails
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2.5 text-xs text-slate-400 p-4 pt-0 leading-relaxed">
              <div className="p-2.5 rounded-lg bg-navy-950 border border-navy-800 space-y-1">
                <strong className="text-slate-200 text-[11px] block">1. Evidence Grounding</strong>
                <p className="text-[11px]">
                  All material statements cite verifiable passage identifiers [E#] corresponding to indexed text.
                </p>
              </div>

              <div className="p-2.5 rounded-lg bg-navy-950 border border-navy-800 space-y-1">
                <strong className="text-slate-200 text-[11px] block">2. Non-Diagnostic Disclosure</strong>
                <p className="text-[11px]">
                  Statistical anomalies represent computational signals, never confirmed real-world outbreak diagnoses or patient triage.
                </p>
              </div>

              <div className="p-2.5 rounded-lg bg-navy-950 border border-navy-800 space-y-1">
                <strong className="text-slate-200 text-[11px] block">3. Prompt Injection Defense</strong>
                <p className="text-[11px]">
                  Retrieved passages are isolated within quotation tags; overriding system directives are ignored.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
