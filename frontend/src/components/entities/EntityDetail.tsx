/**
 * EntityDetail Component
 * Terminal Observatory themed entity detail view with role-based access control
 */

import React, { useState, useEffect } from 'react';
import { Edit, ExternalLink, Clock, CheckCircle, FileText, Plus, Trash2, Shield, Activity, Terminal, Database, Code, Network } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Entity, GraphEdge, EntityType } from '@/types/entity';
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

const typeColors: Record<string, string> = {
  PERSON: 'text-blue-400 bg-blue-400/10 border-blue-400/20',
  ORGANIZATION: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20',
  LOCATION: 'text-amber-400 bg-amber-400/10 border-amber-400/20',
  CONCEPT: 'text-purple-400 bg-purple-400/10 border-purple-400/20',
  EVENT: 'text-rose-400 bg-rose-400/10 border-rose-400/20',
  PRODUCT: 'text-indigo-400 bg-indigo-400/10 border-indigo-400/20',
  DATE: 'text-slate-400 bg-slate-400/10 border-slate-400/20',
  TECHNOLOGY: 'text-cyan-400 bg-cyan-400/10 border-cyan-400/20',
  DOCUMENT: 'text-orange-400 bg-orange-400/10 border-orange-400/20',
  TOPIC: 'text-pink-400 bg-pink-400/10 border-pink-400/20',
  RESEARCH: 'text-violet-400 bg-violet-400/10 border-violet-400/20',
  FINANCIAL: 'text-green-400 bg-green-400/10 border-green-400/20',
  EMAIL: 'text-sky-400 bg-sky-400/10 border-sky-400/20',
  PHONE: 'text-teal-400 bg-teal-400/10 border-teal-400/20',
  URL: 'text-lime-400 bg-lime-400/10 border-lime-400/20',
  JOB_TITLE: 'text-fuchsia-400 bg-fuchsia-400/10 border-fuchsia-400/20',
  OTHER: 'text-gray-400 bg-gray-400/10 border-gray-400/20',
};

const getConfidenceColor = (confidence: number): string => {
  if (confidence >= 0.8) return 'text-[var(--phosphor-green)]';
  if (confidence >= 0.6) return 'text-[var(--amber-gold)]';
  return 'text-red-400';
};

