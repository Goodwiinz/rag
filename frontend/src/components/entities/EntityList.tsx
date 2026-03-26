/**
 * EntityList Component
 * Terminal Observatory themed entity list with role-based access control
 */

import React, { useState } from 'react';
import {
  Edit,
  Trash2,
  Eye,
  ExternalLink,
  Clock,
  CheckCircle,
  Info,
  Database,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { IconButton } from '@/components/ui/icon-button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Entity, EntityType } from '@/types/entity';
import { useEntityPermissions } from '@/hooks/useEntityPermissions';
import { cn } from '@/lib/utils';

interface EntityListProps {
  entities: Entity[];
  loading?: boolean;
  onEdit?: (entity: Entity) => void;
  onView?: (entity: Entity) => void;
  onDelete?: (entityId: string) => void;
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
  return 'text-[var(--terminal-text-muted)]';
};

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
      <div className="flex flex-col h-full bg-[var(--terminal-surface)]">
        {/* Skeleton header bar */}
        <div className="px-6 py-3 border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-4 h-4 rounded bg-[var(--terminal-border)] animate-pulse" />
            <div className="w-20 h-3 rounded bg-[var(--terminal-border)] animate-pulse" />
          </div>
          <div className="w-32 h-3 rounded bg-[var(--terminal-border)] animate-pulse" />
        </div>

        {/* Skeleton table header */}
        <div className="px-6 py-2.5 border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)]/30 grid grid-cols-[3rem_1fr_8rem_5rem_1fr_7rem_7rem] gap-4 items-center">
          <div className="w-4 h-3 rounded bg-[var(--terminal-border)] animate-pulse" />
          <div className="w-24 h-3 rounded bg-[var(--terminal-border)] animate-pulse" />
          <div className="w-20 h-3 rounded bg-[var(--terminal-border)] animate-pulse" />
          <div className="w-16 h-3 rounded bg-[var(--terminal-border)] animate-pulse" />
          <div className="w-28 h-3 rounded bg-[var(--terminal-border)] animate-pulse" />
          <div className="w-20 h-3 rounded bg-[var(--terminal-border)] animate-pulse" />
          <div className="w-20 h-3 rounded bg-[var(--terminal-border)] animate-pulse ml-auto" />
        </div>

        {/* Skeleton rows */}
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="px-6 py-3.5 border-b border-[var(--terminal-border)] grid grid-cols-[3rem_1fr_8rem_5rem_1fr_7rem_7rem] gap-4 items-center"
            style={{ animationDelay: `${i * 75}ms` }}
          >
            <div
              className="w-4 h-4 rounded bg-[var(--terminal-border)] animate-pulse"
              style={{ animationDelay: `${i * 75}ms` }}
            />
            <div className="space-y-1.5">
              <div
                className="h-4 rounded bg-[var(--terminal-border)] animate-pulse"
                style={{
                  width: `${60 + (i % 3) * 15}%`,
                  animationDelay: `${i * 75}ms`,
                }}
              />
              <div
                className="h-2.5 rounded bg-[var(--terminal-border)]/50 animate-pulse"
                style={{
                  width: `${30 + (i % 2) * 20}%`,
                  animationDelay: `${i * 75}ms`,
                }}
              />
            </div>
            <div
              className="h-5 rounded-full bg-[var(--terminal-border)] animate-pulse"
              style={{
                width: `${50 + (i % 4) * 10}%`,
                animationDelay: `${i * 75}ms`,
              }}
            />
            <div className="space-y-1">
              <div
                className="h-1.5 rounded-full bg-[var(--terminal-border)] animate-pulse"
                style={{ animationDelay: `${i * 75}ms` }}
              />
              <div
                className="h-3 w-10 rounded bg-[var(--terminal-border)]/50 animate-pulse"
                style={{ animationDelay: `${i * 75}ms` }}
              />
            </div>
            <div
              className="h-3 rounded bg-[var(--terminal-border)]/50 animate-pulse"
              style={{
                width: `${40 + (i % 3) * 20}%`,
                animationDelay: `${i * 75}ms`,
              }}
            />
            <div
              className="h-3 w-16 rounded bg-[var(--terminal-border)]/50 animate-pulse"
              style={{ animationDelay: `${i * 75}ms` }}
            />
            <div className="flex items-center justify-end gap-1.5">
              <div
                className="w-7 h-7 rounded bg-[var(--terminal-border)] animate-pulse"
                style={{ animationDelay: `${i * 75}ms` }}
              />
              <div
                className="w-7 h-7 rounded bg-[var(--terminal-border)] animate-pulse"
                style={{ animationDelay: `${i * 75 + 25}ms` }}
              />
              <div
                className="w-7 h-7 rounded bg-[var(--terminal-border)] animate-pulse"
                style={{ animationDelay: `${i * 75 + 50}ms` }}
              />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[var(--terminal-surface)]">
      {/* Header with selection controls */}
      <div className="px-6 py-3 border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <input
            type="checkbox"
            checked={
              selectedItems.length === entities.length && entities.length > 0
            }
            onChange={handleSelectAll}
            className="rounded border-[var(--terminal-border)] bg-[var(--terminal-bg)] text-[var(--phosphor-green)] focus:ring-0 focus:ring-offset-0"
          />
          <span className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest">
            Select All
          </span>
          {selectedItems.length > 0 && (
            <div className="flex items-center gap-3 ml-4 pl-4 border-l border-[var(--terminal-border)]">
              <Badge
                variant="outline"
                className="font-mono text-[10px] border-[var(--phosphor-green)]/30 text-[var(--phosphor-green)] bg-[var(--phosphor-green)]/5"
              >
                {selectedItems.length} SELECTED
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedItems([])}
                className="h-7 text-[10px] font-mono text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)]"
              >
                CLEAR_SELECTION
              </Button>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 text-[10px] font-mono text-[var(--terminal-text-muted)]">
          <span>{entities.length} ENTITIES_LOADED</span>
        </div>
      </div>

      {/* Table */}
      {entities.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center py-16 gap-3">
          <div className="w-14 h-14 rounded-full bg-[var(--terminal-bg)] border border-[var(--terminal-border)] flex items-center justify-center">
            <Database className="w-7 h-7 text-[var(--terminal-text-muted)] opacity-40" />
          </div>
          <p className="text-sm font-mono font-bold text-[var(--terminal-text-dim)] uppercase tracking-wider">
            NO_ENTITIES_FOUND
          </p>
          <p className="text-xs font-mono text-[var(--terminal-text-muted)] text-center max-w-xs leading-relaxed">
            No entities match the current filters. Try adjusting your search
            query, type selections, or confidence range.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto terminal-scrollbar">
          <Table>
            <TableHeader className="bg-[var(--terminal-bg)]/30 sticky top-0 z-10">
              <TableRow className="border-[var(--terminal-border)] hover:bg-transparent">
                <TableHead className="w-12"></TableHead>
                <TableHead className="font-mono text-[10px] uppercase tracking-widest text-[var(--terminal-text-dim)]">
                  Node_Identity
                </TableHead>
                <TableHead className="font-mono text-[10px] uppercase tracking-widest text-[var(--terminal-text-dim)]">
                  Classification
                </TableHead>
                <TableHead className="font-mono text-[10px] uppercase tracking-widest text-[var(--terminal-text-dim)]">
                  Confidence
                </TableHead>
                <TableHead className="font-mono text-[10px] uppercase tracking-widest text-[var(--terminal-text-dim)]">
                  Attributes_Dump
                </TableHead>
                <TableHead className="font-mono text-[10px] uppercase tracking-widest text-[var(--terminal-text-dim)]">
                  Timestamp
                </TableHead>
                <TableHead className="text-right font-mono text-[10px] uppercase tracking-widest text-[var(--terminal-text-dim)] pr-6">
                  Direct_Access
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entities.map((entity) => (
                <TableRow
                  key={entity.id}
                  className={cn(
                    'border-[var(--terminal-border)] transition-colors group',
                    selectedItems.includes(entity.id)
                      ? 'bg-[var(--phosphor-green)]/5'
                      : 'hover:bg-[var(--terminal-elevated)]'
                  )}
                >
                  <TableCell className="w-12">
                    <input
                      type="checkbox"
                      checked={selectedItems.includes(entity.id)}
                      onChange={() => handleSelectItem(entity.id)}
                      className="rounded border-[var(--terminal-border)] bg-[var(--terminal-bg)] text-[var(--phosphor-green)] focus:ring-0 focus:ring-offset-0"
                    />
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-0.5">
                      <span className="font-mono text-sm font-bold text-[var(--terminal-text)] group-hover:text-[var(--phosphor-green)] transition-colors">
                        {entity.name}
                      </span>
                      {entity.metadata?.aliases &&
                        entity.metadata.aliases.length > 0 && (
                          <span className="text-[9px] font-mono text-[var(--terminal-text-muted)] uppercase mt-0.5">
                            AKA:{' '}
                            {entity.metadata.aliases.slice(0, 2).join(', ')}
                          </span>
                        )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={cn(
                        'font-mono text-[10px] uppercase tracking-wide border',
                        typeColors[entity.type] ||
                          'text-gray-400 bg-gray-400/10 border-gray-400/20'
                      )}
                    >
                      {entity.type}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-1">
                      <div className="w-16 h-1.5 bg-[var(--terminal-bg)] rounded-full overflow-hidden border border-[var(--terminal-border)]">
                        <div
                          className={cn(
                            'h-full transition-all duration-500',
                            entity.confidence && entity.confidence >= 0.8
                              ? 'bg-[var(--phosphor-green)]'
                              : 'bg-[var(--amber-gold)]'
                          )}
                          style={{
                            width: `${(entity.confidence || 0) * 100}%`,
                          }}
                        />
                      </div>
                      <span
                        className={cn(
                          'font-mono text-[10px] font-bold',
                          getConfidenceColor(entity.confidence || 0)
                        )}
                      >
                        {((entity.confidence || 0) * 100).toFixed(1)}%
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div
                      className="text-[10px] font-mono text-[var(--terminal-text-dim)] max-w-xs truncate"
                      title={formatMetadata(entity.metadata ?? {})}
                    >
                      {formatMetadata(entity.metadata ?? {}) || 'NO_METADATA'}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5 text-[10px] font-mono text-[var(--terminal-text-muted)]">
                      <Clock className="w-3 h-3" />
                      {entity.created_at
                        ? new Date(entity.created_at).toLocaleDateString()
                        : 'N/A'}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center justify-end gap-1 pr-2">
                      {onView && (
                        <IconButton
                          variant="ghost"
                          label="View entity details"
                          onClick={() => onView(entity)}
                          className="h-8 w-8 text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] hover:bg-[var(--phosphor-green)]/10"
                          icon={<Eye className="h-4 w-4" />}
                        />
                      )}
                      {onEdit && (
                        <IconButton
                          variant="ghost"
                          label={
                            !canEdit
                              ? 'Edit entity (Admin access required)'
                              : 'Edit entity'
                          }
                          onClick={() => onEdit(entity)}
                          disabled={!canEdit}
                          className="h-8 w-8 text-[var(--terminal-text-dim)] hover:text-[var(--cyan)] hover:bg-[var(--cyan)]/10 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent"
                          icon={<Edit className="h-4 w-4" />}
                        />
                      )}
                      {entity.source_document_id && (
                        <IconButton
                          variant="ghost"
                          label="View source document"
                          onClick={() =>
                            window.open(
                              `/documents/${entity.source_document_id}`,
                              '_blank'
                            )
                          }
                          className="h-8 w-8 text-[var(--terminal-text-dim)] hover:text-[var(--amber-gold)] hover:bg-[var(--amber-gold)]/10"
                          icon={<ExternalLink className="h-4 w-4" />}
                        />
                      )}
                      {onDelete && (
                        <IconButton
                          variant="ghost"
                          label={
                            !canDelete
                              ? 'Delete entity (Admin access required)'
                              : 'Delete entity'
                          }
                          onClick={() => onDelete(entity.id)}
                          disabled={!canDelete}
                          className="h-8 w-8 text-[var(--terminal-text-dim)] hover:text-red-400 hover:bg-red-400/10 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent"
                          icon={<Trash2 className="h-4 w-4" />}
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
