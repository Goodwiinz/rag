/**
 * DocumentEntityExtractor Component
 * Integrates document entity extraction with the knowledge graph
 */

import React, { useState, useEffect } from 'react';
import {
  FileText,
  Loader2,
  CheckCircle,
  AlertCircle,
  Download,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Progress } from '@/components/ui/progress';
import toast from 'react-hot-toast';
import { api } from '@/services/api-client';
import { entityService } from '@/services/entityService';
import { APIErrorClass } from '@/types/api';

interface Document {
  id: string;
  title: string;
  filename: string;
  created_at: string;
}

interface ExtractionResult {
  document_ids: string[];
  entities_found: number;
  entities_created: number;
  errors: number;
}

const isRetryablePollError = (error: unknown): boolean => {
  if (error instanceof APIErrorClass) {
    const statusCode = error.error.status_code;
    return [404, 429, 500, 502, 503, 504].includes(statusCode);
  }
  return true;
};

export const DocumentEntityExtractor: React.FC = () => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [progress, setProgress] = useState(0);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobStep, setJobStep] = useState('');

  useEffect(() => {
    fetchDocuments();
  }, []);

  useEffect(() => {
    if (!activeJobId) return;
    let consecutivePollFailures = 0;

    const poll = setInterval(async () => {
      try {
        const job = await entityService.getProcessingJob(activeJobId);
        consecutivePollFailures = 0;
        setProgress(Math.round(job.progress_percentage || 0));
        setJobStep(job.current_step || 'Processing extraction job');

        if (job.status === 'completed') {
          clearInterval(poll);
          setLoading(false);
          setActiveJobId(null);
          setProgress(100);
          setResult((job as any).result || null);
          toast.success('Extraction job completed');
          setTimeout(() => setProgress(0), 1200);
        }

        if (job.status === 'failed' || job.status === 'cancelled') {
          clearInterval(poll);
          setLoading(false);
          setActiveJobId(null);
          toast.error(job.error_message || 'Extraction job failed');
          setTimeout(() => setProgress(0), 1200);
        }
      } catch (error) {
        if (isRetryablePollError(error) && consecutivePollFailures < 10) {
          consecutivePollFailures += 1;
          setJobStep('Waiting for job status...');
          return;
        }
        clearInterval(poll);
        setLoading(false);
        setActiveJobId(null);
        toast.error('Failed to fetch extraction job status');
      }
    }, 2000);

    return () => clearInterval(poll);
  }, [activeJobId]);

  const fetchDocuments = async () => {
    try {
      setLoadingDocs(true);
      const data = await api.get<{ documents?: Document[] }>('/documents/?page_size=100');
      setDocuments(data.documents || []);
    } catch (error) {
      console.warn('Document fetch failed:', error);
      toast.error('Failed to fetch documents');
      setDocuments([]);
    } finally {
      setLoadingDocs(false);
    }
  };

  const startExtractionJob = async (documentIds: string[]) => {
    try {
      setLoading(true);
      setProgress(5);
      const job = await entityService.createExtractionJob(documentIds);
      if (!job.job_id || job.job_id === 'None') {
        throw new Error('Extraction job was not created. Please retry.');
      }
      setActiveJobId(job.job_id);
      setJobStep('Extraction job queued');
      toast.success('Extraction job queued');
    } catch (error) {
      setLoading(false);
      setProgress(0);
      toast.error('Failed to queue extraction job');
    }
  };

  const handleExtractEntities = async () => {
    if (!selectedDocumentId) {
      toast.error('Please select a document');
      return;
    }
    await startExtractionJob([selectedDocumentId]);
  };

  const handleBatchExtract = async () => {
    if (documents.length === 0) {
      toast.error('No documents available');
      return;
    }

    const confirmed = window.confirm(
      `Extract entities from all ${documents.length} documents? This will run in the background.`
    );

    if (!confirmed) return;

    await startExtractionJob(documents.map((doc) => doc.id));
  };

  return (
    <div className="space-y-4">
      <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
        <CardHeader className="border-b border-[var(--terminal-border)] py-3">
          <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Document Entity Extraction
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-4">
          <div className="space-y-2">
            <label className="text-xs font-mono text-[var(--terminal-text-dim)]">
              Select Document
            </label>
            <Select
              value={selectedDocumentId}
              onValueChange={setSelectedDocumentId}
              disabled={loadingDocs || loading}
            >
              <SelectTrigger className="font-mono text-xs bg-[var(--terminal-bg)] border-[var(--terminal-border)] text-[var(--terminal-text)]">
                <SelectValue
                  placeholder={loadingDocs ? 'Loading documents...' : 'Select a document'}
                />
              </SelectTrigger>
              <SelectContent className="bg-[var(--terminal-surface)] border-[var(--terminal-border)]">
                {documents.map((doc) => (
                  <SelectItem
                    key={doc.id}
                    value={doc.id}
                    className="font-mono text-xs text-[var(--terminal-text)]"
                  >
                    {doc.title || doc.filename}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {loading && progress > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs font-mono text-[var(--terminal-text-dim)]">
                <span>{jobStep || 'Processing...'}</span>
                <span>{progress}%</span>
              </div>
              <Progress value={progress} className="h-2" />
              {activeJobId && <p className="text-[10px] font-mono text-[var(--terminal-text-dim)]">JOB: {activeJobId}</p>}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <Button
              onClick={handleExtractEntities}
              disabled={loading || !selectedDocumentId}
              className="font-mono text-xs font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)]"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  QUEUED...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4 mr-2" />
                  EXTRACT_ENTITIES
                </>
              )}
            </Button>

            <Button
              onClick={handleBatchExtract}
              disabled={loading || documents.length === 0}
              variant="outline"
              className="font-mono text-xs font-bold border-[var(--terminal-border)]"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  QUEUED...
                </>
              ) : (
                <>
                  <FileText className="w-4 h-4 mr-2" />
                  BATCH_EXTRACT_ALL
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {result && (
        <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
          <CardHeader className="border-b border-[var(--terminal-border)] py-3">
            <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)]">
              Extraction Results
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-3 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="w-4 h-4 text-[var(--cyan)]" />
                  <span className="text-xs font-mono text-[var(--terminal-text-dim)]">FOUND</span>
                </div>
                <p className="text-2xl font-mono font-bold text-[var(--cyan)]">{result.entities_found}</p>
              </div>

              <div className="p-3 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle className="w-4 h-4 text-[var(--phosphor-green)]" />
                  <span className="text-xs font-mono text-[var(--terminal-text-dim)]">CREATED</span>
                </div>
                <p className="text-2xl font-mono font-bold text-[var(--phosphor-green)]">{result.entities_created}</p>
              </div>

              <div className="p-3 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
                <div className="flex items-center gap-2 mb-2">
                  <AlertCircle className="w-4 h-4 text-[var(--amber-gold)]" />
                  <span className="text-xs font-mono text-[var(--terminal-text-dim)]">ERRORS</span>
                </div>
                <p className="text-2xl font-mono font-bold text-[var(--amber-gold)]">{result.errors}</p>
              </div>

              <div className="p-3 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
                <div className="flex items-center gap-2 mb-2">
                  <Loader2 className="w-4 h-4 text-[var(--purple)]" />
                  <span className="text-xs font-mono text-[var(--terminal-text-dim)]">DOCS</span>
                </div>
                <p className="text-2xl font-mono font-bold text-[var(--purple)]">{result.document_ids?.length || 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