export const EntityDetail: React.FC<EntityDetailProps> = ({
  entity,
  onEdit,
  onClose,
  onEntityClick
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
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  const renderMetadata = (metadata: Record<string, any>) => {
    if (!metadata || Object.keys(metadata).length === 0) {
      return (
        <div className="flex flex-col items-center justify-center py-8 text-[var(--terminal-text-dim)]">
          <Database className="w-8 h-8 mb-2 opacity-20" />
          <p className="font-mono text-sm">NO_METADATA_AVAILABLE</p>
        </div>
      );
    }

    return (
      <div className="space-y-4">
        {Object.entries(metadata).map(([key, value]) => {
          if (key === 'properties') return null;
          if (key === 'aliases' && Array.isArray(value)) {
            return (
              <div key={key} className="border-b border-[var(--terminal-border)] pb-3">
                <dt className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest mb-2">{key}</dt>
                <dd className="flex flex-wrap gap-2">
                  {value.map((alias, index) => (
                    <Badge
                      key={index}
                      variant="outline"
                      className="font-mono text-[10px] border-[var(--terminal-border)] text-[var(--terminal-text-muted)] bg-[var(--terminal-elevated)]"
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
              <div key={key} className="border-b border-[var(--terminal-border)] pb-3">
                <dt className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest mb-2">{key}</dt>
                <dd>
                  <pre className="text-[10px] font-mono bg-[var(--terminal-bg)] p-3 rounded border border-[var(--terminal-border)] text-[var(--terminal-text-muted)] overflow-auto custom-scrollbar">
                    {JSON.stringify(value, null, 2)}
                  </pre>
                </dd>
              </div>
            );
          }
          return (
            <div key={key} className="border-b border-[var(--terminal-border)] pb-3 flex justify-between items-center">
              <dt className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest">{key}</dt>
              <dd className="text-xs font-mono text-[var(--terminal-text)]">{String(value)}</dd>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="space-y-6 text-[var(--terminal-text)]">
      {/* Header */}
      <div className="flex items-start justify-between pb-6 border-b border-[var(--terminal-border)]">
        <div>
          <h2 className="text-2xl font-mono font-bold text-[var(--terminal-text)] tracking-tight flex items-center gap-3">
            {entity.name}
            <Badge
              className={cn(
                "font-mono text-[10px] font-bold border rounded px-1.5 py-0.5 ml-2 align-middle",
                typeColors[entity.type] || 'text-gray-400 bg-gray-400/10 border-gray-400/20'
              )}
            >
              {entity.type}
            </Badge>
          </h2>
          <div className="flex items-center gap-4 mt-2 text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest">
            <div className="flex items-center gap-1.5">
              <span className="text-[var(--terminal-text-muted)]">ID:</span>
              <span className="font-mono">{entity.id.substring(0, 8)}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[var(--terminal-text-muted)]">Confidence:</span>
              <span className={cn("font-bold", getConfidenceColor(entity.confidence || 0))}>
                {((entity.confidence || 0) * 100).toFixed(1)}%
              </span>
            </div>
            {entity.confidence && entity.confidence >= 0.8 && (
              <div className="flex items-center gap-1 text-[var(--phosphor-green)]">
                <CheckCircle className="w-3 h-3" />
                VERIFIED
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {entity.source_document_id && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(`/documents/${entity.source_document_id}`, '_blank')}
              className="font-mono text-[10px] font-bold border-[var(--terminal-border)] hover:bg-[var(--terminal-elevated)] hover:text-[var(--amber-gold)]"
            >
              <FileText className="h-3.5 w-3.5 mr-1.5" />
              SOURCE_DOC
            </Button>
          )}
          {onEdit && (
            <Button
              variant="outline"
              size="sm"
              onClick={onEdit}
              disabled={!canEdit}
              className="font-mono text-[10px] font-bold border-[var(--terminal-border)] hover:bg-[var(--terminal-elevated)] hover:text-[var(--cyan)] disabled:opacity-30 disabled:cursor-not-allowed"
              title={!canEdit ? 'Admin access required' : 'Edit entity'}
            >
              <Edit className="h-3.5 w-3.5 mr-1.5" />
              EDIT_NODE {!canEdit && '(ADMIN)'}
            </Button>
          )}
        </div>
      </div>

      {/* Main Content */}
      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList className="bg-[var(--terminal-bg)] border border-[var(--terminal-border)] p-1 rounded-xl w-full justify-start">
          <TabsTrigger value="overview" className="flex items-center gap-2 rounded-lg data-[state=active]:bg-[var(--terminal-elevated)] data-[state=active]:text-[var(--phosphor-green)] font-mono text-xs font-bold px-4">
            <Activity className="w-3.5 h-3.5" />
            OVERVIEW
          </TabsTrigger>
          <TabsTrigger value="relationships" className="flex items-center gap-2 rounded-lg data-[state=active]:bg-[var(--terminal-elevated)] data-[state=active]:text-[var(--phosphor-green)] font-mono text-xs font-bold px-4">
            <Network className="w-3.5 h-3.5" />
            RELATIONSHIPS
          </TabsTrigger>
          <TabsTrigger value="neighborhood" className="flex items-center gap-2 rounded-lg data-[state=active]:bg-[var(--terminal-elevated)] data-[state=active]:text-[var(--phosphor-green)] font-mono text-xs font-bold px-4">
            <Shield className="w-3.5 h-3.5" />
            NEIGHBORHOOD
          </TabsTrigger>
          <TabsTrigger value="metadata" className="flex items-center gap-2 rounded-lg data-[state=active]:bg-[var(--terminal-elevated)] data-[state=active]:text-[var(--phosphor-green)] font-mono text-xs font-bold px-4">
            <Code className="w-3.5 h-3.5" />
            METADATA
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-0 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-lg">
              <CardHeader className="border-b border-[var(--terminal-border)] py-3">
                <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
                  <Terminal className="w-4 h-4" />
                  System_Log
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-4">
                <div className="flex justify-between items-center border-b border-[var(--terminal-border)] pb-2 border-dashed">
                  <span className="text-xs font-mono text-[var(--terminal-text-muted)]">Entity_UUID</span>
                  <span className="text-xs font-mono text-[var(--terminal-text)]">{entity.id}</span>
                </div>
                <div className="flex justify-between items-center border-b border-[var(--terminal-border)] pb-2 border-dashed">
                  <span className="text-xs font-mono text-[var(--terminal-text-muted)]">Created_At</span>
                  <div className="flex items-center text-xs font-mono text-[var(--terminal-text)]">
                    <Clock className="h-3 w-3 mr-1.5 text-[var(--terminal-text-dim)]" />
                    {formatDate(entity.created_at)}
                  </div>
                </div>
                <div className="flex justify-between items-center border-b border-[var(--terminal-border)] pb-2 border-dashed">
                  <span className="text-xs font-mono text-[var(--terminal-text-muted)]">Last_Update</span>
                  <div className="flex items-center text-xs font-mono text-[var(--terminal-text)]">
                    <Clock className="h-3 w-3 mr-1.5 text-[var(--terminal-text-dim)]" />
                    {formatDate(entity.updated_at)}
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs font-mono text-[var(--terminal-text-muted)]">Extraction_Protocol</span>
                  <span className="text-xs font-mono text-[var(--cyan)]">{entity.extraction_method || 'AUTO_INFERENCE'}</span>
                </div>
              </CardContent>
            </Card>

            <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-lg flex flex-col">
              <CardHeader className="border-b border-[var(--terminal-border)] py-3">
                <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  Description_Buffer
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 flex-1">
                <p className="text-xs font-mono text-[var(--terminal-text)] leading-relaxed">
                  {entity.metadata?.description || (
                    <span className="text-[var(--terminal-text-dim)] italic opacity-50">NO_DESCRIPTION_BUFFER_AVAILABLE</span>
                  )}
                </p>
                {entity.metadata?.category && (
                  <div className="mt-4 pt-4 border-t border-[var(--terminal-border)] border-dashed">
                    <span className="text-[10px] font-mono text-[var(--terminal-text-muted)] uppercase mr-2">Category_Tag:</span>
                    <Badge variant="outline" className="font-mono text-[10px] border-[var(--terminal-border)] text-[var(--terminal-text)]">
                      {entity.metadata.category}
                    </Badge>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="relationships" className="mt-0">
          <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-lg overflow-hidden">
            <CardHeader className="border-b border-[var(--terminal-border)] py-3 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
                <Network className="w-4 h-4" />
                Connectivity_Matrix
              </CardTitle>
              <Button
                size="sm"
                variant="ghost"
                disabled={!canCreate}
                className="h-7 font-mono text-[10px] font-bold hover:text-[var(--phosphor-green)] hover:bg-[var(--phosphor-green)]/10 disabled:opacity-30 disabled:cursor-not-allowed"
                title={!canCreate ? 'Admin access required' : 'Add relationship'}
              >
                <Plus className="h-3.5 w-3.5 mr-1.5" />
                ADD_LINK {!canCreate && '(ADMIN)'}
              </Button>
            </CardHeader>
            <CardContent className="p-0">
              {loading ? (
                <div className="p-8 space-y-3">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="h-12 bg-[var(--terminal-bg)] border border-[var(--terminal-border)] rounded animate-pulse"></div>
                  ))}
                </div>
              ) : relationships.length === 0 ? (
                <div className="text-center py-12 flex flex-col items-center gap-3">
                  <Network className="w-10 h-10 text-[var(--terminal-text-muted)] opacity-20" />
                  <p className="text-sm font-mono text-[var(--terminal-text-dim)]">NO_RELATIONSHIPS_MAPPED</p>
                </div>
              ) : (
                <Table>
                  <TableHeader className="bg-[var(--terminal-bg)]/50">
                    <TableRow className="border-[var(--terminal-border)] hover:bg-transparent">
                      <TableHead className="font-mono text-[10px] uppercase tracking-widest text-[var(--terminal-text-dim)] pl-6">Linked_Entity</TableHead>
                      <TableHead className="font-mono text-[10px] uppercase tracking-widest text-[var(--terminal-text-dim)]">Link_Type</TableHead>
                      <TableHead className="font-mono text-[10px] uppercase tracking-widest text-[var(--terminal-text-dim)]">Strength_Index</TableHead>
                      <TableHead className="font-mono text-[10px] uppercase tracking-widest text-[var(--terminal-text-dim)]">Confidence</TableHead>
                      <TableHead className="font-mono text-[10px] uppercase tracking-widest text-[var(--terminal-text-dim)]">Context_Data</TableHead>
                      <TableHead className="font-mono text-[10px] uppercase tracking-widest text-[var(--terminal-text-dim)] text-right pr-6">Ops</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {relationships.map((rel) => (
                      <TableRow key={rel.id} className="border-[var(--terminal-border)] hover:bg-[var(--terminal-elevated)]">
                        <TableCell className="pl-6">
                          <div className="font-mono text-xs font-bold text-[var(--terminal-text)]">
                            {rel.source === entity.id ? rel.target : rel.source}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="font-mono text-[9px] border-[var(--terminal-border)] text-[var(--terminal-text-muted)]">
                            {rel.type}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center space-x-2">
                            <div className="w-16 bg-[var(--terminal-bg)] rounded-full h-1.5 border border-[var(--terminal-border)]">
                              <div
                                className="bg-[var(--cyan)] h-full rounded-full"
                                style={{ width: `${(rel.strength || 0) * 100}%` }}
                              />
                            </div>
                            <span className="text-[10px] font-mono text-[var(--cyan)]">
                              {((rel.strength || 0) * 100).toFixed(0)}%
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className={cn("text-[10px] font-mono font-bold", getConfidenceColor(rel.confidence || 0))}>
                            {((rel.confidence || 0) * 100).toFixed(1)}%
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="text-[10px] font-mono text-[var(--terminal-text-muted)] max-w-xs truncate">
                            {rel.context || 'NULL'}
                          </div>
                        </TableCell>
                        <TableCell className="text-right pr-6">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeleteRelationship(rel.id)}
                            disabled={!canDelete}
                            className="h-6 w-6 text-red-500/50 hover:text-red-400 hover:bg-red-400/10 disabled:opacity-30 disabled:cursor-not-allowed"
                            title={!canDelete ? 'Admin access required' : 'Delete relationship'}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
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
          <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-lg">
            <CardHeader className="border-b border-[var(--terminal-border)] py-3">
              <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
                <Code className="w-4 h-4" />
                Raw_Metadata_Dump
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
