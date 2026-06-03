import React, { useState, useCallback, useMemo } from 'react';
import {
  FunnelIcon,
  MagnifyingGlassIcon,
  TagIcon,
  ChartBarIcon,
  SwatchIcon,
  AdjustmentsHorizontalIcon,
  EyeIcon,
  EyeSlashIcon,
  ArrowPathIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  XMarkIcon,
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
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

interface EntityTypeFilterProps {
  entities: Entity[];
  relationships?: Relationship[];
  onFilterChange?: (filters: EntityFilters) => void;
  onEntitiesSelected?: (entityIds: string[]) => void;
  className?: string;
  initialFilters?: Partial<EntityFilters>;
  showStats?: boolean;
  enableMultiSelect?: boolean;
}

interface EntityFilters {
  searchTerm: string;
  types: Entity['type'][];
  minConfidence: number;
  maxConfidence: number;
  minMentions: number;
  dateRange: {
    start: string;
    end: string;
  } | null;
  documentIds: string[];
  sortBy: 'name' | 'confidence' | 'mentions' | 'recent';
  sortOrder: 'asc' | 'desc';
  selectedEntityIds: string[];
}

interface EntityTypeStats {
  type: Entity['type'];
  count: number;
  avgConfidence: number;
  totalMentions: number;
  avgRelationships: number;
  color: string;
  icon: React.ComponentType<{ className?: string }>;
}

export const EntityTypeFilter: React.FC<EntityTypeFilterProps> = ({
  entities = [],
  relationships = [],
  onFilterChange,
  onEntitiesSelected,
  className,
  initialFilters,
  showStats = true,
  enableMultiSelect = true,
}) => {
  const [filters, setFilters] = useState<EntityFilters>({
    searchTerm: '',
    types: [],
    minConfidence: 0,
    maxConfidence: 1,
    minMentions: 0,
    dateRange: null,
    documentIds: [],
    sortBy: 'name',
    sortOrder: 'asc',
    selectedEntityIds: [],
    ...initialFilters,
  });

  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set());
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);

  // Entity type configuration
  const entityTypeConfig = useMemo(
    () => ({
      person: {
        label: 'People',
        color: 'bg-blue-100 text-blue-800 border-blue-200',
        icon: () => <span className="text-lg">👤</span>,
      },
      organization: {
        label: 'Organizations',
        color: 'bg-green-100 text-green-800 border-green-200',
        icon: () => <span className="text-lg">🏢</span>,
      },
      location: {
        label: 'Locations',
        color: 'bg-yellow-100 text-yellow-800 border-yellow-200',
        icon: () => <span className="text-lg">📍</span>,
      },
      concept: {
        label: 'Concepts',
        color: 'bg-purple-100 text-purple-800 border-purple-200',
        icon: () => <span className="text-lg">💡</span>,
      },
      date: {
        label: 'Dates',
        color: 'bg-orange-100 text-orange-800 border-orange-200',
        icon: () => <span className="text-lg">📅</span>,
      },
      product: {
        label: 'Products',
        color: 'bg-pink-100 text-pink-800 border-pink-200',
        icon: () => <span className="text-lg">📦</span>,
      },
    }),
    []
  );

  // Calculate statistics for each entity type
  const entityTypeStats = useMemo((): EntityTypeStats[] => {
    const stats: Record<Entity['type'], EntityTypeStats> = {} as any;

    // Initialize stats for all types
    Object.keys(entityTypeConfig).forEach((type) => {
      const config = entityTypeConfig[type as Entity['type']];
      stats[type as Entity['type']] = {
        type: type as Entity['type'],
        count: 0,
        avgConfidence: 0,
        totalMentions: 0,
        avgRelationships: 0,
        color: config.color,
        icon: config.icon,
      };
    });

    // Calculate actual stats
    entities.forEach((entity) => {
      const stat = stats[entity.type];
      stat.count++;
      stat.totalMentions += entity.mentions;
    });

    // Calculate averages
    Object.values(stats).forEach((stat) => {
      if (stat.count > 0) {
        const typeEntities = entities.filter((e) => e.type === stat.type);
        stat.avgConfidence =
          typeEntities.reduce((sum, e) => sum + e.confidence, 0) / stat.count;

        // Calculate average relationships per entity of this type
        const totalRelationships = relationships.filter((r) =>
          typeEntities.some(
            (e) => e.id === r.source_entity_id || e.id === r.target_entity_id
          )
        ).length;
        stat.avgRelationships = totalRelationships / stat.count;
      }
    });

    return Object.values(stats).filter((stat) => stat.count > 0);
  }, [entities, relationships, entityTypeConfig]);

  // Filter entities based on current filters
  const filteredEntities = useMemo(() => {
    let filtered = entities;

    // Search term filter
    if (filters.searchTerm) {
      const term = filters.searchTerm.toLowerCase();
      filtered = filtered.filter(
        (entity) =>
          entity.name.toLowerCase().includes(term) ||
          entity.description?.toLowerCase().includes(term) ||
          entity.aliases.some((alias) => alias.toLowerCase().includes(term))
      );
    }

    // Type filter
    if (filters.types.length > 0) {
      filtered = filtered.filter((entity) =>
        filters.types.includes(entity.type)
      );
    }

    // Confidence filter
    filtered = filtered.filter(
      (entity) =>
        entity.confidence >= filters.minConfidence &&
        entity.confidence <= filters.maxConfidence
    );

    // Mentions filter
    filtered = filtered.filter(
      (entity) => entity.mentions >= filters.minMentions
    );

    // Date range filter
    if (filters.dateRange) {
      const start = new Date(filters.dateRange.start);
      const end = new Date(filters.dateRange.end);
      filtered = filtered.filter((entity) => {
        const entityDate = new Date(entity.first_seen);
        return entityDate >= start && entityDate <= end;
      });
    }

    // Document filter
    if (filters.documentIds.length > 0) {
      filtered = filtered.filter((entity) =>
        entity.document_ids.some((docId) => filters.documentIds.includes(docId))
      );
    }

    // Sort
    filtered.sort((a, b) => {
      let aValue, bValue;

      switch (filters.sortBy) {
        case 'confidence':
          aValue = a.confidence;
          bValue = b.confidence;
          break;
        case 'mentions':
          aValue = a.mentions;
          bValue = b.mentions;
          break;
        case 'recent':
          aValue = new Date(a.last_seen).getTime();
          bValue = new Date(b.last_seen).getTime();
          break;
        default:
          aValue = a.name.toLowerCase();
          bValue = b.name.toLowerCase();
      }

      if (aValue < bValue) return filters.sortOrder === 'asc' ? -1 : 1;
      if (aValue > bValue) return filters.sortOrder === 'asc' ? 1 : -1;
      return 0;
    });

    return filtered;
  }, [entities, filters, relationships]);

  // Update filters and notify parent
  const updateFilters = useCallback(
    (newFilters: Partial<EntityFilters>) => {
      const updatedFilters = { ...filters, ...newFilters };
      setFilters(updatedFilters);
      onFilterChange?.(updatedFilters);
    },
    [filters, onFilterChange]
  );

  // Toggle entity type filter
  const toggleTypeFilter = useCallback(
    (type: Entity['type']) => {
      const newTypes = filters.types.includes(type)
        ? filters.types.filter((t) => t !== type)
        : [...filters.types, type];
      updateFilters({ types: newTypes });
    },
    [filters.types, updateFilters]
  );

  // Toggle entity selection
  const toggleEntitySelection = useCallback(
    (entityId: string) => {
      if (!enableMultiSelect) {
        const newSelected = [entityId];
        updateFilters({ selectedEntityIds: newSelected });
        onEntitiesSelected?.(newSelected);
        return;
      }

      const newSelected = filters.selectedEntityIds.includes(entityId)
        ? filters.selectedEntityIds.filter((id) => id !== entityId)
        : [...filters.selectedEntityIds, entityId];

      updateFilters({ selectedEntityIds: newSelected });
      onEntitiesSelected?.(newSelected);
    },
    [
      filters.selectedEntityIds,
      enableMultiSelect,
      updateFilters,
      onEntitiesSelected,
    ]
  );

  // Select all entities of a type
  const selectAllOfType = useCallback(
    (type: Entity['type']) => {
      const typeEntityIds = filteredEntities
        .filter((e) => e.type === type)
        .map((e) => e.id);

      if (enableMultiSelect) {
        const newSelected = Array.from(
          new Set([...filters.selectedEntityIds, ...typeEntityIds])
        );
        updateFilters({ selectedEntityIds: newSelected });
        onEntitiesSelected?.(newSelected);
      }
    },
    [
      filteredEntities,
      filters.selectedEntityIds,
      enableMultiSelect,
      updateFilters,
      onEntitiesSelected,
    ]
  );

  // Clear all filters
  const clearAllFilters = useCallback(() => {
    const clearedFilters: EntityFilters = {
      searchTerm: '',
      types: [],
      minConfidence: 0,
      maxConfidence: 1,
      minMentions: 0,
      dateRange: null,
      documentIds: [],
      sortBy: 'name',
      sortOrder: 'asc',
      selectedEntityIds: [],
    };
    setFilters(clearedFilters);
    onFilterChange?.(clearedFilters);
    onEntitiesSelected?.([]);
  }, [onFilterChange, onEntitiesSelected]);

  // Toggle type expansion
  const toggleTypeExpansion = useCallback((type: string) => {
    setExpandedTypes((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(type)) {
        newSet.delete(type);
      } else {
        newSet.add(type);
      }
      return newSet;
    });
  }, []);

  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString();
  };

  return (
    <div className={cn('space-y-6', className)}>
      {/* Quick Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center">
              <FunnelIcon className="h-5 w-5 mr-2" />
              Entity Filters
            </div>
            <Button variant="ghost" size="sm" onClick={clearAllFilters}>
              <ArrowPathIcon className="h-4 w-4 mr-2" />
              Reset
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Search */}
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                <MagnifyingGlassIcon className="h-4 w-4 inline mr-1" />
                Search Entities
              </label>
              <Input
                value={filters.searchTerm}
                onChange={(e) => updateFilters({ searchTerm: e.target.value })}
                placeholder="Search by name, description, or aliases..."
                className="w-full"
              />
            </div>

            {/* Type Quick Filters */}
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                <TagIcon className="h-4 w-4 inline mr-1" />
                Entity Types
              </label>
              <div className="flex flex-wrap gap-2">
                {entityTypeStats.map((stat) => (
                  <Button
                    key={stat.type}
                    variant={
                      filters.types.includes(stat.type) ? 'default' : 'outline'
                    }
                    size="sm"
                    onClick={() => toggleTypeFilter(stat.type)}
                    className={cn(
                      'h-8',
                      filters.types.includes(stat.type)
                        ? ''
                        : stat.color.replace('text-', 'border-')
                    )}
                  >
                    <span className="mr-2">
                      <stat.icon />
                    </span>
                    {stat.type} ({stat.count})
                  </Button>
                ))}
              </div>
            </div>

            {/* Sort Controls */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Sort By
                </label>
                <Select
                  value={filters.sortBy}
                  onValueChange={(value: any) =>
                    updateFilters({ sortBy: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="name">Name</SelectItem>
                    <SelectItem value="confidence">Confidence</SelectItem>
                    <SelectItem value="mentions">Mentions</SelectItem>
                    <SelectItem value="recent">Most Recent</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  Order
                </label>
                <Select
                  value={filters.sortOrder}
                  onValueChange={(value: any) =>
                    updateFilters({ sortOrder: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="asc">Ascending</SelectItem>
                    <SelectItem value="desc">Descending</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Advanced Filters Toggle */}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
              className="w-full"
            >
              <AdjustmentsHorizontalIcon className="h-4 w-4 mr-2" />
              {showAdvancedFilters ? 'Hide' : 'Show'} Advanced Filters
              <ChevronDownIcon
                className={cn(
                  'h-4 w-4 ml-2 transition-transform',
                  showAdvancedFilters && 'rotate-180'
                )}
              />
            </Button>

            {/* Advanced Filters */}
            {showAdvancedFilters && (
              <div className="space-y-4 pt-4 border-t">
                {/* Confidence Range */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Confidence Range: {Math.round(filters.minConfidence * 100)}%
                    - {Math.round(filters.maxConfidence * 100)}%
                  </label>
                  <div className="space-y-2">
                    <Progress
                      value={filters.minConfidence * 100}
                      className="h-2"
                    />
                    <Progress
                      value={filters.maxConfidence * 100}
                      className="h-2"
                    />
                  </div>
                </div>

                {/* Minimum Mentions */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Minimum Mentions: {filters.minMentions}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={filters.minMentions}
                    onChange={(e) =>
                      updateFilters({ minMentions: parseInt(e.target.value) })
                    }
                    className="w-full"
                  />
                </div>

                {/* Selection Info */}
                {enableMultiSelect && (
                  <div className="flex items-center justify-between p-3 bg-blue-50 rounded">
                    <span className="text-sm text-blue-800">
                      {filters.selectedEntityIds.length} entities selected
                    </span>
                    {filters.selectedEntityIds.length > 0 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          updateFilters({ selectedEntityIds: [] });
                          onEntitiesSelected?.([]);
                        }}
                      >
                        <XMarkIcon className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Entity Statistics */}
      {showStats && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <ChartBarIcon className="h-5 w-5 mr-2" />
              Entity Statistics
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Overall Stats */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                <div>
                  <div className="text-2xl font-bold text-foreground">
                    {entities.length}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Total Entities
                  </div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-foreground">
                    {filteredEntities.length}
                  </div>
                  <div className="text-sm text-muted-foreground">Filtered</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-foreground">
                    {entityTypeStats.length}
                  </div>
                  <div className="text-sm text-muted-foreground">Types</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-foreground">
                    {entities.reduce((sum, e) => sum + e.mentions, 0)}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Total Mentions
                  </div>
                </div>
              </div>

              {/* Type Breakdown */}
              <div>
                <h4 className="font-medium text-foreground mb-3">
                  Type Breakdown
                </h4>
                <div className="space-y-2">
                  {entityTypeStats.map((stat) => {
                    const percentage = (stat.count / entities.length) * 100;
                    return (
                      <div
                        key={stat.type}
                        className="flex items-center space-x-3"
                      >
                        <span className="text-lg">
                          <stat.icon />
                        </span>
                        <div className="flex-1">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-medium">
                              {stat.type}
                            </span>
                            <span className="text-sm text-muted-foreground">
                              {stat.count} ({percentage.toFixed(1)}%)
                            </span>
                          </div>
                          <Progress value={percentage} className="h-2" />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Categorized Entity List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center">
              <SwatchIcon className="h-5 w-5 mr-2" />
              Entity Categories
            </div>
            <span className="text-sm text-muted-foreground">
              Showing {filteredEntities.length} of {entities.length} entities
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {entityTypeStats.map((stat) => {
              const typeEntities = filteredEntities.filter(
                (e) => e.type === stat.type
              );
              const isExpanded = expandedTypes.has(stat.type);
              const allOfTypeSelected =
                enableMultiSelect &&
                typeEntities.every((e) =>
                  filters.selectedEntityIds.includes(e.id)
                );
              const someOfTypeSelected =
                enableMultiSelect &&
                typeEntities.some((e) =>
                  filters.selectedEntityIds.includes(e.id)
                );

              return (
                <div key={stat.type} className="border rounded-lg">
                  {/* Type Header */}
                  <div
                    className="flex items-center justify-between p-4 bg-gray-50 cursor-pointer hover:bg-gray-100"
                    onClick={() => toggleTypeExpansion(stat.type)}
                  >
                    <div className="flex items-center space-x-3">
                      <ChevronRightIcon
                        className={cn(
                          'h-4 w-4 transition-transform',
                          isExpanded && 'rotate-90'
                        )}
                      />
                      <span className="text-lg">
                        <stat.icon />
                      </span>
                      <div>
                        <div className="font-medium">{stat.type}</div>
                        <div className="text-sm text-muted-foreground">
                          {typeEntities.length} entities • Avg. confidence:{' '}
                          {Math.round(stat.avgConfidence * 100)}% • Total
                          mentions: {formatNumber(stat.totalMentions)}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2">
                      {enableMultiSelect && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            selectAllOfType(stat.type);
                          }}
                          className={cn(
                            'h-6 px-2',
                            allOfTypeSelected && 'text-blue-600'
                          )}
                        >
                          {allOfTypeSelected ? (
                            <EyeSlashIcon className="h-4 w-4" />
                          ) : (
                            <EyeIcon className="h-4 w-4" />
                          )}
                        </Button>
                      )}
                      <Badge className={stat.color}>{stat.count}</Badge>
                    </div>
                  </div>

                  {/* Entity List */}
                  {isExpanded && typeEntities.length > 0 && (
                    <div className="border-t max-h-96 overflow-auto">
                      <div className="p-2 space-y-1">
                        {typeEntities.map((entity) => {
                          const isSelected =
                            enableMultiSelect &&
                            filters.selectedEntityIds.includes(entity.id);
                          const EntityIcon =
                            entityTypeConfig[entity.type]?.icon ||
                            (() => <span>📄</span>);

                          return (
                            <div
                              key={entity.id}
                              className={cn(
                                'flex items-center justify-between p-3 rounded-lg cursor-pointer hover:bg-gray-50',
                                isSelected &&
                                  'bg-blue-50 border border-blue-200'
                              )}
                              onClick={() => toggleEntitySelection(entity.id)}
                            >
                              <div className="flex items-center space-x-3">
                                {enableMultiSelect && (
                                  <div
                                    className={cn(
                                      'w-4 h-4 rounded border-2 flex items-center justify-center',
                                      isSelected
                                        ? 'bg-blue-600 border-blue-600'
                                        : 'border-border'
                                    )}
                                  >
                                    {isSelected && (
                                      <span className="text-white text-xs">
                                        ✓
                                      </span>
                                    )}
                                  </div>
                                )}
                                <EntityIcon />
                                <div>
                                  <div className="font-medium text-sm">
                                    {entity.name}
                                  </div>
                                  <div className="flex items-center space-x-2 text-xs text-muted-foreground">
                                    <span>
                                      {Math.round(entity.confidence * 100)}%
                                      confidence
                                    </span>
                                    <span>•</span>
                                    <span>{entity.mentions} mentions</span>
                                    {entity.aliases.length > 0 && (
                                      <>
                                        <span>•</span>
                                        <span>
                                          {entity.aliases.length} aliases
                                        </span>
                                      </>
                                    )}
                                  </div>
                                  {entity.description && (
                                    <div className="text-xs text-foreground mt-1 line-clamp-1">
                                      {entity.description}
                                    </div>
                                  )}
                                </div>
                              </div>

                              <Badge variant="outline" className="text-xs">
                                {formatDate(entity.first_seen)}
                              </Badge>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {isExpanded && typeEntities.length === 0 && (
                    <div className="border-t p-8 text-center text-muted-foreground">
                      No entities of this type match the current filters.
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default EntityTypeFilter;
