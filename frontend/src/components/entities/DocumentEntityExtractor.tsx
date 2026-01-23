/**
 * DocumentEntityExtractor Component
 * Integrates document entity extraction with the knowledge graph
 */

import React, { useState, useEffect } from 'react';
import { FileText, Loader2, CheckCircle, AlertCircle, Download, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Progress } from '@/components/ui/progress';
import toast from 'react-hot-toast';

/**
 * Retry wrapper utility for extraction API calls
 * Automatically retries failed requests once with exponential backoff
 */
async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 1
): Promise<T> {
  let lastError: Error | undefined;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      if (attempt < maxRetries) {
        // Exponential backoff: wait 1s on first retry
        await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
      }
    }
  }

  throw lastError;
}

interface Document {
  id: string;
  title: string;
  filename: string;
  created_at: string;
}

interface ExtractionResult {
  document_id: string;
  entities_found: number;
  entities_created: number;
  errors: number;
  processing_time: number;
}

export const DocumentEntityExtractor: React.FC = () => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [progress, setProgress] = useState(0);

  // Fetch available documents
  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      setLoadingDocs(true);
      const response = await fetch('/api/documents?limit=100', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch documents');
      }

      const data = await response.json();
      setDocuments(data.documents || []);
    } catch (error) {
      console.error('Error fetching documents:', error);
      toast.error('Failed to fetch documents');
      setDocuments([]);
    } finally {
      setLoadingDocs(false);
    }
  };

  const handleExtractEntities = async () => {
    if (!selectedDocumentId) {
      toast.error('Please select a document');
      return;
    }

    try {
      setLoading(true);
      setProgress(10);

      // Use retry wrapper for extraction API call (T028)
      const extractionResult = await withRetry(async () => {
        const response = await fetch(
          `/api/knowledge-graph/documents/${selectedDocumentId}/extract-entities`,
          {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`,
              'Content-Type': 'application/json',
            },
          }
        );

        setProgress(50);

        if (!response.ok) {
          throw new Error('Failed to extract entities');
        }

        return await response.json();
      });

      setProgress(100);
      setResult(extractionResult);

      toast.success(
        `Extracted ${extractionResult.entities_created} entities from document`
      );
    } catch (error) {
      console.error('Error extracting entities:', error);
      toast.error('Failed to extract entities. Please try again.');
      setResult(null);
    } finally {
      setLoading(false);
      setTimeout(() => setProgress(0), 1000);
    }
  };

  const handleBatchExtract = async () => {
    if (documents.length === 0) {
      toast.error('No documents available');
      return;
    }

    const confirmed = window.confirm(
      `Extract entities from all ${documents.length} documents? This may take a while.`
    );

    if (!confirmed) return;

    try {
      setLoading(true);
      let successCount = 0;
      let errorCount = 0;

      for (let i = 0; i < documents.length; i++) {
        const doc = documents[i];
        setProgress(Math.round(((i + 1) / documents.length) * 100));

        try {
          // Use retry wrapper for batch extraction (T028)
          await withRetry(async () => {
            const response = await fetch(
              `/api/knowledge-graph/documents/${doc.id}/extract-entities`,
              {
                method: 'POST',
                headers: {
                  'Authorization': `Bearer ${localStorage.getItem('token')}`,
                  'Content-Type': 'application/json',
                },
              }
            );

            if (!response.ok) {
              throw new Error('Extraction failed');
            }

            return response.json();
          });

          successCount++;
        } catch (error) {
          errorCount++;
        }
      }

      toast.success(
        `Batch extraction complete: ${successCount} succeeded, ${errorCount} failed`
      );
    } catch (error) {
      console.error('Error in batch extraction:', error);
      toast.error('Batch extraction failed');
    } finally {
      setLoading(false);
      setProgress(0);
    }
  };

  return (
    <div className="space-y-4">
      {/* Document Selection */}
      <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
        <CardHeader className="border-b border-[var(--terminal-border)] py-3">
          <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Document Entity Extraction
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-4">
          {/* Document Selector */}
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
                <SelectValue placeholder={loadingDocs ? 'Loading documents...' : 'Select a document'} />
              </SelectTrigger>
              <SelectContent className="bg-[var(--terminal-surface)] border-[var(--terminal-border)]">
                {documents.map((doc) => (
                  <SelectItem
                    key={doc.id}
                    value={doc.id}
                    className="font-mono text-xs text-[var(--terminal-text)] hover:bg-[var(--terminal-elevated)]"
                  >
                    {doc.title || doc.filename}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Progress Bar */}
          {loading && progress > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs font-mono text-[var(--terminal-text-dim)]">
                <span>Processing...</span>
                <span>{progress}%</span>
              </div>
              <Progress value={progress} className="h-2" />
            </div>
          )}

          {/* Action Buttons */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <Button
              onClick={handleExtractEntities}
              disabled={loading || !selectedDocumentId}
              className="font-mono text-xs font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_15px_var(--phosphor-green-glow)]"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  EXTRACTING...
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
              className="font-mono text-xs font-bold border-[var(--terminal-border)] hover:bg-[var(--terminal-elevated)]"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  PROCESSING...
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

      {/* Extraction Results */}
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
                  <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                    FOUND
                  </span>
                </div>
                <p className="text-2xl font-mono font-bold text-[var(--cyan)]">
                  {result.entities_found}
                </p>
              </div>

              <div className="p-3 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle className="w-4 h-4 text-[var(--phosphor-green)]" />
                  <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                    CREATED
                  </span>
                </div>
                <p className="text-2xl font-mono font-bold text-[var(--phosphor-green)]">
                  {result.entities_created}
                </p>
              </div>

              <div className="p-3 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
                <div className="flex items-center gap-2 mb-2">
                  <AlertCircle className="w-4 h-4 text-[var(--amber-gold)]" />
                  <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                    ERRORS
                  </span>
                </div>
                <p className="text-2xl font-mono font-bold text-[var(--amber-gold)]">
                  {result.errors}
                </p>
              </div>

              <div className="p-3 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
                <div className="flex items-center gap-2 mb-2">
                  <Loader2 className="w-4 h-4 text-[var(--purple)]" />
                  <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                    TIME
                  </span>
                </div>
                <p className="text-2xl font-mono font-bold text-[var(--purple)]">
                  {result.processing_time.toFixed(2)}s
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Info Card */}
      <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
        <CardContent className="p-4">
          <div className="text-xs font-mono text-[var(--terminal-text-dim)] space-y-2">
            <p>💡 <strong>Single Extraction:</strong> Select a document and click EXTRACT_ENTITIES</p>
            <p>💡 <strong>Batch Extraction:</strong> Click BATCH_EXTRACT_ALL to process all documents</p>
            <p>💡 <strong>Auto-Linking:</strong> Extracted entities are automatically linked to relationships</p>
            <p>💡 <strong>Duplicate Handling:</strong> Existing entities are updated, not duplicated</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
