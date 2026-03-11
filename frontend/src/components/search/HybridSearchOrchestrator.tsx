import React, { useState, useCallback, useEffect } from 'react';
import {
  BoltIcon,
  DocumentTextIcon,
  ShareIcon,
  MagnifyingGlassIcon,
  ChartBarIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  PlayIcon,
  PauseIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import { HybridSearchConfig, SearchStageResult } from '@/types/search';
import { cn } from '@/lib/utils';
import { IconButton, IconButtonSm } from "@/components/ui/icon-button";
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';

interface HybridSearchOrchestratorProps {
  query: string;
  config?: Partial<HybridSearchConfig>;
  onSearchComplete?: (results: SearchStageResult[]) => void;
  onStageUpdate?: (stage: string, result: SearchStageResult) => void;
  autoStart?: boolean;
  showDetails?: boolean;
  className?: string;
}

interface SearchStageProps {
  stage: SearchStageResult;
  isActive: boolean;
  isCompleted: boolean;
  hasError: boolean;
  onRetry?: () => void;
}

const SearchStage: React.FC<SearchStageProps> = ({ stage, isActive, isCompleted, hasError, onRetry }) => {
  const getStageIcon = () => {
    if (isActive && !isCompleted) {
      return <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />;
    }

    if (hasError) {
      return <XCircleIcon className="h-5 w-5 text-red-600" />;
    }

    if (isCompleted) {
      return <CheckCircleIcon className="h-5 w-5 text-green-600" />;
    }

    switch (stage.stage) {
      case 'vector':
        return <BoltIcon className="h-5 w-5 text-purple-600" />;
      case 'graph':
        return <ShareIcon className="h-5 w-5 text-blue-600" />;
      case 'keyword':
        return <MagnifyingGlassIcon className="h-5 w-5 text-green-600" />;
      default:
        return <MagnifyingGlassIcon className="h-5 w-5 text-gray-600" />;
    }
  };

  const getStageColor = () => {
    if (hasError) return 'border-red-200 bg-red-50';
    if (isCompleted) return 'border-green-200 bg-green-50';
    if (isActive) return 'border-blue-200 bg-blue-50';
    return 'border-gray-200 bg-gray-50';
  };

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-600';
    if (score >= 80) return 'text-yellow-600';
    if (score >= 70) return 'text-orange-600';
    return 'text-red-600';
  };

  return (
    <div className={cn("border rounded-lg p-4 transition-colors", getStageColor())}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-3">
          {getStageIcon()}
          <div>
            <h4 className="font-medium text-gray-900 capitalize">{stage.stage} Search</h4>
            <p className="text-sm text-gray-600">
              {stage.latency_ms}ms latency
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {stage.confidence_score && (
            <span className={cn("text-sm font-medium", getScoreColor(stage.confidence_score))}>
              {Math.round(stage.confidence_score * 100)}%
            </span>
          )}
          {hasError && onRetry && (
            <IconButtonSm
              icon={<ArrowPathIcon className="h-3 w-3" />}
              label="Retry search stage"
              onClick={onRetry}
              className="h-6 w-6"
            />
          )}
        </div>
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-600">
          {stage.results.length} result{stage.results.length !== 1 ? 's' : ''}
        </span>
        {stage.error && (
          <span className="text-red-600 text-xs">{stage.error}</span>
        )}
      </div>

      {/* Progress Bar for Active Stage */}
      {isActive && !isCompleted && (
        <div className="mt-3">
          <div className="w-full bg-gray-200 rounded-full h-1">
            <div className="bg-blue-600 h-1 rounded-full animate-pulse" style={{ width: '60%' }} />
          </div>
        </div>
      )}
    </div>
  );
};

interface SearchDetailProps {
  results: SearchStageResult[];
  config: HybridSearchConfig;
  isOpen: boolean;
  onClose: () => void;
}

