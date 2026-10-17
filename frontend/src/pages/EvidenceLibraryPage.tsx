import React, { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '@/lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import { Pagination } from '@/components/common/Pagination'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'
import { Modal } from '@/components/common/Modal'
import { formatBytes, formatDateTime } from '@/lib/utils'
import type {
  DocumentChunk,
  DocumentMetadata,
  EvidenceSearchResponse,
} from '@/types/api'
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Database,
  ExternalLink,
  Eye,
  FileText,
  Layers,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Sparkles,
  Upload,
  X,
} from 'lucide-react'

export const EvidenceLibraryPage: React.FC = () => {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'documents' | 'search'>('documents')
  const [page, setPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(10)
  const [formatFilter, setFormatFilter] = useState<string>('')
  const [publisherFilter, setPublisherFilter] = useState<string>('')
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false)
  const [selectedDoc, setSelectedDoc] = useState<DocumentMetadata | null>(null)
  const [inspectingDocId, setInspectingDocId] = useState<string | null>(null)
  const [processingDocId, setProcessingDocId] = useState<string | null>(null)

  // Ingestion Form State
  const [filename, setFilename] = useState<string>('')
  const [title, setTitle] = useState<string>('')
  const [content, setContent] = useState<string>('')
  const [publisher, setPublisher] = useState<string>('')
  const [url, setUrl] = useState<string>('')
  const [pubDate, setPubDate] = useState<string>('')
  const [uploadFeedback, setUploadFeedback] = useState<{
    type: 'success' | 'duplicate' | 'error'
    message: string
    documentId?: string
  } | null>(null)

  // Semantic Search State
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [searchTopK, setSearchTopK] = useState<number>(5)
  const [searchPublisher, setSearchPublisher] = useState<string>('')
  const [searchMinSim, setSearchMinSim] = useState<number>(0.0)
  const [searchResults, setSearchResults] = useState<EvidenceSearchResponse | null>(null)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [processingNotification, setProcessingNotification] = useState<{
    type: 'success' | 'error'
    message: string
  } | null>(null)

  // Query documents
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['documents_list', { page, pageSize, formatFilter, publisherFilter }],
    queryFn: () =>
      api.listDocuments({
        page,
        page_size: pageSize,
        doc_format: formatFilter || undefined,
        source_publisher: publisherFilter || undefined,
      }),
  })

  // Query evidence subsystem status
  const { data: subsystemStatus, refetch: refetchStatus } = useQuery({
    queryKey: ['evidence_subsystem_status'],
    queryFn: () => api.getEvidenceStatus(),
  })

  // Ingestion Mutation
  const ingestMutation = useMutation({
    mutationFn: () =>
      api.ingestDocument({
        filename: filename.trim(),
        content,
        title: title.trim() || undefined,
        source_publisher: publisher.trim() || undefined,
        source_url: url.trim() || undefined,
        publication_date: pubDate || undefined,
      }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['documents_list'] })
      queryClient.invalidateQueries({ queryKey: ['evidence_subsystem_status'] })
      if (res.status === 'DUPLICATE') {
        setUploadFeedback({
          type: 'duplicate',
          message: `Duplicate detected: identical SHA-256 hash matched existing record (${res.document_id}). No duplicate file was created on disk.`,
          documentId: res.document_id,
        })
      } else {
        setUploadFeedback({
          type: 'success',
          message: `Document successfully ingested and registered with ID: ${res.document_id}`,
          documentId: res.document_id,
        })
        setFilename('')
        setTitle('')
        setContent('')
        setPublisher('')
        setUrl('')
        setPubDate('')
      }
    },
    onError: (err: any) => {
      if (err instanceof ApiError && err.statusCode === 409) {
        setUploadFeedback({
          type: 'duplicate',
          message: err.message || 'Duplicate document: content hash already exists in repository.',
        })
      } else {
        setUploadFeedback({
          type: 'error',
          message: err.message || 'Failed to ingest document. Verify format (.txt, .md) and file size.',
        })
      }
    },
  })

  // Process Document Mutation
  const processMutation = useMutation({
    mutationFn: (docId: string) => api.processDocument(docId),
    onMutate: (docId: string) => {
      setProcessingDocId(docId)
      setProcessingNotification(null)
    },
    onSuccess: (res) => {
      setProcessingDocId(null)
      queryClient.invalidateQueries({ queryKey: ['evidence_subsystem_status'] })
      queryClient.invalidateQueries({ queryKey: ['documents_list'] })
      queryClient.invalidateQueries({ queryKey: ['document_chunks', res.document_id] })
      setProcessingNotification({
        type: 'success',
        message: `Document ${res.document_id} successfully chunked into ${res.chunks_created} passages and indexed.`,
      })
    },
    onError: (err: any) => {
      setProcessingDocId(null)
      setProcessingNotification({
        type: 'error',
        message: `Processing failed: ${err.message || 'Unknown processing error'}`,
      })
    },
  })

  // Rebuild Index Mutation
  const rebuildMutation = useMutation({
    mutationFn: () => api.rebuildEvidenceIndex(),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['evidence_subsystem_status'] })
      queryClient.invalidateQueries({ queryKey: ['documents_list'] })
      setProcessingNotification({
        type: 'success',
        message: res.message || 'Vector index successfully rebuilt from database.',
      })
    },
    onError: (err: any) => {
      setProcessingNotification({
        type: 'error',
        message: `Index rebuild failed: ${err.message || 'Unknown rebuild failure'}`,
      })
    },
  })

  // Semantic Search Mutation
  const searchMutation = useMutation({
    mutationFn: () => {
      setSearchError(null)
      return api.searchEvidence({
        query: searchQuery.trim(),
        top_k: searchTopK,
        source_publisher: searchPublisher.trim() || undefined,
        min_similarity: searchMinSim,
      })
    },
    onSuccess: (res) => {
      setSearchResults(res)
    },
    onError: (err: any) => {
      setSearchError(err.message || 'Could not execute query. Verify index status and parameters.')
    },
  })

  // Query chunks for inspecting modal
  const { data: chunksData, isLoading: isChunksLoading } = useQuery({
    queryKey: ['document_chunks', inspectingDocId],
    queryFn: () => (inspectingDocId ? api.getDocumentChunks(inspectingDocId, { page_size: 100 }) : null),
    enabled: !!inspectingDocId,
  })

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setFilename(file.name)
    const reader = new FileReader()
    reader.onload = (event) => {
      const text = event.target?.result as string
      setContent(text || '')
    }
    reader.readAsText(file)
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-100">
              Evidence Library & Semantic Retrieval
            </h1>
            <Badge variant="info" size="sm">
              Phase 6B.2 Active
            </Badge>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Reference protocols, passage chunking, local dense vector embeddings, and semantic evidence retrieval.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant={activeTab === 'documents' ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setActiveTab('documents')}
            leftIcon={<Layers className="w-3.5 h-3.5" />}
          >
            Reference Documents
          </Button>
          <Button
            variant={activeTab === 'search' ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setActiveTab('search')}
            leftIcon={<Search className="w-3.5 h-3.5" />}
          >
            Semantic Search
          </Button>
        </div>
      </div>

      {/* Subsystem Health & Metric Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="bg-navy-900/60 border-navy-800">
          <CardContent className="p-3.5 flex items-center justify-between">
            <div>
              <span className="text-[11px] font-medium text-slate-400 block">Vector Index Status</span>
              <div className="flex items-center gap-1.5 mt-0.5">
                <Badge
                  variant={
                    subsystemStatus?.status === 'HEALTHY'
                      ? 'success'
                      : subsystemStatus?.status === 'DEGRADED' || subsystemStatus?.is_degraded
                      ? 'warning'
                      : 'outline'
                  }
                  size="sm"
                >
                  {subsystemStatus?.status || 'INITIALIZING'}
                </Badge>
              </div>
            </div>
            <Database className="w-5 h-5 text-cyan-400 opacity-80" />
          </CardContent>
        </Card>

        <Card className="bg-navy-900/60 border-navy-800">
          <CardContent className="p-3.5 flex items-center justify-between">
            <div>
              <span className="text-[11px] font-medium text-slate-400 block">Indexed Passages</span>
              <span className="text-lg font-bold text-slate-100 font-mono">
                {subsystemStatus?.total_indexed_chunks ?? 0}
              </span>
            </div>
            <Layers className="w-5 h-5 text-emerald-400 opacity-80" />
          </CardContent>
        </Card>

        <Card className="bg-navy-900/60 border-navy-800">
          <CardContent className="p-3.5 flex items-center justify-between">
            <div>
              <span className="text-[11px] font-medium text-slate-400 block">Active Model</span>
              <span className="text-xs font-semibold text-slate-200 font-mono truncate max-w-[130px] block" title={subsystemStatus?.active_embedding_model || 'all-MiniLM-L6-v2'}>
                {subsystemStatus?.active_embedding_model ? subsystemStatus.active_embedding_model.split('/').pop() : 'all-MiniLM-L6-v2'}
              </span>
            </div>
            <Cpu className="w-5 h-5 text-indigo-400 opacity-80" />
          </CardContent>
        </Card>

        <Card className="bg-navy-900/60 border-navy-800">
          <CardContent className="p-3.5 flex items-center justify-between">
            <div>
              <span className="text-[11px] font-medium text-slate-400 block">Embedding Dimension</span>
              <span className="text-lg font-bold text-slate-100 font-mono">
                {subsystemStatus?.dimension ? `${subsystemStatus.dimension}-D` : '384-D'}
              </span>
            </div>
            <Sparkles className="w-5 h-5 text-amber-400 opacity-80" />
          </CardContent>
        </Card>
      </div>

      {/* Degraded Index Recovery Banner */}
      {(subsystemStatus?.status === 'DEGRADED' || subsystemStatus?.is_degraded) && (
        <div className="p-4 rounded-lg border border-amber-600/50 bg-amber-950/30 text-xs text-amber-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg shadow-amber-950/20">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <strong className="text-amber-300 font-semibold text-sm block">Vector Index Degraded</strong>
              <p className="mt-0.5 text-amber-200/90 leading-relaxed">
                {subsystemStatus.degraded_reason || 'Index files are corrupted, out of sync, or encountering a model mismatch. Searches are suspended or operating on partial data until resynchronization.'}
              </p>
            </div>
          </div>
          <Button
            size="sm"
            variant="secondary"
            isLoading={rebuildMutation.isPending}
            onClick={() => rebuildMutation.mutate()}
            leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
            className="shrink-0 self-start sm:self-center font-semibold bg-amber-600/80 hover:bg-amber-600 text-white border-amber-500/80"
          >
            Rebuild Index from Relational DB
          </Button>
        </div>
      )}

      {/* Operation Feedback Notification */}
      {processingNotification && (
        <div
          className={`p-3.5 rounded-lg border text-xs flex items-center justify-between gap-2.5 transition-all ${
            processingNotification.type === 'success'
              ? 'border-emerald-600/40 bg-emerald-950/30 text-emerald-200'
              : 'border-rose-600/40 bg-rose-950/30 text-rose-200'
          }`}
        >
          <div className="flex items-center gap-2">
            {processingNotification.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            )}
            <span>{processingNotification.message}</span>
          </div>
          <button
            onClick={() => setProcessingNotification(null)}
            className="text-slate-400 hover:text-slate-200 p-1 text-xs"
            aria-label="Dismiss notification"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Synthetic Research Benchmark Notice */}
      <div className="p-3 rounded-lg border border-cyan-800/40 bg-cyan-950/20 text-xs text-cyan-300 flex items-start gap-2.5">
        <AlertCircle className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
        <p className="leading-relaxed">
          <strong>Phase 6B.2 Provenance Notice:</strong> Reference materials and passages retrieved by vector similarity represent guidelines for surveillance method evaluation. Similarity scores measure semantic phrasing alignment and do not constitute clinical verification, diagnostic outbreak confirmation, or automated diagnosis.
        </p>
      </div>

      {activeTab === 'documents' ? (
        /* ================= REFERENCE DOCUMENTS TAB ================= */
        <div className="space-y-6">
          {/* Controls and Ingestion Action */}
          <Card>
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-sm font-semibold text-slate-200">
                  Registered Documents ({data?.total ?? 0})
                </CardTitle>
                <CardDescription className="text-xs text-slate-400">
                  Ingest, chunk, embed, and inspect traceable evidence documents.
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    refetch()
                    refetchStatus()
                  }}
                  leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />}
                >
                  Refresh
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  isLoading={rebuildMutation.isPending}
                  onClick={() => rebuildMutation.mutate()}
                  leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
                  title="Reconstruct vector index from stored relational chunk embeddings"
                >
                  Rebuild Index
                </Button>
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => {
                    setUploadFeedback(null)
                    setIsUploadOpen(true)
                  }}
                  leftIcon={<Plus className="w-3.5 h-3.5" />}
                >
                  Ingest Document
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Document Format</label>
                  <select
                    value={formatFilter}
                    onChange={(e) => {
                      setFormatFilter(e.target.value)
                      setPage(1)
                    }}
                    className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-200 focus:outline-none focus:border-cyan-500"
                  >
                    <option value="">All Formats (.md, .txt)</option>
                    <option value="md">Markdown (.md)</option>
                    <option value="txt">Plain Text (.txt)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Publisher / Agency</label>
                  <input
                    type="text"
                    placeholder="e.g. State Health Department"
                    value={publisherFilter}
                    onChange={(e) => {
                      setPublisherFilter(e.target.value)
                      setPage(1)
                    }}
                    className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500"
                  />
                </div>

                <div className="flex items-end">
                  {(formatFilter || publisherFilter) && (
                    <button
                      onClick={() => {
                        setFormatFilter('')
                        setPublisherFilter('')
                        setPage(1)
                      }}
                      className="text-xs text-cyan-400 hover:text-cyan-300 underline underline-offset-2 pb-2"
                    >
                      Clear Library Filters
                    </button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Ingest Modal */}
          <Modal
            isOpen={isUploadOpen}
            onClose={() => setIsUploadOpen(false)}
            title="Ingest Public Health Reference Document"
            subtitle="SHA-256 Hashing, Path Traversal Defense & Duplicate Prevention"
            maxWidth="xl"
          >
            <div className="space-y-4 text-xs">
              {uploadFeedback && (
                <div
                  className={`p-3.5 rounded-lg border text-xs flex items-start gap-2.5 ${
                    uploadFeedback.type === 'success'
                      ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300'
                      : uploadFeedback.type === 'duplicate'
                      ? 'bg-amber-950/40 border-amber-800 text-amber-300'
                      : 'bg-rose-950/40 border-rose-800 text-rose-300'
                  }`}
                >
                  {uploadFeedback.type === 'success' ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  )}
                  <div className="leading-relaxed">
                    <strong>
                      {uploadFeedback.type === 'success'
                        ? 'Ingestion Successful'
                        : uploadFeedback.type === 'duplicate'
                        ? 'Duplicate Document'
                        : 'Ingestion Error'}
                      :
                    </strong>{' '}
                    {uploadFeedback.message}
                  </div>
                </div>
              )}

              <div className="p-3 rounded-lg border border-dashed border-navy-700 bg-navy-950/50 flex flex-col items-center justify-center text-center gap-2">
                <Upload className="w-6 h-6 text-cyan-400" />
                <span className="text-xs text-slate-300 font-medium">
                  Upload local file or paste content directly
                </span>
                <span className="text-[11px] text-slate-500">
                  Supported formats: .txt, .md (Max size: 5 MB)
                </span>
                <input
                  type="file"
                  accept=".txt,.md"
                  onChange={handleFileUpload}
                  className="text-xs text-slate-400 file:mr-2 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:bg-navy-800 file:text-cyan-400 hover:file:bg-navy-750 cursor-pointer"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input
                  label="Filename (required, e.g. outbreak_protocol.md)"
                  placeholder="protocol_ebola_2026.md"
                  value={filename}
                  onChange={(e) => setFilename(e.target.value)}
                />
                <Input
                  label="Document Title (optional)"
                  placeholder="e.g. State VHF Protocol"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
                <Input
                  label="Source Publisher / Agency (optional)"
                  placeholder="e.g. State Department of Health"
                  value={publisher}
                  onChange={(e) => setPublisher(e.target.value)}
                />
                <Input
                  label="Publication Date (optional)"
                  type="date"
                  value={pubDate}
                  onChange={(e) => setPubDate(e.target.value)}
                />
              </div>

              <Input
                label="Source Reference URL (optional)"
                placeholder="https://health.state.gov/guidelines/vhf"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Document Content (required, UTF-8 text or markdown)
                </label>
                <textarea
                  rows={8}
                  placeholder="# Case Definition and Response Protocol&#10;&#10;Enter full guideline text..."
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  className="w-full px-3 py-2 text-xs font-mono rounded-lg bg-navy-950 border border-navy-800 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-navy-800">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setIsUploadOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  disabled={!filename.trim() || !content.trim()}
                  isLoading={ingestMutation.isPending}
                  onClick={() => ingestMutation.mutate()}
                >
                  Ingest & Hash Document
                </Button>
              </div>
            </div>
          </Modal>

          {/* Document Library Table */}
          <Card>
            <CardContent className="p-0">
              {isLoading ? (
                <LoadingSpinner text="Querying registered reference documents..." />
              ) : isError ? (
                <div className="p-6">
                  <ErrorState
                    message={(error as any)?.message || 'Failed to list reference documents.'}
                    onRetry={() => refetch()}
                  />
                </div>
              ) : !data || data.items.length === 0 ? (
                <div className="p-6">
                  <EmptyState
                    icon={<FileText className="w-6 h-6 text-slate-400" />}
                    title="No reference documents found"
                    description="Ingest protocols, case definitions, or public health guidelines to build the evidence library foundation."
                    actionLabel="Ingest First Document"
                    onAction={() => setIsUploadOpen(true)}
                  />
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-navy-950/70 border-b border-navy-800 text-slate-400 uppercase tracking-wider font-mono text-[11px]">
                      <tr>
                        <th className="px-5 py-3 font-semibold">Document ID</th>
                        <th className="px-4 py-3 font-semibold">Title / Filename</th>
                        <th className="px-4 py-3 font-semibold">Format</th>
                        <th className="px-4 py-3 font-semibold">Publisher</th>
                        <th className="px-4 py-3 font-semibold">Size</th>
                        <th className="px-4 py-3 font-semibold">Content Hash (SHA-256)</th>
                        <th className="px-4 py-3 font-semibold">Status</th>
                        <th className="px-5 py-3 font-semibold text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-navy-800/60 text-slate-200">
                      {data.items.map((doc) => (
                        <tr
                          key={doc.id}
                          className="hover:bg-navy-850/60 transition-colors"
                        >
                          <td className="px-5 py-3 font-mono font-medium text-cyan-400">
                            {doc.document_id}
                          </td>
                          <td className="px-4 py-3">
                            <div className="font-semibold text-slate-200 truncate max-w-xs">
                              {doc.title || doc.filename}
                            </div>
                            <div className="text-[11px] text-slate-400 font-mono truncate max-w-xs">
                              {doc.filename}
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <Badge variant="outline" size="sm" className="font-mono uppercase">
                              {doc.doc_format}
                            </Badge>
                          </td>
                          <td className="px-4 py-3 text-slate-300">
                            {doc.source_publisher || '—'}
                          </td>
                          <td className="px-4 py-3 font-mono text-slate-400">
                            {formatBytes(doc.document_size_bytes)}
                          </td>
                          <td className="px-4 py-3 font-mono text-slate-400 text-[11px]">
                            <span className="truncate block max-w-[120px]" title={doc.content_hash}>
                              {doc.content_hash.slice(0, 12)}...
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <Badge variant="success" size="sm">
                              {doc.ingestion_status}
                            </Badge>
                          </td>
                          <td className="px-5 py-3 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <Button
                                size="sm"
                                variant="secondary"
                                className="text-[11px] h-7 px-2"
                                isLoading={processingDocId === doc.document_id}
                                disabled={processingDocId !== null}
                                onClick={() => processMutation.mutate(doc.document_id)}
                                title="Split into passage chunks and generate local embeddings"
                              >
                                {processingDocId === doc.document_id ? 'Indexing...' : 'Process & Index'}
                              </Button>

                              <Button
                                size="sm"
                                variant="outline"
                                className="text-[11px] h-7 px-2"
                                onClick={() => setInspectingDocId(doc.document_id)}
                                title="Inspect passage chunks extracted from this document"
                              >
                                Chunks
                              </Button>

                              <button
                                onClick={() => setSelectedDoc(doc)}
                                className="text-cyan-400 hover:text-cyan-300 p-1.5 rounded hover:bg-navy-800 focus:outline-none focus:ring-1 focus:ring-cyan-400"
                                title="Inspect Metadata"
                                aria-label={`Inspect metadata for document ${doc.filename}`}
                              >
                                <Eye className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {data && data.total > 0 && (
                <Pagination
                  currentPage={page}
                  totalPages={data.total_pages}
                  totalItems={data.total}
                  pageSize={pageSize}
                  onPageChange={(p) => setPage(p)}
                  onPageSizeChange={(s) => {
                    setPageSize(s)
                    setPage(1)
                  }}
                  disabled={isFetching}
                />
              )}
            </CardContent>
          </Card>
        </div>
      ) : (
        /* ================= SEMANTIC RETRIEVAL TAB ================= */
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-slate-200">
                Natural-Language Evidence Search
              </CardTitle>
              <CardDescription className="text-xs text-slate-400">
                Vector similarity search against indexed document chunks using local dense embeddings.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-col sm:flex-row gap-2">
                <div className="relative flex-1">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && searchQuery.trim()) {
                        searchMutation.mutate()
                      }
                    }}
                    placeholder="e.g. What are early syndromic surveillance thresholds for respiratory illness?"
                    className="w-full pl-9 pr-3 py-2 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  disabled={!searchQuery.trim()}
                  isLoading={searchMutation.isPending}
                  onClick={() => searchMutation.mutate()}
                  leftIcon={<Search className="w-3.5 h-3.5" />}
                >
                  Retrieve Evidence
                </Button>
              </div>

              {/* Filters */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
                <div>
                  <label className="block text-[11px] font-medium text-slate-300 mb-1">
                    Passage Limit (Top K: {searchTopK})
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="20"
                    value={searchTopK}
                    onChange={(e) => setSearchTopK(Number(e.target.value))}
                    className="w-full accent-cyan-400 cursor-pointer"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-medium text-slate-300 mb-1">
                    Source Publisher Filter (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. State Health Department"
                    value={searchPublisher}
                    onChange={(e) => setSearchPublisher(e.target.value)}
                    className="w-full px-2.5 py-1 text-xs rounded-lg bg-navy-950 border border-navy-700 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-medium text-slate-300 mb-1">
                    Min Similarity Cutoff: {searchMinSim.toFixed(2)}
                  </label>
                  <input
                    type="range"
                    min="0.0"
                    max="0.9"
                    step="0.05"
                    value={searchMinSim}
                    onChange={(e) => setSearchMinSim(Number(e.target.value))}
                    className="w-full accent-cyan-400 cursor-pointer"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Search Error Alert */}
          {searchError && (
            <div className="p-3.5 rounded-lg border border-rose-800/50 bg-rose-950/30 text-xs text-rose-200 flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <div className="flex-1">
                <span className="font-semibold text-rose-300 block">Query Execution Error</span>
                <span className="text-rose-200/90">{searchError}</span>
              </div>
              <button
                onClick={() => setSearchError(null)}
                className="text-slate-400 hover:text-slate-200 p-1"
                aria-label="Dismiss search error"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Search Results Display */}
          {searchMutation.isPending ? (
            <LoadingSpinner text="Computing query embedding and searching active vector index..." />
          ) : searchResults ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                <span>
                  Query execution <strong>{searchResults.query_id}</strong> returned{' '}
                  <strong className="text-cyan-400">{searchResults.total_results}</strong> passages
                </span>
                <span className="font-mono text-[11px]">
                  Model: {searchResults.embedding_model}
                </span>
              </div>

              {searchResults.items.length === 0 ? (
                <EmptyState
                  icon={<Search className="w-6 h-6 text-slate-400" />}
                  title="No matching evidence passages"
                  description="No indexed passages met the similarity cutoff. Try broadening the search query or processing additional reference documents."
                />
              ) : (
                <div className="space-y-3">
                  {searchResults.items.map((item, idx) => (
                    <Card key={item.chunk_id} className="bg-navy-900/80 border-navy-800 hover:border-navy-700 transition-colors">
                      <CardContent className="p-4 space-y-2.5 text-xs">
                        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-navy-800/60 pb-2">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-[11px] text-cyan-400 font-semibold">
                              #{idx + 1}
                            </span>
                            <span className="font-semibold text-slate-200">
                              {item.title || item.document_id}
                            </span>
                            <span className="text-[11px] font-mono text-slate-500">
                              {item.chunk_id}
                            </span>
                          </div>

                          <div className="flex items-center gap-2">
                            <span className="text-[11px] text-slate-400">Cosine Similarity:</span>
                            <Badge
                              variant={item.similarity_score >= 0.5 ? 'success' : item.similarity_score >= 0.3 ? 'info' : 'default'}
                              size="sm"
                              className="font-mono font-bold"
                            >
                              {item.similarity_score.toFixed(4)}
                            </Badge>
                          </div>
                        </div>

                        {/* Passage Text */}
                        <div className="p-3 rounded-lg bg-navy-950/80 border border-navy-800 text-slate-200 text-xs font-mono whitespace-pre-wrap leading-relaxed select-text">
                          {item.text}
                        </div>

                        {/* Provenance Metadata */}
                        <div className="flex flex-wrap items-center justify-between text-[11px] text-slate-400 pt-1">
                          <div className="flex items-center gap-3">
                            <span>
                              Offsets: <strong className="font-mono text-slate-300">{item.char_start}–{item.char_end}</strong>
                            </span>
                            <span>
                              Publisher: <strong className="text-slate-300">{item.source_publisher || 'Unspecified'}</strong>
                            </span>
                            {item.publication_date && (
                              <span>
                                Date: <strong className="text-slate-300">{item.publication_date}</strong>
                              </span>
                            )}
                          </div>

                          {item.source_url && (
                            <a
                              href={item.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-cyan-400 hover:underline flex items-center gap-1"
                            >
                              Source <ExternalLink className="w-3 h-3" />
                            </a>
                          )}
                        </div>

                        {/* Non-clinical disclosure */}
                        <p className="text-[10px] text-slate-500 italic">
                          {item.score_interpretation}
                        </p>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </div>
      )}

      {/* Chunks Inspector Modal */}
      {inspectingDocId && (
        <Modal
          isOpen={!!inspectingDocId}
          onClose={() => setInspectingDocId(null)}
          title={`Document Passage Chunks`}
          subtitle={`Source Identifier: ${inspectingDocId}`}
          maxWidth="2xl"
        >
          <div className="space-y-4 text-xs">
            {isChunksLoading ? (
              <LoadingSpinner text="Loading passage chunks from database..." />
            ) : !chunksData || chunksData.items.length === 0 ? (
              <EmptyState
                icon={<Layers className="w-6 h-6 text-slate-400" />}
                title="No chunks extracted"
                description="This document has not been processed yet. Click 'Process & Index' in the document table to extract passage chunks and generate embeddings."
              />
            ) : (
              <div className="space-y-3 max-h-[65vh] overflow-y-auto pr-1">
                <div className="text-[11px] text-slate-400 pb-1 flex justify-between">
                  <span>Total chunks: {chunksData.total}</span>
                  <span className="font-mono">Model: {chunksData.items[0]?.embedding_model || '—'}</span>
                </div>

                {chunksData.items.map((chunk: DocumentChunk) => (
                  <div
                    key={chunk.chunk_id}
                    className="p-3 rounded-lg bg-navy-950 border border-navy-800 space-y-2"
                  >
                    <div className="flex items-center justify-between font-mono text-[11px] text-slate-400 border-b border-navy-800/60 pb-1.5">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" size="sm">
                          Chunk #{chunk.sequence_number}
                        </Badge>
                        <span className="text-cyan-400">{chunk.chunk_id}</span>
                      </div>
                      <span>
                        Offsets: {chunk.char_start}–{chunk.char_end} ({chunk.char_end - chunk.char_start} chars)
                      </span>
                    </div>

                    <p className="text-xs text-slate-200 font-mono whitespace-pre-wrap leading-relaxed select-text p-2 rounded bg-navy-900/60 border border-navy-850">
                      {chunk.text}
                    </p>

                    <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono">
                      <span>Hash: {chunk.content_hash.slice(0, 16)}...</span>
                      <span>Created: {formatDateTime(chunk.created_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="flex justify-end pt-2 border-t border-navy-800">
              <Button size="sm" variant="secondary" onClick={() => setInspectingDocId(null)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Document Detail Modal */}
      {selectedDoc && (
        <Modal
          isOpen={!!selectedDoc}
          onClose={() => setSelectedDoc(null)}
          title={selectedDoc.title || selectedDoc.filename}
          subtitle={`Identifier: ${selectedDoc.document_id}`}
          maxWidth="lg"
        >
          <div className="space-y-4 text-xs">
            <div className="p-3 rounded-lg bg-navy-950 border border-navy-800 space-y-2">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                Cryptographic SHA-256 Digest:
              </span>
              <p className="font-mono text-[11px] text-cyan-300 break-all select-all p-2 rounded bg-navy-900 border border-navy-800">
                {selectedDoc.content_hash}
              </p>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800">
                <span className="text-slate-400">File Size:</span>
                <p className="text-base font-bold text-slate-100 font-mono mt-0.5">
                  {formatBytes(selectedDoc.document_size_bytes)}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800">
                <span className="text-slate-400">Word Count:</span>
                <p className="text-base font-bold text-slate-100 font-mono mt-0.5">
                  {selectedDoc.word_count}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800">
                <span className="text-slate-400">Characters:</span>
                <p className="text-base font-bold text-slate-100 font-mono mt-0.5">
                  {selectedDoc.character_count}
                </p>
              </div>
            </div>

            <div className="space-y-2 pt-2 border-t border-navy-800">
              <div className="flex justify-between py-1.5 border-b border-navy-800/40">
                <span className="text-slate-400">Filename:</span>
                <span className="font-mono text-slate-200">{selectedDoc.filename}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-navy-800/40">
                <span className="text-slate-400">Format:</span>
                <Badge variant="outline">{selectedDoc.doc_format.toUpperCase()}</Badge>
              </div>
              <div className="flex justify-between py-1.5 border-b border-navy-800/40">
                <span className="text-slate-400">Publisher:</span>
                <span className="text-slate-200">{selectedDoc.source_publisher || 'Unspecified'}</span>
              </div>
              {selectedDoc.source_url && (
                <div className="flex justify-between py-1.5 border-b border-navy-800/40">
                  <span className="text-slate-400">Source URL:</span>
                  <a
                    href={selectedDoc.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-cyan-400 hover:underline flex items-center gap-1"
                  >
                    Link <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              )}
              <div className="flex justify-between py-1.5 border-b border-navy-800/40">
                <span className="text-slate-400">Publication Date:</span>
                <span className="font-mono text-slate-200">{selectedDoc.publication_date || '—'}</span>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="text-slate-400">Ingested At:</span>
                <span className="font-mono text-slate-400">{formatDateTime(selectedDoc.ingestion_timestamp)}</span>
              </div>
            </div>

            <div className="flex justify-end pt-3">
              <Button size="sm" variant="secondary" onClick={() => setSelectedDoc(null)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
