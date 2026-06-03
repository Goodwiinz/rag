import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  PlayIcon,
  PauseIcon,
  StopIcon,
  ArrowPathIcon,
  InformationCircleIcon,
  ChartBarIcon,
  SparklesIcon,
  BoltIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';
import {
  QueryProcessingState,
  QueryIntent,
  QueryRewrite,
  SearchStageResult,
  ResultAggregation,
  QueryPerformanceMetrics,
  EnhancedSearchRequest,
  QueryProcessingUpdate,
} from '@/types/search';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { QueryIntentDetector } from './QueryIntentDetector';
import { QueryRewriter } from './QueryRewriter';
import { HybridSearchOrchestrator } from './HybridSearchOrchestrator';
import { ResultAggregator } from './ResultAggregator';
import { QueryPerformanceMonitor } from './QueryPerformanceMonitor';

interface QueryProcessorProps {
  query: string;
  config?: EnhancedSearchRequest['processing_config'];
  onProcessingComplete?: (state: QueryProcessingState) => void;
  onProcessingUpdate?: (state: QueryProcessingState) => void;
  autoStart?: boolean;
  showStages?: boolean;
  showPerformance?: boolean;
  className?: string;
}

interface ProcessingStageProps {
  stage: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  progress: number;
  duration?: number;
  error?: string;
  icon?: React.ReactNode;
}