const SearchDetail: React.FC<SearchDetailProps> = ({ results, config, isOpen, onClose }) => {
  const totalLatency = results.reduce((sum, result) => sum + result.latency_ms, 0);
  const totalResults = results.reduce((sum, result) => sum + result.results.length, 0);
  const successfulStages = results.filter(result => !result.error).length;

  const getFusionStrategyDescription = (strategy: string) => {
    switch (strategy) {
      case 'rrf':
        return 'Reciprocal Rank Fusion - Combines rankings from multiple search methods';
      case 'weighted_average':
        return 'Weighted Average - Combines scores based on configured weights';
      case 'condorcet':
        return 'Condorcet Method - Uses pairwise comparison to determine ranking';
      case 'rank_biased':
        return 'Rank Biased Fusion - Probabilistic approach to result merging';
      default:
        return 'Unknown fusion strategy';
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Hybrid Search Details</DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Configuration */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Search Configuration</h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="p-3 bg-purple-50 rounded-lg">
                <h4 className="font-medium text-purple-900 mb-2">Vector Search</h4>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span>Weight:</span>
                    <span className="font-medium">{config.vector_search.weight}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Threshold:</span>
                    <span className="font-medium">{config.vector_search.similarity_threshold}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Max Results:</span>
                    <span className="font-medium">{config.vector_search.max_results}</span>
                  </div>
                </div>
              </div>

              <div className="p-3 bg-blue-50 rounded-lg">
                <h4 className="font-medium text-blue-900 mb-2">Graph Search</h4>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span>Weight:</span>
                    <span className="font-medium">{config.graph_search.weight}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Max Depth:</span>
                    <span className="font-medium">{config.graph_search.max_depth}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Relationships:</span>
                    <span className="font-medium">{config.graph_search.relationship_types.length}</span>
                  </div>
                </div>
              </div>

              <div className="p-3 bg-green-50 rounded-lg">
                <h4 className="font-medium text-green-900 mb-2">Keyword Search</h4>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span>Weight:</span>
                    <span className="font-medium">{config.keyword_search.weight}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Fuzzy:</span>
                    <span className="font-medium">{config.keyword_search.fuzzy_threshold}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Max Results:</span>
                    <span className="font-medium">{config.keyword_search.max_results}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Fusion Strategy */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Fusion Strategy</h3>
            <div className="p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-gray-900 capitalize">{config.fusion_strategy}</span>
                <Badge className="bg-blue-100 text-blue-800">
                  Max {config.max_total_results} results
                </Badge>
              </div>
              <p className="text-sm text-gray-600">{getFusionStrategyDescription(config.fusion_strategy)}</p>
            </div>
          </div>

          {/* Performance Summary */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Performance Summary</h3>
            <div className="grid grid-cols-4 gap-3">
              <div className="p-3 bg-gray-50 rounded-lg text-center">
                <div className="text-2xl font-bold text-gray-900">{totalLatency}ms</div>
                <div className="text-sm text-gray-600">Total Latency</div>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg text-center">
                <div className="text-2xl font-bold text-gray-900">{totalResults}</div>
                <div className="text-sm text-gray-600">Total Results</div>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg text-center">
                <div className="text-2xl font-bold text-gray-900">{successfulStages}/{results.length}</div>
                <div className="text-sm text-gray-600">Successful Stages</div>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg text-center">
                <div className="text-2xl font-bold text-gray-900">
                  {Math.round(totalLatency / results.length)}ms
                </div>
                <div className="text-sm text-gray-600">Avg Stage Latency</div>
              </div>
            </div>
          </div>

          {/* Stage Details */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Stage Details</h3>
            <div className="space-y-3">
              {results.map((result, index) => (
                <div key={index} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-3">
                      <h4 className="font-medium text-gray-900 capitalize">{result.stage} Search</h4>
                      {result.error && (
                        <Badge className="bg-red-100 text-red-800">Failed</Badge>
                      )}
                      {!result.error && (
                        <Badge className="bg-green-100 text-green-800">Success</Badge>
                      )}
                    </div>
                    <div className="text-sm text-gray-600">
                      {result.latency_ms}ms • {result.results.length} results
                    </div>
                  </div>

                  {result.error && (
                    <div className="p-3 bg-red-50 rounded-lg mb-3">
                      <div className="flex items-center space-x-2 text-red-800">
                        <ExclamationTriangleIcon className="h-4 w-4" />
                        <span className="text-sm font-medium">Error:</span>
                        <span className="text-sm">{result.error}</span>
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-gray-600">Confidence Score:</span>
                      <span className="ml-2 font-medium">
                        {result.confidence_score ? `${Math.round(result.confidence_score * 100)}%` : 'N/A'}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-600">Metadata:</span>
                      <span className="ml-2 font-medium">
                        {Object.keys(result.metadata).length} items
                      </span>
                    </div>
                  </div>

                  {Object.keys(result.metadata).length > 0 && (
                    <div className="mt-3">
                      <details className="text-sm">
                        <summary className="cursor-pointer text-gray-600 hover:text-gray-900">
                          View metadata
                        </summary>
                        <div className="mt-2 p-3 bg-gray-50 rounded text-xs font-mono">
                          {JSON.stringify(result.metadata, null, 2)}
                        </div>
                      </details>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export const HybridSearchOrchestrator: React.FC<HybridSearchOrchestratorProps> = ({
  query,
  config: userConfig,
  onSearchComplete,
  onStageUpdate,
  autoStart = false,
  showDetails = false,
  className,
}) => {
  const [searchResults, setSearchResults] = useState<SearchStageResult[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [showDetailDialog, setShowDetailDialog] = useState(false);
  const [config] = useState<HybridSearchConfig>({
    vector_search: {
      enabled: true,
      weight: 0.5,
      similarity_threshold: 0.7,
      max_results: 50,
    },
    graph_search: {
      enabled: true,
      weight: 0.3,
      max_depth: 3,
      relationship_types: ['related_to', 'mentions', 'part_of', 'contains'],
    },
    keyword_search: {
      enabled: true,
      weight: 0.2,
      fuzzy_threshold: 0.8,
      max_results: 100,
    },
    fusion_strategy: 'rrf',
    max_total_results: 20,
    ...userConfig,
  });

  const executeSearchStage = useCallback(async (
    stage: 'vector' | 'graph' | 'keyword',
    queryText: string
  ): Promise<SearchStageResult> => {
    // Simulate different latencies for different search types
    const baseLatency = {
      vector: 200 + Math.random() * 300,
      graph: 150 + Math.random() * 250,
      keyword: 50 + Math.random() * 150,
    };

    const latency = Math.round(baseLatency[stage]);

    // Simulate search execution
    await new Promise(resolve => setTimeout(resolve, latency));

    // Simulate potential failures (10% chance)
    if (Math.random() < 0.1) {
      return {
        stage,
        results: [],
        latency_ms: latency,
        confidence_score: 0,
        error: `Search service temporarily unavailable for ${stage} search`,
        metadata: { error_type: 'service_unavailable', retry_count: 0 }
      };
    }

    // Simulate search results based on stage
    const resultCounts = {
      vector: Math.floor(Math.random() * 30) + 10,
      graph: Math.floor(Math.random() * 20) + 5,
      keyword: Math.floor(Math.random() * 50) + 20,
    };

    const confidenceScores = {
      vector: 0.7 + Math.random() * 0.3,
      graph: 0.6 + Math.random() * 0.4,
      keyword: 0.5 + Math.random() * 0.5,
    };

    return {
      stage,
      results: Array.from({ length: resultCounts[stage] }, (_, i) => ({
        id: `${stage}_${i}`,
        title: `${stage} result ${i + 1}`,
        score: Math.random(),
      })),
      latency_ms: latency,
      confidence_score: confidenceScores[stage],
      metadata: {
        query_length: queryText.length,
        timestamp: new Date().toISOString(),
        search_type: stage,
        index_size: Math.floor(Math.random() * 100000) + 10000,
      }
    };
  }, []);

  const runHybridSearch = useCallback(async () => {
    if (!query?.trim()) return;

    setIsRunning(true);
    setSearchResults([]);
    const results: SearchStageResult[] = [];

    const stages: Array<'vector' | 'graph' | 'keyword'> = [];

    if (config.vector_search.enabled) stages.push('vector');
    if (config.graph_search.enabled) stages.push('graph');
    if (config.keyword_search.enabled) stages.push('keyword');

    for (const stage of stages) {
      setCurrentStage(stage);

      try {
        const result = await executeSearchStage(stage, query);
        results.push(result);
        setSearchResults(prev => [...prev, result]);
        onStageUpdate?.(stage, result);

        // Small delay between stages for better UX
        await new Promise(resolve => setTimeout(resolve, 100));
      } catch (error) {
        console.error(`${stage} search failed:`, error);
        const errorResult: SearchStageResult = {
          stage,
          results: [],
          latency_ms: 0,
          confidence_score: 0,
          error: error instanceof Error ? error.message : 'Unknown error',
          metadata: { error_type: 'exception' }
        };
        results.push(errorResult);
        setSearchResults(prev => [...prev, errorResult]);
      }
    }

    setCurrentStage(null);
    setIsRunning(false);
    onSearchComplete?.(results);
  }, [query, config, executeSearchStage, onStageUpdate, onSearchComplete]);

  useEffect(() => {
    if (autoStart && query?.trim()) {
      runHybridSearch();
    }
  }, [autoStart, query, runHybridSearch]);

  const handleRetryStage = useCallback(async (stage: string) => {
    setCurrentStage(stage);
    try {
      const result = await executeSearchStage(stage as 'vector' | 'graph' | 'keyword', query);
      setSearchResults(prev =>
        prev.map(r => r.stage === stage ? result : r)
      );
      onStageUpdate?.(stage, result);
    } catch (error) {
      console.error(`Retry ${stage} search failed:`, error);
    } finally {
      setCurrentStage(null);
    }
  }, [query, executeSearchStage, onStageUpdate]);

  const totalLatency = searchResults.reduce((sum, result) => sum + result.latency_ms, 0);
  const totalResults = searchResults.reduce((sum, result) => sum + result.results.length, 0);
  const successfulStages = searchResults.filter(result => !result.error).length;
  const hasErrors = searchResults.some(result => result.error);

  if (!query) {
    return null;
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Search Header */}
      <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
        <div className="flex items-center space-x-3">
          {isRunning ? (
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          ) : (
            <BoltIcon className="h-5 w-5 text-blue-600" />
          )}
          <div>
            <h3 className="font-medium text-gray-900">Hybrid Search</h3>
            <p className="text-sm text-gray-600">
              {config.vector_search.enabled && 'Vector'}{' '}
              {config.graph_search.enabled && '+ Graph'}{' '}
              {config.keyword_search.enabled && '+ Keyword'}{' '}
              ({config.fusion_strategy.toUpperCase()})
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {searchResults.length > 0 && (
            <div className="text-right">
              <div className="text-sm font-medium text-gray-900">
                {totalResults} results
              </div>
              <div className="text-xs text-gray-600">
                {totalLatency}ms total
              </div>
            </div>
          )}

          <div className="flex items-center space-x-2">
            {!isRunning && searchResults.length === 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={runHybridSearch}
                className="h-8"
              >
                <PlayIcon className="h-3 w-3 mr-1" />
                Start Search
              </Button>
            )}

            {!isRunning && searchResults.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={runHybridSearch}
                className="h-8"
              >
                <ArrowPathIcon className="h-3 w-3 mr-1" />
                Retry
              </Button>
            )}

            {showDetails && searchResults.length > 0 && (
              <IconButton
                icon={<InformationCircleIcon className="h-4 w-4" />}
                label="Show search details"
                onClick={() => setShowDetailDialog(true)}
                className="h-8 w-8"
              />
            )}
          </div>
        </div>
      </div>

      {/* Search Stages */}
      {searchResults.length > 0 && (
        <div className="space-y-3">
          {['vector', 'graph', 'keyword'].map((stage) => {
            const result = searchResults.find(r => r.stage === stage);
            const stageConfig = config[`${stage}_search` as keyof HybridSearchConfig];
            if (!result || (typeof stageConfig === 'object' && !stageConfig.enabled)) {
              return null;
            }

            return (
              <SearchStage
                key={stage}
                stage={result}
                isActive={currentStage === stage}
                isCompleted={result.latency_ms > 0}
                hasError={!!result.error}
                onRetry={() => handleRetryStage(stage)}
              />
            );
          })}
        </div>
      )}

      {/* Status Indicator */}
      {isRunning && (
        <div className="flex items-center space-x-2 p-3 bg-blue-50 rounded-lg">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          <span className="text-sm text-blue-800">
            {currentStage ? `Executing ${currentStage} search...` : 'Initializing hybrid search...'}
          </span>
        </div>
      )}

      {/* Error Indicator */}
      {hasErrors && !isRunning && (
        <div className="flex items-center space-x-2 p-3 bg-yellow-50 rounded-lg">
          <ExclamationTriangleIcon className="h-4 w-4 text-yellow-600" />
          <span className="text-sm text-yellow-800">
            {successfulStages}/{searchResults.length} search stages completed successfully
          </span>
        </div>
      )}

      {/* Success Indicator */}
      {!isRunning && searchResults.length > 0 && !hasErrors && (
        <div className="flex items-center space-x-2 p-3 bg-green-50 rounded-lg">
          <CheckCircleIcon className="h-4 w-4 text-green-600" />
          <span className="text-sm text-green-800">
            All {searchResults.length} search stages completed successfully
          </span>
        </div>
      )}

      {/* Detail Dialog */}
      {searchResults.length > 0 && (
        <SearchDetail
          results={searchResults}
          config={config}
          isOpen={showDetailDialog}
          onClose={() => setShowDetailDialog(false)}
        />
      )}
    </div>
  );
};

export default HybridSearchOrchestrator;