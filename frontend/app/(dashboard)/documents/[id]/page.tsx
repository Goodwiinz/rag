/**
 * Document Detail Page
 * Terminal Observatory themed document details interface
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
  Tag,
  Trash2,
  RefreshCw,
  AlertTriangle,
  Eye,
  Shield,
  Sparkles,
  Activity,
  Cpu,
  Terminal,
  Code,
  BookOpen,
  Loader2,
  Table2,
  Crop,
} from 'lucide-react';
import { ProcessingStatus } from '@/components/documents/ProcessingStatus';
import { IntegrityBadge } from '@/components/documents/IntegrityBadge';
import { IntegrityDetail } from '@/components/documents/IntegrityDetail';
import { citationService } from '@/services/citationService';
import { getIntegrityScore, extractTables } from '@/services/scispaceService';
import { ExtractedTablePreview } from '@/components/documents/ExtractedTablePreview';
import { CropExtractOverlay } from '@/components/documents/CropExtractOverlay';
import type { ExtractedTable, ExtractRegionResponse } from '@/types/scispace';
import type { CitationResponse } from '@/types/research';

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

    if (
      confirm(
        'Are you sure you want to delete this document? This action cannot be undone.'
      )
    ) {
      try {
        await api.delete(`/documents/${document.id}`);
        router.push('/documents');
      } catch (err) {
        console.error('Failed to delete document:', err);
        alert('Failed to delete document');
      }
    }
  };

  const handleRetry = async () => {
    if (!document) return;

    try {
      await api.post(`/documents/${document.id}/reprocess`);
      fetchDocument();
    } catch (err) {
      console.error('Failed to retry processing:', err);
      alert('Failed to retry processing');
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
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-[#D4A039]/30 border-t-[#D4A039] rounded-full animate-spin" />
          <p className="text-[#D4A039] font-mono text-sm animate-pulse">
            ACCESSING ARCHIVE...
          </p>
        </div>
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center p-6">
        <div className="max-w-md w-full border border-red-500/30 bg-red-500/5 rounded-xl p-8 text-center">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-mono font-bold text-red-500 mb-2">
            ACCESS DENIED
          </h2>
          <p className="text-red-400/80 font-mono text-sm mb-6">
            {error || 'Document not found'}
          </p>
          <button
            onClick={() => router.push('/documents')}
            className="px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-500 font-mono text-sm hover:bg-red-500/20 transition-all"
          >
            RETURN TO INDEX
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-muted-foreground font-sans pb-20">
      {/* Header / Nav */}
      <header className="border-b border-[#1a1a28] bg-[#0a0a0f]/80 backdrop-blur-xl sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push('/documents')}
              className="p-2 rounded-lg hover:bg-[#1a1a28] text-muted-foreground hover:text-[#D4A039] transition-all"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="h-6 w-px bg-[#1a1a28]" />
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded bg-[#D4A039]/10 border border-[#D4A039]/20 flex items-center justify-center">
                <FileText className="w-4 h-4 text-[#D4A039]" />
              </div>
              <div>
                <h1 className="text-sm font-mono font-bold text-white tracking-wide truncate max-w-[200px] md:max-w-md">
                  {document.title}
                </h1>
                <p className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">
                  ID: {document.id.substring(0, 8)}
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[#1a1a28] bg-[#0d0d14] text-xs font-mono text-muted-foreground hover:text-white hover:border-border transition-all">
              <Download className="w-3.5 h-3.5" />
              DOWNLOAD
            </button>
            <button className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[#1a1a28] bg-[#0d0d14] text-xs font-mono text-muted-foreground hover:text-white hover:border-border transition-all">
              <Share2 className="w-3.5 h-3.5" />
              SHARE
            </button>
            <button
              onClick={handleDelete}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-red-500/20 bg-red-500/5 text-xs font-mono text-red-500 hover:bg-red-500/10 transition-all"
            >
              <Trash2 className="w-3.5 h-3.5" />
              DELETE
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content Area */}
          <div className="lg:col-span-2 space-y-6">
            {/* Status Card */}
            <div className="rounded-xl border border-[#1a1a28] bg-[#0d0d14] overflow-hidden">
              <div className="px-6 py-4 border-b border-[#1a1a28] flex items-center justify-between">
                <h2 className="text-xs font-mono font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                  <Activity className="w-4 h-4 text-[#D4A039]" />
                  Processing Status
                </h2>
                {document.processing_status === 'failed' && (
                  <button
                    onClick={handleRetry}
                    className="text-xs font-mono text-[#D4A039] hover:underline flex items-center gap-1"
                  >
                    <RefreshCw className="w-3 h-3" />
                    RETRY
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
            </div>

            {/* Citations Card */}
            <div className="rounded-xl border border-[#1a1a28] bg-[#0d0d14] overflow-hidden">
              <div className="px-6 py-4 border-b border-[#1a1a28] flex items-center justify-between">
                <h2 className="text-xs font-mono font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-[#D4A039]" />
                  Research Citations
                </h2>
                <button
                  onClick={handleExtractCitations}
                  disabled={
                    extracting || document.processing_status !== 'indexed'
                  }
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-xs font-mono font-bold flex items-center gap-2 transition-all',
                    extracting || document.processing_status !== 'indexed'
                      ? 'bg-gray-800 text-muted-foreground cursor-not-allowed'
                      : 'bg-[#D4A039]/10 border border-[#D4A039]/30 text-[#D4A039] hover:bg-[#D4A039]/20 hover:shadow-[0_0_20px_rgba(212,160,57,0.2)]'
                  )}
                >
                  {extracting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      EXTRACTING...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" />
                      EXTRACT CITATIONS
                    </>
                  )}
                </button>
              </div>

              <div className="p-6">
                {/* Extraction Error */}
                {extractionError && (
                  <div className="mb-4 p-4 rounded-lg border border-red-500/30 bg-red-500/5 flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-mono font-bold text-red-500">
                        Extraction Failed
                      </p>
                      <p className="text-xs font-mono text-red-400/80 mt-1">
                        {extractionError}
                      </p>
                    </div>
                  </div>
                )}

                {/* Extraction Progress */}
                {extracting && (
                  <div className="space-y-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full border-4 border-[#D4A039]/30 border-t-[#D4A039] animate-spin" />
                      <div>
                        <p className="text-sm font-mono font-bold text-[#D4A039]">
                          Analyzing Document...
                        </p>
                        <p className="text-xs font-mono text-muted-foreground mt-0.5">
                          Using hybrid extraction pipeline (ArXiv → Semantic
                          Scholar → CrossRef)
                        </p>
                      </div>
                    </div>
                    <div className="h-1 bg-[#1a1a28] rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-[#D4A039] to-cyan-500 animate-pulse w-2/3" />
                    </div>
                  </div>
                )}

                {/* Citations List */}
                {!extracting && citations.length > 0 && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between mb-4">
                      <p className="text-xs font-mono text-muted-foreground">
                        Found{' '}
                        <span className="text-[#D4A039] font-bold">
                          {citations.length}
                        </span>{' '}
                        citation{citations.length !== 1 ? 's' : ''}
                      </p>
                    </div>

                    <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                      {citations.map((citation) => (
                        <div
                          key={citation.id}
                          className="p-4 rounded-lg border border-[#1a1a28] bg-[#1a1a28]/30 hover:bg-[#1a1a28]/50 transition-all"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <h4 className="text-sm font-mono font-bold text-white line-clamp-2 mb-2">
                                {citation.documentTitle || 'Untitled'}
                              </h4>
                              <p className="text-xs font-mono text-muted-foreground">
                                {citation.authors && citation.authors.length > 0
                                  ? citation.authors.slice(0, 3).join(', ') +
                                    (citation.authors.length > 3
                                      ? ', et al.'
                                      : '')
                                  : 'Unknown authors'}
                                {citation.year && ` (${citation.year})`}
                              </p>
                              {citation.venue && (
                                <p className="text-xs font-mono text-muted-foreground mt-1">
                                  {citation.venue}
                                </p>
                              )}
                            </div>

                            {citation.needsReview && (
                              <span className="px-2 py-1 rounded text-[9px] font-mono font-bold uppercase tracking-wider bg-[#ffb700]/10 text-[#ffb700] border border-[#ffb700]/20 flex items-center gap-1 flex-shrink-0">
                                <AlertTriangle className="w-3 h-3" />
                                Review
                              </span>
                            )}
                          </div>

                          {(citation.arxivId || citation.doi) && (
                            <div className="mt-3 pt-3 border-t border-[#1a1a28] flex flex-wrap gap-2">
                              {citation.arxivId && (
                                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[#D4A039]/5 text-[#D4A039] border border-[#D4A039]/20">
                                  ArXiv: {citation.arxivId}
                                </span>
                              )}
                              {citation.doi && (
                                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-500/5 text-cyan-500 border border-cyan-500/20">
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
                    <BookOpen className="w-12 h-12 text-foreground mx-auto mb-4" />
                    <p className="font-mono text-sm text-muted-foreground mb-2">
                      No citations extracted yet
                    </p>
                    <p className="font-mono text-xs text-foreground">
                      Click "Extract Citations" to analyze this document
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Tabs */}
            <div className="flex items-center gap-2 border-b border-[#1a1a28]">
              {[
                { id: 'overview', label: 'Overview', icon: Terminal },
                { id: 'metadata', label: 'Metadata', icon: Code },
                { id: 'preview', label: 'Preview', icon: Eye },
                { id: 'tables', label: 'Tables', icon: Table2 },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={cn(
                    'px-4 py-3 text-xs font-mono font-bold flex items-center gap-2 border-b-2 transition-all',
                    activeTab === tab.id
                      ? 'border-[#D4A039] text-[#D4A039] bg-[#D4A039]/5'
                      : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-[#1a1a28]/50'
                  )}
                >
                  <tab.icon className="w-4 h-4" />
                  {tab.label.toUpperCase()}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="min-h-[400px]">
              {activeTab === 'overview' && (
                <div className="space-y-6 py-6">
                  {/* Summary / Description */}
                  <div className="rounded-xl border border-[#1a1a28] bg-[#0d0d14] p-6">
                    <h3 className="text-xs font-mono font-bold text-muted-foreground uppercase tracking-widest mb-4 flex items-center gap-2">
                      <FileText className="w-4 h-4" />
                      Content Summary
                    </h3>
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      {document.content_summary ||
                        document.content_preview ||
                        document.description ||
                        'No description available for this document.'}
                    </p>

                    {/* Tags */}
                    {document.tags && document.tags.length > 0 && (
                      <div className="mt-6 pt-6 border-t border-[#1a1a28]">
                        <div className="flex flex-wrap gap-2">
                          {document.tags.map((tag) => (
                            <span
                              key={tag}
                              className="px-2 py-1 rounded bg-[#1a1a28] text-[10px] font-mono text-[#D4A039] border border-[#D4A039]/20 flex items-center gap-1"
                            >
                              <Tag className="w-3 h-3" />
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* AI Insights Placeholder */}
                  <div className="rounded-xl border border-[#1a1a28] bg-[#0d0d14] p-6 relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-10">
                      <Sparkles className="w-24 h-24 text-[#D4A039]" />
                    </div>
                    <h3 className="text-xs font-mono font-bold text-muted-foreground uppercase tracking-widest mb-4 flex items-center gap-2">
                      <Cpu className="w-4 h-4" />
                      AI Analysis
                    </h3>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="p-4 rounded-lg bg-[#1a1a28]/50 border border-[#1a1a28]">
                        <span className="text-[10px] font-mono text-muted-foreground uppercase">
                          Entity Density
                        </span>
                        <div className="text-xl font-mono font-bold text-white mt-1">
                          High{' '}
                          <span className="text-xs font-normal text-muted-foreground">
                            (Top 10%)
                          </span>
                        </div>
                      </div>
                      <div className="p-4 rounded-lg bg-[#1a1a28]/50 border border-[#1a1a28]">
                        <span className="text-[10px] font-mono text-muted-foreground uppercase">
                          Knowledge Graph
                        </span>
                        <div className="text-xl font-mono font-bold text-white mt-1">
                          Connected{' '}
                          <span className="text-xs font-normal text-muted-foreground">
                            (12 Nodes)
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'metadata' && (
                <div className="py-6">
                  <div className="rounded-xl border border-[#1a1a28] bg-[#0d0d14] overflow-hidden">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-[#1a1a28] text-xs font-mono text-muted-foreground uppercase">
                        <tr>
                          <th className="px-6 py-3 font-bold">Property</th>
                          <th className="px-6 py-3 font-bold">Value</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#1a1a28] font-mono text-xs">
                        {Object.entries(document.metadata || {}).map(
                          ([key, value]) => (
                            <tr
                              key={key}
                              className="hover:bg-[#1a1a28]/50 transition-colors"
                            >
                              <td className="px-6 py-3 text-[#D4A039]">
                                {key}
                              </td>
                              <td className="px-6 py-3 text-muted-foreground">
                                {typeof value === 'object'
                                  ? JSON.stringify(value)
                                  : String(value)}
                              </td>
                            </tr>
                          )
                        )}
                        {(!document.metadata ||
                          Object.keys(document.metadata).length === 0) && (
                          <tr>
                            <td
                              colSpan={2}
                              className="px-6 py-8 text-center text-muted-foreground italic"
                            >
                              No metadata extracted
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {activeTab === 'preview' && (
                <div className="py-6 flex items-center justify-center min-h-[400px] rounded-xl border border-[#1a1a28] border-dashed bg-[#0d0d14]/50">
                  <div className="text-center">
                    <Eye className="w-12 h-12 text-foreground mx-auto mb-4" />
                    <p className="font-mono text-sm text-muted-foreground">
                      Preview not available in this view
                    </p>
                    <button className="mt-4 px-4 py-2 rounded-lg bg-[#1a1a28] text-xs font-mono text-[#D4A039] hover:bg-[#D4A039]/10 transition-all">
                      OPEN ORIGINAL FILE
                    </button>
                  </div>
                </div>
              )}

              {activeTab === 'tables' && (
                <div
                  ref={tablesContainerRef}
                  className="py-6 space-y-6 relative"
                >
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-mono font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                      <Table2 className="w-4 h-4 text-[#00d4ff]" />
                      Extracted Tables & Formulas
                    </h3>
                    {(document.document_type === 'pdf' ||
                      document.file_type === 'pdf') && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setCropActive(true)}
                          className="px-3 py-1.5 rounded-lg text-xs font-mono font-bold bg-[#00d4ff]/10 border border-[#00d4ff]/30 text-[#00d4ff] hover:bg-[#00d4ff]/20 transition-all flex items-center gap-2"
                        >
                          <Crop className="w-3.5 h-3.5" />
                          CROP EXTRACT
                        </button>
                        <button
                          onClick={handleFetchTables}
                          disabled={
                            tablesLoading ||
                            document.processing_status !== 'indexed'
                          }
                          className={cn(
                            'px-3 py-1.5 rounded-lg text-xs font-mono font-bold flex items-center gap-2 transition-all',
                            tablesLoading ||
                              document.processing_status !== 'indexed'
                              ? 'bg-gray-800 text-muted-foreground cursor-not-allowed'
                              : 'bg-[#D4A039]/10 border border-[#D4A039]/30 text-[#D4A039] hover:bg-[#D4A039]/20'
                          )}
                        >
                          {tablesLoading ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Table2 className="w-3.5 h-3.5" />
                          )}
                          {tablesLoading ? 'EXTRACTING...' : 'EXTRACT TABLES'}
                        </button>
                      </div>
                    )}
                  </div>

                  {document.document_type === 'pdf' ||
                  document.file_type === 'pdf' ? (
                    <>
                      {regionResult && (
                        <div>
                          <h4 className="text-xs font-mono text-muted-foreground mb-2">
                            Crop Extraction Result
                          </h4>
                          <ExtractedTablePreview
                            documentId={documentId}
                            regionResult={regionResult}
                            onClose={() => setRegionResult(null)}
                          />
                        </div>
                      )}

                      {tables.length > 0 ? (
                        <div className="space-y-4">
                          {tables.map((table, idx) => (
                            <ExtractedTablePreview
                              key={idx}
                              documentId={documentId}
                              table={table}
                              onClose={() =>
                                setTables((prev) =>
                                  prev.filter((_, i) => i !== idx)
                                )
                              }
                            />
                          ))}
                        </div>
                      ) : !tablesLoading ? (
                        <div className="text-center py-12 rounded-xl border border-[#1a1a28] border-dashed bg-[#0d0d14]/50">
                          <Table2 className="w-12 h-12 text-foreground mx-auto mb-4" />
                          <p className="font-mono text-sm text-muted-foreground">
                            No tables extracted yet
                          </p>
                          <p className="font-mono text-xs text-foreground mt-2">
                            Click &quot;Extract Tables&quot; to find tables in
                            this document
                          </p>
                        </div>
                      ) : null}

                      <CropExtractOverlay
                        active={cropActive}
                        pageNumber={1}
                        documentId={documentId}
                        containerRef={tablesContainerRef}
                        onCancel={() => setCropActive(false)}
                        onExtracted={(data) => {
                          setRegionResult(data);
                          setCropActive(false);
                        }}
                      />
                    </>
                  ) : (
                    <div className="text-center py-12 rounded-xl border border-[#1a1a28] border-dashed bg-[#0d0d14]/50">
                      <Table2 className="w-12 h-12 text-foreground mx-auto mb-4" />
                      <p className="font-mono text-sm text-muted-foreground">
                        Table extraction is only available for PDF documents
                      </p>
                      <p className="font-mono text-xs text-foreground mt-2">
                        Upload a PDF to use this feature
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* File Info Card */}
            <div className="rounded-xl border border-[#1a1a28] bg-[#0d0d14] p-6">
              <h3 className="text-xs font-mono font-bold text-muted-foreground uppercase tracking-widest mb-4 flex items-center gap-2">
                <HardDrive className="w-4 h-4" />
                File Details
              </h3>

              <div className="space-y-4 font-mono text-xs">
                <div className="flex justify-between items-center border-b border-[#1a1a28] pb-2">
                  <span className="text-muted-foreground">Filename</span>
                  <span
                    className="text-white truncate max-w-[150px]"
                    title={document.filename}
                  >
                    {document.filename}
                  </span>
                </div>
                <div className="flex justify-between items-center border-b border-[#1a1a28] pb-2">
                  <span className="text-muted-foreground">Type</span>
                  <span className="text-[#D4A039] bg-[#D4A039]/10 px-2 py-0.5 rounded">
                    {document.document_type?.toUpperCase() ||
                      document.file_type?.toUpperCase() ||
                      document.mime_type?.toUpperCase() ||
                      'UNKNOWN'}
                  </span>
                </div>
                <div className="flex justify-between items-center border-b border-[#1a1a28] pb-2">
                  <span className="text-muted-foreground">Size</span>
                  <span className="text-white">
                    {formatFileSize(
                      document.file_size_bytes || document.file_size
                    )}
                  </span>
                </div>
                <div className="flex justify-between items-center border-b border-[#1a1a28] pb-2">
                  <span className="text-muted-foreground">Uploaded</span>
                  <span className="text-white">
                    {formatDate(
                      document.created_at || document.upload_timestamp
                    )}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Last Modified</span>
                  <span className="text-white">
                    {formatDate(
                      document.updated_at ||
                        document.created_at ||
                        document.upload_timestamp
                    )}
                  </span>
                </div>
              </div>
            </div>

            {/* AI Integrity Card */}
            <div className="rounded-xl border border-[#1a1a28] bg-[#0d0d14] p-6">
              <h3 className="text-xs font-mono font-bold text-muted-foreground uppercase tracking-widest mb-4 flex items-center gap-2">
                <Shield className="w-4 h-4" />
                AI Integrity
              </h3>
              <div className="flex items-center justify-between mb-4">
                <IntegrityBadge
                  documentId={documentId}
                  score={integrityScore}
                  onRequestCheck={() => setIntegrityOpen(true)}
                />
              </div>
              <button
                onClick={() => setIntegrityOpen(true)}
                className="w-full px-3 py-2 rounded-lg border border-[#1a1a28] bg-[#1a1a28]/50 text-xs font-mono text-muted-foreground hover:text-[#D4A039] hover:border-[#D4A039]/30 transition-all"
              >
                View Details
              </button>
            </div>
          </div>
        </div>
      </main>
      <IntegrityDetail
        documentId={documentId}
        isOpen={integrityOpen}
        onClose={() => setIntegrityOpen(false)}
      />
    </div>
  );
}
