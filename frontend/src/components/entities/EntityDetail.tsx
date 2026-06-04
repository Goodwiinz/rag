/**
 * EntityDetail Component
 * Entity detail view with role-based access control.
 */

import React, { useState, useEffect } from 'react';
import {
  Edit,
  Clock,
  CheckCircle,
  FileText,
  Plus,
  Trash2,
  Info,
  Network,
  Code2,
  Database,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Entity, GraphEdge } from '@/types/entity';
import { entityService } from '@/services/entityService';
import { useEntityPermissions } from '@/hooks/useEntityPermissions';
import { NeighborhoodExplorer } from './NeighborhoodExplorer';
import { cn } from '@/lib/utils';

interface EntityDetailProps {
  entity: Entity;
  onEdit?: () => void;
  onClose?: () => void;
  onEntityClick?: (entity: Entity) => void;
}

const formatField = (key: string): string => {
  const spaced = key.replace(/_/g, ' ');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
};

export const EntityDetail: React.FC<EntityDetailProps> = ({
  entity,
  onEdit,
  onClose,
  onEntityClick,
}) => {
  const { canCreate, canEdit, canDelete } = useEntityPermissions();
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
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleString();
  };

  const renderMetadata = (metadata: Record<string, any>) => {
    if (!metadata || Object.keys(metadata).length === 0) {
      return (
        <div className="flex flex-col items-center justify-center py-8 gap-2 text-muted-foreground">
          <Database aria-hidden="true" className="w-8 h-8 opacity-20" />
          <p className="text-sm">No metadata available</p>
        </div>
      );
    }

    return (
      <div className="space-y-4">
        {Object.entries(metadata).map(([key, value]) => {
          if (key === 'properties') return null;
          if (key === 'aliases' && Array.isArray(value)) {
            return (
              <div key={key} className="border-b border-border pb-3">
                <dt className="text-xs font-medium text-muted-foreground mb-2">
                  {formatField(key)}
                </dt>
                <dd className="flex flex-wrap gap-2">
                  {value.map((alias, index) => (
                    <Badge
                      key={index}
                      variant="outline"
                      className="border-border bg-muted text-muted-foreground font-normal"
                    >
                      {alias}
                    </Badge>
                  ))}
                </dd>
              </div>
            );
          }
          if (typeof value === 'object' && value !== null) {
            return (
              <div key={key} className="border-b border-border pb-3">
                <dt className="text-xs font-medium text-muted-foreground mb-2">
                  {formatField(key)}
                </dt>
                <dd>
                  <pre className="text-xs font-[var(--nous-font-mono)] bg-muted/50 p-3 rounded-md border border-border text-muted-foreground overflow-auto custom-scrollbar">
                    {JSON.stringify(value, null, 2)}
                  </pre>
                </dd>
              </div>
            );
          }
          return (
            <div
              key={key}
              className="border-b border-border pb-3 flex justify-between items-center gap-4"
            >
              <dt className="text-xs font-medium text-muted-foreground">
                {formatField(key)}
              </dt>
              <dd className="text-sm text-foreground text-right">
                {String(value)}
              </dd>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="space-y-6 text-foreground">
      {/* Header */}
      <div className="flex items-start justify-between pb-6 border-b border-border gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-foreground tracking-tight flex items-center gap-3 flex-wrap">
            {entity.name}
            <Badge
              variant="outline"
              className="border-border bg-muted text-muted-foreground font-normal align-middle"
            >
              {entity.type}
            </Badge>
          </h2>
          <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground flex-wrap">
            <div className="flex items-center gap-1.5">
              <span>ID</span>
              <span className="font-[var(--nous-font-mono)] text-foreground">
                {entity.id.substring(0, 8)}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span>Confidence</span>
              <span className="font-medium text-foreground tabular-nums">
                {((entity.confidence || 0) * 100).toFixed(1)}%
              </span>
            </div>
            {entity.confidence && entity.confidence >= 0.8 && (
              <div className="flex items-center gap-1 text-primary">
                <CheckCircle aria-hidden="true" className="w-3.5 h-3.5" />
                High confidence
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {entity.source_document_id && (
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                window.open(`/documents/${entity.source_document_id}`, '_blank')
              }
            >
              <FileText aria-hidden="true" className="h-3.5 w-3.5 mr-1.5" />
              Source document
            </Button>
          )}
          {onEdit && (
            <Button
              variant="outline"
              size="sm"
              onClick={onEdit}
              disabled={!canEdit}
              title={!canEdit ? 'Admin access required' : 'Edit entity'}
            >
              <Edit aria-hidden="true" className="h-3.5 w-3.5 mr-1.5" />
              Edit
              {!canEdit && (
                <span className="ml-1 text-xs opacity-80">(admin)</span>
              )}
            </Button>
          )}
        </div>
      </div>

      {/* Main Content */}
      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList className="bg-muted/40 border border-border p-1 rounded-lg w-full justify-start">
          <TabsTrigger
            value="overview"
            className="flex items-center gap-2 rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary text-sm px-4"
          >
            <Info aria-hidden="true" className="w-3.5 h-3.5" />
            Overview
          </TabsTrigger>
          <TabsTrigger
            value="relationships"
            className="flex items-center gap-2 rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary text-sm px-4"
          >
            <Network aria-hidden="true" className="w-3.5 h-3.5" />
            Relationships
          </TabsTrigger>
          <TabsTrigger
            value="neighborhood"
            className="flex items-center gap-2 rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary text-sm px-4"
          >
            <Network aria-hidden="true" className="w-3.5 h-3.5" />
            Neighborhood
          </TabsTrigger>
          <TabsTrigger
            value="metadata"
            className="flex items-center gap-2 rounded-md data-[state=active]:bg-primary/15 data-[state=active]:text-primary text-sm px-4"
          >
            <Code2 aria-hidden="true" className="w-3.5 h-3.5" />
            Metadata
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-0 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="border-border bg-card shadow-sm">
              <CardHeader className="border-b border-border py-3 bg-muted/30">
                <CardTitle className="text-sm font-medium text-foreground flex items-center gap-2">
                  <Info
                    aria-hidden="true"
                    className="w-4 h-4 text-muted-foreground"
                  />
                  Details
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-4">
                <div className="flex justify-between items-center gap-4 border-b border-border pb-2">
                  <span className="text-sm text-muted-foreground">
                    Entity ID
                  </span>
                  <span className="text-xs font-[var(--nous-font-mono)] text-foreground truncate">
                    {entity.id}
                  </span>
                </div>
                <div className="flex justify-between items-center gap-4 border-b border-border pb-2">
                  <span className="text-sm text-muted-foreground">Created</span>
                  <div className="flex items-center text-sm text-foreground">
                    <Clock
                      aria-hidden="true"
                      className="h-3 w-3 mr-1.5 text-muted-foreground"
                    />
                    {formatDate(entity.created_at)}
                  </div>
                </div>
                <div className="flex justify-between items-center gap-4 border-b border-border pb-2">
                  <span className="text-sm text-muted-foreground">
                    Last updated
                  </span>
                  <div className="flex items-center text-sm text-foreground">
                    <Clock
                      aria-hidden="true"
                      className="h-3 w-3 mr-1.5 text-muted-foreground"
                    />
                    {formatDate(entity.updated_at)}
                  </div>
                </div>
                <div className="flex justify-between items-center gap-4">
                  <span className="text-sm text-muted-foreground">
                    Extraction method
                  </span>
                  <span className="text-sm text-foreground">
                    {entity.extraction_method || 'Automatic'}
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card className="border-border bg-card shadow-sm flex flex-col">
              <CardHeader className="border-b border-border py-3 bg-muted/30">
                <CardTitle className="text-sm font-medium text-foreground flex items-center gap-2">
                  <FileText
                    aria-hidden="true"
                    className="w-4 h-4 text-muted-foreground"
                  />
                  Description
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 flex-1">
                <p className="text-sm text-foreground leading-relaxed">
                  {entity.metadata?.description || (
                    <span className="text-muted-foreground italic">
                      No description available
                    </span>
                  )}
                </p>
                {entity.metadata?.category && (
                  <div className="mt-4 pt-4 border-t border-border flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      Category
                    </span>
                    <Badge
                      variant="outline"
                      className="border-border bg-muted text-foreground font-normal"
                    >
                      {entity.metadata.category}
                    </Badge>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="relationships" className="mt-0">
          <Card className="border-border bg-card shadow-sm overflow-hidden">
            <CardHeader className="border-b border-border py-3 bg-muted/30 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-medium text-foreground flex items-center gap-2">
                <Network
                  aria-hidden="true"
                  className="w-4 h-4 text-muted-foreground"
                />
                Relationships
              </CardTitle>
              <Button
                size="sm"
                variant="ghost"
                disabled={!canCreate}
                className="h-7 text-xs hover:text-primary hover:bg-primary/10 disabled:opacity-30 disabled:cursor-not-allowed"
                title={
                  !canCreate ? 'Admin access required' : 'Add relationship'
                }
              >
                <Plus aria-hidden="true" className="h-3.5 w-3.5 mr-1.5" />
                Add relationship
                {!canCreate && <span className="ml-1 opacity-80">(admin)</span>}
              </Button>
            </CardHeader>
            <CardContent className="p-0">
              {loading ? (
                <div
                  className="p-8 space-y-3"
                  role="status"
                  aria-label="Loading relationships"
                >
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div
                      key={i}
                      className="h-12 bg-muted/50 border border-border rounded-md animate-pulse"
                    ></div>
                  ))}
                </div>
              ) : relationships.length === 0 ? (
                <div className="text-center py-12 flex flex-col items-center gap-3">
                  <Network
                    aria-hidden="true"
                    className="w-10 h-10 text-muted-foreground opacity-20"
                  />
                  <p className="text-sm text-muted-foreground">
                    No relationships yet
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader className="bg-muted/20">
                    <TableRow className="border-border hover:bg-transparent">
                      <TableHead className="text-xs font-medium text-muted-foreground pl-6">
                        Connected entity
                      </TableHead>
                      <TableHead className="text-xs font-medium text-muted-foreground">
                        Type
                      </TableHead>
                      <TableHead className="text-xs font-medium text-muted-foreground">
                        Strength
                      </TableHead>
                      <TableHead className="text-xs font-medium text-muted-foreground">
                        Confidence
                      </TableHead>
                      <TableHead className="text-xs font-medium text-muted-foreground">
                        Context
                      </TableHead>
                      <TableHead className="text-xs font-medium text-muted-foreground text-right pr-6">
                        Actions
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {relationships.map((rel) => (
                      <TableRow
                        key={rel.id}
                        className="border-border hover:bg-muted/40"
                      >
                        <TableCell className="pl-6">
                          <div className="text-sm font-medium text-foreground">
                            {rel.source === entity.id ? rel.target : rel.source}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className="border-border bg-muted text-muted-foreground font-normal"
                          >
                            {rel.type}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div className="w-16 bg-muted rounded-full h-1.5 border border-border">
                              <div
                                className="bg-primary h-full rounded-full"
                                style={{
                                  width: `${(rel.strength || 0) * 100}%`,
                                }}
                              />
                            </div>
                            <span className="text-xs text-muted-foreground tabular-nums">
                              {((rel.strength || 0) * 100).toFixed(0)}%
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className="text-xs font-medium text-muted-foreground tabular-nums">
                            {((rel.confidence || 0) * 100).toFixed(1)}%
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="text-xs text-muted-foreground max-w-xs truncate">
                            {rel.context || (
                              <span className="text-muted-foreground/60">
                                None
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-right pr-6">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeleteRelationship(rel.id)}
                            disabled={!canDelete}
                            className="h-6 w-6 text-muted-foreground hover:text-destructive hover:bg-destructive/10 disabled:opacity-30 disabled:cursor-not-allowed"
                            title={
                              !canDelete
                                ? 'Admin access required'
                                : 'Delete relationship'
                            }
                            aria-label={
                              !canDelete
                                ? 'Delete relationship (admin access required)'
                                : 'Delete relationship'
                            }
                          >
                            <Trash2
                              aria-hidden="true"
                              className="h-3.5 w-3.5"
                            />
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

        <TabsContent value="neighborhood" className="mt-0">
          <NeighborhoodExplorer
            centralEntity={entity}
            onEntityClick={onEntityClick}
          />
        </TabsContent>

        <TabsContent value="metadata" className="mt-0">
          <Card className="border-border bg-card shadow-sm">
            <CardHeader className="border-b border-border py-3 bg-muted/30">
              <CardTitle className="text-sm font-medium text-foreground flex items-center gap-2">
                <Code2
                  aria-hidden="true"
                  className="w-4 h-4 text-muted-foreground"
                />
                Metadata
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6">
              {renderMetadata(entity.metadata ?? {})}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};
