import React, { useState, useCallback, useMemo } from 'react';
import {
  SparklesIcon,
  UserGroupIcon,
  DocumentTextIcon,
  ShareIcon,
  ClockIcon,
  EyeIcon,
  ArrowTopRightOnSquareIcon,
  FunnelIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  StarIcon,
  ArrowTrendingUpIcon as TrendingUpIcon,
  LightBulbIcon,
  BookmarkIcon,
} from '@heroicons/react/24/outline';
import { Entity, Relationship } from '@/types/search';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

interface GraphRecommendationsProps {
  entities: Entity[];
  relationships: Relationship[];
  documents?: any[];
  currentUserId?: string;
  userHistory?: Array<{
    entityIds: string[];
    queryText: string;
    timestamp: number;
  }>;
  onEntityClick?: (entity: Entity) => void;
  onDocumentClick?: (documentId: string) => void;
  onRelationshipClick?: (relationship: Relationship) => void;
  onRecommendationAction?: (action: RecommendationAction) => void;
  className?: string;
  maxRecommendations?: number;
}

interface Recommendation {
  id: string;
  type: 'entity' | 'relationship' | 'path' | 'document' | 'query';
  title: string;
  description: string;
  confidence: number;
  relevanceScore: number;
  reasoning: string[];
  actionType: 'explore' | 'connect' | 'analyze' | 'discover';
  metadata: {
    entityId?: string;
    relationshipId?: string;
    documentIds?: string[];
    path?: {
      source: string;
      target: string;
      length: number;
    };
    suggestedQuery?: string;
  };
  priority: 'high' | 'medium' | 'low';
  category: 'discovery' | 'analysis' | 'connection' | 'exploration';
  timestamp: number;
}

interface RecommendationAction {
  type: 'accept' | 'dismiss' | 'snooze' | 'feedback';
  recommendationId: string;
  feedback?: {
    helpful: boolean;
    reason?: string;
  };
}

interface RecommendationFilters {
  types: Recommendation['type'][];
  categories: Recommendation['category'][];
  priorities: Recommendation['priority'][];
  minConfidence: number;
  showAccepted: boolean;
  showDismissed: boolean;
}

