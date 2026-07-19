import React, { useState, useCallback, useMemo } from 'react';
import {
  ChartBarIcon,
  ArrowsRightLeftIcon,
  PlusIcon,
  XMarkIcon,
  DocumentTextIcon,
  UserGroupIcon,
  EyeIcon,
  ArrowTopRightOnSquareIcon,
  FunnelIcon,
  ArrowPathIcon,
  LightBulbIcon,
  CalendarIcon,
  MapPinIcon,
  BuildingOfficeIcon,
  CubeIcon,
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

interface EntityComparisonProps {
  entities: Entity[];
  relationships?: Relationship[];
  documents?: any[];
  availableEntities?: Entity[];
  onEntitySelect?: (entity: Entity) => void;
  onEntityRemove?: (entityId: string) => void;
  onEntityClick?: (entity: Entity) => void;
  onDocumentClick?: (documentId: string) => void;
  className?: string;
  maxComparisons?: number;
}

interface ComparisonMetric {
  id: string;
  label: string;
  type: 'numeric' | 'categorical' | 'temporal';
  getValue: (entity: Entity) => string | number;
  format?: (value: any) => string;
  icon?: React.ComponentType<{ className?: string }>;
  description?: string;
}

interface RelationshipAnalysis {
  sourceEntity: Entity;
  targetEntity: Entity;
  directRelationships: Relationship[];
  indirectRelationships: Array<{
    path: Entity[];
    relationships: Relationship[];
    strength: number;
  }>;
  sharedDocuments: string[];
  sharedConnections: Entity[];
}

export const EntityComparison: React.FC<EntityComparisonProps> = ({
  entities = [],
  relationships = [],
  documents = [],
  availableEntities = [],
  onEntitySelect,
  onEntityRemove,
  onEntityClick,
  onDocumentClick,
  className,
  maxComparisons = 4,
}) => {
  const [selectedEntities, setSelectedEntities] = useState<Entity[]>(
    entities.slice(0, maxComparisons)
  );
  const [showEntitySelector, setShowEntitySelector] = useState(false);
  const [selectedMetric, setSelectedMetric] = useState('overview');
  const [relationshipAnalysis, setRelationshipAnalysis] =
    useState<RelationshipAnalysis | null>(null);

  // Define comparison metrics
  const comparisonMetrics: ComparisonMetric[] = useMemo(
    () => [
      {
        id: 'overview',
        label: 'Overview',
        type: 'categorical',
        getValue: (entity) => entity.name,
        icon: ChartBarIcon,
      },
      {
        id: 'confidence',
        label: 'Confidence Score',
        type: 'numeric',
        getValue: (entity) => entity.confidence,
        format: (value) => `${Math.round(value * 100)}%`,
        icon: ChartBarIcon,
      },
      {
        id: 'mentions',
        label: 'Total Mentions',
        type: 'numeric',
        getValue: (entity) => entity.mentions,
        format: (value) => value.toLocaleString(),
        icon: DocumentTextIcon,
      },
      {
        id: 'documents',
        label: 'Document Count',
        type: 'numeric',
        getValue: (entity) => entity.document_ids.length,
        format: (value) => value.toString(),
        icon: DocumentTextIcon,
      },
      {
        id: 'aliases',
        label: 'Aliases',
        type: 'numeric',
        getValue: (entity) => entity.aliases.length,
        format: (value) => value.toString(),
        icon: UserGroupIcon,
      },
      {
        id: 'firstSeen',
        label: 'First Appearance',
        type: 'temporal',
        getValue: (entity) => entity.first_seen,
        format: (value) => new Date(value).toLocaleDateString(),
        icon: CalendarIcon,
      },
      {
        id: 'lastSeen',
        label: 'Last Appearance',
        type: 'temporal',
        getValue: (entity) => entity.last_seen,
        format: (value) => new Date(value).toLocaleDateString(),
        icon: CalendarIcon,
      },
      {
        id: 'entityType',
        label: 'Entity Type',
        type: 'categorical',
        getValue: (entity) => entity.type,
        icon: CubeIcon,
      },
    ],
    []
  );

  // Get current metric configuration
  const currentMetric = useMemo(() => {
    return (
      comparisonMetrics.find((m) => m.id === selectedMetric) ||
      comparisonMetrics[0]
    );
  }, [selectedMetric, comparisonMetrics]);

  // Calculate relationship analysis between entities
  const analyzeRelationships = useCallback(
    (entity1: Entity, entity2: Entity) => {
      const directRelationships = relationships.filter(
        (r) =>
          (r.source_entity_id === entity1.id &&
            r.target_entity_id === entity2.id) ||
          (r.source_entity_id === entity2.id &&
            r.target_entity_id === entity1.id)
      );

      // Find shared documents
      const sharedDocuments = entity1.document_ids.filter((docId) =>
        entity2.document_ids.includes(docId)
      );

      // Find shared connections (entities that both are connected to)
      const entity1Connections = new Set(
        relationships
          .filter(
            (r) =>
              r.source_entity_id === entity1.id ||
              r.target_entity_id === entity1.id
          )
          .map((r) =>
            r.source_entity_id === entity1.id
              ? r.target_entity_id
              : r.source_entity_id
          )
      );

      const entity2Connections = new Set(
        relationships
          .filter(
            (r) =>
              r.source_entity_id === entity2.id ||
              r.target_entity_id === entity2.id
          )
          .map((r) =>
            r.source_entity_id === entity2.id
              ? r.target_entity_id
              : r.source_entity_id
          )
      );

      const sharedConnectionIds = Array.from(entity1Connections).filter((id) =>
        entity2Connections.has(id)
      );
      const sharedConnections = availableEntities.filter((entity) =>
        sharedConnectionIds.includes(entity.id)
      );

      return {
        sourceEntity: entity1,
        targetEntity: entity2,
        directRelationships,
        indirectRelationships: [], // Would require more complex path finding algorithm
        sharedDocuments,
        sharedConnections,
      };
    },
    [relationships, availableEntities]
  );

  // Add entity to comparison
  const addEntity = useCallback(
    (entity: Entity) => {
      if (selectedEntities.length >= maxComparisons) {
        return; // Would show toast in real implementation
      }

      const newSelected = [...selectedEntities, entity];
      setSelectedEntities(newSelected);
      onEntitySelect?.(entity);
      setShowEntitySelector(false);
    },
    [selectedEntities, maxComparisons, onEntitySelect]
  );

  // Remove entity from comparison
  const removeEntity = useCallback(
    (entityId: string) => {
      const newSelected = selectedEntities.filter((e) => e.id !== entityId);
      setSelectedEntities(newSelected);
      onEntityRemove?.(entityId);
    },
    [selectedEntities, onEntityRemove]
  );

  // Compare two specific entities
  const compareEntities = useCallback(
    (entity1: Entity, entity2: Entity) => {
      const analysis = analyzeRelationships(entity1, entity2);
      setRelationshipAnalysis(analysis);
    },
    [analyzeRelationships]
  );

  // Get entity type icon
  const getEntityTypeIcon = (type: Entity['type']) => {
    const icons = {
      person: UserGroupIcon,
      organization: BuildingOfficeIcon,
      location: MapPinIcon,
      concept: LightBulbIcon,
      date: CalendarIcon,
      product: CubeIcon,
    };
    return icons[type] || CubeIcon;
  };

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
    return colors[type] || 'bg-gray-100 text-foreground border-border';
  };

  // Calculate metric ranges for visualization
  const metricRanges = useMemo(() => {
    if (!currentMetric || currentMetric.type !== 'numeric') return null;

    const values = selectedEntities.map(
      (entity) => currentMetric.getValue(entity) as number
    );
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min;

    return { min, max, range };
  }, [selectedEntities, currentMetric]);

  // Get metric position percentage for bar visualization
  const getMetricPosition = (entity: Entity) => {
    if (!metricRanges || metricRanges.range === 0 || !currentMetric) return 50;
    const value = currentMetric.getValue(entity) as number;
    return ((value - metricRanges.min) / metricRanges.range) * 100;
  };

  const MetricIcon = currentMetric?.icon || ChartBarIcon;

  return (
    <div className={cn('space-y-6', className)}>
      {/* Comparison Header */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center">
              <ArrowsRightLeftIcon className="h-5 w-5 mr-2" />
              Entity Comparison
            </div>
            <div className="flex items-center space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowEntitySelector(!showEntitySelector)}
                disabled={selectedEntities.length >= maxComparisons}
              >
                <PlusIcon className="h-4 w-4 mr-2" />
                Add Entity ({selectedEntities.length}/{maxComparisons})
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedEntities([])}
              >
                <ArrowPathIcon className="h-4 w-4 mr-2" />
                Clear All
              </Button>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Selected Entities */}
          <div className="flex flex-wrap gap-3 mb-6">
            {selectedEntities.map((entity) => {
              const EntityTypeIcon = getEntityTypeIcon(entity.type);
              return (
                <div
                  key={entity.id}
                  className={cn(
                    'flex items-center space-x-2 px-3 py-2 rounded-lg border',
                    getEntityTypeColor(entity.type)
                  )}
                >
                  <EntityTypeIcon className="h-4 w-4" />
                  <span className="font-medium">{entity.name}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeEntity(entity.id)}
                    className="h-6 w-6 p-0 hover:bg-[var(--nous-mars)]/10"
                  >
                    <XMarkIcon className="h-3 w-3" />
                  </Button>
                </div>
              );
            })}
            {selectedEntities.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                <ArrowsRightLeftIcon className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                <p>
                  Select entities to compare their properties and relationships.
                </p>
              </div>
            )}
          </div>

          {/* Metric Selector */}
          {selectedEntities.length > 0 && (
            <div className="flex items-center space-x-4">
              <label className="text-sm font-medium text-foreground">
                Compare by:
              </label>
              <Select value={selectedMetric} onValueChange={setSelectedMetric}>
                <SelectTrigger className="w-64">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {comparisonMetrics.map((metric) => {
                    const MetricIcon = metric.icon || ChartBarIcon;
                    return (
                      <SelectItem key={metric.id} value={metric.id}>
                        <div className="flex items-center space-x-2">
                          <MetricIcon className="h-4 w-4" />
                          <span>{metric.label}</span>
                        </div>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Entity Selector */}
      {showEntitySelector && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Select Entity to Compare</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowEntitySelector(false)}
              >
                <XMarkIcon className="h-4 w-4" />
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-h-96 overflow-auto">
              {availableEntities
                .filter(
                  (entity) =>
                    !selectedEntities.some(
                      (selected) => selected.id === entity.id
                    )
                )
                .map((entity) => {
                  const EntityTypeIcon = getEntityTypeIcon(entity.type);
                  return (
                    <div
                      key={entity.id}
                      className="flex items-center justify-between p-3 border rounded-lg hover:bg-[var(--nous-bg-3)] cursor-pointer"
                      onClick={() => addEntity(entity)}
                    >
                      <div className="flex items-center space-x-2">
                        <EntityTypeIcon className="h-4 w-4" />
                        <div>
                          <div className="font-medium text-sm">
                            {entity.name}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {entity.type}
                          </div>
                        </div>
                      </div>
                      <Button variant="ghost" size="sm">
                        <PlusIcon className="h-4 w-4" />
                      </Button>
                    </div>
                  );
                })}
            </div>
            {availableEntities.filter(
              (entity) =>
                !selectedEntities.some((selected) => selected.id === entity.id)
            ).length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                <CubeIcon className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                <p>No more entities available to compare.</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Comparison Results */}
      {selectedEntities.length > 0 && (
        <>
          {/* Metric Comparison */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <MetricIcon className="h-5 w-5 mr-2" />
                {currentMetric?.label || 'Metric'} Comparison
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {selectedEntities.map((entity) => {
                  const value = currentMetric?.getValue(entity);
                  const formattedValue = currentMetric?.format
                    ? currentMetric.format(value)
                    : value;
                  const EntityTypeIcon = getEntityTypeIcon(entity.type);

                  return (
                    <div key={entity.id} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <EntityTypeIcon className="h-4 w-4" />
                          <span className="font-medium">{entity.name}</span>
                          <Badge className={getEntityTypeColor(entity.type)}>
                            {entity.type}
                          </Badge>
                        </div>
                        <div className="flex items-center space-x-2">
                          <span className="font-bold text-lg">
                            {formattedValue}
                          </span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onEntityClick?.(entity)}
                          >
                            <EyeIcon className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>

                      {/* Progress bar for numeric metrics */}
                      {currentMetric?.type === 'numeric' && metricRanges && (
                        <div className="relative">
                          <Progress
                            value={getMetricPosition(entity)}
                            className="h-6"
                          />
                          <div className="absolute inset-0 flex items-center justify-center">
                            <span className="text-xs font-medium text-white mix-blend-difference">
                              {Math.round(getMetricPosition(entity))}%
                            </span>
                          </div>
                        </div>
                      )}

                      {/* Additional entity details */}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-foreground">
                        <div>
                          <span className="block font-medium">Confidence:</span>
                          {Math.round(entity.confidence * 100)}%
                        </div>
                        <div>
                          <span className="block font-medium">Mentions:</span>
                          {entity.mentions}
                        </div>
                        <div>
                          <span className="block font-medium">Documents:</span>
                          {entity.document_ids.length}
                        </div>
                        <div>
                          <span className="block font-medium">Aliases:</span>
                          {entity.aliases.length}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* Entity vs Entity Comparison */}
          {selectedEntities.length >= 2 && (
            <Card>
              <CardHeader>
                <CardTitle>Entity vs Entity Analysis</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {selectedEntities
                    .slice(0, 2)
                    .map((entity1, index) => {
                      const entity2 = selectedEntities[index === 0 ? 1 : 0];
                      if (!entity2) return null;
                      const analysis = analyzeRelationships(entity1, entity2);
                      const EntityTypeIcon1 = getEntityTypeIcon(entity1.type);
                      const EntityTypeIcon2 = getEntityTypeIcon(entity2.type);

                      return (
                        <div key={entity1.id} className="space-y-4">
                          <div className="flex items-center space-x-2">
                            <EntityTypeIcon1 className="h-5 w-5" />
                            <span className="font-medium">{entity1.name}</span>
                            <ArrowsRightLeftIcon className="h-4 w-4 text-muted-foreground" />
                            <EntityTypeIcon2 className="h-5 w-5" />
                            <span className="font-medium">{entity2.name}</span>
                          </div>

                          <div className="space-y-2">
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-foreground">
                                Direct Relationships:
                              </span>
                              <Badge variant="outline">
                                {analysis.directRelationships.length}
                              </Badge>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-foreground">
                                Shared Documents:
                              </span>
                              <Badge variant="outline">
                                {analysis.sharedDocuments.length}
                              </Badge>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-foreground">
                                Shared Connections:
                              </span>
                              <Badge variant="outline">
                                {analysis.sharedConnections.length}
                              </Badge>
                            </div>
                          </div>

                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => compareEntities(entity1, entity2)}
                            className="w-full"
                          >
                            <FunnelIcon className="h-4 w-4 mr-2" />
                            Detailed Analysis
                          </Button>
                        </div>
                      );
                    })
                    .filter(Boolean)}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Shared Context */}
          {selectedEntities.length >= 2 && (
            <Card>
              <CardHeader>
                <CardTitle>Shared Context</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  {/* Shared Documents */}
                  <div>
                    <h4 className="font-medium text-foreground mb-3">
                      Shared Documents
                    </h4>
                    {(() => {
                      const sharedDocIds = selectedEntities.reduce(
                        (shared, entity) => {
                          if (shared.length === 0) return entity.document_ids;
                          return shared.filter((docId) =>
                            entity.document_ids.includes(docId)
                          );
                        },
                        [] as string[]
                      );

                      return sharedDocIds.length > 0 ? (
                        <div className="space-y-2">
                          {sharedDocIds.slice(0, 5).map((docId) => {
                            const doc = documents.find((d) => d.id === docId);
                            return doc ? (
                              <div
                                key={docId}
                                className="flex items-center justify-between p-3 bg-[var(--nous-bg-2)] rounded-lg cursor-pointer hover:bg-[var(--nous-bg-3)]"
                                onClick={() => onDocumentClick?.(docId)}
                              >
                                <div>
                                  <div className="font-medium text-sm">
                                    {doc.title}
                                  </div>
                                  <div className="text-xs text-muted-foreground">
                                    {doc.filename}
                                  </div>
                                </div>
                                <Button variant="ghost" size="sm">
                                  <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                                </Button>
                              </div>
                            ) : null;
                          })}
                          {sharedDocIds.length > 5 && (
                            <Badge variant="outline">
                              +{sharedDocIds.length - 5} more documents
                            </Badge>
                          )}
                        </div>
                      ) : (
                        <p className="text-muted-foreground">
                          No shared documents found.
                        </p>
                      );
                    })()}
                  </div>

                  {/* Shared Connections */}
                  <div>
                    <h4 className="font-medium text-foreground mb-3">
                      Shared Connections
                    </h4>
                    {(() => {
                      const sharedConnections = selectedEntities.reduce(
                        (shared, entity, index) => {
                          if (index === 0) return [];

                          const entityConnections = new Set(
                            relationships
                              .filter(
                                (r) =>
                                  r.source_entity_id === entity.id ||
                                  r.target_entity_id === entity.id
                              )
                              .map((r) =>
                                r.source_entity_id === entity.id
                                  ? r.target_entity_id
                                  : r.source_entity_id
                              )
                          );

                          return shared.filter((connectionId) =>
                            entityConnections.has(connectionId)
                          );
                        },
                        selectedEntities[0]
                          ? relationships
                              .filter(
                                (r) =>
                                  r.source_entity_id ===
                                    selectedEntities[0]!.id ||
                                  r.target_entity_id === selectedEntities[0]!.id
                              )
                              .map((r) =>
                                r.source_entity_id === selectedEntities[0]!.id
                                  ? r.target_entity_id
                                  : r.source_entity_id
                              )
                          : []
                      );

                      const sharedEntityObjects = availableEntities.filter(
                        (entity) => sharedConnections.includes(entity.id)
                      );

                      return sharedEntityObjects.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {sharedEntityObjects.map((entity) => {
                            const EntityTypeIcon = getEntityTypeIcon(
                              entity.type
                            );
                            return (
                              <Badge
                                key={entity.id}
                                className={cn(
                                  'cursor-pointer hover:opacity-80',
                                  getEntityTypeColor(entity.type)
                                )}
                                onClick={() => onEntityClick?.(entity)}
                              >
                                <EntityTypeIcon className="h-3 w-3 mr-1" />
                                {entity.name}
                              </Badge>
                            );
                          })}
                        </div>
                      ) : (
                        <p className="text-muted-foreground">
                          No shared connections found.
                        </p>
                      );
                    })()}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Detailed Relationship Analysis Modal */}
      {relationshipAnalysis && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              Detailed Relationship Analysis
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setRelationshipAnalysis(null)}
              >
                <XMarkIcon className="h-4 w-4" />
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {/* Direct Relationships */}
              <div>
                <h4 className="font-medium text-foreground mb-3">
                  Direct Relationships
                </h4>
                {relationshipAnalysis.directRelationships.length > 0 ? (
                  <div className="space-y-2">
                    {relationshipAnalysis.directRelationships.map(
                      (relationship) => (
                        <div
                          key={relationship.id}
                          className="p-3 bg-[var(--nous-bg-2)] rounded-lg"
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <Badge className="bg-[var(--nous-sol)]/15 text-[var(--nous-fg-accent-safe)] mb-2">
                                {relationship.relationship_type}
                              </Badge>
                              <p className="text-sm text-foreground italic">
                                "{relationship.context}"
                              </p>
                            </div>
                            <Badge variant="outline">
                              {Math.round(relationship.confidence * 100)}%
                              confidence
                            </Badge>
                          </div>
                        </div>
                      )
                    )}
                  </div>
                ) : (
                  <p className="text-muted-foreground">
                    No direct relationships found.
                  </p>
                )}
              </div>

              {/* Shared Documents */}
              <div>
                <h4 className="font-medium text-foreground mb-3">
                  Shared Documents (
                  {relationshipAnalysis.sharedDocuments.length})
                </h4>
                {relationshipAnalysis.sharedDocuments.length > 0 ? (
                  <div className="space-y-2">
                    {relationshipAnalysis.sharedDocuments
                      .slice(0, 3)
                      .map((docId) => {
                        const doc = documents.find((d) => d.id === docId);
                        return doc ? (
                          <div
                            key={docId}
                            className="flex items-center justify-between p-2 bg-[var(--nous-bg-2)] rounded cursor-pointer hover:bg-[var(--nous-bg-3)]"
                            onClick={() => onDocumentClick?.(docId)}
                          >
                            <span className="text-sm">{doc.title}</span>
                            <ArrowTopRightOnSquareIcon className="h-4 w-4 text-muted-foreground" />
                          </div>
                        ) : null;
                      })}
                    {relationshipAnalysis.sharedDocuments.length > 3 && (
                      <Badge variant="outline">
                        +{relationshipAnalysis.sharedDocuments.length - 3} more
                      </Badge>
                    )}
                  </div>
                ) : (
                  <p className="text-muted-foreground">
                    No shared documents found.
                  </p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default EntityComparison;
