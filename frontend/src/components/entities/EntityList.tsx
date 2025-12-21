/**
 * EntityList Component
 * Displays a paginated table of entities with actions
 */

import React, { useState } from 'react';
import { Edit, Trash2, Eye, ExternalLink, Clock, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Entity, EntityType } from '@/types/entity';

interface EntityListProps {
  entities: Entity[];
  loading?: boolean;
  onEdit?: (entity: Entity) => void;
  onView?: (entity: Entity) => void;
  onDelete?: (entityId: string) => void;
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

const formatMetadata = (metadata: Record<string, any>): string => {
  if (!metadata) return '';
  const items = [];
  if (metadata.description) items.push(metadata.description.substring(0, 100) + '...');
  if (metadata.category) items.push(`Category: ${metadata.category}`);
  return items.slice(0, 2).join(' • ');
};

export const EntityList: React.FC<EntityListProps> = ({
  entities,
  loading,
  onEdit,
  onView,
  onDelete
}) => {
  const [selectedItems, setSelectedItems] = useState<string[]>([]);

  const handleSelectAll = () => {
    if (selectedItems.length === entities.length) {
      setSelectedItems([]);
    } else {
      setSelectedItems(entities.map(e => e.id));
    }
  };

  const handleSelectItem = (entityId: string) => {
    setSelectedItems(prev =>
      prev.includes(entityId)
        ? prev.filter(id => id !== entityId)
        : [...prev, entityId]
    );
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-full mb-2"></div>
                <div className="h-4 bg-gray-200 rounded w-3/4"></div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Entities</CardTitle>
          {selectedItems.length > 0 && (
            <div className="flex items-center space-x-2">
              <Badge variant="outline">
                {selectedItems.length} selected
              </Badge>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedItems([])}
              >
                Clear selection
              </Button>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {entities.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500">No entities found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">
                    <input
                      type="checkbox"
                      checked={selectedItems.length === entities.length}
                      onChange={handleSelectAll}
                      className="rounded"
                    />
                  </TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Properties</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entities.map((entity) => (
                  <TableRow key={entity.id} className="hover:bg-gray-50">
                    <TableCell>
                      <input
                        type="checkbox"
                        checked={selectedItems.includes(entity.id)}
                        onChange={() => handleSelectItem(entity.id)}
                        className="rounded"
                      />
                    </TableCell>
                    <TableCell>
                      <div className="font-medium text-gray-900">
                        {entity.name}
                      </div>
                      {entity.metadata?.aliases && (
                        <div className="text-sm text-gray-500 mt-1">
                          Also known as: {entity.metadata.aliases.slice(0, 2).join(', ')}
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge className={typeColors[entity.type] || 'bg-gray-100 text-gray-800'}>
                        {entity.type}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center space-x-2">
                        <span className={`font-medium ${confidenceColor(entity.confidence || 0)}`}>
                          {((entity.confidence || 0) * 100).toFixed(1)}%
                        </span>
                        {entity.confidence && entity.confidence >= 0.8 && (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm text-gray-600 max-w-md truncate">
                        {formatMetadata(entity.metadata)}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center text-sm text-gray-500">
                        <Clock className="h-3 w-3 mr-1" />
                        {entity.created_at ? new Date(entity.created_at).toLocaleDateString() : 'N/A'}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center justify-end space-x-2">
                        {onView && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onView(entity)}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        )}
                        {onEdit && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onEdit(entity)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                        )}
                        {entity.source_document_id && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => window.open(`/documents/${entity.source_document_id}`, '_blank')}
                          >
                            <ExternalLink className="h-4 w-4" />
                          </Button>
                        )}
                        {onDelete && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onDelete(entity.id)}
                            className="text-red-600 hover:text-red-700"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
};