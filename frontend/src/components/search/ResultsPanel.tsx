import { cn } from '@/lib/utils';
import { SearchMetrics, SearchResult, SourceReference } from '@/types/search';
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
    XCircleIcon
} from '@heroicons/react/24/outline';
import React, { useCallback, useEffect, useState } from 'react';

// Terminal Observatory Theme Constants
import { THEME } from '@/theme/constants';

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

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div
        className="relative z-10 w-full max-w-md p-6 rounded-xl"
        style={{
          background: THEME.colors.card,
          border: `1px solid ${THEME.colors.border}`,
          boxShadow: `0 0 60px ${THEME.colors.primary}10`,
        }}
      >
        <h3 className="text-lg font-mono font-semibold text-white mb-4">Rate this answer</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-mono text-gray-400 mb-2">
              How helpful was this answer?
            </label>
            <div className="flex space-x-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setRating(star)}
                  className="p-1 hover:scale-110 transition-transform"
                >
                  <StarIcon
                    className={cn(
                      "h-6 w-6",
                      star <= rating ? "text-amber-400 fill-amber-400" : "text-gray-600"
                    )}
                  />
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm font-mono text-gray-400 mb-2">
              Additional feedback (optional)
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Tell us more..."
              rows={3}
              className="w-full px-3 py-2 rounded-lg font-mono text-sm text-white bg-transparent outline-none"
              style={{ border: `1px solid ${THEME.colors.border}` }}
            />
          </div>
          <div className="flex justify-end space-x-2 pt-2">
            <button
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-lg font-mono text-sm text-gray-400 hover:text-white transition-colors"
              style={{ border: `1px solid ${THEME.colors.border}` }}
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={rating === 0 || isSubmitting}
              className="px-4 py-2 rounded-lg font-mono text-sm transition-all disabled:opacity-40"
              style={{
                background: `${THEME.colors.primary}20`,
                border: `1px solid ${THEME.colors.primary}50`,
                color: THEME.colors.primary,
              }}
            >
              {isSubmitting ? 'Submitting...' : 'Submit'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

const MetricsDisplay: React.FC<{ metrics: SearchMetrics }> = ({ metrics }) => {
  const getScoreColor = (score: number): string => {
    if (score >= 90) return THEME.colors.primary;
    if (score >= 80) return THEME.colors.accent;
    if (score >= 70) return '#f97316';
    return THEME.colors.error;
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
    <div
      className="rounded-xl p-4"
      style={{
        background: THEME.colors.card,
        border: `1px solid ${THEME.colors.border}`,
      }}
    >
      <div className="flex items-center space-x-2 mb-4">
        <ChartBarIcon className="h-4 w-4 text-gray-500" />
        <span className="text-sm font-mono text-gray-400">Quality Metrics</span>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        {metricItems.map((item) => (
          <div key={item.label} className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-gray-500">{item.label}</span>
              <span
                className="font-mono font-medium text-xs"
                style={{ color: getScoreColor(item.value) }}
              >
                {formatScore(item.value)}
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full overflow-hidden" style={{ background: THEME.colors.border }}>
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

      <div className="border-t pt-4 mt-4" style={{ borderColor: THEME.colors.border }} />

      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'LATENCY', value: `${Math.round(metrics.latency_ms)}ms` },
          { label: 'DOCS', value: metrics.documents_retrieved },
          { label: 'ENTITIES', value: metrics.entities_found },
        ].map((stat) => (
          <div
            key={stat.label}
            className="flex flex-col items-center p-3 rounded-lg"
            style={{ background: '#161b22', border: `1px solid ${THEME.colors.border}` }}
          >
            <span className="font-mono font-medium text-white">{stat.value}</span>
            <span className="text-[10px] font-mono uppercase tracking-wider mt-0.5 text-gray-500">
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

const TypewriterText: React.FC<TypewriterTextProps> = ({ text, speed = 10, className }) => {
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
      <span className="animate-pulse inline-block w-2 h-4 bg-[var(--phosphor-green)] align-middle ml-1" />
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

  const getFileIcon = (fileType: string) => {
    const iconClass = "h-4 w-4";
    switch (fileType) {
      case 'pdf':
        return <DocumentTextIcon className={cn(iconClass)} style={{ color: '#ef4444' }} />;
      case 'txt':
        return <DocumentTextIcon className={cn(iconClass)} style={{ color: '#3b82f6' }} />;
      case 'jpg':
      case 'png':
        return <PhotoIcon className={cn(iconClass)} style={{ color: THEME.colors.primary }} />;
      case 'mp3':
        return <MusicalNoteIcon className={cn(iconClass)} style={{ color: '#a855f7' }} />;
      case 'mp4':
        return <VideoCameraIcon className={cn(iconClass)} style={{ color: THEME.colors.accent }} />;
      default:
        return <DocumentTextIcon className={cn(iconClass)} style={{ color: '#6b7280' }} />;
    }
  };

  const getAnswerTypeConfig = (answerType: string) => {
    switch (answerType) {
      case 'factual':
        return { color: THEME.colors.primary, bg: `${THEME.colors.primary}15`, border: `${THEME.colors.primary}30` };
      case 'reasoning':
        return { color: '#a855f7', bg: '#a855f715', border: '#a855f730' };
      case 'summarization':
        return { color: THEME.colors.secondary, bg: `${THEME.colors.secondary}15`, border: `${THEME.colors.secondary}30` };
      case 'comparison':
        return { color: THEME.colors.accent, bg: `${THEME.colors.accent}15`, border: `${THEME.colors.accent}30` };
      default:
        return { color: '#6b7280', bg: '#6b728015', border: '#6b728030' };
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
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-16 rounded-lg animate-pulse"
            style={{
              background: `linear-gradient(90deg, ${THEME.colors.primary}05 0%, ${THEME.colors.primary}10 50%, ${THEME.colors.primary}05 100%)`,
              border: `1px solid ${THEME.colors.primary}15`,
            }}
          />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn("text-center py-8", className)}>
        <XCircleIcon className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h3 className="text-lg font-mono font-medium text-white mb-2">Search failed</h3>
        <p className="text-gray-400 font-mono text-sm">{error}</p>
      </div>
    );
  }

  if (!result) {
    return (
      <div className={cn("text-center py-8", className)}>
        <div
          className="h-12 w-12 rounded-full mx-auto mb-4 flex items-center justify-center"
          style={{ background: '#161b22', border: `1px solid ${THEME.colors.border}` }}
        >
          <MagnifyingGlassIcon className="h-6 w-6 text-gray-500" />
        </div>
        <h3 className="text-lg font-mono font-medium text-white mb-2">Enter a search query</h3>
        <p className="text-gray-500 font-mono text-sm">
          Search your documents using natural language queries
        </p>
      </div>
    );
  }

  const answerTypeConfig = getAnswerTypeConfig(result.answer.answer_type);

  return (
    <div className={cn("space-y-6", className)}>
      {/* Query and Answer Header */}
      <div className="space-y-4">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <h1 className="text-xl font-mono font-semibold text-gray-300 tracking-tight">
              {result.query}
            </h1>
            <div className="flex items-center flex-wrap gap-3 text-sm">
              <span
                className="capitalize font-mono text-xs px-2 py-1 rounded"
                style={{
                  background: answerTypeConfig.bg,
                  border: `1px solid ${answerTypeConfig.border}`,
                  color: answerTypeConfig.color,
                }}
              >
                {result.answer.answer_type}
              </span>
              <span className="flex items-center text-gray-500 font-mono text-xs">
                <ClockIcon className="h-3.5 w-3.5 mr-1" />
                {formatDate(result.created_at)}
              </span>
              <span className="flex items-center font-mono text-xs" style={{ color: THEME.colors.accent }}>
                <SparklesIcon className="h-3.5 w-3.5 mr-1" />
                {Math.round(result.answer.confidence * 100)}% confidence
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-1">
            {[
              { icon: copiedAnswer ? CheckCircleIcon : ClipboardDocumentIcon, onClick: handleCopyAnswer, title: 'Copy' },
              { icon: ShareIcon, onClick: handleShare, title: 'Share' },
              { icon: ArrowDownTrayIcon, onClick: handleExport, title: 'Export' },
              { icon: StarIcon, onClick: () => setShowFeedbackDialog(true), title: 'Rate' },
            ].map((action, i) => (
              <button
                key={i}
                onClick={action.onClick}
                className="p-2 rounded-lg text-gray-500 hover:text-white hover:bg-white/5 transition-colors"
                title={action.title}
              >
                <action.icon className={cn("h-4 w-4", copiedAnswer && i === 0 && "text-green-500")} />
              </button>
            ))}
          </div>
        </div>

        {/* Answer Text - Using Typewriter Effect */}
        <div className="text-gray-300 font-mono text-sm leading-relaxed min-h-[60px]">
          <TypewriterText text={result.answer.text} speed={10} />
        </div>

        {/* Metrics */}
        <div className="pt-4">
          <MetricsDisplay metrics={result.metrics} />
        </div>
      </div>

      {/* Sources Section */}
      <div className="space-y-4">
        <div className="flex items-center space-x-2">
          <DocumentTextIcon className="h-5 w-5 text-gray-500" />
          <h2 className="text-lg font-mono font-semibold text-gray-300">Sources</h2>
          <span
            className="rounded-full px-2 py-0.5 text-xs font-mono"
            style={{ background: `${THEME.colors.secondary}15`, color: THEME.colors.secondary, border: `1px solid ${THEME.colors.secondary}30` }}
          >
            {result.answer.sources.length}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {result.answer.sources.map((source, index) => (
            <div
              key={`${source.document_id}-${index}`}
              className="group rounded-xl p-4 cursor-pointer transition-all duration-200 hover:scale-[1.02]"
              style={{
                background: THEME.colors.card,
                border: `1px solid ${THEME.colors.border}`,
              }}
              onClick={() => handleSourceClick(source)}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = `${THEME.colors.primary}40`;
                e.currentTarget.style.boxShadow = `0 0 20px ${THEME.colors.primary}10`;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = THEME.colors.border;
                e.currentTarget.style.boxShadow = 'none';
              }}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center space-x-3">
                  <div
                    className="p-2 rounded-lg"
                    style={{ background: '#161b22' }}
                  >
                    {getFileIcon(source.file_type)}
                  </div>
                  <div className="space-y-0.5 min-w-0">
                    <h4
                      className="text-sm font-mono font-medium text-gray-300 truncate"
                      title={source.document_title}
                    >
                      {source.document_title}
                    </h4>
                    <div className="flex items-center space-x-2">
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded uppercase font-mono"
                        style={{ background: '#21262d', color: '#8b949e' }}
                      >
                        {source.file_type}
                      </span>
                      <span className="text-[10px] font-mono text-gray-500">
                        {Math.round(source.confidence * 100)}%
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Source Snippet */}
              <div
                className="p-2 rounded-lg mb-3"
                style={{ background: '#161b22', border: `1px solid ${THEME.colors.border}` }}
              >
                <p className="text-xs font-mono text-gray-400 leading-relaxed line-clamp-3">
                  &quot;{source.snippet}&quot;
                </p>
              </div>

              {/* Footer Actions */}
              <div className="flex items-center justify-between pt-2" style={{ borderTop: `1px solid ${THEME.colors.border}` }}>
                <div className="flex items-center space-x-2 text-[10px] text-gray-500 font-mono">
                  {source.page_number && (
                    <span
                      className="px-1.5 py-0.5 rounded"
                      style={{ background: '#21262d' }}
                    >
                      Page {source.page_number}
                    </span>
                  )}
                </div>
                <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDocumentPreview(source); }}
                    className="p-1.5 rounded text-gray-500 hover:text-white hover:bg-white/5 transition-colors"
                    title="Preview"
                  >
                    <EyeIcon className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleCopySource(source); }}
                    className="p-1.5 rounded text-gray-500 hover:text-white hover:bg-white/5 transition-colors"
                    title="Copy"
                  >
                    <ClipboardDocumentIcon className="h-3.5 w-3.5" />
                  </button>
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