export const GraphRecommendations: React.FC<GraphRecommendationsProps> = ({
  entities = [],
  relationships = [],
  documents = [],
  currentUserId,
  userHistory = [],
  onEntityClick,
  onDocumentClick,
  onRelationshipClick,
  onRecommendationAction,
  className,
  maxRecommendations = 20,
}) => {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [filters, setFilters] = useState<RecommendationFilters>({
    types: [],
    categories: [],
    priorities: [],
    minConfidence: 0.5,
    showAccepted: false,
    showDismissed: false,
  });
  const [selectedRecommendation, setSelectedRecommendation] =
    useState<Recommendation | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<number>(Date.now());

  // Generate recommendations based on graph analysis
  const generateRecommendations = useCallback(async (): Promise<
    Recommendation[]
  > => {
    const recommendations: Recommendation[] = [];
    const now = Date.now();

    // Entity-based recommendations
    // 1. High-value entities with few connections
    const highValueEntities = entities
      .filter((entity) => {
        const connections = relationships.filter(
          (r) =>
            r.source_entity_id === entity.id || r.target_entity_id === entity.id
        ).length;
        return entity.confidence > 0.8 && connections < 3;
      })
      .slice(0, 5);

    highValueEntities.forEach((entity, index) => {
      recommendations.push({
        id: `high-value-entity-${entity.id}`,
        type: 'entity',
        title: `Explore ${entity.name}`,
        description: `This ${entity.type} entity has high confidence (${Math.round(entity.confidence * 100)}%) but few connections. It might be a key node in your knowledge graph.`,
        confidence: entity.confidence,
        relevanceScore: 0.9 - index * 0.1,
        reasoning: [
          'High confidence entity with limited connections',
          'Potential central node in the knowledge graph',
          'May lead to discovering related entities',
        ],
        actionType: 'explore',
        metadata: { entityId: entity.id },
        priority: 'high',
        category: 'discovery',
        timestamp: now + index,
      });
    });

    // 2. Relationship recommendations
    // Find entities that should be connected but aren't
    const entityPairs = [];
    for (let i = 0; i < Math.min(entities.length, 50); i++) {
      for (let j = i + 1; j < Math.min(entities.length, 50); j++) {
        const entity1 = entities[i];
        const entity2 = entities[j];

        // Skip if entities are undefined
        if (!entity1 || !entity2) continue;

        // Skip if already connected
        const isConnected = relationships.some(
          (r) =>
            (r.source_entity_id === entity1.id &&
              r.target_entity_id === entity2.id) ||
            (r.source_entity_id === entity2.id &&
              r.target_entity_id === entity1.id)
        );

        if (
          !isConnected &&
          entity1.type === entity2.type &&
          entity1.confidence > 0.7 &&
          entity2.confidence > 0.7
        ) {
          entityPairs.push({ entity1, entity2 });
        }
      }
    }

    entityPairs.slice(0, 3).forEach((pair, index) => {
      recommendations.push({
        id: `relationship-rec-${pair.entity1.id}-${pair.entity2.id}`,
        type: 'relationship',
        title: `Connect ${pair.entity1.name} and ${pair.entity2.name}`,
        description: `Both are ${pair.entity1.type} entities with high confidence but no known relationship. Consider investigating potential connections.`,
        confidence: (pair.entity1.confidence + pair.entity2.confidence) / 2,
        relevanceScore: 0.8 - index * 0.1,
        reasoning: [
          'Same entity type with high confidence',
          'No existing relationship found',
          'Potential semantic or contextual connection',
        ],
        actionType: 'connect',
        metadata: {
          path: {
            source: pair.entity1.id,
            target: pair.entity2.id,
            length: 1,
          },
        },
        priority: 'medium',
        category: 'connection',
        timestamp: now + 1000 + index,
      });
    });

    // 3. Path recommendations
    // Find interesting paths between distant entities
    const distantPairs = [];
    for (let i = 0; i < Math.min(entities.length, 20); i++) {
      for (let j = i + 1; j < Math.min(entities.length, 20); j++) {
        const entity1 = entities[i];
        const entity2 = entities[j];

        // Skip if entities are undefined
        if (!entity1 || !entity2) continue;

        if (
          entity1.type !== entity2.type &&
          entity1.confidence > 0.6 &&
          entity2.confidence > 0.6
        ) {
          distantPairs.push({ entity1, entity2 });
        }
      }
    }

    distantPairs.slice(0, 2).forEach((pair, index) => {
      recommendations.push({
        id: `path-rec-${pair.entity1.id}-${pair.entity2.id}`,
        type: 'path',
        title: `Explore connection between ${pair.entity1.name} and ${pair.entity2.name}`,
        description: `Find paths between this ${pair.entity1.type} and ${pair.entity2.type}. They might have interesting indirect relationships.`,
        confidence: (pair.entity1.confidence + pair.entity2.confidence) / 2,
        relevanceScore: 0.7 - index * 0.1,
        reasoning: [
          'Different entity types suggest potential relationships',
          'May uncover hidden connections',
          'Could reveal new insights',
        ],
        actionType: 'discover',
        metadata: {
          path: {
            source: pair.entity1.id,
            target: pair.entity2.id,
            length: 3, // Estimated
          },
        },
        priority: 'medium',
        category: 'exploration',
        timestamp: now + 2000 + index,
      });
    });

    // 4. Document recommendations based on entities
    if (documents && documents.length > 0) {
      const underrepresentedEntities = entities
        .filter((entity) => {
          const docCount = documents.filter((doc) =>
            doc.entities?.some((e: any) => e.id === entity.id)
          ).length;
          return entity.mentions > 5 && docCount < 2;
        })
        .slice(0, 3);

      underrepresentedEntities.forEach((entity, index) => {
        recommendations.push({
          id: `document-rec-${entity.id}`,
          type: 'document',
          title: `Review documents containing ${entity.name}`,
          description: `This entity is mentioned ${entity.mentions} times but appears in few documents. Review for completeness.`,
          confidence: 0.7,
          relevanceScore: 0.6 - index * 0.1,
          reasoning: [
            'High mention count but low document coverage',
            'May indicate incomplete document processing',
            'Important for comprehensive analysis',
          ],
          actionType: 'analyze',
          metadata: {
            entityId: entity.id,
            documentIds: entity.document_ids.slice(0, 3),
          },
          priority: 'low',
          category: 'analysis',
          timestamp: now + 3000 + index,
        });
      });
    }

    // 5. Query recommendations based on patterns
    const commonPatterns = [
      {
        pattern: 'What is the relationship between',
        suggestion: 'Find relationships between entities',
        confidence: 0.8,
      },
      {
        pattern: 'Show me all',
        suggestion: 'List entities of specific type',
        confidence: 0.7,
      },
      {
        pattern: 'How does',
        suggestion: 'Explore entity connections and influences',
        confidence: 0.75,
      },
    ];

    commonPatterns.forEach((pattern, index) => {
      recommendations.push({
        id: `query-rec-${index}`,
        type: 'query',
        title: pattern.suggestion,
        description: `Try querying with "${pattern.pattern}" to discover new insights.`,
        confidence: pattern.confidence,
        relevanceScore: 0.5,
        reasoning: [
          'Common query pattern based on graph structure',
          'May reveal frequently sought information',
          'Optimizes exploration workflow',
        ],
        actionType: 'discover',
        metadata: {
          suggestedQuery: pattern.pattern,
        },
        priority: 'low',
        category: 'exploration',
        timestamp: now + 4000 + index,
      });
    });

    return recommendations.sort(
      (a, b) =>
        b.confidence * b.relevanceScore - a.confidence * a.relevanceScore
    );
  }, [entities, relationships, documents]);

  // Load recommendations
  const loadRecommendations = useCallback(async () => {
    setIsLoading(true);
    try {
      const recs = await generateRecommendations();
      setRecommendations(recs);
      setLastRefresh(Date.now());
    } catch (error) {
      console.error('Error generating recommendations:', error);
    } finally {
      setIsLoading(false);
    }
  }, [generateRecommendations]);

  // Filter recommendations
  const filteredRecommendations = useMemo(() => {
    let filtered = recommendations;

    // Filter by type
    if (filters.types.length > 0) {
      filtered = filtered.filter((rec) => filters.types.includes(rec.type));
    }

    // Filter by category
    if (filters.categories.length > 0) {
      filtered = filtered.filter((rec) =>
        filters.categories.includes(rec.category)
      );
    }

    // Filter by priority
    if (filters.priorities.length > 0) {
      filtered = filtered.filter((rec) =>
        filters.priorities.includes(rec.priority)
      );
    }

    // Filter by confidence
    filtered = filtered.filter(
      (rec) => rec.confidence >= filters.minConfidence
    );

    return filtered.slice(0, maxRecommendations);
  }, [recommendations, filters, maxRecommendations]);

  // Handle recommendation action
  const handleRecommendationAction = useCallback(
    (action: RecommendationAction) => {
      // In a real implementation, this would send the action to a backend
      console.log('Recommendation action:', action);
      onRecommendationAction?.(action);

      // Update local state (mock implementation)
      if (action.type === 'dismiss') {
        setRecommendations((prev) =>
          prev.filter((rec) => rec.id !== action.recommendationId)
        );
      }
    },
    [onRecommendationAction]
  );

  // Execute recommendation
  const executeRecommendation = useCallback(
    (recommendation: Recommendation) => {
      switch (recommendation.actionType) {
        case 'explore':
          if (recommendation.metadata.entityId) {
            const entity = entities.find(
              (e) => e.id === recommendation.metadata.entityId
            );
            if (entity) onEntityClick?.(entity);
          }
          break;
        case 'connect':
          // This would open a relationship creation dialog
          console.log(
            'Would open connection dialog for:',
            recommendation.metadata.path
          );
          break;
        case 'analyze':
          if (recommendation.metadata.documentIds) {
            recommendation.metadata.documentIds.forEach((docId) => {
              onDocumentClick?.(docId);
            });
          }
          break;
        case 'discover':
          if (recommendation.metadata.suggestedQuery) {
            console.log(
              'Would execute query:',
              recommendation.metadata.suggestedQuery
            );
          }
          break;
      }

      handleRecommendationAction({
        type: 'accept',
        recommendationId: recommendation.id,
      });
    },
    [entities, onEntityClick, onDocumentClick, handleRecommendationAction]
  );

  // Get recommendation icon
  const getRecommendationIcon = (type: Recommendation['type']) => {
    switch (type) {
      case 'entity':
        return UserGroupIcon;
      case 'relationship':
        return ShareIcon;
      case 'path':
        return TrendingUpIcon;
      case 'document':
        return DocumentTextIcon;
      case 'query':
        return LightBulbIcon;
      default:
        return SparklesIcon;
    }
  };

  // Get action type icon
  const getActionTypeIcon = (actionType: Recommendation['actionType']) => {
    switch (actionType) {
      case 'explore':
        return EyeIcon;
      case 'connect':
        return ShareIcon;
      case 'analyze':
        return DocumentTextIcon;
      case 'discover':
        return TrendingUpIcon;
      default:
        return SparklesIcon;
    }
  };

  // Get priority color
  const getPriorityColor = (priority: Recommendation['priority']) => {
    switch (priority) {
      case 'high':
        return 'border-[var(--nous-mars)]/30 bg-[var(--nous-mars)]/10';
      case 'medium':
        return 'border-[var(--nous-corona)]/30 bg-[var(--nous-corona)]/10';
      case 'low':
        return 'border-border bg-[var(--nous-bg-2)]';
    }
  };

  // Get confidence color
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-[var(--nous-terra)]';
    if (confidence >= 0.6) return 'text-[var(--nous-corona)]';
    return 'text-[var(--nous-mars)]';
  };

  // Load recommendations on mount
  React.useEffect(() => {
    loadRecommendations();
  }, [loadRecommendations]);

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center">
              <SparklesIcon className="h-5 w-5 mr-2" />
              Graph-Based Recommendations
            </div>
            <div className="flex items-center space-x-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={loadRecommendations}
                disabled={isLoading}
              >
                <ArrowPathIcon
                  className={cn('h-4 w-4 mr-2', isLoading && 'animate-spin')}
                />
                Refresh
              </Button>
              <span className="text-sm text-muted-foreground">
                Last updated: {new Date(lastRefresh).toLocaleTimeString()}
              </span>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Types
              </label>
              <div className="space-y-1">
                {['entity', 'relationship', 'path', 'document', 'query'].map(
                  (type) => (
                    <label key={type} className="flex items-center">
                      <input
                        type="checkbox"
                        checked={filters.types.includes(type as any)}
                        onChange={(e) => {
                          const newTypes = e.target.checked
                            ? [...filters.types, type as any]
                            : filters.types.filter((t) => t !== type);
                          setFilters((prev) => ({ ...prev, types: newTypes }));
                        }}
                        className="rounded border-border text-[var(--nous-fg-accent-safe)] focus:ring-[var(--nous-sol)] mr-2"
                      />
                      <span className="text-sm capitalize">{type}</span>
                    </label>
                  )
                )}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Categories
              </label>
              <div className="space-y-1">
                {['discovery', 'analysis', 'connection', 'exploration'].map(
                  (category) => (
                    <label key={category} className="flex items-center">
                      <input
                        type="checkbox"
                        checked={filters.categories.includes(category as any)}
                        onChange={(e) => {
                          const newCategories = e.target.checked
                            ? [...filters.categories, category as any]
                            : filters.categories.filter((c) => c !== category);
                          setFilters((prev) => ({
                            ...prev,
                            categories: newCategories,
                          }));
                        }}
                        className="rounded border-border text-[var(--nous-fg-accent-safe)] focus:ring-[var(--nous-sol)] mr-2"
                      />
                      <span className="text-sm capitalize">{category}</span>
                    </label>
                  )
                )}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Min Confidence: {Math.round(filters.minConfidence * 100)}%
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={filters.minConfidence}
                onChange={(e) =>
                  setFilters((prev) => ({
                    ...prev,
                    minConfidence: parseFloat(e.target.value),
                  }))
                }
                className="w-full"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Max Recommendations
              </label>
              <Select
                value={maxRecommendations.toString()}
                onValueChange={(value) => {
                  /* Would update maxRecommendations */
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="5">5</SelectItem>
                  <SelectItem value="10">10</SelectItem>
                  <SelectItem value="20">20</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recommendations List */}
      {isLoading ? (
        <Card>
          <CardContent className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-[var(--nous-sol)] border-t-transparent mx-auto mb-4"></div>
            <p className="text-muted-foreground">
              Generating recommendations...
            </p>
          </CardContent>
        </Card>
      ) : filteredRecommendations.length === 0 ? (
        <Card>
          <CardContent className="text-center py-8">
            <SparklesIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">
              No recommendations available.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={loadRecommendations}
              className="mt-4"
            >
              Generate New Recommendations
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredRecommendations.map((recommendation) => {
            const RecommendationIcon = getRecommendationIcon(
              recommendation.type
            );
            const ActionTypeIcon = getActionTypeIcon(recommendation.actionType);

            return (
              <div
                key={recommendation.id}
                className={cn(
                  'border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer',
                  getPriorityColor(recommendation.priority)
                )}
              >
                <div className="flex items-start space-x-4">
                  {/* Icon */}
                  <div className="flex-shrink-0">
                    <div className="p-2 bg-background rounded-lg border">
                      <RecommendationIcon className="h-5 w-5 text-[var(--nous-fg-accent-safe)]" />
                    </div>
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-lg font-medium text-foreground">
                        {recommendation.title}
                      </h3>
                      <div className="flex items-center space-x-2">
                        <Badge variant="outline" className="capitalize">
                          {recommendation.type}
                        </Badge>
                        <Badge variant="outline" className="capitalize">
                          {recommendation.category}
                        </Badge>
                        <span
                          className={cn(
                            'text-sm font-medium',
                            getConfidenceColor(recommendation.confidence)
                          )}
                        >
                          {Math.round(recommendation.confidence * 100)}%
                        </span>
                      </div>
                    </div>

                    <p className="text-sm text-foreground mb-3">
                      {recommendation.description}
                    </p>

                    {/* Reasoning */}
                    <div className="mb-3">
                      <h4 className="text-sm font-medium text-foreground mb-1">
                        Why this recommendation:
                      </h4>
                      <ul className="text-sm text-foreground space-y-1">
                        {recommendation.reasoning.map((reason, index) => (
                          <li
                            key={index}
                            className="flex items-start space-x-2"
                          >
                            <StarIcon className="h-3 w-3 text-[var(--nous-sol)] mt-0.5 flex-shrink-0" />
                            <span>{reason}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Button
                          size="sm"
                          onClick={() => executeRecommendation(recommendation)}
                          className="flex items-center space-x-1"
                        >
                          <ActionTypeIcon className="h-4 w-4" />
                          <span className="capitalize">
                            {recommendation.actionType}
                          </span>
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            setSelectedRecommendation(recommendation)
                          }
                        >
                          <EyeIcon className="h-4 w-4 mr-1" />
                          Details
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            handleRecommendationAction({
                              type: 'snooze',
                              recommendationId: recommendation.id,
                            })
                          }
                        >
                          <ClockIcon className="h-4 w-4" />
                        </Button>
                      </div>

                      <div className="flex items-center space-x-2 text-xs text-muted-foreground">
                        <span>Priority: {recommendation.priority}</span>
                        <span>•</span>
                        <span>
                          Relevance:{' '}
                          {Math.round(recommendation.relevanceScore * 100)}%
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Dismiss */}
                  <div className="flex-shrink-0">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        handleRecommendationAction({
                          type: 'dismiss',
                          recommendationId: recommendation.id,
                        })
                      }
                    >
                      ×
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Recommendation Detail Modal */}
      {selectedRecommendation && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center">
                <SparklesIcon className="h-5 w-5 mr-2" />
                Recommendation Details
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedRecommendation(null)}
              >
                ×
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <h3 className="font-medium text-foreground mb-2">
                  {selectedRecommendation.title}
                </h3>
                <p className="text-sm text-foreground">
                  {selectedRecommendation.description}
                </p>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-3 bg-[var(--nous-bg-2)] rounded">
                  <div className="text-lg font-bold">
                    {Math.round(selectedRecommendation.confidence * 100)}%
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Confidence
                  </div>
                </div>
                <div className="text-center p-3 bg-[var(--nous-bg-2)] rounded">
                  <div className="text-lg font-bold">
                    {Math.round(selectedRecommendation.relevanceScore * 100)}%
                  </div>
                  <div className="text-sm text-muted-foreground">Relevance</div>
                </div>
                <div className="text-center p-3 bg-[var(--nous-bg-2)] rounded">
                  <div className="text-lg font-bold capitalize">
                    {selectedRecommendation.priority}
                  </div>
                  <div className="text-sm text-muted-foreground">Priority</div>
                </div>
                <div className="text-center p-3 bg-[var(--nous-bg-2)] rounded">
                  <div className="text-lg font-bold capitalize">
                    {selectedRecommendation.category}
                  </div>
                  <div className="text-sm text-muted-foreground">Category</div>
                </div>
              </div>

              <div>
                <h4 className="font-medium text-foreground mb-2">
                  Detailed Reasoning:
                </h4>
                <ul className="space-y-2">
                  {selectedRecommendation.reasoning.map((reason, index) => (
                    <li key={index} className="flex items-start space-x-2">
                      <span className="text-[var(--nous-fg-accent-safe)]">•</span>
                      <span className="text-sm">{reason}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="flex items-center space-x-3">
                <Button
                  onClick={() => {
                    executeRecommendation(selectedRecommendation);
                    setSelectedRecommendation(null);
                  }}
                >
                  Execute Recommendation
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    handleRecommendationAction({
                      type: 'snooze',
                      recommendationId: selectedRecommendation.id,
                    });
                    setSelectedRecommendation(null);
                  }}
                >
                  <ClockIcon className="h-4 w-4 mr-2" />
                  Snooze
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    handleRecommendationAction({
                      type: 'feedback',
                      recommendationId: selectedRecommendation.id,
                      feedback: { helpful: false },
                    });
                    setSelectedRecommendation(null);
                  }}
                >
                  Not Helpful
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default GraphRecommendations;
