import React, { useState, useCallback, useMemo } from 'react';
import {
  ChartBarIcon,
  LightBulbIcon,
  ShareIcon,
  UsersIcon,
  MapIcon,
  AcademicCapIcon,
  FunnelIcon,
  ArrowPathIcon,
  EyeIcon,
  ArrowTopRightOnSquareIcon,
  InformationCircleIcon,
  CogIcon,
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

interface GraphCentralityMetricsProps {
  entities: Entity[];
  relationships: Relationship[];
  onEntityClick?: (entity: Entity) => void;
  onRelationshipClick?: (relationship: Relationship) => void;
  className?: string;
  maxResults?: number;
}

interface CentralityScore {
  entityId: string;
  degree: number;
  betweenness: number;
  closeness: number;
  eigenvector: number;
  pagerank: number;
  clustering: number;
}

interface CentralityMetric {
  id: string;
  name: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  formula?: string;
  interpretation: string;
}

interface MetricDetail {
  entity: Entity;
  metric: string;
  value: number;
  rank: number;
  percentile: number;
  relatedEntities: Array<{
    entity: Entity;
    relationship: Relationship;
    contribution: number;
  }>;
}

export const GraphCentralityMetrics: React.FC<GraphCentralityMetricsProps> = ({
  entities = [],
  relationships = [],
  onEntityClick,
  onRelationshipClick,
  className,
  maxResults = 20,
}) => {
  const [selectedMetric, setSelectedMetric] = useState('degree');
  const [showFilters, setShowFilters] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [metricDetail, setMetricDetail] = useState<MetricDetail | null>(null);
  const [filters, setFilters] = useState({
    entityType: 'all',
    minValue: 0,
    topN: 10,
  });

  // Define centrality metrics
  const centralityMetrics: CentralityMetric[] = [
    {
      id: 'degree',
      name: 'Degree Centrality',
      description: 'Number of direct connections',
      icon: ShareIcon,
      color: 'text-blue-600',
      formula: 'CD(v) = deg(v)',
      interpretation:
        'Higher values indicate well-connected entities with many direct relationships.',
    },
    {
      id: 'betweenness',
      name: 'Betweenness Centrality',
      description: 'Frequency of appearing on shortest paths',
      icon: UsersIcon,
      color: 'text-green-600',
      formula: 'CB(v) = Σ(s≠v≠t) σst(v) / σst',
      interpretation:
        'Higher values indicate entities that act as bridges between different parts of the network.',
    },
    {
      id: 'closeness',
      name: 'Closeness Centrality',
      description: 'Average distance to all other entities',
      icon: MapIcon,
      color: 'text-purple-600',
      formula: 'CC(v) = (n-1) / Σu d(v,u)',
      interpretation:
        'Higher values indicate entities that can quickly reach all other entities in the network.',
    },
    {
      id: 'eigenvector',
      name: 'Eigenvector Centrality',
      description: 'Influence based on connected entities importance',
      icon: AcademicCapIcon,
      color: 'text-orange-600',
      formula: 'Ax = λx',
      interpretation:
        'Higher values indicate entities connected to other important entities (influence propagation).',
    },
    {
      id: 'pagerank',
      name: 'PageRank',
      description: 'Importance based on incoming link quality',
      icon: ChartBarIcon,
      color: 'text-red-600',
      formula: 'PR(v) = (1-d)/n + d Σ PR(u)/L(u)',
      interpretation:
        'Higher values indicate entities that are referenced by other important entities.',
    },
    {
      id: 'clustering',
      name: 'Clustering Coefficient',
      description: 'Degree of interconnection among neighbors',
      icon: CogIcon,
      color: 'text-indigo-600',
      formula: 'C(v) = 2T(v) / (deg(v) * (deg(v) - 1))',
      interpretation:
        'Higher values indicate entities whose neighbors are well-connected to each other.',
    },
  ];

  // Stable signature of the graph input so the (cubic) centrality
  // computation only re-runs when the actual nodes/edges change, not on
  // every render that happens to recreate the prop arrays.
  const graphSignature = useMemo(() => {
    const entitySig = entities.map((e) => `${e.id}:${e.confidence}`).join('|');
    const relationshipSig = relationships
      .map(
        (r) =>
          `${r.source_entity_id}>${r.target_entity_id}:${r.confidence}:${r.weight}`
      )
      .join('|');
    return `${entitySig}#${relationshipSig}`;
  }, [entities, relationships]);

  // Calculate centrality scores
  const centralityScores = useMemo((): CentralityScore[] => {
    const scores: CentralityScore[] = [];

    // Build adjacency list
    const adjacencyList = new Map<string, Set<string>>();
    const entityMap = new Map(entities.map((e) => [e.id, e]));

    relationships.forEach((rel) => {
      if (!adjacencyList.has(rel.source_entity_id)) {
        adjacencyList.set(rel.source_entity_id, new Set());
      }
      if (!adjacencyList.has(rel.target_entity_id)) {
        adjacencyList.set(rel.target_entity_id, new Set());
      }
      adjacencyList.get(rel.source_entity_id)!.add(rel.target_entity_id);
      adjacencyList.get(rel.target_entity_id)!.add(rel.source_entity_id);
    });

    entities.forEach((entity) => {
      const neighbors = adjacencyList.get(entity.id) || new Set();

      // Degree Centrality
      const degree = neighbors.size;

      // Closeness Centrality (simplified)
      let totalDistance = 0;
      let reachableCount = 0;
      const visited = new Set<string>();
      const queue = Array.from(neighbors).map((n) => ({
        node: n,
        distance: 1,
      }));
      visited.add(entity.id);
      queue.forEach((q) => visited.add(q.node));

      while (queue.length > 0) {
        const current = queue.shift()!;
        totalDistance += current.distance;
        reachableCount++;

        const currentNeighbors = adjacencyList.get(current.node) || new Set();
        currentNeighbors.forEach((neighbor) => {
          if (!visited.has(neighbor)) {
            visited.add(neighbor);
            queue.push({ node: neighbor, distance: current.distance + 1 });
          }
        });
      }

      const closeness =
        reachableCount > 1 ? (reachableCount - 1) / totalDistance : 0;

      // Betweenness Centrality (simplified approximation)
      let betweenness = 0;
      if (degree > 1) {
        // Simplified: count how many shortest paths potentially go through this node
        entities.forEach((other1) => {
          if (other1.id === entity.id) return;
          entities.forEach((other2) => {
            if (other2.id === entity.id || other2.id === other1.id) return;

            const other1Neighbors = adjacencyList.get(other1.id) || new Set();
            const other2Neighbors = adjacencyList.get(other2.id) || new Set();

            // Simple heuristic: if this entity connects to both, it might be on a path
            if (neighbors.has(other1.id) && neighbors.has(other2.id)) {
              betweenness += 0.1;
            }
          });
        });
      }

      // Eigenvector Centrality (simplified)
      let eigenvector = 0;
      neighbors.forEach((neighborId) => {
        const neighborEntity = entityMap.get(neighborId);
        if (neighborEntity) {
          eigenvector += neighborEntity.confidence;
        }
      });
      eigenvector = eigenvector / Math.max(degree, 1);

      // PageRank (simplified)
      let pagerank = 0.15; // Damping factor
      neighbors.forEach((neighborId) => {
        const neighborDegree = (adjacencyList.get(neighborId) || new Set())
          .size;
        if (neighborDegree > 0) {
          pagerank += 0.85 / neighborDegree;
        }
      });

      // Clustering Coefficient
      let clustering = 0;
      if (degree > 1) {
        let neighborConnections = 0;
        const neighborArray = Array.from(neighbors);

        neighborArray.forEach((neighbor1, i) => {
          neighborArray.slice(i + 1).forEach((neighbor2) => {
            const neighbor1Neighbors =
              adjacencyList.get(neighbor1) || new Set();
            if (neighbor1Neighbors.has(neighbor2)) {
              neighborConnections++;
            }
          });
        });

        clustering = (2 * neighborConnections) / (degree * (degree - 1));
      }

      scores.push({
        entityId: entity.id,
        degree,
        betweenness,
        closeness,
        eigenvector,
        pagerank,
        clustering,
      });
    });

    return scores;
    // The cubic centrality computation reads `entities`/`relationships`, but is
    // keyed on `graphSignature` (derived from those same inputs) so it only
    // recomputes when the graph content actually changes, not when the parent
    // recreates the array references with identical contents.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphSignature]);

  // Get current metric data
  const currentMetricData = useMemo(() => {
    const metric = centralityMetrics.find((m) => m.id === selectedMetric);
    if (!metric) return [];

    const scoresWithEntities = centralityScores
      .map((score) => ({
        entity: entities.find((e) => e.id === score.entityId),
        value: score[selectedMetric as keyof CentralityScore] as number,
        score,
      }))
      .filter((item) => item.entity !== undefined)
      .sort((a, b) => b.value - a.value);

    // Apply filters
    let filtered = scoresWithEntities;

    if (filters.entityType !== 'all') {
      filtered = filtered.filter(
        (item) => item.entity!.type === filters.entityType
      );
    }

    if (filters.minValue > 0) {
      filtered = filtered.filter((item) => item.value >= filters.minValue);
    }

    return filtered.slice(0, filters.topN);
  }, [centralityScores, entities, selectedMetric, filters]);

  // Calculate metric statistics
  const metricStats = useMemo(() => {
    if (currentMetricData.length === 0) return null;

    const values = currentMetricData.map((d) => d.value);
    const max = Math.max(...values);
    const min = Math.min(...values);
    const avg = values.reduce((sum, val) => sum + val, 0) / values.length;
    const median = values.sort((a, b) => a - b)[Math.floor(values.length / 2)];

    return { max, min, avg, median, count: values.length };
  }, [currentMetricData]);

  // Get metric detail for an entity
  const getMetricDetail = useCallback(
    (entity: Entity) => {
      const score = centralityScores.find((s) => s.entityId === entity.id);
      if (!score) return null;

      const value = score[selectedMetric as keyof CentralityScore] as number;
      const rank =
        currentMetricData.findIndex((d) => d.entity?.id === entity.id) + 1;
      const percentile =
        ((currentMetricData.length - rank) / currentMetricData.length) * 100;

      // Find related entities that contribute to this metric
      const relatedEntities = relationships
        .filter(
          (r) =>
            r.source_entity_id === entity.id || r.target_entity_id === entity.id
        )
        .map((rel) => {
          const relatedId =
            rel.source_entity_id === entity.id
              ? rel.target_entity_id
              : rel.source_entity_id;
          const relatedEntity = entities.find((e) => e.id === relatedId);
          return {
            entity: relatedEntity,
            relationship: rel,
            contribution: rel.confidence * rel.weight,
          };
        })
        .filter((item) => item.entity !== undefined)
        .sort((a, b) => b.contribution - a.contribution)
        .slice(0, 5);

      return {
        entity,
        metric: selectedMetric,
        value,
        rank,
        percentile,
        relatedEntities: relatedEntities as any[],
      };
    },
    [
      centralityScores,
      selectedMetric,
      currentMetricData,
      relationships,
      entities,
    ]
  );

  // Handle entity click
  const handleEntityClick = useCallback(
    (entity: Entity) => {
      setSelectedEntity(entity);
      const detail = getMetricDetail(entity);
      if (detail) {
        setMetricDetail(detail);
      }
    },
    [getMetricDetail]
  );

  // Get entity type color
  const getEntityTypeColor = (type: Entity['type']) => {
    const colors = {
      person: 'bg-blue-100 text-blue-800 border-blue-200',
      organization: 'bg-green-100 text-green-800 border-green-200',
      location: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      concept: 'bg-purple-100 text-purple-800 border-purple-200',
      date: 'bg-orange-100 text-orange-800 border-orange-200',
      product: 'bg-pink-100 text-pink-800 border-pink-200',
    };
    return (
      colors[type] || 'bg-[var(--nous-bg-2)] text-foreground border-border'
    );
  };

  // Get metric icon
  const getMetricIcon = (metricId: string) => {
    const metric = centralityMetrics.find((m) => m.id === metricId);
    return metric?.icon || ChartBarIcon;
  };

  // Get entity type icon
  const getEntityTypeIcon = (type: Entity['type']) => {
    const icons = {
      person: UsersIcon,
      organization: ShareIcon,
      location: MapIcon,
      concept: LightBulbIcon,
      date: ChartBarIcon,
      product: CogIcon,
    };
    return icons[type] || ChartBarIcon;
  };

  // Get metric color
  const getMetricColor = (metricId: string) => {
    const metric = centralityMetrics.find((m) => m.id === metricId);
    return metric?.color || 'text-foreground';
  };

  // Format metric value
  const formatMetricValue = (value: number, metricId: string) => {
    switch (metricId) {
      case 'degree':
      case 'clustering':
        return value.toFixed(2);
      case 'betweenness':
      case 'closeness':
      case 'eigenvector':
      case 'pagerank':
        return value.toFixed(4);
      default:
        return value.toString();
    }
  };

  const currentMetric = centralityMetrics.find((m) => m.id === selectedMetric);
  const CurrentMetricIcon = getMetricIcon(selectedMetric);

  return (
    <div className={cn('space-y-6', className)}>
      {/* Metric Selection Header */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center">
              <ChartBarIcon className="h-5 w-5 mr-2" />
              Graph Centrality Metrics
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
            >
              <FunnelIcon className="h-4 w-4 mr-2" />
              Filters
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Metric Selection */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
            {centralityMetrics.map((metric) => {
              const MetricIcon = metric.icon;
              return (
                <Button
                  key={metric.id}
                  variant={selectedMetric === metric.id ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSelectedMetric(metric.id)}
                  className="h-16 flex-col space-y-1"
                >
                  <MetricIcon
                    className={cn(
                      'h-6 w-6',
                      selectedMetric === metric.id ? '' : metric.color
                    )}
                  />
                  <span className="text-xs">{metric.name}</span>
                </Button>
              );
            })}
          </div>

          {/* Current Metric Info */}
          {currentMetric && (
            <div className="p-4 bg-[var(--nous-bg-2)] rounded-lg">
              <div className="flex items-start space-x-3">
                <CurrentMetricIcon
                  className={cn('h-6 w-6 mt-1', currentMetric.color)}
                />
                <div className="flex-1">
                  <h3 className="font-medium text-foreground">
                    {currentMetric.name}
                  </h3>
                  <p className="text-sm text-foreground mt-1">
                    {currentMetric.description}
                  </p>
                  <div className="mt-2 space-y-1">
                    <p className="text-xs text-muted-foreground">
                      <span className="font-medium">Formula:</span>{' '}
                      {currentMetric.formula}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      <span className="font-medium">Interpretation:</span>{' '}
                      {currentMetric.interpretation}
                    </p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label="Metric Information"
                >
                  <InformationCircleIcon className="h-5 w-5" />
                </Button>
              </div>
            </div>
          )}

          {/* Filters */}
          {showFilters && (
            <div className="mt-4 pt-4 border-t grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Entity Type
                </label>
                <Select
                  value={filters.entityType}
                  onValueChange={(value: any) =>
                    setFilters((prev) => ({ ...prev, entityType: value }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="person">People</SelectItem>
                    <SelectItem value="organization">Organizations</SelectItem>
                    <SelectItem value="location">Locations</SelectItem>
                    <SelectItem value="concept">Concepts</SelectItem>
                    <SelectItem value="date">Dates</SelectItem>
                    <SelectItem value="product">Products</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Minimum Value
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={filters.minValue}
                  onChange={(e) =>
                    setFilters((prev) => ({
                      ...prev,
                      minValue: parseFloat(e.target.value) || 0,
                    }))
                  }
                  className="w-full px-3 py-2 border border-border rounded-md text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Top Results
                </label>
                <Select
                  value={filters.topN.toString()}
                  onValueChange={(value) =>
                    setFilters((prev) => ({ ...prev, topN: parseInt(value) }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="5">Top 5</SelectItem>
                    <SelectItem value="10">Top 10</SelectItem>
                    <SelectItem value="20">Top 20</SelectItem>
                    <SelectItem value="50">Top 50</SelectItem>
                    <SelectItem value="100">Top 100</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {/* Statistics */}
          {metricStats && (
            <div className="mt-4 pt-4 border-t">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                <div>
                  <div className="text-lg font-bold text-foreground">
                    {metricStats.count}
                  </div>
                  <div className="text-sm text-muted-foreground">Entities</div>
                </div>
                <div>
                  <div className="text-lg font-bold text-foreground">
                    {formatMetricValue(metricStats.max, selectedMetric)}
                  </div>
                  <div className="text-sm text-muted-foreground">Maximum</div>
                </div>
                <div>
                  <div className="text-lg font-bold text-foreground">
                    {formatMetricValue(metricStats.avg, selectedMetric)}
                  </div>
                  <div className="text-sm text-muted-foreground">Average</div>
                </div>
                <div>
                  <div className="text-lg font-bold text-foreground">
                    {formatMetricValue(metricStats.median || 0, selectedMetric)}
                  </div>
                  <div className="text-sm text-muted-foreground">Median</div>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Results */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <CurrentMetricIcon
              className={cn('h-5 w-5 mr-2', currentMetric?.color)}
            />
            {currentMetric?.name} Results
          </CardTitle>
        </CardHeader>
        <CardContent>
          {currentMetricData.length === 0 ? (
            <div className="text-center py-8">
              <ChartBarIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">
                No entities found matching the current criteria.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {currentMetricData.map((item, index) => {
                const entity = item.entity!;
                const percentage = metricStats
                  ? (item.value / metricStats.max) * 100
                  : 0;

                return (
                  <div
                    key={entity.id}
                    className="flex items-center space-x-4 p-4 border rounded-lg hover:bg-[var(--nous-bg-3)] cursor-pointer transition-colors"
                    onClick={() => handleEntityClick(entity)}
                  >
                    {/* Rank */}
                    <div className="flex-shrink-0 w-8 text-center">
                      <div
                        className={cn(
                          'text-sm font-bold',
                          index < 3
                            ? 'text-[var(--nous-fg-accent-safe)]'
                            : 'text-muted-foreground'
                        )}
                      >
                        #{index + 1}
                      </div>
                    </div>

                    {/* Entity Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <span className="font-medium truncate">
                          {entity.name}
                        </span>
                        <Badge className={getEntityTypeColor(entity.type)}>
                          {entity.type}
                        </Badge>
                      </div>
                      <div className="flex items-center space-x-4 mt-1 text-sm text-muted-foreground">
                        <span>{entity.mentions} mentions</span>
                        <span>{entity.document_ids.length} documents</span>
                        <span>
                          {Math.round(entity.confidence * 100)}% confidence
                        </span>
                      </div>
                    </div>

                    {/* Metric Value */}
                    <div className="flex-shrink-0 text-right">
                      <div className="text-lg font-bold">
                        {formatMetricValue(item.value, selectedMetric)}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {Math.round(percentage)}th percentile
                      </div>
                    </div>

                    {/* Visual Indicator */}
                    <div className="flex-shrink-0 w-24">
                      <Progress value={percentage} className="h-2" />
                    </div>

                    {/* Actions */}
                    <div className="flex-shrink-0">
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label="View Entity Details"
                      >
                        <EyeIcon className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Metric Detail Modal */}
      {metricDetail && (
        <Dialog
          open={!!metricDetail}
          onOpenChange={() => setMetricDetail(null)}
        >
          <DialogContent className="max-w-4xl">
            <DialogHeader>
              <DialogTitle className="flex items-center">
                <CurrentMetricIcon
                  className={cn('h-5 w-5 mr-2', currentMetric?.color)}
                />
                {metricDetail.entity.name} - {currentMetric?.name}
              </DialogTitle>
            </DialogHeader>

            <div className="space-y-6">
              {/* Overview */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 bg-[var(--nous-bg-2)] rounded-lg">
                  <div className="text-2xl font-bold text-foreground">
                    {formatMetricValue(metricDetail.value, selectedMetric)}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {currentMetric?.name}
                  </div>
                </div>
                <div className="text-center p-4 bg-[var(--nous-bg-2)] rounded-lg">
                  <div className="text-2xl font-bold text-[var(--nous-fg-accent-safe)]">
                    #{metricDetail.rank}
                  </div>
                  <div className="text-sm text-muted-foreground">Rank</div>
                </div>
                <div className="text-center p-4 bg-[var(--nous-bg-2)] rounded-lg">
                  <div className="text-2xl font-bold text-[var(--nous-terra)]">
                    {Math.round(metricDetail.percentile)}%
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Percentile
                  </div>
                </div>
                <div className="text-center p-4 bg-[var(--nous-bg-2)] rounded-lg">
                  <div className="text-2xl font-bold text-[var(--nous-fg-accent)]">
                    {metricDetail.relatedEntities.length}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Related Entities
                  </div>
                </div>
              </div>

              {/* Related Entities */}
              {metricDetail.relatedEntities.length > 0 && (
                <div>
                  <h4 className="font-medium text-foreground mb-3">
                    Entities Contributing to This Score
                  </h4>
                  <div className="space-y-2">
                    {metricDetail.relatedEntities.map(
                      ({ entity, relationship, contribution }) => {
                        const EntityTypeIcon = getEntityTypeIcon(entity.type);
                        return (
                          <div
                            key={entity.id}
                            className="flex items-center justify-between p-3 bg-[var(--nous-bg-2)] rounded-lg"
                          >
                            <div className="flex items-center space-x-2">
                              <EntityTypeIcon className="h-4 w-4" />
                              <span className="font-medium">{entity.name}</span>
                              <Badge
                                className={getEntityTypeColor(entity.type)}
                              >
                                {entity.type}
                              </Badge>
                            </div>
                            <div className="flex items-center space-x-3">
                              <Badge variant="outline">
                                {relationship.relationship_type}
                              </Badge>
                              <span className="text-sm text-muted-foreground">
                                Contribution: {contribution.toFixed(3)}
                              </span>
                              <Button
                                variant="ghost"
                                size="sm"
                                aria-label="Open Relationship"
                              >
                                <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        );
                      }
                    )}
                  </div>
                </div>
              )}

              {/* Entity Details */}
              <div>
                <h4 className="font-medium text-foreground mb-3">
                  Entity Details
                </h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium text-foreground">
                      Description:
                    </span>
                    <p className="mt-1">
                      {metricDetail.entity.description ||
                        'No description available'}
                    </p>
                  </div>
                  <div>
                    <span className="font-medium text-foreground">
                      Aliases:
                    </span>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {metricDetail.entity.aliases.map((alias, index) => (
                        <Badge
                          key={index}
                          variant="secondary"
                          className="text-xs"
                        >
                          {alias}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span className="font-medium text-foreground">
                      First Seen:
                    </span>
                    <div className="mt-1">
                      {new Date(
                        metricDetail.entity.first_seen
                      ).toLocaleDateString()}
                    </div>
                  </div>
                  <div>
                    <span className="font-medium text-foreground">
                      Last Seen:
                    </span>
                    <div className="mt-1">
                      {new Date(
                        metricDetail.entity.last_seen
                      ).toLocaleDateString()}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

export default GraphCentralityMetrics;
