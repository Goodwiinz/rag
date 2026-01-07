/**
 * EntityDetail Component
 * Displays comprehensive information about an entity including relationships
 */

import React, { useState, useEffect } from 'react';
import { Edit, ExternalLink, Clock, CheckCircle, Link2, FileText, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Entity, GraphEdge, EntityType } from '@/types/entity';
import { entityService } from '@/services/entityService';

interface EntityDetailProps {
  entity: Entity;
  onEdit?: () => void;
  onClose?: () => void;
}

const typeColors: Record<EntityType, string> = {
  PERSON: 'bg-blue-100 text-blue-800',
  ORGANIZATION: 'bg-green-100 text-green-800',
  LOCATION: 'bg-yellow-100 text-yellow-800',
  CONCEPT: 'bg-purple-100 text-purple-800',
  EVENT: 'bg-red-100 text-red-800',
  PRODUCT: 'bg-indigo-100 text-indigo-800',
  DATE: 'bg-gray-100 text-gray-800',
  TECHNOLOGY: 'bg-pink-100 text-pink-800',
  DOCUMENT: 'bg-orange-100 text-orange-800',
};

const confidenceColor = (confidence: number): string => {
  if (confidence >= 0.8) return 'text-green-600';
  if (confidence >= 0.6) return 'text-yellow-600';
  return 'text-red-600';
};

export const EntityDetail: React.FC<EntityDetailProps> = ({
  entity,
  onEdit,
  onClose
}) => {
  const [relationships, setRelationships] = useState<GraphEdge[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (entity?.id) {
      fetchRelationships();
    }
  }, [entity?.id]);

  const fetchRelationships = async () => {
    try {
      setLoading(true);
      const response = await entityService.getEntityRelationships(entity.id);
      setRelationships(response);
    } catch (error) {
      console.error('Error fetching relationships:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteRelationship = async (relationshipId: string) => {
    if (!window.confirm('Are you sure you want to delete this relationship?')) {
      return;
    }

    try {
      await entityService.deleteRelationship(relationshipId);
      await fetchRelationships();
    } catch (error) {
      console.error('Error deleting relationship:', error);
    }
  };

  const formatDate = (dateString?: string): string => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  const renderMetadata = (metadata: Record<string, any>) => {
    if (!metadata || Object.keys(metadata).length === 0) {
      return <p className="text-gray-500">No metadata available</p>;
    }

    return (
      <dl className="space-y-2">
        {Object.entries(metadata).map(([key, value]) => {
          if (key === 'properties') return null;
          if (key === 'aliases' && Array.isArray(value)) {
            return (
              <div key={key}>
                <dt className="text-sm font-medium text-gray-600 capitalize">{key}</dt>
                <dd className="mt-1">
                  <div className="flex flex-wrap gap-1">
                    {value.map((alias, index) => (
                      <Badge key={index} variant="outline">{alias}</Badge>
                    ))}
                  </div>
                </dd>
              </div>
            );
          }
          if (typeof value === 'object' && value !== null) {
            return (
              <div key={key}>
                <dt className="text-sm font-medium text-gray-600 capitalize">{key}</dt>
                <dd className="mt-1">
                  <pre className="text-xs bg-gray-100 p-2 rounded overflow-auto">
                    {JSON.stringify(value, null, 2)}
                  </pre>
                </dd>
              </div>
            );
          }
          return (
            <div key={key}>
              <dt className="text-sm font-medium text-gray-600 capitalize">{key}</dt>
              <dd className="mt-1 text-sm text-gray-900">{String(value)}</dd>
            </div>
          );
        })}
      </dl>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{entity.name}</h2>
          <div className="flex items-center space-x-2 mt-2">
            <Badge className={typeColors[entity.type] || 'bg-gray-100 text-gray-800'}>
              {entity.type}
            </Badge>
            <div className="flex items-center space-x-1">
              <span className={`font-medium ${confidenceColor(entity.confidence || 0)}`}>
                {((entity.confidence || 0) * 100).toFixed(1)}%
              </span>
              {entity.confidence && entity.confidence >= 0.8 && (
                <CheckCircle className="h-4 w-4 text-green-500" />
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {entity.source_document_id && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(`/documents/${entity.source_document_id}`, '_blank')}
            >
              <FileText className="h-4 w-4 mr-2" />
              View Source
            </Button>
          )}
          {onEdit && (
            <Button variant="outline" size="sm" onClick={onEdit}>
              <Edit className="h-4 w-4 mr-2" />
              Edit
            </Button>
          )}
        </div>
      </div>

      {/* Main Content */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="relationships">Relationships</TabsTrigger>
          <TabsTrigger value="metadata">Metadata</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Basic Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <dt className="text-sm font-medium text-gray-600">Entity ID</dt>
                  <dd className="text-sm text-gray-900 font-mono">{entity.id}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-600">Created</dt>
                  <dd className="text-sm text-gray-900">
                    <div className="flex items-center">
                      <Clock className="h-3 w-3 mr-1" />
                      {formatDate(entity.created_at)}
                    </div>
                  </dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-600">Last Updated</dt>
                  <dd className="text-sm text-gray-900">
                    <div className="flex items-center">
                      <Clock className="h-3 w-3 mr-1" />
                      {formatDate(entity.updated_at)}
                    </div>
                  </dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-600">Extraction Method</dt>
                  <dd className="text-sm text-gray-900">{entity.extraction_method || 'N/A'}</dd>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-600">
                  {entity.metadata?.description || 'No description available'}
                </p>
                {entity.metadata?.category && (
                  <div className="mt-3">
                    <Badge variant="outline">{entity.metadata.category}</Badge>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="relationships" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Entity Relationships</CardTitle>
                <Button size="sm">
                  <Plus className="h-4 w-4 mr-2" />
                  Add Relationship
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="animate-pulse space-y-3">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="h-12 bg-gray-200 rounded"></div>
                  ))}
                </div>
              ) : relationships.length === 0 ? (
                <p className="text-center text-gray-500 py-8">
                  No relationships found for this entity
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Related Entity</TableHead>
                      <TableHead>Relationship Type</TableHead>
                      <TableHead>Strength</TableHead>
                      <TableHead>Confidence</TableHead>
                      <TableHead>Context</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {relationships.map((rel) => (
                      <TableRow key={rel.id}>
                        <TableCell>
                          <div className="font-medium">
                            {rel.source === entity.id ? rel.target : rel.source}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{rel.type}</Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center space-x-2">
                            <div className="w-16 bg-gray-200 rounded-full h-2">
                              <div
                                className="bg-blue-500 h-2 rounded-full"
                                style={{ width: `${(rel.strength || 0) * 100}%` }}
                              />
                            </div>
                            <span className="text-sm">
                              {((rel.strength || 0) * 100).toFixed(0)}%
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          {((rel.confidence || 0) * 100).toFixed(1)}%
                        </TableCell>
                        <TableCell className="max-w-xs truncate">
                          {rel.context || 'N/A'}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteRelationship(rel.id)}
                            className="text-red-600 hover:text-red-700"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="metadata" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Entity Metadata</CardTitle>
            </CardHeader>
            <CardContent>
              {renderMetadata(entity.metadata ?? {})}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};