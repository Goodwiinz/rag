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
} from '@heroicons/react/24/outline';
import { SearchResult, SourceReference, SearchMetrics } from '@/types/search';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';

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
    <div className="bg-gray-50 rounded-lg p-4">
      <div className="flex items-center space-x-2 mb-3">
        <ChartBarIcon className="h-4 w-4 text-gray-600" />
        <h4 className="text-sm font-medium text-gray-900">Quality Metrics</h4>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <div className="flex items-center justify-between">
            <span className="text-gray-600">Answer Relevancy</span>
            <span className={cn("font-medium", getScoreColor(metrics.answer_relevancy))}>
              {formatScore(metrics.answer_relevancy)}
            </span>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between">
            <span className="text-gray-600">Faithfulness</span>
            <span className={cn("font-medium", getScoreColor(metrics.faithfulness_score))}>
              {formatScore(metrics.faithfulness_score)}
            </span>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between">
            <span className="text-gray-600">Context Relevancy</span>
            <span className={cn("font-medium", getScoreColor(metrics.contextual_relevancy))}>
              {formatScore(metrics.contextual_relevancy)}
            </span>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between">
            <span className="text-gray-600">Hallucination Risk</span>
            <span className={cn("font-medium", getScoreColor(100 - metrics.hallucination_score))}>
              {formatScore(100 - metrics.hallucination_score)}
            </span>
          </div>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-gray-200">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>Processing Time</span>
          <span>{metrics.latency_ms}ms</span>
        </div>
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>Documents Retrieved</span>
          <span>{metrics.documents_retrieved}</span>
        </div>
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>Entities Found</span>
          <span>{metrics.entities_found}</span>
        </div>
      </div>
    </div>
  );
};

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
    return (
      <div className={cn("space-y-4", className)}>
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
          <div className="h-20 bg-gray-200 rounded"></div>
        </div>
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
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
    <div className={cn("space-y-6", className)}>
      {/* Query and Answer */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1">
            <div className="flex items-center space-x-2 mb-2">
              <h3 className="text-lg font-semibold text-gray-900">
                "{result.query}"
              </h3>
              <Badge className={getAnswerTypeColor(result.answer.answer_type)}>
                {result.answer.answer_type}
              </Badge>
            </div>
            <p className="text-sm text-gray-500">
              {formatDate(result.created_at)}
            </p>
          </div>

          <div className="flex items-center space-x-2 ml-4">
            <Button
              variant="outline"
              size="sm"
              onClick={handleShare}
              className="h-8 w-8 p-0"
            >
              <ShareIcon className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExport}
              className="h-8 w-8 p-0"
            >
              <ArrowDownTrayIcon className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowFeedbackDialog(true)}
              className="h-8 w-8 p-0"
            >
              <StarIcon className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Answer */}
        <div className="prose prose-sm max-w-none">
          <p className="text-gray-800 leading-relaxed">
            {result.answer.text}
          </p>
        </div>

        {/* Answer Confidence */}
        <div className="flex items-center space-x-2 mt-4">
          <span className="text-sm text-gray-600">Confidence:</span>
          <div className="flex-1 max-w-xs bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${result.answer.confidence * 100}%` }}
            />
          </div>
          <span className="text-sm font-medium text-gray-900">
            {Math.round(result.answer.confidence * 100)}%
          </span>
        </div>
      </div>

      {/* Quality Metrics */}
      <MetricsDisplay metrics={result.metrics} />

      {/* Sources */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">
            Sources ({result.answer.sources.length})
          </h3>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setExpandedSources(!expandedSources)}
          >
            {expandedSources ? 'Show less' : 'Show all'}
          </Button>
        </div>

        <div className={cn("space-y-3", !expandedSources && "max-h-96 overflow-y-auto")}>
          {result.answer.sources.map((source, index) => (
            <div
              key={`${source.document_id}-${index}`}
              className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center space-x-2">
                  {getFileIcon(source.file_type)}
                  <div>
                    <h4 className="text-sm font-medium text-gray-900">
                      {source.document_title}
                    </h4>
                    <p className="text-xs text-gray-500">
                      Confidence: {Math.round(source.confidence * 100)}%
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleSourceClick(source)}
                    className="h-6 w-6 p-0"
                  >
                    <ArrowTopRightOnSquareIcon className="h-3 w-3" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDocumentPreview(source)}
                    className="h-6 w-6 p-0"
                  >
                    <EyeIcon className="h-3 w-3" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleCopySource(source)}
                    className="h-6 w-6 p-0"
                  >
                    <ArrowDownTrayIcon className="h-3 w-3" />
                  </Button>
                </div>
              </div>

              {/* Source Snippet */}
              <div className="bg-gray-50 rounded p-3 mb-3">
                <p className="text-sm text-gray-700 leading-relaxed">
                  {source.snippet}
                </p>
                {copiedSource === source.snippet && (
                  <p className="text-xs text-green-600 mt-1">
                    Copied to clipboard!
                  </p>
                )}
              </div>

              {/* Source Metadata */}
              <div className="flex items-center space-x-4 text-xs text-gray-500">
                {source.page_number && (
                  <span>Page {source.page_number}</span>
                )}
                {source.timestamp && (
                  <span>{formatDate(source.timestamp)}</span>
                )}
                {source.file_type && (
                  <span className="uppercase">{source.file_type}</span>
                )}
              </div>
            </div>
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