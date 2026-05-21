'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  Network,
  RefreshCw,
} from 'lucide-react';
import { api } from '@/services/api-client';
import { APIErrorClass } from '@/types/api';

interface KnowledgeEntity {
  id: string;
  name: string;
  entity_type: string;
  confidence_score: number;
  source_document_id?: string | null;
  metadata?: Record<string, unknown>;
}

interface KnowledgeRelationship {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relationship_type: string;
  strength: number;
}

interface PaginatedEntities {
  entities: KnowledgeEntity[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

interface ProjectKnowledgeTreeProps {
  projectId: string;
}

const ENTITY_FETCH_LIMIT = 500;
const RELATIONSHIP_FETCH_LIMIT = 1000;

function readErrorMessage(err: unknown): string {
  if (err instanceof APIErrorClass) return err.message;
  if (err instanceof Error) return err.message;
  return 'Failed to load the knowledge tree';
}

export function ProjectKnowledgeTree({ projectId }: ProjectKnowledgeTreeProps) {
  const [entities, setEntities] = useState<KnowledgeEntity[]>([]);
  const [relationships, setRelationships] = useState<KnowledgeRelationship[]>(
    []
  );
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [entityPage, relList] = await Promise.all([
        api.get<PaginatedEntities>(`/knowledge-graph/entities?project_id=${projectId}&limit=${ENTITY_FETCH_LIMIT}`),
        api.get<KnowledgeRelationship[]>(
          `/knowledge-graph/relationships?project_id=${projectId}&limit=${RELATIONSHIP_FETCH_LIMIT}`
        ),
      ]);
      setEntities(entityPage.entities);
      setTotal(entityPage.total);
      setRelationships(relList);
    } catch (err) {
      setError(readErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const grouped = useMemo(() => {
    const map = new Map<string, KnowledgeEntity[]>();
    for (const entity of entities) {
      const key = entity.entity_type || 'OTHER';
      const bucket = map.get(key);
      if (bucket) {
        bucket.push(entity);
      } else {
        map.set(key, [entity]);
      }
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [entities]);

  const toggle = (key: string) => {
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Network className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-medium">Knowledge Tree</h2>
          <span className="text-sm text-muted-foreground">
            {total} {total === 1 ? 'entity' : 'entities'} ·{' '}
            {relationships.length} relationship
            {relationships.length === 1 ? '' : 's'}
          </span>
        </div>
        <button
          onClick={() => void load()}
          disabled={loading}
          className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 border border-border rounded-md hover:bg-muted/40 disabled:opacity-50"
        >
          {loading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          Refresh
        </button>
      </div>

      {error && (
        <div className="p-3 bg-destructive/10 border border-destructive/30 rounded-md text-sm text-destructive">
          {error}
        </div>
      )}

      {loading && entities.length === 0 ? (
        <div className="flex items-center justify-center py-16 text-muted-foreground text-sm">
          <Loader2 className="h-5 w-5 animate-spin mr-2" />
          Loading knowledge tree…
        </div>
      ) : !loading && entities.length === 0 && !error ? (
        <div className="py-12 text-center text-sm text-muted-foreground border border-dashed border-border rounded-md">
          <p>No entities have been extracted for this project yet.</p>
          <p className="mt-1 text-xs">
            Extraction is queued automatically when you add a document. Refresh
            in a moment to see results.
          </p>
        </div>
      ) : (
        <ul className="border border-border rounded-md divide-y divide-border">
          {grouped.map(([type, items]) => {
            const isCollapsed = collapsed[type] ?? false;
            return (
              <li key={type}>
                <button
                  onClick={() => toggle(type)}
                  className="w-full flex items-center justify-between px-3 py-2 hover:bg-muted/30 text-left"
                >
                  <span className="flex items-center gap-2 text-sm font-medium">
                    {isCollapsed ? (
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    )}
                    {type}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {items.length}
                  </span>
                </button>
                {!isCollapsed && (
                  <ul className="bg-muted/10">
                    {items.map((entity) => (
                      <li
                        key={entity.id}
                        className="px-9 py-1.5 text-sm flex items-center justify-between gap-3"
                      >
                        <span className="truncate">{entity.name}</span>
                        <span className="text-xs text-muted-foreground shrink-0">
                          {(entity.confidence_score * 100).toFixed(0)}%
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
