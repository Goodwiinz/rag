import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { CheckCircle, AlertCircle, Loader2, Zap } from 'lucide-react';
import { api } from '@/services/api-client';

interface ExtractionProgress {
  status: 'idle' | 'running' | 'completed' | 'error';
  message: string;
  progress: number;
  processed: number;
  total: number;
  currentFile?: string;
  results?: any[];
  error?: string;
}

export function ArxivStreamingExtraction() {
  const [progress, setProgress] = useState<ExtractionProgress>({
    status: 'idle',
    message: '',
    progress: 0,
    processed: 0,
    total: 0,
  });

  const [options, setOptions] = useState({
    extract_entities: true,
    extract_topics: true,
    extract_keyphrases: true,
    extract_summaries: true,
    update_knowledge_graph: true,
    batch_size: 3,
  });

  const handleStreamExtraction = async () => {
    if (progress.status === 'running') return;

    setProgress({
      status: 'running',
      message: 'Initializing extraction...',
      progress: 0,
      processed: 0,
      total: 0,
    });

    try {
      // Get auth from Supabase session
      const { createClient } = await import('@/lib/supabase/client');
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const token = session?.access_token ?? null;
      const orgId = session?.user?.user_metadata?.organization_id || 'default';

      const url = new URL(
        'http://localhost:8000/api/v1/arxiv/batch/stream-extraction'
      );
      url.searchParams.set(
        'extract_entities',
        String(options.extract_entities)
      );
      url.searchParams.set('extract_topics', String(options.extract_topics));
      url.searchParams.set(
        'extract_keyphrases',
        String(options.extract_keyphrases)
      );
      url.searchParams.set(
        'extract_summaries',
        String(options.extract_summaries)
      );
      url.searchParams.set(
        'update_knowledge_graph',
        String(options.update_knowledge_graph)
      );
      url.searchParams.set('batch_size', String(options.batch_size));

      const eventSource = new EventSource(url.toString(), {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-Organization-ID': orgId,
        },
      } as any);

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);

        switch (data.status) {
          case 'started':
            setProgress((prev) => ({
              ...prev,
              status: 'running',
              message: data.message,
              total: data.total_files,
            }));
            break;

          case 'batch_processing':
            setProgress((prev) => ({
              ...prev,
              message: data.message,
            }));
            break;

          case 'progress':
            setProgress((prev) => ({
              ...prev,
              processed: data.processed,
              progress: data.progress_percent,
              currentFile: data.current_file,
            }));
            break;

          case 'completed':
            eventSource.close();
            setProgress({
              status: 'completed',
              message: data.message,
              progress: 100,
              processed: data.total_processed,
              total: data.total_processed,
            });
            break;

          case 'error':
            eventSource.close();
            setProgress({
              status: 'error',
              message: 'Extraction failed',
              progress: 0,
              processed: 0,
              total: 0,
              error: data.message,
            });
            break;
        }
      };

      eventSource.onerror = (error) => {
        console.error('EventSource error:', error);
        eventSource.close();
        setProgress({
          status: 'error',
          message: 'Connection error',
          progress: 0,
          processed: 0,
          total: 0,
          error: 'Failed to connect to streaming endpoint',
        });
      };

      // Timeout after 5 minutes
      setTimeout(() => {
        if (eventSource.readyState !== EventSource.CLOSED) {
          eventSource.close();
          setProgress({
            status: 'error',
            message: 'Operation timed out',
            progress: progress.progress,
            processed: progress.processed,
            total: progress.total,
            error: 'The operation timed out after 5 minutes',
          });
        }
      }, 300000); // 5 minutes
    } catch (error: any) {
      setProgress({
        status: 'error',
        message: 'Failed to start extraction',
        progress: 0,
        processed: 0,
        total: 0,
        error: error.message,
      });
    }
  };

  const handleStop = () => {
    if (progress.status === 'running') {
      setProgress({
        ...progress,
        status: 'idle',
        message: 'Extraction stopped by user',
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Zap className="h-5 w-5" />
          Streaming PDF Extraction
        </CardTitle>
        <CardDescription>
          Process local PDF files with real-time progress updates and no
          timeouts
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Options */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={options.extract_topics}
              onChange={(e) =>
                setOptions({ ...options, extract_topics: e.target.checked })
              }
              className="rounded"
            />
            <span className="text-sm">Extract Topics</span>
          </label>
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={options.extract_keyphrases}
              onChange={(e) =>
                setOptions({ ...options, extract_keyphrases: e.target.checked })
              }
              className="rounded"
            />
            <span className="text-sm">Extract Keyphrases</span>
          </label>
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={options.update_knowledge_graph}
              onChange={(e) =>
                setOptions({
                  ...options,
                  update_knowledge_graph: e.target.checked,
                })
              }
              className="rounded"
            />
            <span className="text-sm">Update Knowledge Graph</span>
          </label>
        </div>

        {/* Batch Size */}
        <div className="flex items-center gap-4">
          <label className="text-sm font-medium">Batch Size:</label>
          <select
            value={options.batch_size}
            onChange={(e) =>
              setOptions({ ...options, batch_size: parseInt(e.target.value) })
            }
            className="px-3 py-1 border rounded-md"
          >
            <option value="1">1 file at a time</option>
            <option value="3">3 files at a time</option>
            <option value="5">5 files at a time</option>
            <option value="10">10 files at a time</option>
          </select>
        </div>

        {/* Progress */}
        {progress.status !== 'idle' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Badge
                  variant={
                    progress.status === 'running'
                      ? 'default'
                      : progress.status === 'completed'
                        ? 'default'
                        : progress.status === 'error'
                          ? 'destructive'
                          : 'secondary'
                  }
                >
                  {progress.status.toUpperCase()}
                </Badge>
                <span className="text-sm font-medium">{progress.message}</span>
              </div>
              {progress.status === 'running' && (
                <Button variant="outline" size="sm" onClick={handleStop}>
                  Stop
                </Button>
              )}
            </div>

            <div className="space-y-2">
              <Progress value={progress.progress} className="w-full" />
              <div className="flex justify-between text-sm text-muted-foreground">
                <span>
                  Progress: {progress.processed} / {progress.total}
                </span>
                <span>{progress.progress.toFixed(1)}%</span>
              </div>
              {progress.currentFile && (
                <div className="text-sm text-muted-foreground">
                  Currently processing:{' '}
                  <code className="bg-muted px-2 py-1 rounded">
                    {progress.currentFile}
                  </code>
                </div>
              )}
            </div>

            {progress.error && (
              <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
                <div className="flex items-center gap-2 text-destructive">
                  <AlertCircle className="h-4 w-4" />
                  <span className="text-sm font-medium">Error:</span>
                </div>
                <p className="text-sm mt-1">{progress.error}</p>
              </div>
            )}

            {progress.status === 'completed' && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
                <div className="flex items-center gap-2 text-amber-700">
                  <CheckCircle className="h-4 w-4" />
                  <span className="text-sm font-medium">Success!</span>
                </div>
                <p className="text-sm mt-1 text-amber-600">
                  Successfully processed {progress.processed} PDF files
                </p>
              </div>
            )}
          </div>
        )}

        {/* Action Button */}
        <Button
          onClick={handleStreamExtraction}
          disabled={progress.status === 'running'}
          className="w-full"
        >
          {progress.status === 'running' ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Processing...
            </>
          ) : (
            'Start Streaming Extraction'
          )}
        </Button>

        {/* Instructions */}
        <div className="text-sm text-muted-foreground">
          <p>• This method processes PDF files in batches to avoid timeouts</p>
          <p>• Progress updates are shown in real-time</p>
          <p>• Knowledge graph is updated as each file is processed</p>
          <p>• No 30-second timeout limitation</p>
        </div>
      </CardContent>
    </Card>
  );
}
