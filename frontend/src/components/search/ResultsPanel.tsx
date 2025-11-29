import React, { useState, useCallback } from 'react';
import {
  DocumentTextIcon,
  PhotoIcon,
  MusicalNoteIcon,
  VideoCameraIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  EyeIcon,
  ShareIcon,
  ArrowDownTrayIcon,
  StarIcon,
  ChartBarIcon,
  ArrowTopRightOnSquareIcon,
  InformationCircleIcon,
  MagnifyingGlassIcon,
  ClipboardDocumentIcon,
  CheckIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import { Skeleton } from '@/components/ui/skeleton';
import { SearchResult, SourceReference, SearchMetrics } from '@/types/search';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';

interface ResultsPanelProps {
  result: SearchResult | null;
  loading?: boolean;
  error?: string | null;
  onSourceClick?: (source: SourceReference) => void;
  onDocumentPreview?: (documentId: string) => void;
  onShare?: (result: SearchResult) => void;
  onExport?: (result: SearchResult) => void;
  onFeedback?: (result: SearchResult, rating: number, comment?: string) => void;
  className?: string;
}

interface FeedbackDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (rating: number, comment?: string) => void;
}

const FeedbackDialog: React.FC<FeedbackDialogProps> = ({ isOpen, onClose, onSubmit }) => {
  const [rating, setRating] = useState<number>(0);
  const [comment, setComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = useCallback(async () => {
    if (rating === 0) return;

    setIsSubmitting(true);
    try {
      await onSubmit(rating, comment);
      onClose();
      setRating(0);
      setComment('');
    } catch (error) {
      console.error('Failed to submit feedback:', error);
    } finally {
      setIsSubmitting(false);
    }
  }, [rating, comment, onSubmit, onClose]);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Rate this answer</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              How helpful was this answer?
            </label>
            <div className="flex space-x-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setRating(star)}
                  className={cn(
                    "p-1 hover:scale-110 transition-transform",
                    star <= rating ? "text-yellow-400" : "text-gray-300"
                  )}
                >
                  <StarIcon className="h-6 w-6 fill-current" />
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Additional feedback (optional)
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Tell us more about your experience..."
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <div className="flex justify-end space-x-2">
            <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={rating === 0 || isSubmitting}
              className="min-w-[80px]"
            >
              {isSubmitting ? (
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
              ) : (
                'Submit'
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

const MetricsDisplay: React.FC<{ metrics: SearchMetrics }> = ({ metrics }) => {
  const getScoreColor = (score: number): string => {
    if (score >= 90) return 'text-green-600';
    if (score >= 80) return 'text-yellow-600';
    if (score >= 70) return 'text-orange-600';
    return 'text-red-600';
  };

  const formatScore = (score: number): string => {
    return `${score}%`;
  };

  return (
    <Card className="bg-muted/30 border-border">
      <CardHeader className="pb-2">
        <div className="flex items-center space-x-2">
          <ChartBarIcon className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-sm font-medium text-foreground">Quality Metrics</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 text-sm mb-4">
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground text-xs">Answer Relevancy</span>
              <span className={cn("font-mono font-medium text-xs", getScoreColor(metrics.answer_relevancy))}>
                {formatScore(metrics.answer_relevancy)}
              </span>
            </div>
            <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
              <div className={cn("h-full rounded-full", getScoreColor(metrics.answer_relevancy).replace('text-', 'bg-'))} style={{ width: `${metrics.answer_relevancy}%` }} />
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground text-xs">Faithfulness</span>
              <span className={cn("font-mono font-medium text-xs", getScoreColor(metrics.faithfulness_score))}>
                {formatScore(metrics.faithfulness_score)}
              </span>
            </div>
            <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
              <div className={cn("h-full rounded-full", getScoreColor(metrics.faithfulness_score).replace('text-', 'bg-'))} style={{ width: `${metrics.faithfulness_score}%` }} />
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground text-xs">Context Relevancy</span>
              <span className={cn("font-mono font-medium text-xs", getScoreColor(metrics.contextual_relevancy))}>
                {formatScore(metrics.contextual_relevancy)}
              </span>
            </div>
            <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
              <div className={cn("h-full rounded-full", getScoreColor(metrics.contextual_relevancy).replace('text-', 'bg-'))} style={{ width: `${metrics.contextual_relevancy}%` }} />
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground text-xs">Hallucination Risk</span>
              <span className={cn("font-mono font-medium text-xs", getScoreColor(100 - metrics.hallucination_score))}>
                {formatScore(100 - metrics.hallucination_score)}
              </span>
            </div>
            <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
              <div className={cn("h-full rounded-full", getScoreColor(100 - metrics.hallucination_score).replace('text-', 'bg-'))} style={{ width: `${100 - metrics.hallucination_score}%` }} />
            </div>
          </div>
        </div>

        <Separator className="my-3 bg-border" />

        <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
          <div className="flex flex-col items-center p-2 bg-background rounded border border-border/50">
            <span className="font-mono font-medium text-foreground">{metrics.latency_ms}ms</span>
            <span className="text-[10px] uppercase tracking-wider mt-0.5 opacity-70">Latency</span>
          </div>
          <div className="flex flex-col items-center p-2 bg-background rounded border border-border/50">
            <span className="font-mono font-medium text-foreground">{metrics.documents_retrieved}</span>
            <span className="text-[10px] uppercase tracking-wider mt-0.5 opacity-70">Docs</span>
          </div>
          <div className="flex flex-col items-center p-2 bg-background rounded border border-border/50">
            <span className="font-mono font-medium text-foreground">{metrics.entities_found}</span>
            <span className="text-[10px] uppercase tracking-wider mt-0.5 opacity-70">Entities</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

const ResultsSkeleton = () => (
  <div className="space-y-6">
    {/* Answer Skeleton */}
    <Card className="border-blue-100 shadow-sm overflow-hidden">
      <CardHeader className="bg-gray-50/50 pb-4 border-b border-gray-100">
        <div className="flex items-start justify-between">
          <div className="space-y-2 w-full max-w-md">
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </div>
          <div className="flex space-x-1">
            <Skeleton className="h-8 w-8 rounded-md" />
            <Skeleton className="h-8 w-8 rounded-md" />
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-6 space-y-4">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-4/5" />
      </CardContent>
      <CardFooter className="bg-gray-50/50 py-3 border-t border-gray-100">
        <div className="flex items-center w-full space-x-3">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="flex-1 h-2 rounded-full" />
          <Skeleton className="h-4 w-8" />
        </div>
      </CardFooter>
    </Card>

    {/* Metrics Skeleton */}
    <Card className="bg-gray-50/50 border-gray-200">
      <CardHeader className="pb-2">
        <Skeleton className="h-5 w-32" />
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 mb-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="space-y-1">
              <div className="flex justify-between">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-3 w-8" />
              </div>
              <Skeleton className="h-1.5 w-full rounded-full" />
            </div>
          ))}
        </div>
        <Separator className="my-3" />
        <div className="grid grid-cols-3 gap-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-12 w-full rounded" />
          ))}
        </div>
      </CardContent>
    </Card>

    {/* Sources Skeleton */}
    <Card>
      <CardHeader className="pb-3">
        <div className="flex justify-between">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-8 w-20" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="border border-gray-100 shadow-sm">
              <CardContent className="p-4">
                <div className="flex justify-between mb-3">
                  <div className="flex space-x-3 w-full">
                    <Skeleton className="h-10 w-10 rounded-lg" />
                    <div className="space-y-2 flex-1">
                      <Skeleton className="h-4 w-3/4" />
                      <Skeleton className="h-3 w-1/3" />
                    </div>
                  </div>
                </div>
                <Skeleton className="h-16 w-full rounded-md" />
              </CardContent>
            </Card>
          ))}
        </div>
      </CardContent>
    </Card>
  </div>
);

