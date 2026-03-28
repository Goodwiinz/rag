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
import { motion } from 'framer-motion';
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
import { EnhancedSearch } from '@/components/entities/EnhancedSearch';
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
        toast.error('Failed to load entity types and analytics');
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
    } catch (error) {
      logEntityPageError('Error fetching entities', error);
      toast.error('Failed to fetch entities');
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
        entityService.getAllRelationships(500),
        entityService.getEntities(500, 0, undefined, true),
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
    <div className="min-h-screen bg-[var(--terminal-bg)] flex flex-col">
      <div className="p-6 space-y-4 flex-1 overflow-y-auto terminal-scrollbar">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-6 shadow-xl"
        >
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/20 flex items-center justify-center">
                <Network className="w-6 h-6 text-[var(--phosphor-green)]" />
              </div>
              <div>
                <h1 className="text-2xl font-mono font-bold text-[var(--terminal-text)] tracking-wider">
                  NEURAL_ENTITY_REGISTRY
                </h1>
                <p className="text-xs font-mono text-[var(--terminal-text-dim)] mt-0.5 uppercase tracking-widest">
                  Knowledge Graph Nodes Management
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
                className="font-mono text-[10px] font-bold border-[var(--terminal-border)] hover:bg-[var(--terminal-elevated)]"
              >
                <RefreshCw
                  className={cn(
                    'h-3.5 w-3.5 mr-1.5',
                    loading && 'animate-spin'
                  )}
                />
                REFRESH
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={exportEntities}
                className="font-mono text-[10px] font-bold border-[var(--terminal-border)] hover:bg-[var(--terminal-elevated)]"
              >
                <Download className="h-3.5 w-3.5 mr-1.5" />
                EXPORT
              </Button>
              <Button
                size="sm"
                onClick={() => {
                  setSelectedEntity(null);
                  setEditDialogOpen(true);
                }}
                disabled={!canCreate}
                className="font-mono text-[10px] font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_15px_var(--phosphor-green-glow)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Plus className="h-3.5 w-3.5 mr-1.5" />
                NEW_NODE {!canCreate && '(ADMIN)'}
              </Button>
            </div>
          </div>
        </motion.div>

        {/* Filters */}
        <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-lg">
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
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <div className="mb-4 space-y-2">
            {/* View group */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-[9px] text-primary uppercase tracking-wider w-14 shrink-0">
                // View
              </span>
              <TabsList className="bg-[var(--terminal-bg)] border border-[var(--terminal-border)] p-1 rounded-lg">
                <TabsTrigger
                  value="list"
                  className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary font-mono text-xs gap-1.5"
                >
                  <List className="h-3.5 w-3.5" />
                  List
                </TabsTrigger>
                <TabsTrigger
                  value="graph"
                  className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary font-mono text-xs gap-1.5"
                >
                  <Network className="h-3.5 w-3.5" />
                  Graph
                </TabsTrigger>
                <TabsTrigger
                  value="pathfinder"
                  className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary font-mono text-xs gap-1.5"
                >
                  <Route className="h-3.5 w-3.5" />
                  Path Finder
                </TabsTrigger>
                <TabsTrigger
                  value="search"
                  className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary font-mono text-xs gap-1.5"
                >
                  <Search className="h-3.5 w-3.5" />
                  Search
                </TabsTrigger>
              </TabsList>

              {/* Actions group */}
              <span className="font-mono text-[9px] text-primary uppercase tracking-wider w-14 shrink-0 ml-2">
                // Actions
              </span>
              <TabsList className="bg-[var(--terminal-bg)] border border-[var(--terminal-border)] p-1 rounded-lg">
                <TabsTrigger
                  value="bulk"
                  className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary font-mono text-xs gap-1.5"
                >
                  <Layers className="h-3.5 w-3.5" />
                  Bulk Ops
                </TabsTrigger>
                <TabsTrigger
                  value="extractor"
                  className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary font-mono text-xs gap-1.5"
                >
                  <FileSearch className="h-3.5 w-3.5" />
                  Extract
                </TabsTrigger>
                <TabsTrigger
                  value="merge"
                  className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary font-mono text-xs gap-1.5"
                >
                  <GitMerge className="h-3.5 w-3.5" />
                  Merge
                </TabsTrigger>
              </TabsList>
            </div>

            {/* Monitor group */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-[9px] text-primary uppercase tracking-wider w-14 shrink-0">
                // Monitor
              </span>
              <TabsList className="bg-[var(--terminal-bg)] border border-[var(--terminal-border)] p-1 rounded-lg">
                <TabsTrigger
                  value="statistics"
                  className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary font-mono text-xs gap-1.5"
                >
                  <TrendingUp className="h-3.5 w-3.5" />
                  Metrics
                </TabsTrigger>
                <TabsTrigger
                  value="analytics"
                  className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary font-mono text-xs gap-1.5"
                >
                  <BarChart3 className="h-3.5 w-3.5" />
                  Analytics
                </TabsTrigger>
                <TabsTrigger
                  value="health"
                  className="rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary font-mono text-xs gap-1.5"
                >
                  <HeartPulse className="h-3.5 w-3.5" />
                  Health
                </TabsTrigger>
              </TabsList>
            </div>
          </div>

          <TabsContent value="list" className="mt-0 outline-none">
            <div className="rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] overflow-hidden shadow-xl">
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
            <div className="rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] overflow-hidden shadow-xl p-4">
              {relationshipsLoading ? (
                <div className="flex items-center justify-center h-[600px]">
                  <div className="flex flex-col items-center gap-6">
                    {/* Animated network visualization skeleton */}
                    <div className="relative">
                      <div className="w-20 h-20 rounded-full border-2 border-[var(--terminal-border)] bg-[var(--terminal-bg)] flex items-center justify-center">
                        <Network className="w-8 h-8 text-[var(--phosphor-green)] animate-pulse" />
                      </div>
                      {/* Orbiting nodes */}
                      <div className="absolute -top-2 -right-2 w-4 h-4 rounded-full bg-[var(--terminal-border)] animate-pulse" />
                      <div className="absolute -bottom-1 -left-3 w-3 h-3 rounded-full bg-[var(--terminal-border)] animate-pulse delay-150" />
                      <div className="absolute top-1/2 -right-6 w-3 h-3 rounded-full bg-[var(--terminal-border)] animate-pulse delay-300" />
                      <div className="absolute -top-4 left-1/2 w-2 h-2 rounded-full bg-[var(--terminal-border)] animate-pulse delay-500" />
                    </div>

                    {/* Loading spinner */}
                    <Loader2 className="w-6 h-6 text-[var(--phosphor-green)] animate-spin" />

                    {/* Status text */}
                    <div className="text-center space-y-2">
                      <p className="font-mono text-sm text-[var(--terminal-text)]">
                        LOADING_GRAPH_DATA...
                      </p>
                      <p className="font-mono text-xs text-[var(--terminal-text-dim)]">
                        Fetching connected nodes and relationships
                      </p>
                    </div>

                    {/* Progress skeleton bars */}
                    <div className="w-48 space-y-2">
                      <div className="h-1 bg-[var(--terminal-bg)] rounded-full overflow-hidden border border-[var(--terminal-border)]">
                        <div className="h-full w-2/3 bg-[var(--phosphor-green)]/50 rounded-full animate-pulse" />
                      </div>
                    </div>
                  </div>
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
                  label: 'Total Entities',
                  value: statistics.totalEntities.toLocaleString(),
                  icon: Database,
                  color: 'var(--phosphor-green)',
                },
                {
                  label: 'Unique Types',
                  value: statistics.uniqueTypes,
                  icon: Filter,
                  color: 'var(--cyan)',
                },
                {
                  label: 'Avg Confidence',
                  value: `${(statistics.averageConfidence * 100).toFixed(1)}%`,
                  icon: TrendingUp,
                  color: 'var(--amber-gold)',
                },
                {
                  label: 'Relationships',
                  value: statistics.totalRelationships.toLocaleString(),
                  icon: Network,
                  color: 'var(--purple)',
                },
              ].map((stat) => (
                <Card
                  key={stat.label}
                  className="border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-lg overflow-hidden relative group"
                >
                  <div
                    className="absolute top-0 left-0 w-1 h-full opacity-20 group-hover:opacity-100 transition-opacity"
                    style={{ backgroundColor: stat.color }}
                  />
                  <CardHeader className="p-4 pb-1">
                    <CardTitle className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest flex items-center gap-2">
                      <stat.icon
                        className="w-3 h-3"
                        style={{ color: stat.color }}
                      />
                      {stat.label}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 pt-0">
                    <p className="text-2xl font-mono font-bold text-[var(--terminal-text)]">
                      {stat.value}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Type Distribution */}
            <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-lg">
              <CardHeader className="border-b border-[var(--terminal-border)] py-3">
                <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
                  <BarChart3 className="w-4 h-4" />
                  Type Distribution
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <div className="space-y-3">
                  {Object.entries(statistics.typeDistribution)
                    .sort(([, a], [, b]) => b - a)
                    .map(([type, count]) => {
                      const percentage = (count / entities.length) * 100;
                      return (
                        <div key={type} className="space-y-1">
                          <div className="flex justify-between text-xs font-mono">
                            <span className="text-[var(--terminal-text)]">
                              {type}
                            </span>
                            <span className="text-[var(--terminal-text-dim)]">
                              {count} ({percentage.toFixed(1)}%)
                            </span>
                          </div>
                          <div className="h-2 bg-[var(--terminal-bg)] rounded-full overflow-hidden border border-[var(--terminal-border)]">
                            <div
                              className="h-full bg-[var(--phosphor-green)] rounded-full transition-all duration-500"
                              style={{ width: `${percentage}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                </div>
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
            <EnhancedSearch
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
        <DialogContent className="max-w-2xl bg-[var(--terminal-surface)] border-[var(--terminal-border)] text-[var(--terminal-text)] font-mono">
          <DialogHeader className="border-b border-[var(--terminal-border)] pb-4">
            <DialogTitle className="text-lg font-bold tracking-tight">
              {selectedEntity ? 'EDIT_NODE_PARAMETERS' : 'PROVISION_NEW_NODE'}
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
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto bg-[var(--terminal-surface)] border-[var(--terminal-border)] text-[var(--terminal-text)] font-mono">
          <DialogHeader className="border-b border-[var(--terminal-border)] pb-4">
            <DialogTitle className="text-lg font-bold tracking-tight uppercase">
              Node_Analysis_Dump
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
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto bg-[var(--terminal-surface)] border-[var(--terminal-border)] text-[var(--terminal-text)] font-mono">
          <DialogHeader className="border-b border-[var(--terminal-border)] pb-4">
            <DialogTitle className="text-lg font-bold tracking-tight uppercase">
              ESTABLISH_NEW_LINK
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
  );
}

// Loading fallback component
function EntityPageLoading() {
  return (
    <div className="min-h-screen bg-[var(--terminal-bg)] flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="w-8 h-8 text-[var(--phosphor-green)] animate-spin" />
        <p className="font-mono text-sm text-[var(--terminal-text-dim)]">
          LOADING_ENTITY_REGISTRY...
        </p>
      </div>
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
