import React, { useState, useCallback, useEffect } from 'react';
import {
  ArrowsRightLeftIcon,
  DocumentDuplicateIcon,
  ChartBarIcon,
  CheckCircleIcon,
  XCircleIcon,
  InformationCircleIcon,
  SparklesIcon,
  FunnelIcon,
  EyeIcon,
  ArrowDownTrayIcon,
  StarIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import { ResultAggregation, SearchStageResult } from '@/types/search';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';

interface ResultAggregatorProps {
  searchResults: SearchStageResult[];
  fusionStrategy?: 'rrf' | 'weighted_average' | 'condorcet' | 'rank_biased';
  maxResults?: number;
  onAggregationComplete?: (aggregation: ResultAggregation) => void;
  showDetails?: boolean;
  autoAggregate?: boolean;
  className?: string;
}

interface AggregationDetailProps {
  aggregation: ResultAggregation;
  searchResults: SearchStageResult[];
  isOpen: boolean;
  onClose: () => void;
}

interface DuplicateGroupProps {
  group: any[];
  onKeep: (item: any) => void;
  onRemove: (item: any) => void;
}

const DuplicateGroup: React.FC<DuplicateGroupProps> = ({ group, onKeep, onRemove }) => {
  const [selectedItem, setSelectedItem] = useState(group[0]);

  return (
    <div className="border border-orange-200 rounded-lg p-4 bg-orange-50">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <DocumentDuplicateIcon className="h-4 w-4 text-orange-600" />
          <span className="text-sm font-medium text-orange-900">
            Duplicate Group ({group.length} items)
          </span>
          <Badge className="bg-orange-100 text-orange-800">
            {Math.round(group[0].similarity * 100)}% similar
          </Badge>
        </div>
      </div>

      <div className="space-y-2">
        {group.map((item, index) => (
          <div
            key={index}
            className={cn(
              "p-3 rounded-lg border cursor-pointer transition-colors",
              selectedItem === item
                ? "border-blue-300 bg-blue-50"
                : "border-gray-200 bg-white hover:bg-gray-50"
            )}
            onClick={() => setSelectedItem(item)}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h4 className="font-medium text-gray-900">{item.title}</h4>
                <div className="flex items-center space-x-2 mt-1">
                  <Badge variant="outline" className="text-xs">
                    {item.source}
                  </Badge>
                  <span className="text-xs text-gray-500">
                    Score: {Math.round(item.score * 100)}%
                  </span>
                </div>
              </div>
              <div className="flex items-center space-x-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onKeep(item);
                  }}
                  className="h-6 w-6 p-0"
                  disabled={selectedItem === item}
                >
                  <CheckCircleIcon className="h-3 w-3 text-green-600" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemove(item);
                  }}
                  className="h-6 w-6 p-0"
                >
                  <XCircleIcon className="h-3 w-3 text-red-600" />
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const AggregationDetail: React.FC<AggregationDetailProps> = ({
  aggregation,
  searchResults,
  isOpen,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'duplicates' | 'sources' | 'metrics'>('overview');

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-600';
    if (score >= 80) return 'text-yellow-600';
    if (score >= 70) return 'text-orange-600';
    return 'text-red-600';
  };

  const getScoreBackground = (score: number) => {
    if (score >= 90) return 'bg-green-100 text-green-800';
    if (score >= 80) return 'bg-yellow-100 text-yellow-800';
    if (score >= 70) return 'bg-orange-100 text-orange-800';
    return 'bg-red-100 text-red-800';
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Result Aggregation Analysis</DialogTitle>
        </DialogHeader>

        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="flex space-x-8" role="tablist">
            {['overview', 'duplicates', 'sources', 'metrics'].map((tab) => (
              <button
                key={tab}
                role="tab"
                aria-selected={activeTab === tab}
                onClick={() => setActiveTab(tab as any)}
                className={cn(
                  "py-2 px-1 border-b-2 font-medium text-sm capitalize focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
                  activeTab === tab
                    ? "border-blue-500 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                )}
              >
                {tab}
              </button>
            ))}
          </nav>
        </div>

        <div className="mt-6">
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Summary Stats */}
              <div className="grid grid-cols-4 gap-4">
                <div className="p-4 bg-blue-50 rounded-lg">
                  <div className="text-2xl font-bold text-blue-900">
                    {aggregation.final_results.length}
                  </div>
                  <div className="text-sm text-blue-700">Final Results</div>
                </div>
                <div className="p-4 bg-green-50 rounded-lg">
                  <div className="text-2xl font-bold text-green-900">
                    {aggregation.deduplication_stats.duplicates_removed}
                  </div>
                  <div className="text-sm text-green-700">Duplicates Removed</div>
                </div>
                <div className="p-4 bg-purple-50 rounded-lg">
                  <div className="text-2xl font-bold text-purple-900">
                    {Math.round(aggregation.diversity_score * 100)}%
                  </div>
                  <div className="text-sm text-purple-700">Diversity Score</div>
                </div>
                <div className="p-4 bg-orange-50 rounded-lg">
                  <div className="text-2xl font-bold text-orange-900">
                    {Math.round(aggregation.coverage_score * 100)}%
                  </div>
                  <div className="text-sm text-orange-700">Coverage Score</div>
                </div>
              </div>

              {/* Source Breakdown */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Source Contribution</h3>
                <div className="grid grid-cols-4 gap-4">
                  {Object.entries(aggregation.source_breakdown).map(([source, count]) => (
                    <div key={source} className="p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-gray-900 capitalize">{source}</span>
                        <span className="text-lg font-bold text-gray-900">{count}</span>
                      </div>
                      <div className="mt-2 w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full"
                          style={{
                            width: `${(count / aggregation.final_results.length) * 100}%`
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Top Results */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Top Results</h3>
                <div className="space-y-2">
                  {aggregation.final_results.slice(0, 5).map((result, index) => (
                    <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center space-x-3">
                        <span className="font-medium text-gray-900">#{index + 1}</span>
                        <span className="text-gray-800">{result.title}</span>
                      </div>
                      <Badge className={getScoreBackground(result.score * 100)}>
                        {Math.round(result.score * 100)}%
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Duplicates Tab */}
          {activeTab === 'duplicates' && (
            <div className="space-y-4">
              <div className="p-4 bg-yellow-50 rounded-lg">
                <div className="flex items-center space-x-2">
                  <DocumentDuplicateIcon className="h-5 w-5 text-yellow-600" />
                  <div>
                    <h3 className="font-medium text-yellow-900">Deduplication Summary</h3>
                    <p className="text-sm text-yellow-800">
                      {aggregation.deduplication_stats.initial_count} → {aggregation.deduplication_stats.final_count} results
                      ({aggregation.deduplication_stats.duplicates_removed} duplicates removed)
                    </p>
                  </div>
                </div>
              </div>

              {/* Simulate duplicate groups for demonstration */}
              <div className="space-y-3">
                <div className="p-4 border border-gray-200 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-900">Similarity Threshold: 85%</span>
                    <Badge className="bg-green-100 text-green-800">Active</Badge>
                  </div>
                  <p className="text-sm text-gray-600">
                    Items with similarity above 85% are flagged as potential duplicates
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Sources Tab */}
          {activeTab === 'sources' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900">Search Stage Details</h3>
              <div className="space-y-3">
                {searchResults.map((result, index) => (
                  <div key={index} className="p-4 border border-gray-200 rounded-lg">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center space-x-3">
                        <h4 className="font-medium text-gray-900 capitalize">{result.stage} Search</h4>
                        {result.error ? (
                          <Badge className="bg-red-100 text-red-800">Failed</Badge>
                        ) : (
                          <Badge className="bg-green-100 text-green-800">Success</Badge>
                        )}
                      </div>
                      <div className="text-sm text-gray-600">
                        {result.results.length} results • {result.latency_ms}ms
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-gray-600">Contribution:</span>
                        <span className="ml-2 font-medium">
                          {aggregation.source_breakdown[result.stage as keyof typeof aggregation.source_breakdown]} items
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-600">Confidence:</span>
                        <span className={cn("ml-2 font-medium", getScoreColor(result.confidence_score * 100))}>
                          {result.confidence_score ? `${Math.round(result.confidence_score * 100)}%` : 'N/A'}
                        </span>
                      </div>
                    </div>

                    {result.error && (
                      <div className="mt-3 p-3 bg-red-50 rounded-lg">
                        <p className="text-sm text-red-800">{result.error}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Metrics Tab */}
          {activeTab === 'metrics' && (
            <div className="space-y-6">
              {/* Quality Metrics */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Quality Metrics</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-gray-700">Aggregation Confidence</span>
                      <span className={cn("font-bold", getScoreColor(aggregation.aggregation_confidence * 100))}>
                        {Math.round(aggregation.aggregation_confidence * 100)}%
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={cn("h-2 rounded-full",
                          aggregation.aggregation_confidence >= 0.9 ? "bg-green-600" :
                          aggregation.aggregation_confidence >= 0.8 ? "bg-yellow-600" : "bg-red-600"
                        )}
                        style={{ width: `${aggregation.aggregation_confidence * 100}%` }}
                      />
                    </div>
                  </div>

                  <div className="p-4 bg-gray-50 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-gray-700">Diversity Score</span>
                      <span className={cn("font-bold", getScoreColor(aggregation.diversity_score * 100))}>
                        {Math.round(aggregation.diversity_score * 100)}%
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={cn("h-2 rounded-full",
                          aggregation.diversity_score >= 0.9 ? "bg-green-600" :
                          aggregation.diversity_score >= 0.8 ? "bg-yellow-600" : "bg-red-600"
                        )}
                        style={{ width: `${aggregation.diversity_score * 100}%` }}
                      />
                    </div>
                  </div>

                  <div className="p-4 bg-gray-50 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-gray-700">Coverage Score</span>
                      <span className={cn("font-bold", getScoreColor(aggregation.coverage_score * 100))}>
                        {Math.round(aggregation.coverage_score * 100)}%
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={cn("h-2 rounded-full",
                          aggregation.coverage_score >= 0.9 ? "bg-green-600" :
                          aggregation.coverage_score >= 0.8 ? "bg-yellow-600" : "bg-red-600"
                        )}
                        style={{ width: `${aggregation.coverage_score * 100}%` }}
                      />
                    </div>
                  </div>

                  <div className="p-4 bg-gray-50 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-gray-700">Fusion Method</span>
                      <span className="font-bold text-gray-900 capitalize">
                        {aggregation.fusion_method}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600">
                      {aggregation.fusion_method === 'rrf' && 'Reciprocal Rank Fusion'}
                      {aggregation.fusion_method === 'weighted_average' && 'Weighted Average'}
                      {aggregation.fusion_method === 'condorcet' && 'Condorcet Method'}
                      {aggregation.fusion_method === 'rank_biased' && 'Rank Biased Fusion'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export const ResultAggregator: React.FC<ResultAggregatorProps> = ({
  searchResults,
  fusionStrategy = 'rrf',
  maxResults = 20,
  onAggregationComplete,
  showDetails = false,
  autoAggregate = false,
  className,
}) => {
  const [aggregation, setAggregation] = useState<ResultAggregation | null>(null);
  const [isAggregating, setIsAggregating] = useState(false);
  const [showDetailDialog, setShowDetailDialog] = useState(false);

  const calculateSimilarity = useCallback((item1: any, item2: any): number => {
    // Simple similarity calculation based on title and content
    const title1 = (item1.title || '').toLowerCase();
    const title2 = (item2.title || '').toLowerCase();

    // Calculate Jaccard similarity
    const words1 = new Set(title1.split(/\s+/));
    const words2 = new Set(title2.split(/\s+/));

    const intersection = new Set([...words1].filter(x => words2.has(x)));
    const union = new Set([...words1, ...words2]);

    return intersection.size / union.size;
  }, []);

  const rrfFusion = useCallback((rankings: any[][], k: number = 60): any[] => {
    const scoreMap = new Map<string, { score: number; item: any; sources: string[] }>();

    rankings.forEach((ranking, sourceIndex) => {
      ranking.forEach((item, rank) => {
        const key = item.title || item.id;
        const existing = scoreMap.get(key);

        if (existing) {
          existing.score += 1 / (k + rank + 1);
          existing.sources.push(`source_${sourceIndex}`);
        } else {
          scoreMap.set(key, {
            score: 1 / (k + rank + 1),
            item: { ...item, score: 1 / (k + rank + 1) },
            sources: [`source_${sourceIndex}`]
          });
        }
      });
    });

    return Array.from(scoreMap.values())
      .sort((a, b) => b.score - a.score)
      .map(v => v.item);
  }, []);

  const weightedAverageFusion = useCallback((rankings: any[][], weights: number[]): any[] => {
    const scoreMap = new Map<string, { score: number; item: any; sources: string[] }>();

    rankings.forEach((ranking, sourceIndex) => {
      const weight = weights[sourceIndex] || 1;

      ranking.forEach((item) => {
        const key = item.title || item.id;
        const normalizedScore = item.score || 1;
        const weightedScore = normalizedScore * weight;

        const existing = scoreMap.get(key);

        if (existing) {
          existing.score += weightedScore;
          existing.sources.push(`source_${sourceIndex}`);
        } else {
          scoreMap.set(key, {
            score: weightedScore,
            item: { ...item, score: weightedScore },
            sources: [`source_${sourceIndex}`]
          });
        }
      });
    });

    return Array.from(scoreMap.values())
      .sort((a, b) => b.score - a.score)
      .map(v => v.item);
  }, []);

  const deduplicateResults = useCallback((results: any[]): { deduplicated: any[]; duplicatesRemoved: number } => {
    if (results.length === 0) return { deduplicated: [], duplicatesRemoved: 0 };

    const groups: any[][] = [];
    const used = new Set<number>();

    for (let i = 0; i < results.length; i++) {
      if (used.has(i)) continue;

      const group = [results[i]];
      used.add(i);

      for (let j = i + 1; j < results.length; j++) {
        if (used.has(j)) continue;

        const similarity = calculateSimilarity(results[i], results[j]);
        if (similarity > 0.85) { // 85% similarity threshold
          group.push(results[j]);
          used.add(j);
        }
      }

      groups.push(group);
    }

    const deduplicated = groups.map(group => group[0]); // Keep first item from each group
    const duplicatesRemoved = results.length - deduplicated.length;

    return { deduplicated, duplicatesRemoved };
  }, [calculateSimilarity]);

  const calculateDiversityScore = useCallback((results: any[]): number => {
    if (results.length === 0) return 0;
    if (results.length === 1) return 1;

    let totalSimilarity = 0;
    let comparisons = 0;

    for (let i = 0; i < Math.min(results.length, 10); i++) {
      for (let j = i + 1; j < Math.min(results.length, 10); j++) {
        totalSimilarity += calculateSimilarity(results[i], results[j]);
        comparisons++;
      }
    }

    const avgSimilarity = totalSimilarity / comparisons;
    return 1 - avgSimilarity; // Diversity = 1 - average similarity
  }, [calculateSimilarity]);

  const calculateCoverageScore = useCallback((searchResults: SearchStageResult[], finalResults: any[]): number => {
    const totalPossible = searchResults.reduce((sum, result) => sum + result.results.length, 0);
    const uniqueSources = new Set(searchResults.filter(r => !r.error).map(r => r.stage)).size;

    if (totalPossible === 0) return 0;

    // Coverage based on ratio of final results to total possible
    const ratioCoverage = finalResults.length / Math.min(totalPossible, maxResults);

    // Coverage based on source diversity
    const sourceCoverage = uniqueSources / 3; // Assuming max 3 sources

    return (ratioCoverage * 0.7 + sourceCoverage * 0.3);
  }, [maxResults]);

  const performAggregation = useCallback(async () => {
    if (searchResults.length === 0) return;

    setIsAggregating(true);

    try {
      // Simulate aggregation time
      await new Promise(resolve => setTimeout(resolve, 800));

      const successfulResults = searchResults.filter(result => !result.error);
      const rankings = successfulResults.map(result => result.results);

      let fusedResults: any[] = [];

      // Apply fusion strategy
      switch (fusionStrategy) {
        case 'rrf':
          fusedResults = rrfFusion(rankings);
          break;
        case 'weighted_average':
          const weights = [0.5, 0.3, 0.2]; // Vector, Graph, Keyword weights
          fusedResults = weightedAverageFusion(rankings, weights);
          break;
        default:
          fusedResults = rrfFusion(rankings);
      }

      // Deduplicate results
      const { deduplicated, duplicatesRemoved } = deduplicateResults(fusedResults);

      // Limit results
      const finalResults = deduplicated.slice(0, maxResults);

      // Calculate source breakdown
      const sourceBreakdown = {
        vector: 0,
        graph: 0,
        keyword: 0,
        fused: finalResults.length
      };

      // Calculate metrics
      const diversityScore = calculateDiversityScore(finalResults);
      const coverageScore = calculateCoverageScore(searchResults, finalResults);
      const aggregationConfidence = Math.min(1, (diversityScore + coverageScore) / 2);

      const resultAggregation: ResultAggregation = {
        final_results: finalResults,
        source_breakdown: sourceBreakdown,
        deduplication_stats: {
          initial_count: fusedResults.length,
          final_count: finalResults.length,
          duplicates_removed: duplicatesRemoved
        },
        aggregation_confidence: aggregationConfidence,
        diversity_score: diversityScore,
        coverage_score: coverageScore,
        fusion_method: fusionStrategy
      };

      setAggregation(resultAggregation);
      onAggregationComplete?.(resultAggregation);

    } catch (error) {
      console.error('Aggregation failed:', error);
    } finally {
      setIsAggregating(false);
    }
  }, [searchResults, fusionStrategy, maxResults, rrfFusion, weightedAverageFusion, deduplicateResults, calculateDiversityScore, calculateCoverageScore, onAggregationComplete]);

  useEffect(() => {
    if (autoAggregate && searchResults.length > 0) {
      performAggregation();
    }
  }, [autoAggregate, searchResults, performAggregation]);

  if (searchResults.length === 0) {
    return null;
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Aggregation Header */}
      <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
        <div className="flex items-center space-x-3">
          {isAggregating ? (
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
          ) : (
            <ArrowsRightLeftIcon className="h-5 w-5 text-purple-600" />
          )}
          <div>
            <h3 className="font-medium text-gray-900">Result Aggregation</h3>
            <p className="text-sm text-gray-600">
              {fusionStrategy.toUpperCase()} fusion • {maxResults} max results
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {aggregation && (
            <div className="text-right">
              <div className="text-sm font-medium text-gray-900">
                {aggregation.final_results.length} final results
              </div>
              <div className="text-xs text-gray-600">
                {aggregation.deduplication_stats.duplicates_removed} duplicates removed
              </div>
            </div>
          )}

          <div className="flex items-center space-x-2">
            {!isAggregating && !aggregation && (
              <Button
                variant="outline"
                size="sm"
                onClick={performAggregation}
                className="h-8"
              >
                <SparklesIcon className="h-3 w-3 mr-1" />
                Aggregate
              </Button>
            )}

            {!isAggregating && aggregation && (
              <Button
                variant="outline"
                size="sm"
                onClick={performAggregation}
                className="h-8"
              >
                <ArrowPathIcon className="h-3 w-3 mr-1" />
                Re-aggregate
              </Button>
            )}

            {showDetails && aggregation && (
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
        </div>
      </div>

      {/* Aggregation Progress */}
      {isAggregating && (
        <div className="space-y-3">
          <div className="flex items-center space-x-2 p-3 bg-purple-50 rounded-lg">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-purple-600 border-t-transparent" />
            <span className="text-sm text-purple-800">Aggregating results...</span>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">Fusing search results</span>
              <span className="text-gray-900">50%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div className="bg-purple-600 h-2 rounded-full transition-all duration-500" style={{ width: '50%' }} />
            </div>
          </div>
        </div>
      )}

      {/* Aggregation Results */}
      {aggregation && !isAggregating && (
        <div className="space-y-3">
          {/* Quick Stats */}
          <div className="grid grid-cols-3 gap-3">
            <div className="flex items-center space-x-2 p-3 bg-green-50 rounded-lg">
              <CheckCircleIcon className="h-4 w-4 text-green-600" />
              <div>
                <div className="text-sm font-medium text-green-900">
                  {aggregation.final_results.length} Results
                </div>
                <div className="text-xs text-green-700">After aggregation</div>
              </div>
            </div>

            <div className="flex items-center space-x-2 p-3 bg-blue-50 rounded-lg">
              <DocumentDuplicateIcon className="h-4 w-4 text-blue-600" />
              <div>
                <div className="text-sm font-medium text-blue-900">
                  {aggregation.deduplication_stats.duplicates_removed} Removed
                </div>
                <div className="text-xs text-blue-700">Duplicates</div>
              </div>
            </div>

            <div className="flex items-center space-x-2 p-3 bg-purple-50 rounded-lg">
              <ChartBarIcon className="h-4 w-4 text-purple-600" />
              <div>
                <div className="text-sm font-medium text-purple-900">
                  {Math.round(aggregation.aggregation_confidence * 100)}% Confidence
                </div>
                <div className="text-xs text-purple-700">Quality score</div>
              </div>
            </div>
          </div>

          {/* Quality Indicators */}
          <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
            <Badge variant="outline" className="text-xs">
              Diversity: {Math.round(aggregation.diversity_score * 100)}%
            </Badge>
            <Badge variant="outline" className="text-xs">
              Coverage: {Math.round(aggregation.coverage_score * 100)}%
            </Badge>
            <Badge variant="outline" className="text-xs">
              Fusion: {aggregation.fusion_method.toUpperCase()}
            </Badge>
          </div>
        </div>
      )}

      {/* Detail Dialog */}
      {aggregation && (
        <AggregationDetail
          aggregation={aggregation}
          searchResults={searchResults}
          isOpen={showDetailDialog}
          onClose={() => setShowDetailDialog(false)}
        />
      )}
    </div>
  );
};

export default ResultAggregator;