export const ResultsPanel: React.FC<ResultsPanelProps> = ({
  result,
  loading = false,
  error,
  onSourceClick,
  onDocumentPreview,
  onShare,
  onExport,
  onFeedback,
  className,
}) => {
  const [showFeedbackDialog, setShowFeedbackDialog] = useState(false);
  const [expandedSources, setExpandedSources] = useState(false);
  const [copiedSource, setCopiedSource] = useState<string | null>(null);
  const [copiedAnswer, setCopiedAnswer] = useState(false);

  const getFileIcon = (fileType: string) => {
    const iconClass = "h-4 w-4";
    switch (fileType) {
      case 'pdf':
        return <DocumentTextIcon className={cn(iconClass, "text-red-600")} />;
      case 'txt':
        return <DocumentTextIcon className={cn(iconClass, "text-blue-600")} />;
      case 'jpg':
      case 'png':
        return <PhotoIcon className={cn(iconClass, "text-green-600")} />;
      case 'mp3':
        return <MusicalNoteIcon className={cn(iconClass, "text-purple-600")} />;
      case 'mp4':
        return <VideoCameraIcon className={cn(iconClass, "text-orange-600")} />;
      default:
        return <DocumentTextIcon className={cn(iconClass, "text-gray-600")} />;
    }
  };

  const getAnswerTypeColor = (answerType: string) => {
    switch (answerType) {
      case 'factual':
        return 'bg-blue-100 text-blue-800';
      case 'reasoning':
        return 'bg-purple-100 text-purple-800';
      case 'summarization':
        return 'bg-green-100 text-green-800';
      case 'comparison':
        return 'bg-orange-100 text-orange-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const handleSourceClick = useCallback((source: SourceReference) => {
    onSourceClick?.(source);
  }, [onSourceClick]);

  const handleCopySource = useCallback((source: SourceReference) => {
    navigator.clipboard.writeText(source.snippet);
    setCopiedSource(source.snippet);
    setTimeout(() => setCopiedSource(null), 2000);
  }, []);

  const handleCopyAnswer = useCallback(() => {
    if (result?.answer?.text) {
      navigator.clipboard.writeText(result.answer.text);
      setCopiedAnswer(true);
      setTimeout(() => setCopiedAnswer(false), 2000);
    }
  }, [result]);

  const handleDocumentPreview = useCallback((source: SourceReference) => {
    onDocumentPreview?.(source.document_id);
  }, [onDocumentPreview]);

  const handleShare = useCallback(() => {
    onShare?.(result!);
  }, [result, onShare]);

  const handleExport = useCallback(() => {
    onExport?.(result!);
  }, [result, onExport]);

  const handleFeedback = useCallback((rating: number, comment?: string) => {
    onFeedback?.(result!, rating, comment);
  }, [result, onFeedback]);

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return <ResultsSkeleton />;
  }

  if (error) {
    return (
      <div className={cn("text-center py-8", className)}>
        <XCircleIcon className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Search failed
        </h3>
        <p className="text-gray-600">{error}</p>
      </div>
    );
  }

  if (!result) {
    return (
      <div className={cn("text-center py-8", className)}>
        <div className="h-12 w-12 bg-gray-100 rounded-full mx-auto mb-4 flex items-center justify-center">
          <MagnifyingGlassIcon className="h-6 w-6 text-gray-400" />
        </div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Enter a search query
        </h3>
        <p className="text-gray-600">
          Search your documents using natural language queries
        </p>
      </div>
    );
  }

  return (
    <div className={cn("space-y-8", className)}>
      {/* Query and Answer */}
      <div className="space-y-6">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <h1 className="text-2xl font-semibold text-foreground tracking-tight">
              {result.query}
            </h1>
            <div className="flex items-center space-x-3 text-sm text-muted-foreground">
              <Badge variant="secondary" className={cn("capitalize font-medium px-2 py-0.5 text-xs", getAnswerTypeColor(result.answer.answer_type))}>
                {result.answer.answer_type}
              </Badge>
              <span className="flex items-center">
                <ClockIcon className="h-3.5 w-3.5 mr-1" />
                {formatDate(result.created_at)}
              </span>
              <span className="flex items-center">
                <SparklesIcon className="h-3.5 w-3.5 mr-1 text-primary" />
                {Math.round(result.answer.confidence * 100)}% confidence
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={handleCopyAnswer}
              className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted/50"
              title="Copy Answer"
            >
              {copiedAnswer ? (
                <CheckCircleIcon className="h-4 w-4 text-green-600" />
              ) : (
                <ClipboardDocumentIcon className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={handleShare}
              className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted/50"
              title="Share"
            >
              <ShareIcon className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={handleExport}
              className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted/50"
              title="Export"
            >
              <ArrowDownTrayIcon className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowFeedbackDialog(true)}
              className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted/50"
              title="Rate Answer"
            >
              <StarIcon className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="prose prose-lg max-w-none text-foreground leading-relaxed">
          <p className="text-[17px] text-foreground/90 font-light">{result.answer.text}</p>
        </div>

        {/* Quality Metrics - Subtle */}
        <div className="pt-4 border-t border-border/40">
          <MetricsDisplay metrics={result.metrics} />
        </div>
      </div>

      {/* Sources Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <DocumentTextIcon className="h-5 w-5 text-muted-foreground" />
            <h2 className="text-lg font-semibold text-foreground">Sources</h2>
            <Badge variant="secondary" className="rounded-full px-2 py-0.5 text-xs font-mono bg-muted text-muted-foreground">
              {result.answer.sources.length}
            </Badge>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {result.answer.sources.map((source, index) => (
            <Card
              key={`${source.document_id}-${index}`}
              className="group border border-border/60 shadow-sm hover:border-primary/30 hover:shadow-md transition-all duration-200 cursor-pointer bg-card/50 hover:bg-card"
              onClick={() => handleSourceClick(source)}
            >
              <CardContent className="p-4 space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-muted/50 rounded-lg group-hover:bg-primary/10 transition-colors">
                      {getFileIcon(source.file_type)}
                    </div>
                    <div className="space-y-0.5">
                      <h4 className="text-sm font-medium text-foreground line-clamp-1" title={source.document_title}>
                        {source.document_title}
                      </h4>
                      <div className="flex items-center space-x-2">
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 border-border text-muted-foreground uppercase">
                          {source.file_type}
                        </Badge>
                        <span className="text-[10px] text-muted-foreground font-mono">
                          {Math.round(source.confidence * 100)}%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Source Snippet */}
                <div className="relative">
                  <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3 font-mono bg-muted/30 p-2 rounded-md border border-border/30 group-hover:border-border/50 transition-colors">
                    "{source.snippet}"
                  </p>
                </div>

                {/* Footer Actions */}
                <div className="flex items-center justify-between pt-2 border-t border-border/30">
                  <div className="flex items-center space-x-2 text-[10px] text-muted-foreground">
                    {source.page_number && (
                      <span className="flex items-center bg-muted/50 px-1.5 py-0.5 rounded">
                        Page {source.page_number}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => { e.stopPropagation(); handleDocumentPreview(source); }}
                      className="h-6 w-6 text-muted-foreground hover:text-primary"
                      title="Preview"
                    >
                      <EyeIcon className="h-3 w-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => { e.stopPropagation(); handleCopySource(source); }}
                      className="h-6 w-6 text-muted-foreground hover:text-primary"
                      title="Copy"
                    >
                      <ClipboardDocumentIcon className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Feedback Dialog */}
      <FeedbackDialog
        isOpen={showFeedbackDialog}
        onClose={() => setShowFeedbackDialog(false)}
        onSubmit={handleFeedback}
      />
    </div>
  );
};

export default ResultsPanel;