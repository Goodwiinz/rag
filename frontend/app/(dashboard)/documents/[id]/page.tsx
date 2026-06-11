/**
 * Document Detail Page
 * Document overview, citations, metadata, preview, and table extraction.
 */

'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { api } from '@/services/api-client';
import { Document, APIErrorClass } from '@/types';
import { cn } from '@/lib/utils';
import {
  ArrowLeft,
  Download,
  FileText,
  HardDrive,
  Share2,
  Trash2,
  RefreshCw,
  AlertTriangle,
  Eye,
  Shield,
  Sparkles,
  Activity,
  Code,
  LayoutGrid,
  BookOpen,
  Loader2,
  Table2,
} from 'lucide-react';
import { ProcessingStatus } from '@/components/documents/ProcessingStatus';
import { IntegrityBadge } from '@/components/documents/IntegrityBadge';
import { IntegrityDetail } from '@/components/documents/IntegrityDetail';
import { citationService } from '@/services/citationService';
import { getIntegrityScore, extractTables } from '@/services/scispaceService';
import { DocumentOverviewTab } from '@/components/documents/DocumentOverviewTab';
import { DocumentMetadataTab } from '@/components/documents/DocumentMetadataTab';
import { DocumentPreviewTab } from '@/components/documents/DocumentPreviewTab';
import { DocumentTablesTab } from '@/components/documents/DocumentTablesTab';
import type { ExtractedTable, ExtractRegionResponse } from '@/types/scispace';
import type { CitationResponse } from '@/types/research';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();

  const [document, setDocument] = useState<Document | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<
    'overview' | 'metadata' | 'preview' | 'tables'
  >('overview');

  // Citation extraction state
  const [citations, setCitations] = useState<CitationResponse[]>([]);
  const [extracting, setExtracting] = useState(false);
  const [extractionError, setExtractionError] = useState<string | null>(null);

  const [tables, setTables] = useState<ExtractedTable[]>([]);
  const [tablesLoading, setTablesLoading] = useState(false);
  const [regionResult, setRegionResult] =
    useState<ExtractRegionResponse | null>(null);
  const [cropActive, setCropActive] = useState(false);
  const tablesContainerRef = useRef<HTMLDivElement>(null);

  const [integrityOpen, setIntegrityOpen] = useState(false);
  const [integrityScore, setIntegrityScore] = useState<{
    ai_probability: number;
    human_probability: number;
  } | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const documentId = params.id as string;

  const fetchDocument = useCallback(async () => {
    if (!documentId) return;

    setLoading(true);
    try {
      const response = await api.get<Document>(`/documents/${documentId}`);
      if (response) {
        // Normalize: backend detail API returns document_type, not file_type
        const doc =
          response.document_type && !response.file_type
            ? {
                ...response,
                file_type: response.document_type as Document['file_type'],
              }
            : response;
        setDocument(doc);
      } else {
        setError('Document not found');
      }
    } catch (err) {
      console.error('Error fetching document:', err);
      if (err instanceof APIErrorClass) {
        setError(err.error.message || 'Failed to fetch document');
      } else {
        setError('An unexpected error occurred');
      }
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchDocument();
    }
  }, [isAuthenticated, fetchDocument]);

  const handleDelete = async () => {
    if (!document) return;
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!document) return;
    try {
      await api.delete(`/documents/${document.id}`);
      router.push('/documents');
    } catch (err) {
      console.error('Failed to delete document:', err);
      setDeleteDialogOpen(false);
    }
  };

  const handleRetry = async () => {
    if (!document) return;

    try {
      await api.post(`/documents/${document.id}/reprocess`);
      fetchDocument();
    } catch (err) {
      console.error('Failed to retry processing:', err);
    }
  };

  const handleExtractCitations = async () => {
    if (!document) return;

    setExtracting(true);
    setExtractionError(null);

    try {
      // Extract citations using hybrid strategy
      await citationService.extractCitations(document.id, 'auto');

      // Fetch all citations for this document
      const allCitations = await citationService.getCitationsForDocument(
        document.id
      );
      setCitations(allCitations);
    } catch (err) {
      console.error('Citation extraction failed:', err);
      if (err instanceof APIErrorClass) {
        setExtractionError(err.error.message || 'Failed to extract citations');
      } else {
        setExtractionError('An unexpected error occurred during extraction');
      }
    } finally {
      setExtracting(false);
    }
  };

  const handleFetchTables = async () => {
    if (!document) return;
    setTablesLoading(true);
    try {
      const data = await extractTables(document.id);
      setTables(data.tables);
    } catch {
      console.error('Failed to extract tables');
    } finally {
      setTablesLoading(false);
    }
  };

  // Fetch citations on load
  useEffect(() => {
    if (document) {
      citationService
        .getCitationsForDocument(document.id)
        .then(setCitations)
        .catch((err) => console.error('Failed to fetch citations:', err));
    }
  }, [document]);

  useEffect(() => {
    if (document) {
      getIntegrityScore(document.id)
        .then((data) =>
          setIntegrityScore({
            ai_probability: data.ai_probability,
            human_probability: data.human_probability,
          })
        )
        .catch((err) => {
          if (
            !(err instanceof APIErrorClass && err.error.status_code === 404)
          ) {
            console.error('Failed to fetch integrity:', err);
          }
        });
    }
  }, [document]);

  const formatFileSize = (bytes?: number): string => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const formatDate = (dateString?: string): string => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <header className="border-b border-border bg-card/80 backdrop-blur-xl sticky top-0 z-10">
          <div className="max-w-7xl mx-auto px-6 h-16 flex items-center gap-4">
            <div className="h-9 w-9 rounded-lg bg-muted animate-pulse" />
            <div className="h-6 w-px bg-border" />
            <div className="h-8 w-8 rounded-lg bg-muted animate-pulse" />
            <div className="space-y-1.5">
              <div className="h-4 w-48 rounded bg-muted animate-pulse" />
              <div className="h-3 w-24 rounded bg-muted animate-pulse" />
            </div>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-6 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-6">
              <div className="h-40 rounded-xl border border-border bg-card animate-pulse" />
              <div className="h-64 rounded-xl border border-border bg-card animate-pulse" />
            </div>
            <div className="space-y-6">
              <div className="h-64 rounded-xl border border-border bg-card animate-pulse" />
              <div className="h-36 rounded-xl border border-border bg-card animate-pulse" />
            </div>
          </div>
          <span className="sr-only" role="status">
            Loading document…
          </span>
        </main>
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-6">
        <div
          role="alert"
          className="max-w-md w-full rounded-xl border border-destructive/30 bg-destructive/5 p-8 text-center"
        >
          <AlertTriangle
            aria-hidden="true"
            className="w-10 h-10 text-destructive mx-auto mb-4"
          />
          <h2 className="text-lg font-semibold text-foreground mb-2">
            Couldn&apos;t load this document
          </h2>
          <p className="text-sm text-muted-foreground mb-6">
            {error || 'Document not found.'}
          </p>
          <div className="flex items-center justify-center gap-3">
            <button
              type="button"
              onClick={fetchDocument}
              className="px-4 py-2 rounded-lg border border-border bg-card text-sm font-medium text-foreground hover:bg-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              Retry
            </button>
            <button
              type="button"
              onClick={() => router.push('/documents')}
              className="px-4 py-2 rounded-lg bg-primary text-sm font-medium text-primary-foreground hover:bg-[var(--nous-helios)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              Back to documents
            </button>
          </div>
        </div>
      </div>
    );
  }

  const isIndexed = document.processing_status === 'indexed';
  const isPdf =
    document.document_type === 'pdf' || document.file_type === 'pdf';

  return (
    <div className="min-h-screen bg-background text-foreground pb-20">
      {/* Header / Nav */}
      <header className="border-b border-border bg-card/80 backdrop-blur-xl sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-4 min-w-0">
            <button
              type="button"
              onClick={() => router.push('/documents')}
              aria-label="Back to documents"
              className="p-2 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <ArrowLeft aria-hidden="true" className="w-5 h-5" />
            </button>
            <div className="h-6 w-px bg-border" />
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                <FileText aria-hidden="true" className="w-4 h-4 text-primary" />
              </div>
              <div className="min-w-0">
                <h1 className="text-sm font-semibold text-foreground truncate max-w-[200px] md:max-w-md">
                  {document.title}
                </h1>
                <p className="text-xs text-muted-foreground tabular-nums">
                  ID {document.id.substring(0, 8)}
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              className="hidden md:inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border bg-card text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <Download aria-hidden="true" className="w-3.5 h-3.5" />
              Download
            </button>
            <button
              type="button"
              className="hidden md:inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border bg-card text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <Share2 aria-hidden="true" className="w-3.5 h-3.5" />
              Share
            </button>
            <button
              type="button"
              onClick={handleDelete}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-destructive/20 bg-destructive/5 text-xs font-medium text-destructive hover:bg-destructive/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <Trash2 aria-hidden="true" className="w-3.5 h-3.5" />
              Delete
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content Area */}
          <div className="lg:col-span-2 space-y-6">
            {/* Status Card */}
            <section className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
              <div className="px-6 py-4 border-b border-border bg-muted/30 flex items-center justify-between">
                <h2 className="text-sm font-medium text-foreground flex items-center gap-2">
                  <Activity
                    aria-hidden="true"
                    className="w-4 h-4 text-primary"
                  />
                  Processing status
                </h2>
                {document.processing_status === 'failed' && (
                  <button
                    type="button"
                    onClick={handleRetry}
                    className="text-xs font-medium text-primary hover:underline underline-offset-4 inline-flex items-center gap-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded"
                  >
                    <RefreshCw aria-hidden="true" className="w-3.5 h-3.5" />
                    Retry processing
                  </button>
                )}
              </div>
              <div className="p-6">
                <ProcessingStatus
                  document={document}
                  enableRealtime={true}
                  compact={false}
                  className="bg-transparent border-none p-0"
                />
              </div>
            </section>

            {/* Citations Card */}
            <section className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
              <div className="px-6 py-4 border-b border-border bg-muted/30 flex items-center justify-between gap-3">
                <h2 className="text-sm font-medium text-foreground flex items-center gap-2">
                  <BookOpen
                    aria-hidden="true"
                    className="w-4 h-4 text-primary"
                  />
                  Research citations
                </h2>
                <button
                  type="button"
                  onClick={handleExtractCitations}
                  disabled={extracting || !isIndexed}
                  title={
                    !isIndexed
                      ? 'Citations can be extracted once the document is indexed'
                      : undefined
                  }
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                    extracting || !isIndexed
                      ? 'bg-muted text-muted-foreground cursor-not-allowed'
                      : 'bg-primary/10 border border-primary/30 text-primary hover:bg-primary/20'
                  )}
                >
                  {extracting ? (
                    <>
                      <Loader2
                        aria-hidden="true"
                        className="w-3.5 h-3.5 animate-spin"
                      />
                      Extracting…
                    </>
                  ) : (
                    <>
                      <Sparkles aria-hidden="true" className="w-3.5 h-3.5" />
                      Extract citations
                    </>
                  )}
                </button>
              </div>

              <div className="p-6">
                {/* Extraction Error */}
                {extractionError && (
                  <div
                    role="alert"
                    className="mb-4 p-4 rounded-lg border border-destructive/30 bg-destructive/5 flex items-start gap-3"
                  >
                    <AlertTriangle
                      aria-hidden="true"
                      className="w-5 h-5 text-destructive mt-0.5 shrink-0"
                    />
                    <div>
                      <p className="text-sm font-medium text-destructive">
                        Extraction failed
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {extractionError}
                      </p>
                    </div>
                  </div>
                )}

                {/* Extraction Progress */}
                {extracting && (
                  <div
                    role="status"
                    className="space-y-3 rounded-lg border border-border bg-muted/20 p-4"
                  >
                    <div className="flex items-center gap-3">
                      <Loader2
                        aria-hidden="true"
                        className="w-4 h-4 text-primary animate-spin"
                      />
                      <div>
                        <p className="text-sm font-medium text-foreground">
                          Analyzing document…
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Matching references against arXiv, Semantic Scholar,
                          and CrossRef.
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Citations List */}
                {!extracting && citations.length > 0 && (
                  <div className="space-y-3">
                    <p className="text-xs text-muted-foreground mb-4">
                      Found{' '}
                      <span className="font-medium text-foreground tabular-nums">
                        {citations.length}
                      </span>{' '}
                      citation{citations.length !== 1 ? 's' : ''}
                    </p>

                    <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                      {citations.map((citation) => (
                        <div
                          key={citation.id}
                          className="p-4 rounded-lg border border-border bg-muted/10 hover:bg-muted/30 transition-colors"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <h4 className="text-sm font-medium text-foreground line-clamp-2 mb-1.5">
                                {citation.documentTitle || 'Untitled'}
                              </h4>
                              <p className="text-xs text-muted-foreground">
                                {citation.authors && citation.authors.length > 0
                                  ? citation.authors.slice(0, 3).join(', ') +
                                    (citation.authors.length > 3
                                      ? ', et al.'
                                      : '')
                                  : 'Unknown authors'}
                                {citation.year && ` (${citation.year})`}
                              </p>
                              {citation.venue && (
                                <p className="text-xs text-muted-foreground/80 mt-1">
                                  {citation.venue}
                                </p>
                              )}
                            </div>

                            {citation.needsReview && (
                              <span className="px-2 py-1 rounded text-[10px] font-medium bg-[var(--nous-helios)]/10 text-[var(--nous-helios)] border border-[var(--nous-helios)]/20 inline-flex items-center gap-1 shrink-0">
                                <AlertTriangle
                                  aria-hidden="true"
                                  className="w-3 h-3"
                                />
                                Needs review
                              </span>
                            )}
                          </div>

                          {(citation.arxivId || citation.doi) && (
                            <div className="mt-3 pt-3 border-t border-border flex flex-wrap gap-2">
                              {citation.arxivId && (
                                <span className="px-2 py-0.5 rounded text-[11px] bg-muted text-muted-foreground border border-border tabular-nums">
                                  arXiv: {citation.arxivId}
                                </span>
                              )}
                              {citation.doi && (
                                <span className="px-2 py-0.5 rounded text-[11px] bg-muted text-muted-foreground border border-border tabular-nums">
                                  DOI: {citation.doi}
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Empty State */}
                {!extracting && citations.length === 0 && !extractionError && (
                  <div className="text-center py-12">
                    <BookOpen
                      aria-hidden="true"
                      className="w-10 h-10 text-muted-foreground mx-auto mb-4"
                    />
                    <p className="text-sm font-medium text-foreground mb-1">
                      No citations yet
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {isIndexed
                        ? 'Run extraction to pull references from this document.'
                        : 'Citations become available once the document is indexed.'}
                    </p>
                  </div>
                )}
              </div>
            </section>

            {/* Tabs */}
            <div
              role="tablist"
              aria-label="Document sections"
              className="flex items-center gap-1 border-b border-border overflow-x-auto"
            >
              {[
                { id: 'overview', label: 'Overview', icon: LayoutGrid },
                { id: 'metadata', label: 'Metadata', icon: Code },
                { id: 'preview', label: 'Preview', icon: Eye },
                { id: 'tables', label: 'Tables', icon: Table2 },
              ].map((tab) => {
                const active = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    onClick={() => setActiveTab(tab.id as typeof activeTab)}
                    className={cn(
                      'px-4 py-3 text-sm font-medium inline-flex items-center gap-2 border-b-2 -mb-px transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded-t',
                      active
                        ? 'border-primary text-primary'
                        : 'border-transparent text-muted-foreground hover:text-foreground'
                    )}
                  >
                    <tab.icon aria-hidden="true" className="w-4 h-4" />
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* Tab Content */}
            <div className="min-h-[400px]">
              {activeTab === 'overview' && (
                <DocumentOverviewTab document={document} />
              )}

              {activeTab === 'metadata' && (
                <DocumentMetadataTab metadata={document.metadata || {}} />
              )}

              {activeTab === 'preview' && (
                <DocumentPreviewTab />
              )}

              {activeTab === 'tables' && (
                <DocumentTablesTab
                  isPdf={isPdf}
                  isIndexed={isIndexed}
                  tables={tables}
                  tablesLoading={tablesLoading}
                  regionResult={regionResult}
                  cropActive={cropActive}
                  tablesContainerRef={tablesContainerRef}
                  documentId={documentId}
                  onFetchTables={handleFetchTables}
                  onSetTables={setTables}
                  onSetRegionResult={setRegionResult}
                  onSetCropActive={setCropActive}
                />
              )}
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* File Info Card */}
            <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
              <h3 className="text-sm font-medium text-foreground mb-4 flex items-center gap-2">
                <HardDrive
                  aria-hidden="true"
                  className="w-4 h-4 text-muted-foreground"
                />
                File details
              </h3>

              <dl className="space-y-3 text-sm">
                <div className="flex justify-between items-center gap-3 border-b border-border pb-3">
                  <dt className="text-muted-foreground shrink-0">Filename</dt>
                  <dd
                    className="text-foreground truncate max-w-[150px]"
                    title={document.filename}
                  >
                    {document.filename}
                  </dd>
                </div>
                <div className="flex justify-between items-center gap-3 border-b border-border pb-3">
                  <dt className="text-muted-foreground shrink-0">Type</dt>
                  <dd className="text-primary bg-primary/10 px-2 py-0.5 rounded text-xs font-medium">
                    {document.document_type?.toUpperCase() ||
                      document.file_type?.toUpperCase() ||
                      document.mime_type?.toUpperCase() ||
                      'Unknown'}
                  </dd>
                </div>
                <div className="flex justify-between items-center gap-3 border-b border-border pb-3">
                  <dt className="text-muted-foreground shrink-0">Size</dt>
                  <dd className="text-foreground tabular-nums">
                    {formatFileSize(
                      document.file_size_bytes || document.file_size
                    )}
                  </dd>
                </div>
                <div className="flex justify-between items-center gap-3 border-b border-border pb-3">
                  <dt className="text-muted-foreground shrink-0">Uploaded</dt>
                  <dd className="text-foreground text-right">
                    {formatDate(
                      document.created_at || document.upload_timestamp
                    )}
                  </dd>
                </div>
                <div className="flex justify-between items-center gap-3">
                  <dt className="text-muted-foreground shrink-0">
                    Last modified
                  </dt>
                  <dd className="text-foreground text-right">
                    {formatDate(
                      document.updated_at ||
                        document.created_at ||
                        document.upload_timestamp
                    )}
                  </dd>
                </div>
              </dl>
            </section>

            {/* AI Integrity Card */}
            <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
              <h3 className="text-sm font-medium text-foreground mb-4 flex items-center gap-2">
                <Shield
                  aria-hidden="true"
                  className="w-4 h-4 text-muted-foreground"
                />
                Content integrity
              </h3>
              <div className="flex items-center justify-between mb-4">
                <IntegrityBadge
                  documentId={documentId}
                  score={integrityScore}
                  onRequestCheck={() => setIntegrityOpen(true)}
                />
              </div>
              <button
                type="button"
                onClick={() => setIntegrityOpen(true)}
                className="w-full px-3 py-2 rounded-lg border border-border bg-muted/20 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted/40 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                View details
              </button>
            </section>
          </div>
        </div>
      </main>
      <IntegrityDetail
        documentId={documentId}
        isOpen={integrityOpen}
        onClose={() => setIntegrityOpen(false)}
      />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete document?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this document. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
