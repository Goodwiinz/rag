import React, { useState, useCallback, useEffect } from 'react';
import {
  ArrowPathIcon,
  SparklesIcon,
  DocumentTextIcon,
  FunnelIcon,
  ClockIcon,
  AcademicCapIcon,
  LightBulbIcon,
  CheckCircleIcon,
  XCircleIcon,
  InformationCircleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline';
import { QueryRewrite, QueryIntent } from '@/types/search';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';

interface QueryRewriterProps {
  query: string;
  intent?: QueryIntent;
  onRewrite?: (rewrite: QueryRewrite) => void;
  loading?: boolean;
  showDetails?: boolean;
  autoApply?: boolean;
  className?: string;
}

interface RewriteDetailProps {
  rewrite: QueryRewrite;
  intent: QueryIntent;
  isOpen: boolean;
  onClose: () => void;
  onApplyRewrite?: (rewrittenQuery: string) => void;
}

const RewriteDetail: React.FC<RewriteDetailProps> = ({
  rewrite,
  intent,
  isOpen,
  onClose,
  onApplyRewrite
}) => {
  const [expandedQuery, setExpandedQuery] = useState<number | null>(null);

  const getStrategyColor = (strategy: string) => {
    switch (strategy) {
      case 'expansion':
        return 'bg-blue-100 text-blue-800';
      case 'simplification':
        return 'bg-green-100 text-green-800';
      case 'temporal_adaptation':
        return 'bg-purple-100 text-purple-800';
      case 'domain_enhancement':
        return 'bg-orange-100 text-orange-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStrategyIcon = (strategy: string) => {
    const iconClass = "h-4 w-4";
    switch (strategy) {
      case 'expansion':
        return <SparklesIcon className={cn(iconClass, "text-blue-600")} />;
      case 'simplification':
        return <LightBulbIcon className={cn(iconClass, "text-green-600")} />;
      case 'temporal_adaptation':
        return <ClockIcon className={cn(iconClass, "text-purple-600")} />;
      case 'domain_enhancement':
        return <AcademicCapIcon className={cn(iconClass, "text-orange-600")} />;
      default:
        return <DocumentTextIcon className={cn(iconClass, "text-gray-600")} />;
    }
  };

  const getFilterIcon = (filterType: string) => {
    const iconClass = "h-4 w-4";
    switch (filterType) {
      case 'modality':
        return <DocumentTextIcon className={cn(iconClass, "text-blue-600")} />;
      case 'date_range':
        return <ClockIcon className={cn(iconClass, "text-green-600")} />;
      case 'file_type':
        return <FunnelIcon className={cn(iconClass, "text-purple-600")} />;
      case 'entity':
        return <SparklesIcon className={cn(iconClass, "text-orange-600")} />;
      default:
        return <FunnelIcon className={cn(iconClass, "text-gray-600")} />;
    }
  };

  const formatFilterValue = (filter: any, filterType: string): string => {
    switch (filterType) {
      case 'modality':
        return Array.isArray(filter) ? filter.join(', ') : filter;
      case 'date_range':
        if (filter.start && filter.end) {
          return `${new Date(filter.start).toLocaleDateString()} - ${new Date(filter.end).toLocaleDateString()}`;
        }
        return 'Date range';
      case 'file_type':
        return Array.isArray(filter) ? filter.join(', ').toUpperCase() : filter.toUpperCase();
      case 'entity':
        return filter.name || filter;
      default:
        return JSON.stringify(filter);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Query Rewriting Analysis</DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Original Query */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Original Query</h3>
            <div className="p-4 bg-gray-50 rounded-lg">
              <p className="text-gray-800 italic">"{rewrite.original_query}"</p>
            </div>
          </div>

          {/* Rewritten Queries */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Rewritten Queries ({rewrite.rewritten_queries.length})</h3>
            <div className="space-y-3">
              {rewrite.rewritten_queries.map((rewrittenQuery, index) => (
                <div key={index} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center space-x-3">
                      {getStrategyIcon(rewrittenQuery.strategy)}
                      <div>
                        <Badge className={cn("text-xs", getStrategyColor(rewrittenQuery.strategy))}>
                          {rewrittenQuery.strategy.replace('_', ' ')}
                        </Badge>
                        <span className="ml-2 text-sm text-gray-600">
                          Confidence: {Math.round(rewrittenQuery.confidence * 100)}%
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {onApplyRewrite && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onApplyRewrite(rewrittenQuery.query)}
                          className="h-6 text-xs"
                        >
                          Apply
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setExpandedQuery(expandedQuery === index ? null : index)}
                        className="h-6 w-6 p-0"
                      >
                        {expandedQuery === index ? (
                          <ChevronUpIcon className="h-3 w-3" />
                        ) : (
                          <ChevronDownIcon className="h-3 w-3" />
                        )}
                      </Button>
                    </div>
                  </div>

                  <div className="bg-white rounded p-3 border border-gray-200">
                    <p className="text-gray-800">"{rewrittenQuery.query}"</p>
                  </div>

                  {expandedQuery === index && (
                    <div className="mt-3 p-3 bg-blue-50 rounded">
                      <h4 className="text-sm font-medium text-blue-900 mb-2">Reasoning:</h4>
                      <p className="text-sm text-blue-800">{rewrittenQuery.reasoning}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Changes Made */}
          <div className="grid grid-cols-2 gap-6">
            {/* Expanded Terms */}
            {rewrite.expanded_terms.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Added Terms</h3>
                <div className="flex flex-wrap gap-2">
                  {rewrite.expanded_terms.map((term, index) => (
                    <div key={index} className="flex items-center space-x-1 bg-green-50 rounded-full px-3 py-1">
                      <span className="text-sm font-medium text-green-800">{term}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Removed Terms */}
            {rewrite.removed_terms.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Removed Terms</h3>
                <div className="flex flex-wrap gap-2">
                  {rewrite.removed_terms.map((term, index) => (
                    <div key={index} className="flex items-center space-x-1 bg-red-50 rounded-full px-3 py-1">
                      <span className="text-sm font-medium text-red-800">{term}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Suggested Filters */}
          {rewrite.suggested_filters.length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Suggested Filters ({rewrite.suggested_filters.length})</h3>
              <div className="space-y-2">
                {rewrite.suggested_filters.map((filter, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-orange-50 rounded-lg">
                    <div className="flex items-center space-x-3">
                      {getFilterIcon(filter.type)}
                      <div>
                        <span className="font-medium text-gray-900 capitalize">{filter.type.replace('_', ' ')}:</span>
                        <span className="ml-2 text-sm text-gray-600">
                          {formatFilterValue(filter.value, filter.type)}
                        </span>
                      </div>
                    </div>
                    <span className="text-sm text-gray-500">
                      {Math.round(filter.confidence * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Intent Context */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Intent Context</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-3 bg-gray-50 rounded">
                <span className="text-xs font-medium text-gray-700 block">Primary Intent</span>
                <span className="text-sm font-semibold text-gray-900 capitalize">
                  {intent.primary_intent.replace('_', ' ')}
                </span>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <span className="text-xs font-medium text-gray-700 block">Complexity</span>
                <span className="text-sm font-semibold text-gray-900 capitalize">{intent.complexity}</span>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <span className="text-xs font-medium text-gray-700 block">Temporal</span>
                <span className="text-sm font-semibold text-gray-900 capitalize">{intent.temporal_aspect}</span>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <span className="text-xs font-medium text-gray-700 block">Domain</span>
                <span className="text-sm font-semibold text-gray-900 capitalize">
                  {intent.domain_specificity.replace('_', ' ')}
                </span>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export const QueryRewriter: React.FC<QueryRewriterProps> = ({
  query,
  intent,
  onRewrite,
  loading = false,
  showDetails = false,
  autoApply = false,
  className,
}) => {
  const [rewrite, setRewrite] = useState<QueryRewrite | null>(null);
  const [isRewriting, setIsRewriting] = useState(false);
  const [showDetailDialog, setShowDetailDialog] = useState(false);
  const [appliedRewrite, setAppliedRewrite] = useState<string | null>(null);

  const generateRewrite = useCallback(async (
    queryText: string,
    queryIntent?: QueryIntent
  ): Promise<QueryRewrite> => {
    const rewrittenQueries: QueryRewrite['rewritten_queries'] = [];
    const expandedTerms: string[] = [];
    const removedTerms: string[] = [];
    const suggestedFilters: QueryRewrite['suggested_filters'] = [];

    const lowerQuery = queryText.toLowerCase().trim();
    const words = queryText.split(/\s+/);
    const stopWords = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'];

    // Strategy 1: Query Expansion
    if (queryIntent?.domain_specificity === 'technical' || lowerQuery.includes('technical')) {
      const technicalTerms: Record<string, string[]> = {
        'algorithm': ['algorithmic approach', 'computational method', 'procedure'],
        'system': ['architecture', 'framework', 'infrastructure'],
        'process': ['workflow', 'pipeline', 'methodology'],
        'data': ['dataset', 'information', 'metrics'],
        'performance': ['efficiency', 'optimization', 'throughput'],
        'security': ['protection', 'safeguards', 'authentication'],
      };

      const expansions: string[] = [];
      Object.entries(technicalTerms).forEach(([term, synonyms]) => {
        if (lowerQuery.includes(term)) {
          expandedTerms.push(...synonyms.slice(0, 2));
          expansions.push(...synonyms.slice(0, 2));
        }
      });

      if (expansions.length > 0) {
        const expandedQuery = queryText + ' ' + expansions.join(' ');
        rewrittenQueries.push({
          query: expandedQuery,
          strategy: 'expansion',
          confidence: 0.85,
          reasoning: `Added technical terms related to ${Object.keys(technicalTerms).filter(term => lowerQuery.includes(term)).join(', ')} to improve search precision`
        });
      }
    }

    // Strategy 2: Query Simplification
    if (queryIntent?.complexity === 'complex' || words.length > 12) {
      const simplifiedWords = words.filter(word =>
        !stopWords.includes(word.toLowerCase()) &&
        word.length > 2
      ).slice(0, 8);

      const removedWords = words.filter(word =>
        stopWords.includes(word.toLowerCase()) ||
        word.length <= 2
      );
      removedTerms.push(...removedWords);

      const simplifiedQuery = simplifiedWords.join(' ');
      rewrittenQueries.push({
        query: simplifiedQuery,
        strategy: 'simplification',
        confidence: 0.75,
        reasoning: 'Simplified complex query to focus on key concepts and improve search relevance'
      });
    }

    // Strategy 3: Temporal Adaptation
    if (queryIntent?.temporal_aspect === 'current' || lowerQuery.includes('current') || lowerQuery.includes('now')) {
      const temporalQuery = queryText + ' recent latest current 2024 2025';
      rewrittenQueries.push({
        query: temporalQuery,
        strategy: 'temporal_adaptation',
        confidence: 0.9,
        reasoning: 'Added temporal terms to focus on recent and current information'
      });
    } else if (queryIntent?.temporal_aspect === 'historical' || lowerQuery.includes('history') || lowerQuery.includes('past')) {
      const temporalQuery = queryText + ' historical background evolution development timeline';
      rewrittenQueries.push({
        query: temporalQuery,
        strategy: 'temporal_adaptation',
        confidence: 0.85,
        reasoning: 'Added historical context terms to capture background and development information'
      });
    }

    // Strategy 4: Domain Enhancement
    if (queryIntent?.modality_preference && queryIntent.modality_preference.length > 1) {
      const modalityTerms = queryIntent.modality_preference.map(modality => {
        switch (modality) {
          case 'image':
            return 'visual picture photo diagram chart';
          case 'audio':
            return 'sound music voice recording podcast';
          case 'video':
            return 'multimedia recording clip presentation demonstration';
          default:
            return 'text document article report';
        }
      }).join(' ');

      const enhancedQuery = queryText + ' ' + modalityTerms;
      rewrittenQueries.push({
        query: enhancedQuery,
        strategy: 'domain_enhancement',
        confidence: 0.8,
        reasoning: `Enhanced query with ${queryIntent.modality_preference.join(', ')} related terms to capture multimodal content`
      });
    }

    // Generate suggested filters based on intent
    if (queryIntent?.entities && queryIntent.entities.length > 0) {
      queryIntent.entities.slice(0, 3).forEach(entity => {
        suggestedFilters.push({
          type: 'entity',
          value: entity.name,
          confidence: entity.confidence
        });
      });
    }

    if (queryIntent?.modality_preference && queryIntent.modality_preference.length > 0) {
      suggestedFilters.push({
        type: 'modality',
        value: queryIntent.modality_preference,
        confidence: 0.9
      });
    }

    if (queryIntent?.temporal_aspect && queryIntent?.temporal_aspect !== 'timeless') {
      const endDate = new Date();
      const startDate = new Date();

      if (queryIntent.temporal_aspect === 'current') {
        startDate.setMonth(startDate.getMonth() - 12);
      } else if (queryIntent.temporal_aspect === 'historical') {
        startDate.setFullYear(startDate.getFullYear() - 10);
      }

      suggestedFilters.push({
        type: 'date_range',
        value: {
          start: startDate.toISOString().split('T')[0],
          end: endDate.toISOString().split('T')[0]
        },
        confidence: 0.7
      });
    }

    // If no specific strategies were applied, create a general enhancement
    if (rewrittenQueries.length === 0) {
      const enhancedQuery = queryText + ' detailed comprehensive information overview';
      rewrittenQueries.push({
        query: enhancedQuery,
        strategy: 'expansion',
        confidence: 0.7,
        reasoning: 'Added general terms to broaden search scope and capture comprehensive information'
      });
    }

    return {
      original_query: queryText,
      rewritten_queries: rewrittenQueries.slice(0, 4), // Limit to top 4 rewrites
      expanded_terms: [...new Set(expandedTerms)].slice(0, 10),
      removed_terms: [...new Set(removedTerms)].slice(0, 10),
      suggested_filters: suggestedFilters.slice(0, 6) // Limit to top 6 filters
    };
  }, []);

  useEffect(() => {
    if (query && query.trim().length > 0 && intent) {
      setIsRewriting(true);
      const timer = setTimeout(async () => {
        try {
          const queryRewrite = await generateRewrite(query, intent);
          setRewrite(queryRewrite);
          onRewrite?.(queryRewrite);

          // Auto-apply the highest confidence rewrite if enabled
          if (autoApply && queryRewrite.rewritten_queries.length > 0) {
            const bestRewrite = queryRewrite.rewritten_queries.reduce((best, current) =>
              current.confidence > best.confidence ? current : best
            );
            setAppliedRewrite(bestRewrite.query);
          }
        } catch (error) {
          console.error('Query rewriting failed:', error);
        } finally {
          setIsRewriting(false);
        }
      }, 500);

      return () => clearTimeout(timer);
    } else {
      setRewrite(null);
      setAppliedRewrite(null);
      return undefined;
    }
  }, [query, intent, generateRewrite, onRewrite, autoApply]);

  const handleApplyRewrite = useCallback((rewrittenQuery: string) => {
    setAppliedRewrite(rewrittenQuery);
    // In a real implementation, this would trigger a new search with the rewritten query
    console.log('Applied rewrite:', rewrittenQuery);
  }, []);

  if (!query || !intent) {
    return null;
  }

  return (
    <div className={cn("space-y-3", className)}>
      {/* Rewrite Summary */}
      <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
        <div className="flex items-center space-x-3">
          {isRewriting ? (
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-green-600 border-t-transparent" />
          ) : (
            <ArrowPathIcon className="h-4 w-4 text-green-600" />
          )}
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium text-gray-900">Query Enhancement:</span>
              {rewrite ? (
                <span className="text-sm font-semibold text-green-600">
                  {rewrite.rewritten_queries.length} optimization{rewrite.rewritten_queries.length !== 1 ? 's' : ''} available
                </span>
              ) : (
                <span className="text-sm text-gray-500">
                  {isRewriting ? 'Analyzing...' : 'No optimizations available'}
                </span>
              )}
            </div>
            {rewrite && (
              <div className="flex items-center space-x-2 mt-1">
                <Badge variant="outline" className="text-xs">
                  {rewrite.expanded_terms.length} terms added
                </Badge>
                <Badge variant="outline" className="text-xs">
                  {rewrite.suggested_filters.length} filters suggested
                </Badge>
              </div>
            )}
          </div>
        </div>

        {showDetails && rewrite && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDetailDialog(true)}
            className="h-8 w-8 p-0"
          >
            <InformationCircleIcon className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Applied Rewrite Indicator */}
      {appliedRewrite && (
        <div className="flex items-center space-x-2 p-3 bg-green-50 rounded-lg">
          <CheckCircleIcon className="h-4 w-4 text-green-600" />
          <span className="text-sm font-medium text-green-800">Applied optimization:</span>
          <span className="text-sm text-green-700 italic">"{appliedRewrite}"</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setAppliedRewrite(null)}
            className="h-6 w-6 p-0 ml-auto"
          >
            <XCircleIcon className="h-3 w-3" />
          </Button>
        </div>
      )}

      {/* Quick Actions */}
      {rewrite && !loading && rewrite.rewritten_queries.length > 0 && !autoApply && (
        <div className="flex flex-wrap gap-2">
          {rewrite.rewritten_queries.slice(0, 2).map((rewrittenQuery, index) => (
            <Button
              key={index}
              variant="outline"
              size="sm"
              onClick={() => handleApplyRewrite(rewrittenQuery.query)}
              className="h-8 text-xs"
            >
              <ArrowPathIcon className="h-3 w-3 mr-1" />
              Apply {rewrittenQuery.strategy.replace('_', ' ')}
            </Button>
          ))}
        </div>
      )}

      {/* Detail Dialog */}
      {rewrite && (
        <RewriteDetail
          rewrite={rewrite}
          intent={intent}
          isOpen={showDetailDialog}
          onClose={() => setShowDetailDialog(false)}
          onApplyRewrite={handleApplyRewrite}
        />
      )}
    </div>
  );
};

export default QueryRewriter;