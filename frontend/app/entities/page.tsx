/**
 * Entity Management Page
 * Provides a comprehensive interface for viewing, editing, and managing entities
 */

'use client';

import React, { useState, useEffect } from 'react';
import { Search, Filter, Plus, Edit, Trash2, Eye, Download, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { EntityList } from '@/components/entities/EntityList';
import { EntityForm } from '@/components/entities/EntityForm';
import { EntityDetail } from '@/components/entities/EntityDetail';
import { EntityGraph } from '@/components/entities/EntityGraph';
import { Entity, EntityResponse, EntityType, GraphEdge } from '@/types/entity';
import { entityService } from '@/services/entityService';
import toast from 'react-hot-toast';

export default function EntityManagementPage() {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [filteredEntities, setFilteredEntities] = useState<Entity[]>([]);
  const [relationships, setRelationships] = useState<GraphEdge[]>([]);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<EntityType | 'all'>('all');
  const [activeTab, setActiveTab] = useState('list');
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);

  const entityTypes: (EntityType | 'all')[] = ['all', 'PERSON', 'ORGANIZATION', 'LOCATION', 'CONCEPT', 'EVENT', 'PRODUCT', 'DATE', 'TECHNOLOGY', 'DOCUMENT'];

  // Fetch entities and relationships on component mount
  useEffect(() => {
    fetchEntities();
    fetchRelationships();
  }, []);

  // Filter entities based on search and type
  useEffect(() => {
    let filtered = entities;

    // Filter by search query
    if (searchQuery) {
      filtered = filtered.filter(entity =>
        entity.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        entity.type.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    // Filter by type
    if (selectedType !== 'all') {
      filtered = filtered.filter(entity => entity.type === selectedType);
    }

    setFilteredEntities(filtered);
  }, [entities, searchQuery, selectedType]);

  const fetchEntities = async () => {
    try {
      setLoading(true);
      const entitiesData = await entityService.getEntities();

      // Check if entitiesData is an array
      if (!Array.isArray(entitiesData)) {
        console.warn('Received non-array data from entity service:', entitiesData);
        setEntities([]);
        return;
      }

      // Convert EntityResponse to Entity format for display
      const convertedEntities: Entity[] = entitiesData.map(entity => ({
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
        source_document_id: entity.source_document_id
      }));
      setEntities(convertedEntities);
    } catch (error) {
      console.error('Error fetching entities:', error);
      toast.error('Failed to fetch entities');
    } finally {
      setLoading(false);
    }
  };

  const fetchRelationships = async () => {
    try {
      // For now, we'll create mock relationships since we don't have a direct API
      // In a real implementation, you would fetch from the backend
      const mockRelationships: GraphEdge[] = [];
      setRelationships(mockRelationships);
    } catch (error) {
      console.error('Error fetching relationships:', error);
    }
  };

  const handleEntityUpdate = async (entityId: string, updates: Partial<Entity>) => {
    try {
      await entityService.updateEntity(entityId, updates);
      await fetchEntities();
      setEditDialogOpen(false);
      toast.success('Entity updated successfully');
    } catch (error) {
      console.error('Error updating entity:', error);
      toast.error('Failed to update entity');
    }
  };

  const handleEntityDelete = async (entityId: string) => {
    if (!window.confirm('Are you sure you want to delete this entity and all its relationships?')) {
      return;
    }

    try {
      await entityService.deleteEntity(entityId);
      await fetchEntities();
      toast.success('Entity deleted successfully');
    } catch (error) {
      console.error('Error deleting entity:', error);
      toast.error('Failed to delete entity');
    }
  };

  const exportEntities = () => {
    const dataStr = JSON.stringify(filteredEntities, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);

    const exportFileDefaultName = `entities-${new Date().toISOString().split('T')[0]}.json`;

    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Entity Management</h1>
          <p className="text-gray-600 mt-2">
            Manage and edit entities extracted from your documents
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            onClick={() => fetchEntities()}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button variant="outline" onClick={exportEntities}>
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
          <Button onClick={() => setEditDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            New Entity
          </Button>
        </div>
      </div>

      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="flex items-center space-x-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
              <Input
                placeholder="Search entities..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={selectedType} onValueChange={(value: EntityType | 'all') => setSelectedType(value)}>
              <SelectTrigger className="w-48">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue placeholder="Filter by type" />
              </SelectTrigger>
              <SelectContent>
                {entityTypes.map((type) => (
                  <SelectItem key={type} value={type}>
                    {type === 'all' ? 'All Types' : type}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Badge variant="outline" className="px-3 py-1">
              {filteredEntities.length} entities
            </Badge>
          </div>
        </CardContent>
      </Card>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-6">
          <TabsTrigger value="list">List View</TabsTrigger>
          <TabsTrigger value="graph">Graph View</TabsTrigger>
          <TabsTrigger value="statistics">Statistics</TabsTrigger>
        </TabsList>

        <TabsContent value="list">
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
        </TabsContent>

        <TabsContent value="graph">
          <EntityGraph
            entities={filteredEntities}
            relationships={relationships}
            onEntityClick={(entity) => {
              setSelectedEntity(entity);
              setDetailDialogOpen(true);
            }}
            height={600}
          />
        </TabsContent>

        <TabsContent value="statistics">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Total Entities</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">{entities.length}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Entity Types</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">{entityTypes.length - 1}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Average Confidence</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {entities.length > 0
                    ? (entities.reduce((sum, e) => sum + (e.confidence || 0), 0) / entities.length).toFixed(2)
                    : '0.00'
                  }
                </p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      {/* Edit/Create Entity Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {selectedEntity ? 'Edit Entity' : 'Create New Entity'}
            </DialogTitle>
          </DialogHeader>
          <EntityForm
            entity={selectedEntity}
            onSubmit={(data) => {
              if (selectedEntity) {
                handleEntityUpdate(selectedEntity.id, data);
              } else {
                // Handle creation
                console.log('Create entity:', data);
              }
            }}
            onCancel={() => setEditDialogOpen(false)}
          />
        </DialogContent>
      </Dialog>

      {/* Entity Detail Dialog */}
      <Dialog open={detailDialogOpen} onOpenChange={setDetailDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Entity Details</DialogTitle>
          </DialogHeader>
          {selectedEntity && (
            <EntityDetail
              entity={selectedEntity}
              onEdit={() => {
                setDetailDialogOpen(false);
                setEditDialogOpen(true);
              }}
              onClose={() => setDetailDialogOpen(false)}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}