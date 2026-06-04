/**
 * EntityList Component
 * Knowledge-graph entity list with role-based access control.
 */

import React, { useState } from 'react';
import { Edit, Trash2, Eye, ExternalLink, Clock, Network } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { IconButton } from '@/components/ui/icon-button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Entity } from '@/types/entity';
import { useEntityPermissions } from '@/hooks/useEntityPermissions';
import { cn } from '@/lib/utils';

interface EntityListProps {
  entities: Entity[];
  loading?: boolean;
  onEdit?: (entity: Entity) => void;
  onView?: (entity: Entity) => void;
  onDelete?: (entityId: string) => void;
}

const formatMetadata = (metadata: Record<string, any>): string => {
  if (!metadata) return '';
  const items = [];
  if (metadata.description)
    items.push(metadata.description.substring(0, 100) + '...');
  if (metadata.category) items.push(`Category: ${metadata.category}`);
  return items.slice(0, 2).join(' • ');
};

export const EntityList: React.FC<EntityListProps> = ({
  entities,
  loading,
  onEdit,
  onView,
  onDelete,
}) => {
  const { canEdit, canDelete } = useEntityPermissions();
  const [selectedItems, setSelectedItems] = useState<string[]>([]);

  const handleSelectAll = () => {
    if (selectedItems.length === entities.length) {
      setSelectedItems([]);
    } else {
      setSelectedItems(entities.map((e) => e.id));
    }
  };

  const handleSelectItem = (entityId: string) => {
    setSelectedItems((prev) =>
      prev.includes(entityId)
        ? prev.filter((id) => id !== entityId)
        : [...prev, entityId]
    );
  };

  if (loading) {
    return (
      <div className="flex flex-col h-full bg-card">
        {/* Skeleton header bar */}
        <div className="px-6 py-3 border-b border-border bg-muted/30 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-4 h-4 rounded bg-muted animate-pulse" />
            <div className="w-20 h-3 rounded bg-muted animate-pulse" />
          </div>
          <div className="w-32 h-3 rounded bg-muted animate-pulse" />
        </div>

        {/* Skeleton table header */}
        <div className="px-6 py-2.5 border-b border-border bg-muted/20 grid grid-cols-[3rem_1fr_8rem_5rem_1fr_7rem_7rem] gap-4 items-center">
          <div className="w-4 h-3 rounded bg-muted animate-pulse" />
          <div className="w-24 h-3 rounded bg-muted animate-pulse" />
          <div className="w-20 h-3 rounded bg-muted animate-pulse" />
          <div className="w-16 h-3 rounded bg-muted animate-pulse" />
          <div className="w-28 h-3 rounded bg-muted animate-pulse" />
          <div className="w-20 h-3 rounded bg-muted animate-pulse" />
          <div className="w-20 h-3 rounded bg-muted animate-pulse ml-auto" />
        </div>

        {/* Skeleton rows */}
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="px-6 py-3.5 border-b border-border grid grid-cols-[3rem_1fr_8rem_5rem_1fr_7rem_7rem] gap-4 items-center"
            style={{ animationDelay: `${i * 75}ms` }}
          >
            <div
              className="w-4 h-4 rounded bg-muted animate-pulse"
              style={{ animationDelay: `${i * 75}ms` }}
            />
            <div className="space-y-1.5">
              <div
                className="h-4 rounded bg-muted animate-pulse"
                style={{
                  width: `${60 + (i % 3) * 15}%`,
                  animationDelay: `${i * 75}ms`,
                }}
              />
              <div
                className="h-2.5 rounded bg-muted/50 animate-pulse"
                style={{
                  width: `${30 + (i % 2) * 20}%`,
                  animationDelay: `${i * 75}ms`,
                }}
              />
            </div>
            <div
              className="h-5 rounded-full bg-muted animate-pulse"
              style={{
                width: `${50 + (i % 4) * 10}%`,
                animationDelay: `${i * 75}ms`,
              }}
            />
            <div className="space-y-1">
              <div
                className="h-1.5 rounded-full bg-muted animate-pulse"
                style={{ animationDelay: `${i * 75}ms` }}
              />
              <div
                className="h-3 w-10 rounded bg-muted/50 animate-pulse"
                style={{ animationDelay: `${i * 75}ms` }}
              />
            </div>
            <div
              className="h-3 rounded bg-muted/50 animate-pulse"
              style={{
                width: `${40 + (i % 3) * 20}%`,
                animationDelay: `${i * 75}ms`,
              }}
            />
            <div
              className="h-3 w-16 rounded bg-muted/50 animate-pulse"
              style={{ animationDelay: `${i * 75}ms` }}
            />
            <div className="flex items-center justify-end gap-1.5">
              <div
                className="w-7 h-7 rounded bg-muted animate-pulse"
                style={{ animationDelay: `${i * 75}ms` }}
              />
              <div
                className="w-7 h-7 rounded bg-muted animate-pulse"
                style={{ animationDelay: `${i * 75 + 25}ms` }}
              />
              <div
                className="w-7 h-7 rounded bg-muted animate-pulse"
                style={{ animationDelay: `${i * 75 + 50}ms` }}
              />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-card">
      {/* Header with selection controls */}
      <div className="px-6 py-3 border-b border-border bg-muted/30 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <input
            type="checkbox"
            aria-label="Select all entities"
            checked={
              selectedItems.length === entities.length && entities.length > 0
            }
            onChange={handleSelectAll}
            className="h-4 w-4 rounded border-border bg-background text-primary accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card"
          />
          <span className="text-sm text-muted-foreground">Select all</span>
          {selectedItems.length > 0 && (
            <div className="flex items-center gap-3 ml-4 pl-4 border-l border-border">
              <Badge
                variant="outline"
                className="border-primary/30 text-primary bg-primary/5"
              >
                {selectedItems.length} selected
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedItems([])}
                className="h-7 text-xs text-muted-foreground hover:text-primary"
              >
                Clear selection
              </Button>
            </div>
          )}
        </div>
        <div className="text-sm text-muted-foreground tabular-nums">
          {entities.length} {entities.length === 1 ? 'entity' : 'entities'}
        </div>
      </div>

      {/* Table */}
      {entities.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center py-16 gap-3">
          <div className="w-14 h-14 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center">
            <Network aria-hidden="true" className="w-7 h-7 text-primary" />
          </div>
          <p className="text-sm font-medium text-foreground">No entities yet</p>
          <p className="text-sm text-muted-foreground text-center max-w-xs leading-relaxed">
            Process a document to populate the knowledge graph, or adjust your
            filters.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto nous-scrollbar">
          <Table>
            <TableHeader className="bg-muted/20 sticky top-0 z-10">
              <TableRow className="border-border hover:bg-transparent">
                <TableHead className="w-12"></TableHead>
                <TableHead className="text-xs font-medium text-muted-foreground">
                  Name
                </TableHead>
                <TableHead className="text-xs font-medium text-muted-foreground">
                  Type
                </TableHead>
                <TableHead className="text-xs font-medium text-muted-foreground">
                  Confidence
                </TableHead>
                <TableHead className="text-xs font-medium text-muted-foreground">
                  Details
                </TableHead>
                <TableHead className="text-xs font-medium text-muted-foreground">
                  Created
                </TableHead>
                <TableHead className="text-right text-xs font-medium text-muted-foreground pr-6">
                  Actions
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entities.map((entity) => (
                <TableRow
                  key={entity.id}
                  className={cn(
                    'border-border transition-colors group',
                    selectedItems.includes(entity.id)
                      ? 'bg-primary/5'
                      : 'hover:bg-muted/40'
                  )}
                >
                  <TableCell className="w-12">
                    <input
                      type="checkbox"
                      aria-label={`Select ${entity.name}`}
                      checked={selectedItems.includes(entity.id)}
                      onChange={() => handleSelectItem(entity.id)}
                      className="h-4 w-4 rounded border-border bg-background text-primary accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card"
                    />
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-0.5">
                      <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">
                        {entity.name}
                      </span>
                      {entity.metadata?.aliases &&
                        entity.metadata.aliases.length > 0 && (
                          <span className="text-xs text-muted-foreground">
                            Also known as{' '}
                            {entity.metadata.aliases.slice(0, 2).join(', ')}
                          </span>
                        )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className="border-border bg-muted text-muted-foreground font-normal"
                    >
                      {entity.type}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-1">
                      <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden border border-border">
                        <div
                          className="h-full bg-primary transition-all duration-500"
                          style={{
                            width: `${(entity.confidence || 0) * 100}%`,
                          }}
                        />
                      </div>
                      <span className="text-xs font-medium text-muted-foreground tabular-nums">
                        {((entity.confidence || 0) * 100).toFixed(1)}%
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div
                      className="text-xs text-muted-foreground max-w-xs truncate"
                      title={formatMetadata(entity.metadata ?? {})}
                    >
                      {formatMetadata(entity.metadata ?? {}) || (
                        <span className="text-muted-foreground/60">
                          No details
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Clock aria-hidden="true" className="w-3 h-3" />
                      {entity.created_at
                        ? new Date(entity.created_at).toLocaleDateString()
                        : 'Unknown'}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center justify-end gap-1 pr-2">
                      {onView && (
                        <IconButton
                          variant="ghost"
                          size="icon"
                          label="View entity details"
                          onClick={() => onView(entity)}
                          className="h-8 w-8 text-muted-foreground hover:text-primary hover:bg-primary/10"
                          icon={<Eye aria-hidden="true" className="h-4 w-4" />}
                        />
                      )}
                      {onEdit && (
                        <IconButton
                          variant="ghost"
                          size="icon"
                          label={
                            !canEdit
                              ? 'Edit entity (admin access required)'
                              : 'Edit entity'
                          }
                          onClick={() => onEdit(entity)}
                          disabled={!canEdit}
                          className="h-8 w-8 text-muted-foreground hover:text-primary hover:bg-primary/10 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent"
                          icon={<Edit aria-hidden="true" className="h-4 w-4" />}
                        />
                      )}
                      {entity.source_document_id && (
                        <IconButton
                          variant="ghost"
                          size="icon"
                          label="View source document"
                          onClick={() =>
                            window.open(
                              `/documents/${entity.source_document_id}`,
                              '_blank'
                            )
                          }
                          className="h-8 w-8 text-muted-foreground hover:text-primary hover:bg-primary/10"
                          icon={
                            <ExternalLink
                              aria-hidden="true"
                              className="h-4 w-4"
                            />
                          }
                        />
                      )}
                      {onDelete && (
                        <IconButton
                          variant="ghost"
                          size="icon"
                          label={
                            !canDelete
                              ? 'Delete entity (admin access required)'
                              : 'Delete entity'
                          }
                          onClick={() => onDelete(entity.id)}
                          disabled={!canDelete}
                          className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent"
                          icon={
                            <Trash2 aria-hidden="true" className="h-4 w-4" />
                          }
                        />
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
};
