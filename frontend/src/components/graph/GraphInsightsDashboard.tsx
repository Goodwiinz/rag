import React, { useState, useCallback, useMemo } from 'react';
import {
  ChartBarIcon,
  LightBulbIcon,
  UserGroupIcon,
  DocumentTextIcon,
  ArrowTrendingUpIcon as TrendingUpIcon,
  ArrowTrendingDownIcon as TrendingDownIcon,
  ClockIcon,
  GlobeAltIcon,
  ShareIcon,
  ArrowPathIcon,
  FunnelIcon,
  EyeIcon,
  ArrowTopRightOnSquareIcon,
  InformationCircleIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline';
import { Entity, Relationship } from '@/types/search';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

interface GraphInsightsDashboardProps {
  entities: Entity[];
  relationships: Relationship[];
  documents?: any[];
  onEntityClick?: (entity: Entity) => void;
  onRelationshipClick?: (relationship: Relationship) => void;
  onDocumentClick?: (documentId: string) => void;
  className?: string;
  timeRange?: '7d' | '30d' | '90d' | '1y' | 'all';
}

interface GraphStatistics {
  overview: {
    totalEntities: number;
    totalRelationships: number;
    totalDocuments: number;
    avgDegree: number;
    graphDensity: number;
    clusterCount: number;
    largestComponentSize: number;
  };
  entityTypeDistribution: Record<
    Entity['type'],
    {
      count: number;
      percentage: number;
      avgConfidence: number;
      avgConnections: number;
      growthRate: number;
    }
  >;
  relationshipTypeDistribution: Record<
    string,
    {
      count: number;
      percentage: number;
      avgConfidence: number;
      avgWeight: number;
    }
  >;
  temporalMetrics: {
    entitiesCreated: Array<{
      date: string;
      count: number;
      type: Entity['type'];
    }>;
    relationshipsFormed: Array<{ date: string; count: number; type: string }>;
    activityTrend: 'increasing' | 'decreasing' | 'stable';
    peakActivityDate: string;
  };
  qualityMetrics: {
    avgEntityConfidence: number;
    avgRelationshipConfidence: number;
    highConfidenceEntities: number;
    highConfidenceRelationships: number;
    questionableEntities: number;
    questionableRelationships: number;
  };
  connectivityMetrics: {
    avgPathLength: number;
    diameter: number;
    clusteringCoefficient: number;
    components: number;
    isolatedNodes: number;
    bridges: number;
  };
}

interface Insight {
  id: string;
  type: 'opportunity' | 'warning' | 'trend' | 'achievement';
  title: string;
  description: string;
  impact: 'high' | 'medium' | 'low';
  category: 'growth' | 'quality' | 'connectivity' | 'performance';
  actionable: boolean;
  suggestions: string[];
  relatedEntities?: string[];
  relatedRelationships?: string[];
}

export const GraphInsightsDashboard: React.FC<GraphInsightsDashboardProps> = ({
  entities = [],
  relationships = [],
  documents = [],
  onEntityClick,
  onRelationshipClick,
  onDocumentClick,
  className,
  timeRange = '30d',
}) => {
  const [selectedTimeRange, setSelectedTimeRange] = useState(timeRange);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [showFilters, setShowFilters] = useState(false);

  // Calculate comprehensive graph statistics
  const statistics = useMemo((): GraphStatistics => {
    // Basic overview
    const totalEntities = entities.length;
    const totalRelationships = relationships.length;
    const totalDocuments = documents.length;

    // Calculate average degree
    const degrees = entities.map((entity) => {
      const connections = relationships.filter(
        (r) =>
          r.source_entity_id === entity.id || r.target_entity_id === entity.id
      ).length;
      return connections;
    });
    const avgDegree =
      degrees.length > 0
        ? degrees.reduce((sum, deg) => sum + deg, 0) / degrees.length
        : 0;

    // Calculate graph density
    const maxPossibleEdges = (totalEntities * (totalEntities - 1)) / 2;
    const graphDensity =
      maxPossibleEdges > 0 ? totalRelationships / maxPossibleEdges : 0;

    // Entity type distribution
    const entityTypeStats: Record<string, any> = {};
    entities.forEach((entity) => {
      if (!entityTypeStats[entity.type]) {
        entityTypeStats[entity.type] = {
          count: 0,
          totalConfidence: 0,
          totalConnections: 0,
        };
      }
      entityTypeStats[entity.type].count++;
      entityTypeStats[entity.type].totalConfidence += entity.confidence;
      entityTypeStats[entity.type].totalConnections +=
        degrees[entities.indexOf(entity)];
    });

    const entityTypeDistribution: Record<Entity['type'], any> = {} as any;
    Object.keys(entityTypeStats).forEach((type) => {
      const stats = entityTypeStats[type];
      const count = stats.count;
      entityTypeDistribution[type as Entity['type']] = {
        count,
        percentage: totalEntities > 0 ? (count / totalEntities) * 100 : 0,
        avgConfidence: count > 0 ? stats.totalConfidence / count : 0,
        avgConnections: count > 0 ? stats.totalConnections / count : 0,
        growthRate: Math.random() * 20 - 10, // Mock growth rate
      };
    });

    // Relationship type distribution
    const relationshipTypeStats: Record<string, any> = {};
    relationships.forEach((rel) => {
      if (!relationshipTypeStats[rel.relationship_type]) {
        relationshipTypeStats[rel.relationship_type] = {
          count: 0,
          totalConfidence: 0,
          totalWeight: 0,
        };
      }
      relationshipTypeStats[rel.relationship_type].count++;
      relationshipTypeStats[rel.relationship_type].totalConfidence +=
        rel.confidence;
      relationshipTypeStats[rel.relationship_type].totalWeight += rel.weight;
    });

    const relationshipTypeDistribution: Record<string, any> = {};
    Object.keys(relationshipTypeStats).forEach((type) => {
      const stats = relationshipTypeStats[type];
      const count = stats.count;
      relationshipTypeDistribution[type] = {
        count,
        percentage:
          totalRelationships > 0 ? (count / totalRelationships) * 100 : 0,
        avgConfidence: count > 0 ? stats.totalConfidence / count : 0,
        avgWeight: count > 0 ? stats.totalWeight / count : 0,
      };
    });

    // Temporal metrics (mock data for now)
    const entitiesCreated = entities.slice(0, 30).map((entity, index) => {
      const dateStr = new Date(Date.now() - index * 24 * 60 * 60 * 1000)
        .toISOString()
        .split('T')[0];
      return {
        date: (dateStr || new Date().toISOString().split('T')[0]) as string,
        count: Math.floor(Math.random() * 5) + 1,
        type: entity.type,
      };
    });

    const relationshipsFormed = relationships.slice(0, 30).map((rel, index) => {
      const dateStr = new Date(Date.now() - index * 24 * 60 * 60 * 1000)
        .toISOString()
        .split('T')[0];
      return {
        date: (dateStr || new Date().toISOString().split('T')[0]) as string,
        count: Math.floor(Math.random() * 3) + 1,
        type: rel.relationship_type,
      };
    });

    const activityTrend =
      Math.random() > 0.5
        ? 'increasing'
        : Math.random() > 0.5
          ? 'decreasing'
          : 'stable';
    const peakActivityDate =
      entitiesCreated.length > 0
        ? ((entitiesCreated[0]?.date ||
            new Date().toISOString().split('T')[0]) as string)
        : (new Date().toISOString().split('T')[0] as string);

    // Quality metrics
    const avgEntityConfidence =
      entities.length > 0
        ? entities.reduce((sum, e) => sum + e.confidence, 0) / entities.length
        : 0;
    const avgRelationshipConfidence =
      relationships.length > 0
        ? relationships.reduce((sum, r) => sum + r.confidence, 0) /
          relationships.length
        : 0;

    const highConfidenceEntities = entities.filter(
      (e) => e.confidence > 0.8
    ).length;
    const highConfidenceRelationships = relationships.filter(
      (r) => r.confidence > 0.8
    ).length;
    const questionableEntities = entities.filter(
      (e) => e.confidence < 0.5
    ).length;
    const questionableRelationships = relationships.filter(
      (r) => r.confidence < 0.5
    ).length;

    // Connectivity metrics (simplified calculations)
    const avgPathLength = 3.5; // Mock value
    const diameter = 8; // Mock value
    const clusteringCoefficient = 0.3; // Mock value
    const components = Math.max(1, Math.floor(totalEntities / 10)); // Mock calculation
    const isolatedNodes = entities.filter(
      (entity) =>
        !relationships.some(
          (r) =>
            r.source_entity_id === entity.id || r.target_entity_id === entity.id
        )
    ).length;
    const bridges = Math.floor(totalRelationships * 0.1); // Mock calculation

    return {
      overview: {
        totalEntities,
        totalRelationships,
        totalDocuments,
        avgDegree,
        graphDensity,
        clusterCount: components,
        largestComponentSize: totalEntities - isolatedNodes,
      },
      entityTypeDistribution,
      relationshipTypeDistribution,
      temporalMetrics: {
        entitiesCreated,
        relationshipsFormed,
        activityTrend,
        peakActivityDate,
      },
      qualityMetrics: {
        avgEntityConfidence,
        avgRelationshipConfidence,
        highConfidenceEntities,
        highConfidenceRelationships,
        questionableEntities,
        questionableRelationships,
      },
      connectivityMetrics: {
        avgPathLength,
        diameter,
        clusteringCoefficient,
        components,
        isolatedNodes,
        bridges,
      },
    };
  }, [entities, relationships, documents]);

  // Generate insights based on statistics
  const insights = useMemo((): Insight[] => {
    const insights: Insight[] = [];

    // Quality insights
    if (statistics.qualityMetrics.questionableEntities > 0) {
      insights.push({
        id: 'low-confidence-entities',
        type: 'warning',
        title: 'Low Confidence Entities Detected',
        description: `${statistics.qualityMetrics.questionableEntities} entities have confidence below 50%. Consider reviewing or improving these entities.`,
        impact: 'high',
        category: 'quality',
        actionable: true,
        suggestions: [
          'Review entity extraction process',
          'Improve source data quality',
          'Add more training examples',
        ],
      });
    }

    if (statistics.qualityMetrics.avgEntityConfidence > 0.8) {
      insights.push({
        id: 'high-quality-entities',
        type: 'achievement',
        title: 'High Entity Quality Achieved',
        description: `Average entity confidence is ${Math.round(statistics.qualityMetrics.avgEntityConfidence * 100)}%, indicating excellent extraction quality.`,
        impact: 'medium',
        category: 'quality',
        actionable: false,
        suggestions: [
          'Maintain current extraction parameters',
          'Consider expanding data sources',
        ],
      });
    }

    // Connectivity insights
    if (statistics.connectivityMetrics.isolatedNodes > 0) {
      insights.push({
        id: 'isolated-entities',
        type: 'opportunity',
        title: 'Isolated Entities Found',
        description: `${statistics.connectivityMetrics.isolatedNodes} entities have no connections. These could be valuable when connected to the main graph.`,
        impact: 'medium',
        category: 'connectivity',
        actionable: true,
        suggestions: [
          'Review entity linking algorithms',
          'Check for missing relationship extraction',
          'Consider manual curation for key entities',
        ],
      });
    }

    if (statistics.overview.graphDensity < 0.01) {
      insights.push({
        id: 'low-graph-density',
        type: 'warning',
        title: 'Low Graph Density',
        description: `Graph density is ${(statistics.overview.graphDensity * 100).toFixed(2)}%. Consider improving entity and relationship extraction.`,
        impact: 'medium',
        category: 'connectivity',
        actionable: true,
        suggestions: [
          'Review relationship extraction rules',
          'Expand context window for entity linking',
          'Consider additional data sources',
        ],
      });
    }

    // Growth insights
    const growthTrend = statistics.temporalMetrics.activityTrend;
    if (growthTrend === 'increasing') {
      insights.push({
        id: 'growth-trend',
        type: 'trend',
        title: 'Steady Growth Pattern',
        description:
          'Entity and relationship creation is trending upward, indicating healthy knowledge graph expansion.',
        impact: 'low',
        category: 'growth',
        actionable: false,
        suggestions: [
          'Monitor growth sustainability',
          'Plan for scaling infrastructure',
        ],
      });
    }

    // Entity type insights
    const dominantType = Object.entries(statistics.entityTypeDistribution).sort(
      ([, a], [, b]) => b.count - a.count
    )[0];
    if (dominantType) {
      const [type, stats] = dominantType;
      if (stats.percentage > 60) {
        insights.push({
          id: 'entity-type-dominance',
          type: 'opportunity',
          title: `Dominant Entity Type: ${type}`,
          description: `${type} entities make up ${stats.percentage.toFixed(1)}% of all entities. Consider balancing entity diversity.`,
          impact: 'low',
          category: 'growth',
          actionable: true,
          suggestions: [
            'Review entity extraction for other types',
            'Adjust extraction parameters',
            'Focus on underrepresented entity types',
          ],
        });
      }
    }

    return insights;
  }, [statistics]);

  // Filter insights by category
  const filteredInsights = useMemo(() => {
    if (selectedCategory === 'all') return insights;
    return insights.filter((insight) => insight.category === selectedCategory);
  }, [insights, selectedCategory]);

  // Get insight icon and color
  const getInsightIcon = (type: Insight['type']) => {
    switch (type) {
      case 'opportunity':
        return LightBulbIcon;
      case 'warning':
        return ExclamationTriangleIcon;
      case 'trend':
        return TrendingUpIcon;
      case 'achievement':
        return CheckCircleIcon;
      default:
        return InformationCircleIcon;
    }
  };

  const getInsightColor = (type: Insight['type']) => {
    switch (type) {
      case 'opportunity':
        return 'text-[var(--nous-fg-accent-safe)] bg-[var(--nous-sol)]/10 border-[var(--nous-sol)]/30';
      case 'warning':
        return 'text-[var(--nous-corona)] bg-[var(--nous-corona)]/10 border-[var(--nous-corona)]/30';
      case 'trend':
        return 'text-[var(--nous-terra)] bg-[var(--nous-terra)]/10 border-[var(--nous-terra)]/30';
      case 'achievement':
        return 'text-[var(--nous-fg-accent-safe)] bg-[var(--nous-sol)]/10 border-[var(--nous-sol)]/30';
      default:
        return 'text-foreground bg-[var(--nous-bg-2)] border-border';
    }
  };

  const getImpactColor = (impact: Insight['impact']) => {
    switch (impact) {
      case 'high':
        return 'bg-[var(--nous-mars)]/15 text-[var(--nous-mars)]';
      case 'medium':
        return 'bg-[var(--nous-corona)]/15 text-[var(--nous-corona)]';
      case 'low':
        return 'bg-[var(--nous-terra)]/15 text-[var(--nous-terra)]';
      default:
        return 'bg-[var(--nous-bg-3)] text-foreground';
    }
  };

  // Format large numbers
  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  };

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center">
              <ChartBarIcon className="h-5 w-5 mr-2" />
              Graph Insights Dashboard
            </div>
            <div className="flex items-center space-x-2">
              <Select
                value={selectedTimeRange}
                onValueChange={(value: any) => setSelectedTimeRange(value)}
              >
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="7d">Last 7 days</SelectItem>
                  <SelectItem value="30d">Last 30 days</SelectItem>
                  <SelectItem value="90d">Last 90 days</SelectItem>
                  <SelectItem value="1y">Last year</SelectItem>
                  <SelectItem value="all">All time</SelectItem>
                </SelectContent>
              </Select>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowFilters(!showFilters)}
              >
                <FunnelIcon className="h-4 w-4" />
              </Button>
            </div>
          </CardTitle>
        </CardHeader>
      </Card>

      {/* Overview Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <UserGroupIcon className="h-8 w-8 text-[var(--nous-fg-accent-safe)]" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-muted-foreground">
                  Total Entities
                </p>
                <p className="text-2xl font-bold text-foreground">
                  {formatNumber(statistics.overview.totalEntities)}
                </p>
                <p className="text-xs text-muted-foreground">
                  Avg degree: {statistics.overview.avgDegree.toFixed(1)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <ShareIcon className="h-8 w-8 text-[var(--nous-terra)]" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-muted-foreground">
                  Relationships
                </p>
                <p className="text-2xl font-bold text-foreground">
                  {formatNumber(statistics.overview.totalRelationships)}
                </p>
                <p className="text-xs text-muted-foreground">
                  Density: {(statistics.overview.graphDensity * 100).toFixed(2)}
                  %
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <DocumentTextIcon className="h-8 w-8 text-[var(--nous-fg-accent-safe)]" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-muted-foreground">
                  Documents
                </p>
                <p className="text-2xl font-bold text-foreground">
                  {formatNumber(statistics.overview.totalDocuments)}
                </p>
                <p className="text-xs text-muted-foreground">
                  {statistics.overview.clusterCount} components
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <GlobeAltIcon className="h-8 w-8 text-[var(--nous-corona)]" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-muted-foreground">
                  Graph Health
                </p>
                <p className="text-2xl font-bold text-foreground">
                  {Math.round(
                    statistics.qualityMetrics.avgEntityConfidence * 100
                  )}
                  %
                </p>
                <p className="text-xs text-muted-foreground">Avg confidence</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Entity Type Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Entity Type Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(statistics.entityTypeDistribution)
                .sort(([, a], [, b]) => b.count - a.count)
                .map(([type, stats]) => (
                  <div key={type} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Badge className="capitalize" variant="outline">
                          {type}
                        </Badge>
                        <span className="text-sm text-foreground">
                          {stats.count} ({stats.percentage.toFixed(1)}%)
                        </span>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {Math.round(stats.avgConfidence * 100)}% conf.
                      </div>
                    </div>
                    <Progress value={stats.percentage} className="h-2" />
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>

        {/* Quality Metrics */}
        <Card>
          <CardHeader>
            <CardTitle>Quality Metrics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="text-center p-4 bg-[var(--nous-bg-2)] rounded-lg">
                  <div className="text-lg font-bold text-[var(--nous-terra)]">
                    {statistics.qualityMetrics.highConfidenceEntities}
                  </div>
                  <div className="text-sm text-foreground">
                    High Confidence Entities
                  </div>
                  <div className="text-xs text-muted-foreground">
                    &gt;80% confidence
                  </div>
                </div>
                <div className="text-center p-4 bg-[var(--nous-bg-2)] rounded-lg">
                  <div className="text-lg font-bold text-[var(--nous-corona)]">
                    {statistics.qualityMetrics.questionableEntities}
                  </div>
                  <div className="text-sm text-foreground">
                    Questionable Entities
                  </div>
                  <div className="text-xs text-muted-foreground">
                    &lt;50% confidence
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Avg Entity Confidence</span>
                  <span className="font-medium">
                    {Math.round(
                      statistics.qualityMetrics.avgEntityConfidence * 100
                    )}
                    %
                  </span>
                </div>
                <Progress
                  value={statistics.qualityMetrics.avgEntityConfidence * 100}
                  className="h-2"
                />
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Avg Relationship Confidence</span>
                  <span className="font-medium">
                    {Math.round(
                      statistics.qualityMetrics.avgRelationshipConfidence * 100
                    )}
                    %
                  </span>
                </div>
                <Progress
                  value={
                    statistics.qualityMetrics.avgRelationshipConfidence * 100
                  }
                  className="h-2"
                />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Connectivity Metrics */}
      <Card>
        <CardHeader>
          <CardTitle>Connectivity Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 bg-[var(--nous-bg-2)] rounded-lg">
              <div className="text-lg font-bold">
                {statistics.connectivityMetrics.avgPathLength.toFixed(1)}
              </div>
              <div className="text-sm text-foreground">Avg Path Length</div>
            </div>
            <div className="text-center p-4 bg-[var(--nous-bg-2)] rounded-lg">
              <div className="text-lg font-bold">
                {statistics.connectivityMetrics.diameter}
              </div>
              <div className="text-sm text-foreground">Graph Diameter</div>
            </div>
            <div className="text-center p-4 bg-[var(--nous-bg-2)] rounded-lg">
              <div className="text-lg font-bold">
                {statistics.connectivityMetrics.clusteringCoefficient.toFixed(
                  3
                )}
              </div>
              <div className="text-sm text-foreground">
                Clustering Coefficient
              </div>
            </div>
            <div className="text-center p-4 bg-[var(--nous-bg-2)] rounded-lg">
              <div className="text-lg font-bold">
                {statistics.connectivityMetrics.components}
              </div>
              <div className="text-sm text-foreground">Components</div>
            </div>
          </div>

          {statistics.connectivityMetrics.isolatedNodes > 0 && (
            <div className="mt-4 p-3 bg-[var(--nous-corona)]/10 border border-[var(--nous-corona)]/30 rounded-lg">
              <div className="flex items-center space-x-2">
                <ExclamationTriangleIcon className="h-5 w-5 text-[var(--nous-corona)]" />
                <span className="text-sm text-[var(--nous-corona)]">
                  {statistics.connectivityMetrics.isolatedNodes} isolated
                  entities found
                </span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* AI-Generated Insights */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center">
              <LightBulbIcon className="h-5 w-5 mr-2" />
              AI-Generated Insights
            </div>
            <div className="flex items-center space-x-2">
              <Select
                value={selectedCategory}
                onValueChange={setSelectedCategory}
              >
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  <SelectItem value="quality">Quality</SelectItem>
                  <SelectItem value="connectivity">Connectivity</SelectItem>
                  <SelectItem value="growth">Growth</SelectItem>
                  <SelectItem value="performance">Performance</SelectItem>
                </SelectContent>
              </Select>
              <Badge variant="outline">
                {filteredInsights.length} insights
              </Badge>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {filteredInsights.length === 0 ? (
            <div className="text-center py-8">
              <LightBulbIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">
                No insights available for the selected category.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredInsights.map((insight) => {
                const InsightIcon = getInsightIcon(insight.type);
                return (
                  <div
                    key={insight.id}
                    className={cn(
                      'border rounded-lg p-4',
                      getInsightColor(insight.type)
                    )}
                  >
                    <div className="flex items-start space-x-3">
                      <div className="flex-shrink-0 mt-1">
                        <InsightIcon className="h-5 w-5" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="font-medium text-foreground">
                            {insight.title}
                          </h4>
                          <div className="flex items-center space-x-2">
                            <Badge className={getImpactColor(insight.impact)}>
                              {insight.impact} impact
                            </Badge>
                            <Badge variant="outline" className="text-xs">
                              {insight.category}
                            </Badge>
                          </div>
                        </div>
                        <p className="text-sm text-foreground mb-3">
                          {insight.description}
                        </p>

                        {insight.actionable &&
                          insight.suggestions.length > 0 && (
                            <div>
                              <h5 className="text-sm font-medium text-foreground mb-2">
                                Recommended Actions:
                              </h5>
                              <ul className="text-sm text-foreground space-y-1">
                                {insight.suggestions.map(
                                  (suggestion, index) => (
                                    <li
                                      key={index}
                                      className="flex items-start space-x-2"
                                    >
                                      <span className="text-[var(--nous-fg-accent-safe)] mt-1">
                                        •
                                      </span>
                                      <span>{suggestion}</span>
                                    </li>
                                  )
                                )}
                              </ul>
                            </div>
                          )}
                      </div>

                      <div className="flex-shrink-0">
                        <Button variant="ghost" size="sm">
                          <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Relationship Type Distribution */}
      {Object.keys(statistics.relationshipTypeDistribution).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Relationship Types</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Object.entries(statistics.relationshipTypeDistribution)
                .sort(([, a], [, b]) => b.count - a.count)
                .slice(0, 9)
                .map(([type, stats]) => (
                  <div key={type} className="p-4 border rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <Badge variant="outline" className="text-xs">
                        {type}
                      </Badge>
                      <span className="text-sm font-medium">{stats.count}</span>
                    </div>
                    <div className="space-y-1 text-xs text-muted-foreground">
                      <div>
                        {stats.percentage.toFixed(1)}% of all relationships
                      </div>
                      <div>
                        Avg confidence: {Math.round(stats.avgConfidence * 100)}%
                      </div>
                      <div>Avg weight: {stats.avgWeight.toFixed(3)}</div>
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default GraphInsightsDashboard;
