/**
 * Entity Management Page
 * Provides a comprehensive interface for viewing, editing, and managing entities
 */

'use client';

import React, {
  useState,
  useEffect,
  useCallback,
  useMemo,
  Suspense,
} from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion, MotionConfig } from 'framer-motion';
import {
  Plus,
  Download,
  RefreshCw,
  Network,
  TrendingUp,
  Database,
  Filter,
  BarChart3,
  PieChart,
  Loader2,
  List,
  Route,
  Search,
  Layers,
  FileSearch,
  GitMerge,
  HeartPulse,
  AlertTriangle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { EntityList } from '@/components/entities/EntityList';
import { EntityForm } from '@/components/entities/EntityForm';
import { EntityDetail } from '@/components/entities/EntityDetail';
import { EntityGraph } from '@/components/entities/EntityGraph';
import {
  EntityFilters,
  SortField,
  SortOrder,
} from '@/components/entities/EntityFilters';
import { Pagination } from '@/components/entities/Pagination';
import { RelationshipForm } from '@/components/entities/RelationshipForm';
import { PathFinder } from '@/components/entities/PathFinder';
import { NeighborhoodExplorer } from '@/components/entities/NeighborhoodExplorer';
import { GraphAnalyticsDashboard } from '@/components/entities/GraphAnalyticsDashboard';
import { EntitySearch } from '@/components/entities/EntitySearch';
import { BulkOperations } from '@/components/entities/BulkOperations';
import { DocumentEntityExtractor } from '@/components/entities/DocumentEntityExtractor';
import { EntityMergeTool } from '@/components/entities/EntityMergeTool';
import { GraphHealthMonitor } from '@/components/entities/GraphHealthMonitor';
import { EntityErrorBoundary } from '@/components/entities/EntityErrorBoundary';
import { KeyboardShortcutsDialog } from '@/components/entities/KeyboardShortcutsDialog';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { useEntityPermissions } from '@/hooks/useEntityPermissions';
import { Entity, EntityType, GraphEdge } from '@/types/entity';
import {
  entityService,
  PaginatedEntitiesResponse,
} from '@/services/entityService';
import { APIErrorClass } from '@/types/api';
import { cn } from '@/lib/utils';
import toast from 'react-hot-toast';

const isServiceUnavailableError = (error: unknown): boolean => {
  if (error instanceof APIErrorClass) {
    const message = error.error.message?.toLowerCase() || '';
    return (
      error.error.status_code >= 500 ||
      message.includes('service unavailable') ||
      message.includes('circuit breaker')
    );
  }
  const message =
    error instanceof Error
      ? error.message.toLowerCase()
      : String(error).toLowerCase();
  return (
    message.includes('service unavailable') ||
    message.includes('circuit breaker')
  );
};

const logEntityPageError = (context: string, error: unknown) => {
  if (isServiceUnavailableError(error)) {
    console.warn(`${context}:`, error);
    return;
  }
  console.error(`${context}:`, error);
};

function EntityManagementContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { canCreate, canEdit, canDelete } = useEntityPermissions();

  // Core state
  const [entities, setEntities] = useState<Entity[]>([]);
  const [graphEntities, setGraphEntities] = useState<Entity[]>([]);
  const [relationships, setRelationships] = useState<GraphEdge[]>([]);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [loading, setLoading] = useState(true);
  const [relationshipsLoading, setRelationshipsLoading] = useState(false);
  const [serviceUnavailable, setServiceUnavailable] = useState(false);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(100);
  const [totalEntities, setTotalEntities] = useState(0);

  // Filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTypes, setSelectedTypes] = useState<EntityType[]>([]);
  const [confidenceRange, setConfidenceRange] = useState<[number, number]>([
    0, 100,
  ]);
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  // UI state - initialize from URL params
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'list');
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [relationshipDialogOpen, setRelationshipDialogOpen] = useState(false);
  const [sourceEntityId, setSourceEntityId] = useState<string | null>(null);
  const [shortcutsDialogOpen, setShortcutsDialogOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Dynamic types from API
  const [availableEntityTypes, setAvailableEntityTypes] = useState<string[]>(
    []
  );
  const [availableRelationshipTypes, setAvailableRelationshipTypes] = useState<
    string[]
  >([]);
  const [typeCounts, setTypeCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    setMounted(true);

    // Initialize state from URL params
    const tab = searchParams.get('tab');
    const entityId = searchParams.get('entity');
    const page = searchParams.get('page');
    const types = searchParams.get('types');

    if (tab) setActiveTab(tab);
    if (page) setCurrentPage(parseInt(page));
    if (types) {
      setSelectedTypes(types.split(',') as EntityType[]);
    }
  }, []);

  // Update URL when state changes
  useEffect(() => {
    if (!mounted) return;

    const params = new URLSearchParams();
    if (activeTab !== 'list') params.set('tab', activeTab);
    if (currentPage !== 1) params.set('page', currentPage.toString());
    if (selectedTypes.length > 0) params.set('types', selectedTypes.join(','));
    if (selectedEntity) params.set('entity', selectedEntity.id);

    const newUrl = params.toString() ? `?${params.toString()}` : '/entities';
    router.replace(newUrl, { scroll: false });
  }, [activeTab, currentPage, selectedTypes, selectedEntity, mounted, router]);

  // Fetch available types and analytics on mount
  useEffect(() => {
    const fetchTypesAndAnalytics = async () => {
      try {
        const [entityTypes, relationshipTypes, analytics] = await Promise.all([
          entityService.getEntityTypes(),
          entityService.getRelationshipTypes(),
          entityService.getAnalytics(),
        ]);
        setAvailableEntityTypes(entityTypes);
        setAvailableRelationshipTypes(relationshipTypes);
        setTypeCounts(analytics.entity_type_counts || {});
      } catch (error) {
        logEntityPageError('Error fetching types and analytics', error);
        if (isServiceUnavailableError(error)) {
          setServiceUnavailable(true);
        } else {
          toast.error('Failed to load entity types and analytics');
        }
      }
    };
    fetchTypesAndAnalytics();
  }, []);

  // Fetch entities with pagination
  const fetchEntities = useCallback(async () => {
    try {
      setLoading(true);
      const offset = (currentPage - 1) * pageSize;
      const response = await entityService.getEntities(
        pageSize,
        offset,
        selectedTypes.length > 0 ? selectedTypes : undefined
      );

      // Handle paginated response
      const paginatedResponse = response as PaginatedEntitiesResponse;

      // Convert EntityResponse to Entity format for display
      const convertedEntities: Entity[] = paginatedResponse.entities.map(
        (entity) => ({
          id: entity.id,
          name: entity.name,
          type: entity.entity_type,
          confidence: entity.confidence_score,
          confidence_score: entity.confidence_score,
          extraction_method: entity.extraction_method,
          position: entity.position,
          context: entity.context,
          metadata: entity.metadata,
          created_at: entity.created_at,
          updated_at: entity.updated_at,
          source_document_id: entity.source_document_id,
        })
      );

      setEntities(convertedEntities);
      setTotalEntities(paginatedResponse.total);
      setServiceUnavailable(false);
    } catch (error) {
      logEntityPageError('Error fetching entities', error);
      if (isServiceUnavailableError(error)) {
        setServiceUnavailable(true);
      } else {
        toast.error('Failed to fetch entities');
      }
      setEntities([]);
      setTotalEntities(0);
    } finally {
      setLoading(false);
    }
  }, [currentPage, pageSize, selectedTypes]);

  // Fetch relationships and connected entities for graph view
  const fetchRelationships = useCallback(async () => {
    try {
      setRelationshipsLoading(true);
      const [rels, connectedResponse] = await Promise.all([
        entityService.getAllRelationships(200),
        entityService.getEntities(200, 0, undefined, true),
      ]);
      setRelationships(rels);

      const paginatedResponse = connectedResponse as PaginatedEntitiesResponse;
      const converted: Entity[] = paginatedResponse.entities.map((entity) => ({
        id: entity.id,
        name: entity.name,
        type: entity.entity_type,
        confidence: entity.confidence_score,
        confidence_score: entity.confidence_score,
        extraction_method: entity.extraction_method,
        position: entity.position,
        context: entity.context,
        metadata: entity.metadata,
        created_at: entity.created_at,
        updated_at: entity.updated_at,
        source_document_id: entity.source_document_id,
      }));
      setGraphEntities(converted);
    } catch (error) {
      logEntityPageError('Error fetching relationships', error);
      if (isServiceUnavailableError(error)) {
        setServiceUnavailable(true);
      }
      setRelationships([]);
      setGraphEntities([]);
    } finally {
      setRelationshipsLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchEntities();
  }, [fetchEntities]);

  // Fetch relationships and connected entities when switching to graph tab
  useEffect(() => {
    if (activeTab === 'graph' && graphEntities.length === 0) {
      fetchRelationships();
    }
  }, [activeTab, graphEntities.length, fetchRelationships]);

  // Client-side filtering and sorting
  const filteredEntities = useMemo(() => {
    let filtered = [...entities];

    // Filter by entity type (including special null type filter)
    if (selectedTypes.length > 0) {
      const hasNullFilter = selectedTypes.includes('__null__' as EntityType);
      const regularTypes = selectedTypes.filter(
        (t) => t !== ('__null__' as any)
      );

      filtered = filtered.filter((entity) => {
        const entityType = entity.type as string;
        const isNullType =
          !entityType || entityType === '' || entityType === 'null';
        const matchesRegularType =
          regularTypes.length === 0 || regularTypes.includes(entity.type);

        if (hasNullFilter && regularTypes.length > 0) {
          // Include both null types AND regular selected types
          return isNullType || matchesRegularType;
        } else if (hasNullFilter) {
          // Only null types
          return isNullType;
        } else {
          // Only regular selected types
          return matchesRegularType;
        }
      });
    }

    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (entity) =>
          entity.name.toLowerCase().includes(query) ||
          (entity.type && entity.type.toLowerCase().includes(query)) ||
          entity.metadata?.description?.toLowerCase().includes(query)
      );
    }

    // Filter by confidence range
    filtered = filtered.filter((entity) => {
      const confidence = (entity.confidence || 0) * 100;
      return (
        confidence >= confidenceRange[0] && confidence <= confidenceRange[1]
      );
    });

    // Sort
    filtered.sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'confidence':
          comparison = (a.confidence || 0) - (b.confidence || 0);
          break;
        case 'created_at':
          comparison =
            new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
          break;
        case 'type':
          comparison = (a.type || '').localeCompare(b.type || '');
          break;
      }
      return sortOrder === 'asc' ? comparison : -comparison;
    });

    return filtered;
  }, [
    entities,
    selectedTypes,
    searchQuery,
    confidenceRange,
    sortField,
    sortOrder,
  ]);

  // Calculate statistics
  const statistics = useMemo(() => {
    const typeDistribution: Record<string, number> = {};
    let totalConfidence = 0;
    let confidenceCount = 0;

    entities.forEach((entity) => {
      // Type distribution
      typeDistribution[entity.type] = (typeDistribution[entity.type] || 0) + 1;

      // Average confidence
      if (entity.confidence) {
        totalConfidence += entity.confidence;
        confidenceCount++;
      }
    });

    return {
      totalEntities,
      uniqueTypes: Object.keys(typeDistribution).length,
      averageConfidence:
        confidenceCount > 0 ? totalConfidence / confidenceCount : 0,
      typeDistribution,
      totalRelationships: relationships.length,
    };
  }, [entities, totalEntities, relationships.length]);

  // Handlers
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  const handlePageSizeChange = (size: number) => {
    setPageSize(size);
    setCurrentPage(1); // Reset to first page
  };

  const handleTypesChange = (types: EntityType[]) => {
    setSelectedTypes(types);
    setCurrentPage(1); // Reset to first page when filter changes
  };

  const handleSortChange = (field: SortField, order: SortOrder) => {
    setSortField(field);
    setSortOrder(order);
  };

  const handleClearFilters = () => {
    setSearchQuery('');
    setSelectedTypes([]);
    setConfidenceRange([0, 100]);
    setSortField('created_at');
    setSortOrder('desc');
    setCurrentPage(1);
  };

  const handleEntityUpdate = async (
    entityId: string,
    updates: Partial<Entity>
  ) => {
    try {
      await entityService.updateEntity(entityId, updates);
      await fetchEntities();
      setEditDialogOpen(false);
      toast.success('Entity updated successfully');
    } catch (error) {
      logEntityPageError('Error updating entity', error);
      toast.error('Failed to update entity');
    }
  };

  const handleEntityDelete = async (entityId: string) => {
    if (
      !window.confirm(
        'Are you sure you want to delete this entity and all its relationships?'
      )
    ) {
      return;
    }

    try {
      await entityService.deleteEntity(entityId);
      await fetchEntities();
      toast.success('Entity deleted successfully');
    } catch (error) {
      logEntityPageError('Error deleting entity', error);
      toast.error('Failed to delete entity');
    }
  };

  const exportEntities = () => {
    const dataStr = JSON.stringify(filteredEntities, null, 2);
    const dataUri =
      'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
    const exportFileDefaultName = `entities-${new Date().toISOString().split('T')[0]}.json`;
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const handleAddRelationship = (entityId: string) => {
    setSourceEntityId(entityId);
    setRelationshipDialogOpen(true);
  };

  const handleCreateRelationship = async (data: {
    source_entity_id: string;
    target_entity_id: string;
    relationship_type: string;
    strength?: number;
    confidence_score?: number;
    context?: string;
    evidence?: string[];
    metadata?: Record<string, unknown>;
  }) => {
    try {
      await entityService.createRelationship(data);
      toast.success('Relationship created successfully');
      setRelationshipDialogOpen(false);
      setSourceEntityId(null);
      // Refresh relationships if on graph tab
      if (activeTab === 'graph') {
        fetchRelationships();
      }
    } catch (error) {
      logEntityPageError('Error creating relationship', error);
      toast.error('Failed to create relationship');
    }
  };

  const totalPages = Math.ceil(totalEntities / pageSize);

  // Keyboard shortcuts
  useKeyboardShortcuts(
    [
      {
        key: 'n',
        ctrl: true,
        action: () => {
          setSelectedEntity(null);
          setEditDialogOpen(true);
        },
        description: 'Create new entity',
      },
      {
        key: 'r',
        ctrl: true,
        action: () => {
          fetchEntities();
          if (activeTab === 'graph') fetchRelationships();
        },
        description: 'Refresh data',
      },
      {
        key: 'e',
        ctrl: true,
        shift: true,
        action: exportEntities,
        description: 'Export data',
      },
      {
        key: 'g',
        action: () => setActiveTab('graph'),
        description: 'Toggle graph view',
      },
      {
        key: 'a',
        action: () => setActiveTab('analytics'),
        description: 'Toggle analytics',
      },
      {
        key: 'p',
        action: () => setActiveTab('pathfinder'),
        description: 'Open path finder',
      },
      {
        key: 'b',
        action: () => setActiveTab('bulk'),
        description: 'Open bulk operations',
      },
      {
        key: 'h',
        action: () => setActiveTab('health'),
        description: 'Open health monitor',
      },
      {
        key: 'm',
        action: () => setActiveTab('merge'),
        description: 'Open merge tool',
      },
      {
        key: 'd',
        action: () => setActiveTab('extractor'),
        description: 'Open document extractor',
      },
      {
        key: '?',
        action: () => setShortcutsDialogOpen(true),
        description: 'Show keyboard shortcuts',
      },
    ],
    mounted
  );

  if (!mounted) return null;

  return (
    <MotionConfig reducedMotion="user">
      <div className="min-h-screen bg-background flex flex-col">
        <div className="p-6 space-y-4 flex-1 overflow-y-auto">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-border bg-card p-6 shadow-sm"
          >
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Network
                    aria-hidden="true"
                    className="w-6 h-6 text-primary"
                  />
                </div>
                <div>
                  <h1 className="text-xl font-semibold text-foreground">
                    Entities
                  </h1>
                  <p className="text-sm text-muted-foreground mt-0.5">
                    Browse and manage your knowledge-graph entities
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    fetchEntities();
                    if (activeTab === 'graph') fetchRelationships();
                  }}
                  disabled={loading}
                >
                  <RefreshCw
                    aria-hidden="true"
                    className={cn('h-4 w-4 mr-1.5', loading && 'animate-spin')}
                  />
                  Refresh
                </Button>
                <Button variant="outline" size="sm" onClick={exportEntities}>
                  <Download aria-hidden="true" className="h-4 w-4 mr-1.5" />
                  Export
                </Button>
                <Button
                  size="sm"
                  onClick={() => {
                    setSelectedEntity(null);
                    setEditDialogOpen(true);
                  }}
                  disabled={!canCreate}
                >
                  <Plus aria-hidden="true" className="h-4 w-4 mr-1.5" />
                  New entity
                  {!canCreate && (
                    <span className="ml-1 text-xs opacity-80">(admin)</span>
                  )}
                </Button>
              </div>
            </div>
          </motion.div>

          {/* Service Unavailable Banner */}
          {serviceUnavailable && (
            <Card
              role="alert"
              className="border-destructive/40 bg-destructive/5"
            >
              <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center gap-3">
                <AlertTriangle
                  aria-hidden="true"
                  className="w-5 h-5 text-destructive shrink-0"
                />
                <div className="flex-1">
                  <p className="text-sm font-medium text-foreground">
                    Knowledge graph unavailable
                  </p>
                  <p className="text-sm text-muted-foreground mt-1">
                    The graph database is currently unreachable, so entity data
                    cannot be loaded.
                  </p>
                </div>
                <Button
                  onClick={() => {
                    setServiceUnavailable(false);
                    fetchEntities();
                    if (activeTab === 'graph') fetchRelationships();
                  }}
                  variant="outline"
                  size="sm"
                  className="sm:ml-auto shrink-0"
                >
                  <RefreshCw aria-hidden="true" className="w-4 h-4 mr-1.5" />
                  Retry
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Filters */}
          <Card className="border-border bg-card shadow-sm">
            <CardContent className="p-4">
              <EntityFilters
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
                selectedTypes={selectedTypes}
                onTypesChange={handleTypesChange}
                confidenceRange={confidenceRange}
                onConfidenceChange={setConfidenceRange}
                sortField={sortField}
                sortOrder={sortOrder}
                onSortChange={handleSortChange}
                onClearFilters={handleClearFilters}
                totalCount={totalEntities}
                filteredCount={filteredEntities.length}
                availableTypes={
                  availableEntityTypes.length > 0
                    ? availableEntityTypes
                    : undefined
                }
                typeCounts={typeCounts}
              />
            </CardContent>
          </Card>

          {/* Workspace Area */}
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="w-full"
          >
            <div className="mb-4 space-y-2">
              {/* View group */}
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-xs font-medium text-muted-foreground w-16 shrink-0">
                  View
                </span>
                <TabsList className="bg-muted/40 border border-border p-1 rounded-lg">
                  <TabsTrigger
                    value="list"
                    className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary text-xs gap-1.5"
                  >
                    <List aria-hidden="true" className="h-3.5 w-3.5" />
                    List
                  </TabsTrigger>
                  <TabsTrigger
                    value="graph"
                    className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary text-xs gap-1.5"
                  >
                    <Network aria-hidden="true" className="h-3.5 w-3.5" />
                    Graph
                  </TabsTrigger>
                  <TabsTrigger
                    value="pathfinder"
                    className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary text-xs gap-1.5"
                  >
                    <Route aria-hidden="true" className="h-3.5 w-3.5" />
                    Path finder
                  </TabsTrigger>
                  <TabsTrigger
                    value="search"
                    className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary text-xs gap-1.5"
                  >
                    <Search aria-hidden="true" className="h-3.5 w-3.5" />
                    Search
                  </TabsTrigger>
                </TabsList>

                {/* Actions group */}
                <span className="text-xs font-medium text-muted-foreground w-16 shrink-0 ml-2">
                  Actions
                </span>
                <TabsList className="bg-muted/40 border border-border p-1 rounded-lg">
                  <TabsTrigger
                    value="bulk"
                    className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary text-xs gap-1.5"
                  >
                    <Layers aria-hidden="true" className="h-3.5 w-3.5" />
                    Bulk
                  </TabsTrigger>
                  <TabsTrigger
                    value="extractor"
                    className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary text-xs gap-1.5"
                  >
                    <FileSearch aria-hidden="true" className="h-3.5 w-3.5" />
                    Extract
                  </TabsTrigger>
                  <TabsTrigger
                    value="merge"
                    className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary text-xs gap-1.5"
                  >
                    <GitMerge aria-hidden="true" className="h-3.5 w-3.5" />
                    Merge
                  </TabsTrigger>
                </TabsList>
              </div>

              {/* Monitor group */}
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-xs font-medium text-muted-foreground w-16 shrink-0">
                  Monitor
                </span>
                <TabsList className="bg-muted/40 border border-border p-1 rounded-lg">
                  <TabsTrigger
                    value="statistics"
                    className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary text-xs gap-1.5"
                  >
                    <TrendingUp aria-hidden="true" className="h-3.5 w-3.5" />
                    Metrics
                  </TabsTrigger>
                  <TabsTrigger
                    value="analytics"
                    className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary text-xs gap-1.5"
                  >
                    <BarChart3 aria-hidden="true" className="h-3.5 w-3.5" />
                    Analytics
                  </TabsTrigger>
                  <TabsTrigger
                    value="health"
                    className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary text-xs gap-1.5"
                  >
                    <HeartPulse aria-hidden="true" className="h-3.5 w-3.5" />
                    Health
                  </TabsTrigger>
                </TabsList>
              </div>
            </div>

            <TabsContent value="list" className="mt-0 outline-none">
              <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
                <EntityList
                  entities={filteredEntities}
                  loading={loading}
                  onEdit={(entity) => {
                    setSelectedEntity(entity);
                    setEditDialogOpen(true);
                  }}
                  onView={(entity) => {
                    setSelectedEntity(entity);
                    setDetailDialogOpen(true);
                  }}
                  onDelete={handleEntityDelete}
                />
                <Pagination
                  currentPage={currentPage}
                  totalPages={totalPages}
                  pageSize={pageSize}
                  totalItems={totalEntities}
                  onPageChange={handlePageChange}
                  onPageSizeChange={handlePageSizeChange}
                />
              </div>
            </TabsContent>

            <TabsContent value="graph" className="mt-0 outline-none">
              <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm p-4">
                {relationshipsLoading ? (
                  <div
                    role="status"
                    aria-label="Loading graph data"
                    className="space-y-4"
                  >
                    <div className="flex items-center justify-between">
                      <div className="h-4 w-40 rounded bg-muted animate-pulse" />
                      <div className="h-4 w-24 rounded bg-muted animate-pulse" />
                    </div>
                    <div className="h-[600px] rounded-lg border border-border bg-muted/30 animate-pulse" />
                    <p className="text-sm text-muted-foreground">
                      Loading connected nodes and relationships…
                    </p>
                  </div>
                ) : (
                  <EntityGraph
                    entities={graphEntities}
                    relationships={relationships}
                    onEntityClick={(entity) => {
                      setSelectedEntity(entity);
                      setDetailDialogOpen(true);
                    }}
                    height={600}
                  />
                )}
              </div>
            </TabsContent>

            <TabsContent
              value="statistics"
              className="mt-0 outline-none space-y-6"
            >
              {/* Summary Cards */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[
                  {
                    label: 'Total entities',
                    value: statistics.totalEntities.toLocaleString(),
                    icon: Database,
                  },
                  {
                    label: 'Unique types',
                    value: statistics.uniqueTypes,
                    icon: Filter,
                  },
                  {
                    label: 'Avg confidence',
                    value: `${(statistics.averageConfidence * 100).toFixed(1)}%`,
                    icon: TrendingUp,
                  },
                  {
                    label: 'Relationships',
                    value: statistics.totalRelationships.toLocaleString(),
                    icon: Network,
                  },
                ].map((stat) => (
                  <Card
                    key={stat.label}
                    className="border-border bg-card shadow-sm"
                  >
                    <CardHeader className="p-4 pb-1">
                      <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-2">
                        <stat.icon
                          aria-hidden="true"
                          className="w-3.5 h-3.5 text-primary"
                        />
                        {stat.label}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="p-4 pt-0">
                      <p className="text-2xl font-semibold text-foreground tabular-nums">
                        {stat.value}
                      </p>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Type Distribution */}
              <Card className="border-border bg-card shadow-sm">
                <CardHeader className="border-b border-border py-3 bg-muted/30">
                  <CardTitle className="text-sm font-medium text-foreground flex items-center gap-2">
                    <BarChart3
                      aria-hidden="true"
                      className="w-4 h-4 text-muted-foreground"
                    />
                    Type distribution
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4">
                  {Object.keys(statistics.typeDistribution).length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No entities loaded yet. Create an entity or adjust your
                      filters to see how types are distributed.
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {Object.entries(statistics.typeDistribution)
                        .sort(([, a], [, b]) => b - a)
                        .map(([type, count]) => {
                          const percentage = (count / entities.length) * 100;
                          return (
                            <div key={type} className="space-y-1">
                              <div className="flex justify-between text-sm">
                                <span className="text-foreground">{type}</span>
                                <span className="text-muted-foreground tabular-nums">
                                  {count} ({percentage.toFixed(1)}%)
                                </span>
                              </div>
                              <div
                                className="h-2 bg-border rounded-full overflow-hidden"
                                role="progressbar"
                                aria-valuenow={Math.round(percentage)}
                                aria-valuemin={0}
                                aria-valuemax={100}
                                aria-label={`${type} share of entities`}
                              >
                                <motion.div
                                  initial={{ width: 0 }}
                                  animate={{ width: `${percentage}%` }}
                                  transition={{ duration: 0.25 }}
                                  className="h-full bg-primary rounded-full"
                                />
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Path Finder Tab */}
            <TabsContent value="pathfinder" className="mt-0 outline-none">
              <PathFinder
                entities={entities}
                onEntityClick={(entityId) => {
                  const entity = entities.find((e) => e.id === entityId);
                  if (entity) {
                    setSelectedEntity(entity);
                    setDetailDialogOpen(true);
                  }
                }}
              />
            </TabsContent>

            {/* Enhanced Search Tab */}
            <TabsContent value="search" className="mt-0 outline-none">
              <EntitySearch
                onEntityClick={(entityId) => {
                  const entity = entities.find((e) => e.id === entityId);
                  if (entity) {
                    setSelectedEntity(entity);
                    setDetailDialogOpen(true);
                  }
                }}
              />
            </TabsContent>

            {/* Analytics Dashboard Tab */}
            <TabsContent value="analytics" className="mt-0 outline-none">
              <GraphAnalyticsDashboard
                onTypeClick={(entityType) => {
                  // Filter by clicked entity type
                  setSelectedTypes([entityType]);
                  setCurrentPage(1);
                  // Switch to list tab to show filtered results
                  setActiveTab('list');
                  toast.success(`Filtered by ${entityType}`);
                }}
              />
            </TabsContent>

            {/* Bulk Operations Tab */}
            <TabsContent value="bulk" className="mt-0 outline-none">
              <BulkOperations />
            </TabsContent>

            {/* Document Entity Extractor Tab */}
            <TabsContent value="extractor" className="mt-0 outline-none">
              <DocumentEntityExtractor />
            </TabsContent>

            {/* Entity Merge Tool Tab */}
            <TabsContent value="merge" className="mt-0 outline-none">
              <EntityMergeTool />
            </TabsContent>

            {/* Graph Health Monitor Tab */}
            <TabsContent value="health" className="mt-0 outline-none">
              <GraphHealthMonitor />
            </TabsContent>
          </Tabs>
        </div>

        {/* Edit/Create Dialog */}
        <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
          <DialogContent className="max-w-2xl bg-card border-border text-foreground">
            <DialogHeader className="border-b border-border pb-4">
              <DialogTitle className="text-lg font-semibold">
                {selectedEntity ? 'Edit entity' : 'New entity'}
              </DialogTitle>
            </DialogHeader>
            <div className="py-4">
              <EntityForm
                entity={selectedEntity}
                onSubmit={async (data) => {
                  if (selectedEntity) {
                    handleEntityUpdate(selectedEntity.id, data);
                  } else {
                    try {
                      // Map form data to API format
                      const createRequest = {
                        name: data.name!,
                        entity_type: data.type!,
                        confidence_score: data.confidence || 0.8,
                        extraction_method: 'manual',
                        metadata: data.metadata || {},
                      };
                      await entityService.createEntity(createRequest);
                      toast.success('Entity created successfully');
                      setEditDialogOpen(false);
                      fetchEntities();
                    } catch (error) {
                      logEntityPageError('Error creating entity', error);
                      toast.error('Failed to create entity');
                    }
                  }
                }}
                onCancel={() => setEditDialogOpen(false)}
              />
            </div>
          </DialogContent>
        </Dialog>

        {/* Detail Dialog */}
        <Dialog open={detailDialogOpen} onOpenChange={setDetailDialogOpen}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto bg-card border-border text-foreground">
            <DialogHeader className="border-b border-border pb-4">
              <DialogTitle className="text-lg font-semibold">
                Entity details
              </DialogTitle>
            </DialogHeader>
            {selectedEntity && (
              <div className="py-4">
                <EntityDetail
                  entity={selectedEntity}
                  onEdit={() => {
                    setDetailDialogOpen(false);
                    setEditDialogOpen(true);
                  }}
                  onClose={() => setDetailDialogOpen(false)}
                  onEntityClick={(entity) => {
                    // Re-center neighborhood exploration on clicked entity
                    setSelectedEntity(entity);
                  }}
                />
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Relationship Creation Dialog */}
        <Dialog
          open={relationshipDialogOpen}
          onOpenChange={(open) => {
            setRelationshipDialogOpen(open);
            if (!open) setSourceEntityId(null);
          }}
        >
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto bg-card border-border text-foreground">
            <DialogHeader className="border-b border-border pb-4">
              <DialogTitle className="text-lg font-semibold">
                New relationship
              </DialogTitle>
            </DialogHeader>
            <div className="py-4">
              <RelationshipForm
                sourceEntityId={sourceEntityId || undefined}
                onSubmit={handleCreateRelationship}
                onCancel={() => {
                  setRelationshipDialogOpen(false);
                  setSourceEntityId(null);
                }}
              />
            </div>
          </DialogContent>
        </Dialog>

        {/* Keyboard Shortcuts Dialog */}
        <KeyboardShortcutsDialog
          open={shortcutsDialogOpen}
          onOpenChange={setShortcutsDialogOpen}
        />
      </div>
    </MotionConfig>
  );
}

// Loading fallback component
function EntityPageLoading() {
  return (
    <div
      role="status"
      aria-label="Loading entities"
      className="min-h-screen bg-background p-6 space-y-4"
    >
      <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-lg bg-muted animate-pulse" />
          <div className="space-y-2">
            <div className="h-5 w-40 rounded bg-muted animate-pulse" />
            <div className="h-3 w-64 rounded bg-muted animate-pulse" />
          </div>
        </div>
      </div>
      <div className="h-20 rounded-xl border border-border bg-card animate-pulse" />
      <div className="h-96 rounded-xl border border-border bg-card animate-pulse" />
    </div>
  );
}

// Wrap in Suspense for useSearchParams() compatibility
export default function EntityManagementPage() {
  return (
    <EntityErrorBoundary>
      <Suspense fallback={<EntityPageLoading />}>
        <EntityManagementContent />
      </Suspense>
    </EntityErrorBoundary>
  );
}
