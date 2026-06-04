import { cn } from '@/lib/utils';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { SearchMetrics, SearchResult, SourceReference } from '@/types/search';
import { IconButton, IconButtonSm } from '@/components/ui/icon-button';
import {
  ArrowDownTrayIcon,
  ChartBarIcon,
  CheckCircleIcon,
  ClipboardDocumentIcon,
  ClockIcon,
  DocumentTextIcon,
  EyeIcon,
  MagnifyingGlassIcon,
  MusicalNoteIcon,
  PhotoIcon,
  ShareIcon,
  SparklesIcon,
  StarIcon,
  VideoCameraIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline';
import React, { useCallback, useEffect, useState } from 'react';

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

const FeedbackDialog: React.FC<FeedbackDialogProps> = ({
  isOpen,
  onClose,
  onSubmit,
}) => {
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
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md p-6 rounded-xl bg-terminal-surface border border-terminal-border shadow-[0_0_60px_var(--nous-sol-muted)]">
        <DialogHeader>
          <DialogTitle className="text-lg font-mono font-semibold text-white mb-4">
            Rate this answer
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-mono text-muted-foreground mb-2">
              How helpful was this answer?
            </label>
            <div className="flex space-x-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <IconButton
                  key={star}
                  icon={
                    <StarIcon
                      className={cn(
                        'h-6 w-6',
                        star <= rating
                          ? 'text-[var(--nous-sol-safe)] fill-[var(--nous-sol)]'
                          : 'text-foreground'
                      )}
                    />
                  }
                  label={`Rate ${star} stars`}
                  onClick={() => setRating(star)}
                  className="p-1 hover:scale-110 transition-transform bg-transparent hover:bg-transparent"
                />
              ))}
            </div>
          </div>
          <div>
            <label
              htmlFor="feedback-comment"
              className="block text-sm font-mono text-muted-foreground mb-2"
            >
              Additional feedback (optional)
            </label>
            <textarea
              id="feedback-comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Tell us more..."
              rows={3}
              className="w-full px-3 py-2 rounded-lg font-mono text-sm text-white bg-transparent outline-none border border-terminal-border"
            />
          </div>
          <div className="flex justify-end space-x-2 pt-2">
            <button
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-lg font-mono text-sm text-muted-foreground hover:text-white transition-colors border border-terminal-border"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={rating === 0 || isSubmitting}
              className="px-4 py-2 rounded-lg font-mono text-sm transition-all disabled:opacity-40 bg-[var(--nous-sol-muted)] border border-[var(--nous-helios)] text-sol"
            >
              {isSubmitting ? 'Submitting...' : 'Submit'}
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

