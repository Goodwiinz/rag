import React, { useState, useCallback, useMemo } from 'react';
import {
  ArrowPathIcon,
  FunnelIcon,
  MagnifyingGlassIcon,
  ArrowsRightLeftIcon,
  UserGroupIcon,
  BuildingOfficeIcon,
  MapPinIcon,
  LightBulbIcon,
  CalendarIcon,
  CubeIcon,
  EyeIcon,
  EyeSlashIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline';
import { Entity, Relationship } from '@/types/search';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

interface EntityRelationshipDisplayProps {
  centralEntity: Entity;
  relationships: Relationship[];
  relatedEntities: Entity[];
  onEntityClick?: (entity: Entity) => void;
  onRelationshipClick?: (relationship: Relationship) => void;
  onDocumentClick?: (documentId: string) => void;
  className?: string;
  maxRelationships?: number;
  showFilters?: boolean;
}

interface RelationshipGroup {
  type: string;
  relationships: Relationship[];
  entities: Entity[];
  color: string;
}

export const EntityRelationshipDisplay: React.FC<
  EntityRelationshipDisplayProps
> = ({
  centralEntity,
  relationships = [],
  relatedEntities = [],
  onEntityClick,
  onRelationshipClick,
  onDocumentClick,
  className,
  maxRelationships = 50,
  showFilters = true,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [selectedDirection, setSelectedDirection] = useState<
    'all' | 'outgoing' | 'incoming'
  >('all');
  const [showContext, setShowContext] = useState(true);
  const [expandedRelationships, setExpandedRelationships] = useState<
    Set<string>
  >(new Set());
  const [selectedRelationship, setSelectedRelationship] =
    useState<Relationship | null>(null);

  // Get unique relationship types
  const relationshipTypes = useMemo(() => {
    const types = new Set(relationships.map((r) => r.relationship_type));
    return Array.from(types).sort();
  }, [relationships]);

  // Get entity icon
  const getEntityIcon = (type: Entity['type']) => {
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

  // Get relationship color
  const getRelationshipColor = (type: string | undefined): string => {
    const colors = [
      'bg-blue-100 text-blue-800 border-blue-200',
      'bg-green-100 text-green-800 border-green-200',
      'bg-yellow-100 text-yellow-800 border-yellow-200',
      'bg-purple-100 text-purple-800 border-purple-200',
      'bg-pink-100 text-pink-800 border-pink-200',
      'bg-indigo-100 text-indigo-800 border-indigo-200',
    ];
    const safeType = type || 'unknown';
    const hash = safeType
      .split('')
      .reduce((acc, char) => acc + char.charCodeAt(0), 0);
    return colors[hash % colors.length]!;
  };

  // Filter relationships
  const filteredRelationships = useMemo(() => {
    let filtered = relationships;

    // Filter by type
    if (selectedType !== 'all') {
      filtered = filtered.filter((r) => r.relationship_type === selectedType);
    }

    // Filter by direction
    if (selectedDirection !== 'all') {
      filtered = filtered.filter((r) => {
        if (selectedDirection === 'outgoing') {
          return r.source_entity_id === centralEntity.id;
        } else {
          return r.target_entity_id === centralEntity.id;
        }
      });
    }

    // Filter by search term
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(
        (r) =>
          (r.relationship_type || '').toLowerCase().includes(term) ||
          (r.context || '').toLowerCase().includes(term)
      );
    }

    return filtered.slice(0, maxRelationships);
  }, [
    relationships,
    selectedType,
    selectedDirection,
    searchTerm,
    maxRelationships,
    centralEntity.id,
  ]);

  // Group relationships by type
  const relationshipGroups = useMemo(() => {
    const groups: Record<string, RelationshipGroup> = {};

    filteredRelationships.forEach((relationship) => {
      const type = relationship.relationship_type || 'unknown';
      if (!groups[type]) {
        groups[type] = {
          type,
          relationships: [],
          entities: [],
          color: getRelationshipColor(relationship.relationship_type as string),
        };
      }
      groups[type]!.relationships.push(relationship);
    });

    // Find related entities for each group
    Object.values(groups).forEach((group) => {
      const entityIds = new Set<string>();
      group.relationships.forEach((rel) => {
        if (rel.source_entity_id !== centralEntity.id) {
          entityIds.add(rel.source_entity_id);
        }
        if (rel.target_entity_id !== centralEntity.id) {
          entityIds.add(rel.target_entity_id);
        }
      });
      group.entities = relatedEntities.filter((entity) =>
        entityIds.has(entity.id)
      );
    });

    return Object.values(groups);
  }, [filteredRelationships, relatedEntities, centralEntity.id]);

  const toggleRelationshipExpansion = useCallback((relationshipId: string) => {
    setExpandedRelationships((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(relationshipId)) {
        newSet.delete(relationshipId);
      } else {
        newSet.add(relationshipId);
      }
      return newSet;
    });
  }, []);

  const getRelatedEntity = useCallback(
    (entityId: string) => {
      return relatedEntities.find((entity) => entity.id === entityId);
    },
    [relatedEntities]
  );

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className={cn('space-y-6', className)}>
      {/* Filters */}
      {showFilters && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center">
              <FunnelIcon className="h-5 w-5 mr-2" />
              Relationship Filters
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Search */}
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  <MagnifyingGlassIcon className="h-4 w-4 inline mr-1" />
                  Search
                </label>
                <Input
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Search relationships..."
                  className="w-full"
                />
              </div>

              {/* Type Filter */}
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Type
                </label>
                <Select value={selectedType} onValueChange={setSelectedType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">
                      All Types ({relationshipTypes.length})
                    </SelectItem>
                    {relationshipTypes.map((type) => (
                      <SelectItem key={type} value={type}>
                        {type} (
                        {
                          relationships.filter(
                            (r) => r.relationship_type === type
                          ).length
                        }
                        )
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Direction Filter */}
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  <ArrowsRightLeftIcon className="h-4 w-4 inline mr-1" />
                  Direction
                </label>
                <Select
                  value={selectedDirection}
                  onValueChange={(value: any) => setSelectedDirection(value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Directions</SelectItem>
                    <SelectItem value="outgoing">
                      Outgoing (from {centralEntity.name})
                    </SelectItem>
                    <SelectItem value="incoming">
                      Incoming (to {centralEntity.name})
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Toggle Context */}
            <div className="flex items-center justify-between mt-4 pt-4 border-t">
              <div className="text-sm text-foreground">
                Showing {filteredRelationships.length} of {relationships.length}{' '}
                relationships
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowContext(!showContext)}
              >
                {showContext ? (
                  <EyeSlashIcon className="h-4 w-4 mr-2" />
                ) : (
                  <EyeIcon className="h-4 w-4 mr-2" />
                )}
                {showContext ? 'Hide' : 'Show'} Context
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Relationship Groups */}
      {relationshipGroups.length === 0 ? (
        <Card>
          <CardContent className="text-center py-8">
            <ArrowsRightLeftIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">
              No relationships found matching the current filters.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSearchTerm('');
                setSelectedType('all');
                setSelectedDirection('all');
              }}
              className="mt-4"
            >
              <ArrowPathIcon className="h-4 w-4 mr-2" />
              Clear Filters
            </Button>
          </CardContent>
        </Card>
      ) : (
        relationshipGroups.map((group) => (
          <Card key={group.type}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center">
                  <Badge className={cn('mr-3', group.color)}>
                    {group.type}
                  </Badge>
                  <span className="text-lg font-normal text-foreground">
                    {group.relationships.length} relationships
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  <Badge variant="outline" className="text-xs">
                    {group.entities.length} entities
                  </Badge>
                  <Badge variant="outline" className="text-xs">
                    Avg. confidence:{' '}
                    {Math.round(
                      (group.relationships.reduce(
                        (acc, r) => acc + r.confidence,
                        0
                      ) /
                        group.relationships.length) *
                        100
                    )}
                    %
                  </Badge>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {group.relationships.map((relationship) => {
                  const isExpanded = expandedRelationships.has(relationship.id);
                  const isOutgoing =
                    relationship.source_entity_id === centralEntity.id;
                  const relatedEntityId = isOutgoing
                    ? relationship.target_entity_id
                    : relationship.source_entity_id;
                  const relatedEntity = getRelatedEntity(relatedEntityId);
                  const EntityIcon = relatedEntity
                    ? getEntityIcon(relatedEntity.type)
                    : CubeIcon;

                  return (
                    <div
                      key={relationship.id}
                      className="border rounded-lg p-4 hover:bg-[var(--nous-bg-3)] transition-colors"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          {/* Relationship Header */}
                          <div className="flex items-center space-x-3 mb-2">
                            <div className="flex items-center space-x-2">
                              <EntityIcon className="h-5 w-5 text-muted-foreground" />
                              <span className="font-medium">
                                {centralEntity.name}
                              </span>
                              <ArrowsRightLeftIcon className="h-4 w-4 text-muted-foreground" />
                              {relatedEntity && (
                                <>
                                  <span className="font-medium">
                                    {relatedEntity.name}
                                  </span>
                                  <Badge variant="outline" className="text-xs">
                                    {relatedEntity.type}
                                  </Badge>
                                </>
                              )}
                            </div>

                            <div className="flex items-center space-x-2">
                              <Badge className={cn('text-xs', group.color)}>
                                {relationship.relationship_type || 'Unknown'}
                              </Badge>
                              <Badge variant="outline" className="text-xs">
                                {Math.round(relationship.confidence * 100)}%
                                confidence
                              </Badge>
                              <Badge variant="outline" className="text-xs">
                                Weight: {relationship.weight}
                              </Badge>
                            </div>
                          </div>

                          {/* Context (always shown) */}
                          {showContext && relationship.context && (
                            <p className="text-sm text-foreground mb-3 italic">
                              "{relationship.context}"
                            </p>
                          )}

                          {/* Metadata */}
                          <div className="flex items-center justify-between text-xs text-muted-foreground">
                            <div className="flex items-center space-x-4">
                              <span>
                                {relationship.document_ids.length} documents
                              </span>
                              <span>{formatDate(relationship.first_seen)}</span>
                              {relationship.first_seen !==
                                relationship.last_seen && (
                                <span>
                                  → {formatDate(relationship.last_seen)}
                                </span>
                              )}
                            </div>

                            <div className="flex items-center space-x-2">
                              {/* Expand/Collapse Button */}
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() =>
                                  toggleRelationshipExpansion(relationship.id)
                                }
                                className="h-6 px-2 text-xs"
                              >
                                {isExpanded ? 'Show Less' : 'Show More'}
                              </Button>

                              {/* Document References */}
                              {relationship.document_ids.length > 0 && (
                                <Badge variant="outline" className="text-xs">
                                  {relationship.document_ids.length} docs
                                </Badge>
                              )}

                              {/* Action Buttons */}
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() =>
                                  onRelationshipClick?.(relationship)
                                }
                                className="h-6 w-6 p-0"
                              >
                                <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>

                          {/* Expanded Content */}
                          {isExpanded && (
                            <div className="mt-4 pt-4 border-t space-y-3">
                              {/* Document List */}
                              {relationship.document_ids.length > 0 && (
                                <div>
                                  <div className="text-sm font-medium text-foreground mb-2">
                                    Document References:
                                  </div>
                                  <div className="flex flex-wrap gap-2">
                                    {relationship.document_ids
                                      .slice(0, 5)
                                      .map((docId, index) => (
                                        <Badge
                                          key={docId}
                                          variant="secondary"
                                          className="text-xs cursor-pointer hover:bg-[var(--nous-bg-3)]"
                                          onClick={() =>
                                            onDocumentClick?.(docId)
                                          }
                                        >
                                          Document {index + 1}
                                        </Badge>
                                      ))}
                                    {relationship.document_ids.length > 5 && (
                                      <Badge
                                        variant="outline"
                                        className="text-xs"
                                      >
                                        +{relationship.document_ids.length - 5}{' '}
                                        more
                                      </Badge>
                                    )}
                                  </div>
                                </div>
                              )}

                              {/* Additional Metadata */}
                              <div className="grid grid-cols-2 gap-4 text-xs">
                                <div>
                                  <span className="font-medium text-foreground">
                                    Relationship ID:
                                  </span>
                                  <span className="ml-2 font-mono">
                                    {relationship.id}
                                  </span>
                                </div>
                                <div>
                                  <span className="font-medium text-foreground">
                                    Direction:
                                  </span>
                                  <span className="ml-2">
                                    {isOutgoing ? 'Outgoing' : 'Incoming'}
                                  </span>
                                </div>
                              </div>

                              {relationship.metadata &&
                                Object.keys(relationship.metadata).length >
                                  0 && (
                                  <div>
                                    <div className="text-sm font-medium text-foreground mb-2">
                                      Additional Metadata:
                                    </div>
                                    <div className="bg-[var(--nous-bg-2)] rounded p-2 text-xs">
                                      {Object.entries(
                                        relationship.metadata
                                      ).map(([key, value]) => (
                                        <div key={key}>
                                          <span className="font-medium">
                                            {key}:
                                          </span>{' '}
                                          {JSON.stringify(value)}
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        ))
      )}

      {/* Relationship Detail Modal */}
      <Dialog
        open={!!selectedRelationship}
        onOpenChange={() => setSelectedRelationship(null)}
      >
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Relationship Details</DialogTitle>
          </DialogHeader>
          {selectedRelationship && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h4 className="font-medium text-foreground mb-2">
                    Source Entity
                  </h4>
                  {getRelatedEntity(selectedRelationship.source_entity_id) ? (
                    <div className="p-3 bg-[var(--nous-bg-2)] rounded">
                      <div className="font-medium">
                        {
                          getRelatedEntity(
                            selectedRelationship.source_entity_id
                          )?.name
                        }
                      </div>
                      <Badge variant="outline" className="mt-1">
                        {
                          getRelatedEntity(
                            selectedRelationship.source_entity_id
                          )?.type
                        }
                      </Badge>
                    </div>
                  ) : (
                    <div className="p-3 bg-[var(--nous-bg-2)] rounded text-muted-foreground">
                      Entity not found
                    </div>
                  )}
                </div>

                <div>
                  <h4 className="font-medium text-foreground mb-2">
                    Target Entity
                  </h4>
                  {getRelatedEntity(selectedRelationship.target_entity_id) ? (
                    <div className="p-3 bg-[var(--nous-bg-2)] rounded">
                      <div className="font-medium">
                        {
                          getRelatedEntity(
                            selectedRelationship.target_entity_id
                          )?.name
                        }
                      </div>
                      <Badge variant="outline" className="mt-1">
                        {
                          getRelatedEntity(
                            selectedRelationship.target_entity_id
                          )?.type
                        }
                      </Badge>
                    </div>
                  ) : (
                    <div className="p-3 bg-[var(--nous-bg-2)] rounded text-muted-foreground">
                      Entity not found
                    </div>
                  )}
                </div>
              </div>

              <div>
                <h4 className="font-medium text-foreground mb-2">Context</h4>
                <div className="p-3 bg-[var(--nous-bg-2)] rounded italic">
                  "{selectedRelationship.context || 'No context available'}"
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <h4 className="font-medium text-foreground mb-2">Metrics</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>Confidence:</span>
                      <span>
                        {Math.round(selectedRelationship.confidence * 100)}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Weight:</span>
                      <span>{selectedRelationship.weight}</span>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="font-medium text-foreground mb-2">Timeline</h4>
                  <div className="space-y-2 text-sm">
                    <div>
                      <span className="text-foreground">First seen:</span>
                      <div>{formatDate(selectedRelationship.first_seen)}</div>
                    </div>
                    <div>
                      <span className="text-foreground">Last seen:</span>
                      <div>{formatDate(selectedRelationship.last_seen)}</div>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="font-medium text-foreground mb-2">
                    Documents
                  </h4>
                  <div className="text-sm">
                    <div>
                      {selectedRelationship.document_ids.length} documents
                      reference this relationship
                    </div>
                    {selectedRelationship.document_ids.length > 0 && (
                      <Button variant="outline" size="sm" className="mt-2">
                        View Documents
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EntityRelationshipDisplay;