const ProcessingStage: React.FC<ProcessingStageProps> = ({
  stage,
  status,
  progress,
  duration,
  error,
  icon,
}) => {
  const getStatusColor = () => {
    switch (status) {
      case 'in_progress':
        return 'text-blue-600 border-blue-200 bg-blue-50';
      case 'completed':
        return 'text-green-600 border-green-200 bg-green-50';
      case 'failed':
        return 'text-red-600 border-red-200 bg-red-50';
      default:
        return 'text-muted-foreground border-border bg-gray-50';
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'in_progress':
        return (
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
        );
      case 'completed':
        return <CheckCircleIcon className="h-4 w-4 text-green-600" />;
      case 'failed':
        return <XCircleIcon className="h-4 w-4 text-red-600" />;
      default:
        return <ClockIcon className="h-4 w-4 text-muted-foreground" />;
    }
  };

  return (
    <div
      className={cn(
        'border rounded-lg p-3 transition-colors',
        getStatusColor()
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-2">
          {icon || getStatusIcon()}
          <span className="text-sm font-medium capitalize">
            {stage.replace('_', ' ')}
          </span>
        </div>
        <div className="flex items-center space-x-2">
          {duration && (
            <span className="text-xs text-foreground">{duration}ms</span>
          )}
          {error && (
            <Badge className="bg-red-100 text-red-800 text-xs">Error</Badge>
          )}
        </div>
      </div>

      {status === 'in_progress' && (
        <Progress value={progress} className="h-1" />
      )}

      {error && <p className="text-xs text-red-700 mt-1">{error}</p>}
    </div>
  );
};

export const QueryProcessor: React.FC<QueryProcessorProps> = ({
  query,
  config,
  onProcessingComplete,
  onProcessingUpdate,
  autoStart = false,
  showStages = true,
  showPerformance = true,
  className,
}) => {
  const [processingState, setProcessingState] = useState<QueryProcessingState>({
    current_stage: 'intent_detection',
    progress: 0,
    search_results: [],
    start_time: new Date().toISOString(),
  });

  const [isRunning, setIsRunning] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [currentConfig, setCurrentConfig] = useState(config);

  const stageTimeouts = useRef<NodeJS.Timeout[]>([]);
  const startTimeRef = useRef<number>(0);

  const defaultConfig: EnhancedSearchRequest['processing_config'] = {
    enable_intent_detection: true,
    enable_query_rewriting: true,
    enable_hybrid_search: true,
    hybrid_config: {
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
        relationship_types: ['related_to', 'mentions'],
      },
      keyword_search: {
        enabled: true,
        weight: 0.2,
        fuzzy_threshold: 0.8,
        max_results: 100,
      },
      fusion_strategy: 'rrf',
      max_total_results: 20,
    },
    performance_monitoring: true,
  };

  useEffect(() => {
    setCurrentConfig({ ...defaultConfig, ...config });
  }, [config]);

  const updateState = useCallback(
    (updates: Partial<QueryProcessingState>) => {
      setProcessingState((prev) => {
        const newState = { ...prev, ...updates };
        onProcessingUpdate?.(newState);
        return newState;
      });
    },
    [onProcessingUpdate]
  );

  const simulateStage = useCallback(
    async (
      stage: string,
      duration: number,
      onSuccess: () => void,
      onError?: (error: string) => void
    ): Promise<void> => {
      const stageStartTime = Date.now();

      updateState({
        current_stage: stage as QueryProcessingState['current_stage'],
        progress: 0,
      });

      // Simulate progress updates
      const progressInterval = setInterval(() => {
        const elapsed = Date.now() - stageStartTime;
        const progress = Math.min((elapsed / duration) * 100, 95);
        updateState({ progress });
      }, duration / 20);

      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          clearInterval(progressInterval);

          // Random chance of failure (5%)
          if (Math.random() < 0.05 && onError) {
            const error = `${stage} failed due to temporary service unavailability`;
            updateState({ progress: 100, error });
            onError(error);
            reject(new Error(error));
          } else {
            const actualDuration = Date.now() - stageStartTime;
            onSuccess();
            resolve();
          }
        }, duration);

        stageTimeouts.current.push(timeout);
      });
    },
    [updateState]
  );

  const runIntentDetection = useCallback(async (): Promise<QueryIntent> => {
    return new Promise((resolve, reject) => {
      simulateStage(
        'intent_detection',
        500 + Math.random() * 500,
        () => {
          const mockIntent: QueryIntent = {
            primary_intent: 'factual_lookup',
            confidence: 0.85,
            entities: [
              { name: 'Query Processing', type: 'concept', confidence: 0.9 },
              { name: 'RAG System', type: 'concept', confidence: 0.8 },
            ],
            keywords: [
              { term: 'query', importance: 0.9 },
              { term: 'processing', importance: 0.8 },
              { term: 'system', importance: 0.7 },
            ],
            complexity: 'moderate',
            modality_preference: ['text'],
            temporal_aspect: 'timeless',
            domain_specificity: 'technical',
            question_type: 'what',
          };
          updateState({ intent: mockIntent });
          resolve(mockIntent);
        },
        reject
      );
    });
  }, [simulateStage, updateState]);

  const runQueryRewriting = useCallback(
    async (intent: QueryIntent): Promise<QueryRewrite> => {
      return new Promise((resolve, reject) => {
        simulateStage(
          'query_rewriting',
          300 + Math.random() * 400,
          () => {
            const mockRewrite: QueryRewrite = {
              original_query: query,
              rewritten_queries: [
                {
                  query: `${query} optimized processing`,
                  strategy: 'expansion',
                  confidence: 0.8,
                  reasoning: 'Added context terms for better semantic matching',
                },
              ],
              expanded_terms: ['optimized', 'processing'],
              removed_terms: [],
              suggested_filters: [],
            };
            updateState({ rewrite: mockRewrite });
            resolve(mockRewrite);
          },
          reject
        );
      });
    },
    [query, simulateStage, updateState]
  );

  const runHybridSearch = useCallback(async (): Promise<
    SearchStageResult[]
  > => {
    return new Promise((resolve, reject) => {
      simulateStage(
        'search_execution',
        800 + Math.random() * 1200,
        () => {
          const mockSearchResults: SearchStageResult[] = [
            {
              stage: 'vector',
              results: Array.from({ length: 15 }, (_, i) => ({
                id: `vector_${i}`,
                title: `Vector result ${i + 1}`,
                score: 0.8 + Math.random() * 0.2,
              })),
              latency_ms: 200 + Math.random() * 300,
              confidence_score: 0.8 + Math.random() * 0.2,
              metadata: {
                query_length: query.length,
                timestamp: new Date().toISOString(),
              },
            },
            {
              stage: 'graph',
              results: Array.from({ length: 8 }, (_, i) => ({
                id: `graph_${i}`,
                title: `Graph result ${i + 1}`,
                score: 0.7 + Math.random() * 0.3,
              })),
              latency_ms: 150 + Math.random() * 250,
              confidence_score: 0.7 + Math.random() * 0.3,
              metadata: {
                query_length: query.length,
                timestamp: new Date().toISOString(),
              },
            },
            {
              stage: 'keyword',
              results: Array.from({ length: 25 }, (_, i) => ({
                id: `keyword_${i}`,
                title: `Keyword result ${i + 1}`,
                score: 0.6 + Math.random() * 0.4,
              })),
              latency_ms: 50 + Math.random() * 150,
              confidence_score: 0.6 + Math.random() * 0.4,
              metadata: {
                query_length: query.length,
                timestamp: new Date().toISOString(),
              },
            },
          ];
          updateState({ search_results: mockSearchResults });
          resolve(mockSearchResults);
        },
        reject
      );
    });
  }, [query, simulateStage, updateState]);

  const runResultAggregation = useCallback(
    async (searchResults: SearchStageResult[]): Promise<ResultAggregation> => {
      return new Promise((resolve, reject) => {
        simulateStage(
          'result_aggregation',
          400 + Math.random() * 300,
          () => {
            const mockAggregation: ResultAggregation = {
              final_results: Array.from({ length: 20 }, (_, i) => ({
                id: `final_${i}`,
                title: `Aggregated result ${i + 1}`,
                score: 0.9 - i * 0.03,
              })),
              source_breakdown: {
                vector: 8,
                graph: 4,
                keyword: 8,
                fused: 20,
              },
              deduplication_stats: {
                initial_count: 48,
                final_count: 20,
                duplicates_removed: 28,
              },
              aggregation_confidence: 0.85,
              diversity_score: 0.75,
              coverage_score: 0.8,
              fusion_method: 'rrf',
            };
            updateState({ aggregation: mockAggregation });
            resolve(mockAggregation);
          },
          reject
        );
      });
    },
    [simulateStage, updateState]
  );

  const runPerformanceMonitoring = useCallback((): QueryPerformanceMetrics => {
    const totalLatency = Date.now() - startTimeRef.current;

    const mockMetrics: QueryPerformanceMetrics = {
      total_latency_ms: totalLatency,
      stage_latencies: {
        intent_detection: processingState.intent ? 500 : 0,
        query_rewriting: processingState.rewrite ? 400 : 0,
        vector_search: 250,
        graph_search: 200,
        keyword_search: 100,
        result_aggregation: processingState.aggregation ? 500 : 0,
      },
      resource_usage: {
        memory_mb: 150 + Math.random() * 200,
        cpu_percent: 30 + Math.random() * 40,
        network_requests: 8 + Math.round(Math.random() * 10),
      },
      quality_metrics: {
        rag_triad_compliance: {
          answer_relevancy: 75 + Math.random() * 25,
          faithfulness: 85 + Math.random() * 15,
          contextual_relevancy: 80 + Math.random() * 20,
        },
        hallucination_risk: 5 + Math.random() * 10,
        confidence_score: 70 + Math.random() * 30,
      },
      cache_performance: {
        cache_hit_rate: 0.3 + Math.random() * 0.6,
        cache_hits: Math.round(Math.random() * 8),
        cache_misses: Math.round(Math.random() * 5),
      },
      bottlenecks: [],
    };

    updateState({ performance: mockMetrics });
    return mockMetrics;
  }, [processingState, updateState]);

  const startProcessing = useCallback(async () => {
    if (!query?.trim()) return;

    setIsRunning(true);
    setIsPaused(false);
    startTimeRef.current = Date.now();

    // Clear any existing timeouts
    stageTimeouts.current.forEach(clearTimeout);
    stageTimeouts.current = [];

    try {
      let intent: QueryIntent | undefined;
      let rewrite: QueryRewrite | undefined;

      // Stage 1: Intent Detection
      if (currentConfig?.enable_intent_detection) {
        intent = await runIntentDetection();
      }

      // Stage 2: Query Rewriting
      if (currentConfig?.enable_query_rewriting && intent) {
        rewrite = await runQueryRewriting(intent);
      }

      // Stage 3: Hybrid Search
      let searchResults: SearchStageResult[] = [];
      if (currentConfig?.enable_hybrid_search) {
        searchResults = await runHybridSearch();
      }

      // Stage 4: Result Aggregation
      if (searchResults.length > 0) {
        await runResultAggregation(searchResults);
      }

      // Stage 5: Performance Monitoring
      if (currentConfig?.performance_monitoring) {
        runPerformanceMonitoring();
      }

      // Complete processing
      const finalState: QueryProcessingState = {
        ...processingState,
        current_stage: 'completed',
        progress: 100,
        intent,
        rewrite,
        search_results: searchResults,
        aggregation: processingState.aggregation,
        performance: processingState.performance,
        start_time: processingState.start_time,
        estimated_completion: new Date().toISOString(),
      };

      setProcessingState(finalState);
      onProcessingComplete?.(finalState);
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';
      updateState({
        current_stage: 'failed',
        progress: 100,
        error: errorMessage,
      });
    } finally {
      setIsRunning(false);
    }
  }, [
    query,
    currentConfig,
    processingState,
    runIntentDetection,
    runQueryRewriting,
    runHybridSearch,
    runResultAggregation,
    runPerformanceMonitoring,
    updateState,
    onProcessingComplete,
  ]);

  const pauseProcessing = useCallback(() => {
    setIsPaused(true);
    stageTimeouts.current.forEach(clearTimeout);
    stageTimeouts.current = [];
  }, []);

  const resumeProcessing = useCallback(() => {
    setIsPaused(false);
    // Resume from current stage
    startProcessing();
  }, [startProcessing]);

  const stopProcessing = useCallback(() => {
    setIsRunning(false);
    setIsPaused(false);
    stageTimeouts.current.forEach(clearTimeout);
    stageTimeouts.current = [];

    updateState({
      current_stage: 'failed',
      progress: 0,
      error: 'Processing stopped by user',
    });
  }, [updateState]);

  const resetProcessing = useCallback(() => {
    setIsRunning(false);
    setIsPaused(false);
    stageTimeouts.current.forEach(clearTimeout);
    stageTimeouts.current = [];

    setProcessingState({
      current_stage: 'intent_detection',
      progress: 0,
      search_results: [],
      start_time: new Date().toISOString(),
    });
  }, []);

  useEffect(() => {
    if (autoStart && query?.trim()) {
      startProcessing();
    }
  }, [autoStart, query, startProcessing]);

  const getStageStatus = (
    stage: string
  ): 'pending' | 'in_progress' | 'completed' | 'failed' => {
    if (processingState.error && processingState.current_stage === stage)
      return 'failed';
    if (processingState.current_stage === stage) return 'in_progress';

    const stageOrder = [
      'intent_detection',
      'query_rewriting',
      'search_execution',
      'result_aggregation',
      'completed',
    ];
    const currentIndex = stageOrder.indexOf(processingState.current_stage);
    const stageIndex = stageOrder.indexOf(stage);

    return stageIndex < currentIndex ? 'completed' : 'pending';
  };

  const getProcessingIcon = () => {
    if (isPaused) return <PauseIcon className="h-5 w-5 text-yellow-600" />;
    if (isRunning)
      return (
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
      );
    if (processingState.current_stage === 'completed')
      return <CheckCircleIcon className="h-5 w-5 text-green-600" />;
    if (processingState.current_stage === 'failed')
      return <XCircleIcon className="h-5 w-5 text-red-600" />;
    return <BoltIcon className="h-5 w-5 text-blue-600" />;
  };

  if (!query) {
    return null;
  }

  return (
    <div className={cn('space-y-6', className)}>
      {/* Processing Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              {getProcessingIcon()}
              <div>
                <CardTitle className="text-lg">
                  Query Processing Pipeline
                </CardTitle>
                <p className="text-sm text-foreground">
                  {isRunning &&
                    !isPaused &&
                    `Executing ${processingState.current_stage.replace('_', ' ')}...`}
                  {isPaused && 'Processing paused'}
                  {processingState.current_stage === 'completed' &&
                    'Processing completed successfully'}
                  {processingState.current_stage === 'failed' &&
                    'Processing failed'}
                  {!isRunning &&
                    processingState.current_stage === 'intent_detection' &&
                    'Ready to start processing'}
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              {/* Control Buttons */}
              {!isRunning &&
                processingState.current_stage !== 'completed' &&
                processingState.current_stage !== 'failed' && (
                  <Button onClick={startProcessing} size="sm">
                    <PlayIcon className="h-3 w-3 mr-1" />
                    Start
                  </Button>
                )}

              {isRunning && !isPaused && (
                <Button onClick={pauseProcessing} variant="outline" size="sm">
                  <PauseIcon className="h-3 w-3 mr-1" />
                  Pause
                </Button>
              )}

              {isPaused && (
                <Button onClick={resumeProcessing} size="sm">
                  <PlayIcon className="h-3 w-3 mr-1" />
                  Resume
                </Button>
              )}

              {isRunning && (
                <Button onClick={stopProcessing} variant="outline" size="sm">
                  <StopIcon className="h-3 w-3 mr-1" />
                  Stop
                </Button>
              )}

              {(processingState.current_stage === 'completed' ||
                processingState.current_stage === 'failed') && (
                <Button onClick={resetProcessing} variant="outline" size="sm">
                  <ArrowPathIcon className="h-3 w-3 mr-1" />
                  Reset
                </Button>
              )}
            </div>
          </div>
        </CardHeader>

        {/* Progress Bar */}
        <CardContent>
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Progress</span>
              <span>{Math.round(processingState.progress)}%</span>
            </div>
            <Progress value={processingState.progress} className="h-2" />
          </div>

          {processingState.error && (
            <div className="mt-4 p-3 bg-red-50 rounded-lg">
              <p className="text-sm text-red-800">{processingState.error}</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Processing Stages */}
      {showStages && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-foreground">
            Processing Stages
          </h3>

          {currentConfig?.enable_intent_detection && (
            <ProcessingStage
              stage="intent_detection"
              status={getStageStatus('intent_detection')}
              progress={
                processingState.current_stage === 'intent_detection'
                  ? processingState.progress
                  : 100
              }
              icon={<SparklesIcon className="h-4 w-4" />}
            />
          )}

          {currentConfig?.enable_query_rewriting && (
            <ProcessingStage
              stage="query_rewriting"
              status={getStageStatus('query_rewriting')}
              progress={
                processingState.current_stage === 'query_rewriting'
                  ? processingState.progress
                  : 100
              }
              icon={<ArrowPathIcon className="h-4 w-4" />}
            />
          )}

          {currentConfig?.enable_hybrid_search && (
            <ProcessingStage
              stage="search_execution"
              status={getStageStatus('search_execution')}
              progress={
                processingState.current_stage === 'search_execution'
                  ? processingState.progress
                  : 100
              }
              icon={<BoltIcon className="h-4 w-4" />}
            />
          )}

          <ProcessingStage
            stage="result_aggregation"
            status={getStageStatus('result_aggregation')}
            progress={
              processingState.current_stage === 'result_aggregation'
                ? processingState.progress
                : 100
            }
            icon={<ChartBarIcon className="h-4 w-4" />}
          />
        </div>
      )}

      {/* Component Details */}
      {(processingState.intent ||
        processingState.rewrite ||
        processingState.search_results.length > 0) && (
        <div className="space-y-6">
          {processingState.intent && (
            <div>
              <h3 className="text-lg font-semibold text-foreground mb-3">
                Intent Detection
              </h3>
              <QueryIntentDetector
                query={query}
                onIntentDetected={() => {}}
                showDetails={false}
              />
            </div>
          )}

          {processingState.rewrite && (
            <div>
              <h3 className="text-lg font-semibold text-foreground mb-3">
                Query Rewriting
              </h3>
              <QueryRewriter
                query={query}
                intent={processingState.intent}
                showDetails={false}
                autoApply={false}
              />
            </div>
          )}

          {processingState.search_results.length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-foreground mb-3">
                Hybrid Search
              </h3>
              <HybridSearchOrchestrator
                query={query}
                config={currentConfig?.hybrid_config}
                showDetails={false}
                autoStart={false}
              />
            </div>
          )}

          {processingState.aggregation && (
            <div>
              <h3 className="text-lg font-semibold text-foreground mb-3">
                Result Aggregation
              </h3>
              <ResultAggregator
                searchResults={processingState.search_results}
                fusionStrategy={currentConfig?.hybrid_config?.fusion_strategy}
                showDetails={false}
                autoAggregate={false}
              />
            </div>
          )}
        </div>
      )}

      {/* Performance Monitoring */}
      {showPerformance && (isRunning || processingState.performance) && (
        <div>
          <h3 className="text-lg font-semibold text-foreground mb-3">
            Performance Monitoring
          </h3>
          <QueryPerformanceMonitor
            processingState={processingState}
            showRealTime={isRunning}
            showDetails={true}
          />
        </div>
      )}
    </div>
  );
};

export default QueryProcessor;