const MetricsDisplay: React.FC<{ metrics: SearchMetrics }> = ({ metrics }) => {
  const getScoreColor = (score: number): string => {
    if (score >= 90) return 'var(--nous-sol)';
    if (score >= 80) return 'var(--nous-helios)';
    if (score >= 70) return 'var(--nous-corona)';
    return 'var(--nous-mars)';
  };

  const formatScore = (score: number): string => {
    return `${Math.round(score)}%`;
  };

  const metricItems = [
    { label: 'Answer Relevancy', value: metrics.answer_relevancy },
    { label: 'Faithfulness', value: metrics.faithfulness_score },
    { label: 'Context Relevancy', value: metrics.contextual_relevancy },
    { label: 'Safety Score', value: 100 - metrics.hallucination_score },
  ];

  return (
    <div className="rounded-xl p-4 bg-terminal-surface border border-terminal-border">
      <div className="flex items-center space-x-2 mb-4">
        <ChartBarIcon className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-mono text-muted-foreground">
          Quality Metrics
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        {metricItems.map((item) => (
          <div key={item.label} className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-muted-foreground">
                {item.label}
              </span>
              <span
                className="font-mono font-medium text-xs"
                style={{ color: getScoreColor(item.value) }}
              >
                {formatScore(item.value)}
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full overflow-hidden bg-terminal-border">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${item.value}%`,
                  background: `linear-gradient(90deg, ${getScoreColor(item.value)}80, ${getScoreColor(item.value)})`,
                }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-terminal-border pt-4 mt-4" />

      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'LATENCY', value: `${Math.round(metrics.latency_ms)}ms` },
          { label: 'DOCS', value: metrics.documents_retrieved },
          { label: 'ENTITIES', value: metrics.entities_found },
        ].map((stat) => (
          <div
            key={stat.label}
            className="flex flex-col items-center p-3 rounded-lg bg-terminal-bg border border-terminal-border"
          >
            <span className="font-mono font-medium text-white">
              {stat.value}
            </span>
            <span className="text-[10px] font-mono uppercase tracking-wider mt-0.5 text-muted-foreground">
              {stat.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// --- Typewriter Effect Component ---
interface TypewriterTextProps {
  text: string;
  speed?: number;
  className?: string;
}

const TypewriterText: React.FC<TypewriterTextProps> = ({
  text,
  speed = 10,
  className,
}) => {
  const [displayedText, setDisplayedText] = useState('');

  useEffect(() => {
    let index = 0;
    setDisplayedText('');

    // Clear previous if text changes
    const interval = setInterval(() => {
      if (index < text.length) {
        setDisplayedText((prev) => prev + text.charAt(index));
        index++;
      } else {
        clearInterval(interval);
      }
    }, speed);

    return () => clearInterval(interval);
  }, [text, speed]);

  return (
    <span className={className}>
      {displayedText}
      <span className="animate-pulse inline-block w-2 h-4 bg-[var(--nous-sol)] align-middle ml-1" />
    </span>
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
  const [copiedSource, setCopiedSource] = useState<string | null>(null);
  const [copiedAnswer, setCopiedAnswer] = useState(false);

  const getFileIcon = (fileType?: string) => {
    const iconClass = 'h-4 w-4';
    switch (fileType) {
      case 'pdf':
        return (
          <DocumentTextIcon
            className={cn(iconClass, 'text-[var(--nous-fg-3)]')}
          />
        );
      case 'txt':
        return (
          <DocumentTextIcon
            className={cn(iconClass, 'text-[var(--nous-fg-3)]')}
          />
        );
      case 'jpg':
      case 'png':
        return <PhotoIcon className={cn(iconClass, 'text-sol')} />;
      case 'mp3':
        return (
          <MusicalNoteIcon
            className={cn(iconClass, 'text-[var(--nous-fg-3)]')}
          />
        );
      case 'mp4':
        return <VideoCameraIcon className={cn(iconClass, 'text-helios')} />;
      default:
        return (
          <DocumentTextIcon
            className={cn(iconClass, 'text-muted-foreground')}
          />
        );
    }
  };

  const getAnswerTypeConfig = (answerType: string) => {
    switch (answerType) {
      case 'factual':
        return {
          colorClass: 'text-sol',
          bgClass: 'bg-sol-muted',
          borderClass: 'border-sol-dim',
        };
      case 'reasoning':
        return {
          colorClass: 'text-[var(--nous-fg-2)]',
          bgClass: 'bg-[var(--nous-bg-3)]/10',
          borderClass: 'border-[var(--nous-border-1)]/20',
        };
      case 'summarization':
        return {
          colorClass: 'text-brand-cyan',
          bgClass: 'bg-brand-cyan-muted',
          borderClass: 'border-brand-cyan-dim',
        };
      case 'comparison':
        return {
          colorClass: 'text-helios',
          bgClass: 'bg-helios-muted',
          borderClass: 'border-helios-dim',
        };
      default:
        return {
          colorClass: 'text-muted-foreground',
          bgClass: 'bg-[var(--nous-bg-3)]/10',
          borderClass: 'border-border/20',
        };
    }
  };

  const getDeterministicStatusConfig = (
    status?: SearchResult['deterministicStatus']
  ) => {
    switch (status) {
      case 'SUPPORTED':
        return {
          label: 'SUPPORTED',
          colorClass: 'text-sol',
          bgClass: 'bg-sol-muted',
          borderClass: 'border-sol-dim',
        };
      case 'INSUFFICIENT_EVIDENCE':
        return {
          label: 'INSUFFICIENT EVIDENCE',
          colorClass: 'text-[var(--nous-corona)]',
          bgClass: 'bg-[var(--nous-corona)]/10',
          borderClass: 'border-[var(--nous-corona)]/25',
        };
      case 'CONFLICTING_EVIDENCE':
        return {
          label: 'CONFLICTING EVIDENCE',
          colorClass: 'text-[var(--nous-corona)]',
          bgClass: 'bg-[var(--nous-corona)]/10',
          borderClass: 'border-[var(--nous-corona)]/25',
        };
      case 'NO_MATCH':
        return {
          label: 'NO MATCH',
          colorClass: 'text-[var(--nous-mars)]',
          bgClass: 'bg-[var(--nous-mars)]/10',
          borderClass: 'border-[var(--nous-mars)]/25',
        };
      default:
        return {
          label: 'UNKNOWN',
          colorClass: 'text-muted-foreground',
          bgClass: 'bg-[var(--nous-bg-3)]/10',
          borderClass: 'border-border/20',
        };
    }
  };

  const handleSourceClick = useCallback(
    (source: SourceReference) => {
      onSourceClick?.(source);
    },
    [onSourceClick]
  );

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

  const handleDocumentPreview = useCallback(
    (source: SourceReference) => {
      onDocumentPreview?.(source.document_id);
    },
    [onDocumentPreview]
  );

  const handleShare = useCallback(() => {
    onShare?.(result!);
  }, [result, onShare]);

  const handleExport = useCallback(() => {
    onExport?.(result!);
  }, [result, onExport]);

  const handleFeedback = useCallback(
    (rating: number, comment?: string) => {
      onFeedback?.(result!, rating, comment);
    },
    [result, onFeedback]
  );

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
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-16 rounded-lg animate-pulse bg-sol-muted/5 border border-sol-muted"
          />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn('text-center py-8', className)}>
        <XCircleIcon className="h-12 w-12 text-[var(--nous-mars)] mx-auto mb-4" />
        <h3 className="text-lg font-mono font-medium text-white mb-2">
          Search failed
        </h3>
        <p className="text-muted-foreground font-mono text-sm">{error}</p>
      </div>
    );
  }

  if (!result) {
    return (
      <div className={cn('text-center py-8', className)}>
        <div className="h-12 w-12 rounded-full mx-auto mb-4 flex items-center justify-center bg-terminal-bg border border-terminal-border">
          <MagnifyingGlassIcon className="h-6 w-6 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-mono font-medium text-white mb-2">
          Enter a search query
        </h3>
        <p className="text-muted-foreground font-mono text-sm">
          Search your documents using natural language queries
        </p>
      </div>
    );
  }

  const answerTypeConfig = getAnswerTypeConfig(result.answer.answer_type);
  const deterministicStatusConfig = getDeterministicStatusConfig(
    result.deterministicStatus
  );

  return (
    <div className={cn('space-y-6', className)}>
      {/* Query and Answer Header */}
      <div className="space-y-4">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <h1 className="text-xl font-mono font-semibold text-muted-foreground tracking-tight">
              {result.query}
            </h1>
            <div className="flex items-center flex-wrap gap-3 text-sm">
              <span
                className={cn(
                  'capitalize font-mono text-xs px-2 py-1 rounded border',
                  answerTypeConfig.bgClass,
                  answerTypeConfig.borderClass,
                  answerTypeConfig.colorClass
                )}
              >
                {result.answer.answer_type}
              </span>
              <span className="flex items-center text-muted-foreground font-mono text-xs">
                <ClockIcon className="h-3.5 w-3.5 mr-1" />
                {result.created_at
                  ? formatDate(result.created_at)
                  : 'Unknown date'}
              </span>
              <span className="flex items-center font-mono text-xs text-helios">
                <SparklesIcon className="h-3.5 w-3.5 mr-1" />
                {Math.round(result.answer.confidence * 100)}% confidence
              </span>
              {typeof result.answer.coverage === 'number' && (
                <span className="flex items-center font-mono text-xs text-muted-foreground">
                  COVERAGE {Math.round(result.answer.coverage * 100)}%
                </span>
              )}
              <span
                className={cn(
                  'font-mono text-[10px] px-2 py-1 rounded border',
                  deterministicStatusConfig.bgClass,
                  deterministicStatusConfig.borderClass,
                  deterministicStatusConfig.colorClass
                )}
              >
                {deterministicStatusConfig.label}
              </span>
              {result.answer.decisionTraceId && (
                <span className="text-[10px] font-mono text-muted-foreground">
                  trace: {result.answer.decisionTraceId}
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center space-x-1">
            {[
              {
                icon: copiedAnswer ? CheckCircleIcon : ClipboardDocumentIcon,
                onClick: handleCopyAnswer,
                title: 'Copy',
              },
              { icon: ShareIcon, onClick: handleShare, title: 'Share' },
              {
                icon: ArrowDownTrayIcon,
                onClick: handleExport,
                title: 'Export',
              },
              {
                icon: StarIcon,
                onClick: () => setShowFeedbackDialog(true),
                title: 'Rate',
              },
            ].map((action, i) => (
              <IconButton
                key={i}
                icon={
                  <action.icon
                    className={cn(
                      'h-4 w-4',
                      copiedAnswer && i === 0 && 'text-[var(--nous-terra)]'
                    )}
                  />
                }
                label={action.title}
                onClick={action.onClick}
                className="p-2 rounded-lg text-muted-foreground hover:text-white hover:bg-white/5 transition-colors"
              />
            ))}
          </div>
        </div>

        {/* Answer Text - Using Typewriter Effect */}
        <div className="text-muted-foreground font-mono text-sm leading-relaxed min-h-[60px]">
          <TypewriterText text={result.answer.text} speed={10} />
        </div>

        {result.deterministicStatus &&
          result.deterministicStatus !== 'SUPPORTED' && (
            <div
              className={cn(
                'rounded-lg px-3 py-2 text-xs font-mono border',
                deterministicStatusConfig.bgClass,
                deterministicStatusConfig.borderClass,
                deterministicStatusConfig.colorClass
              )}
            >
              {result.deterministicMessage}
              {result.refinementSuggestions &&
                result.refinementSuggestions.length > 0 && (
                  <div className="mt-2 text-muted-foreground">
                    {result.refinementSuggestions
                      .slice(0, 2)
                      .map((suggestion, index) => (
                        <div key={`${suggestion}-${index}`}>- {suggestion}</div>
                      ))}
                  </div>
                )}
            </div>
          )}

        {/* Metrics */}
        <div className="pt-4">
          <MetricsDisplay metrics={result.metrics} />
        </div>
      </div>

      {/* Sources Section */}
      <div className="space-y-4">
        <div className="flex items-center space-x-2">
          <DocumentTextIcon className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-mono font-semibold text-muted-foreground">
            Sources
          </h2>
          <span className="rounded-full px-2 py-0.5 text-xs font-mono bg-[var(--nous-sol-muted)] text-brand-cyan border border-[var(--nous-helios-muted)]">
            {result.answer.sources.length}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {result.answer.sources.map((source, index) => (
            <div
              key={`${source.document_id}-${index}`}
              className="group rounded-xl p-4 cursor-pointer transition-all duration-200 hover:scale-[1.02] bg-terminal-surface border border-terminal-border"
              onClick={() => handleSourceClick(source)}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--nous-helios)';
                e.currentTarget.style.boxShadow =
                  '0 0 20px var(--nous-sol-muted)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--nous-border-1)';
                e.currentTarget.style.boxShadow = 'none';
              }}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center space-x-3">
                  <div className="p-2 rounded-lg bg-terminal-bg">
                    {getFileIcon(source.file_type || '')}
                  </div>
                  <div className="space-y-0.5 min-w-0">
                    <h4
                      className="text-sm font-mono font-medium text-muted-foreground truncate"
                      title={source.document_title}
                    >
                      {source.document_title}
                    </h4>
                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] px-1.5 py-0.5 rounded uppercase font-mono bg-terminal-border-muted text-terminal-text-muted">
                        {source.file_type}
                      </span>
                      <span className="text-[10px] font-mono text-muted-foreground">
                        {Math.round(source.confidence * 100)}%
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Source Snippet */}
              <div className="p-2 rounded-lg mb-3 bg-terminal-bg border border-terminal-border">
                <p className="text-xs font-mono text-muted-foreground leading-relaxed line-clamp-3">
                  &quot;{source.snippet}&quot;
                </p>
              </div>

              {/* Footer Actions */}
              <div className="flex items-center justify-between pt-2 border-t border-terminal-border">
                <div className="flex items-center space-x-2 text-[10px] text-muted-foreground font-mono">
                  {source.page_number && (
                    <span className="px-1.5 py-0.5 rounded bg-terminal-border-muted">
                      Page {source.page_number}
                    </span>
                  )}
                </div>
                <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <IconButtonSm
                    icon={<EyeIcon className="h-3.5 w-3.5" />}
                    label="Preview document"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDocumentPreview(source);
                    }}
                    className="p-1.5 rounded text-muted-foreground hover:text-white hover:bg-white/5 transition-colors"
                  />
                  <IconButtonSm
                    icon={<ClipboardDocumentIcon className="h-3.5 w-3.5" />}
                    label="Copy source snippet"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleCopySource(source);
                    }}
                    className="p-1.5 rounded text-muted-foreground hover:text-white hover:bg-white/5 transition-colors"
                  />
                </div>
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
