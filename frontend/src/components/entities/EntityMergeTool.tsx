/**
 * EntityMergeTool Component
 * Identifies and merges duplicate entities in the knowledge graph
 */

import React, { useEffect, useState } from 'react';
import {
  GitMerge,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  Search,
  Lock,
  XCircle,
  RefreshCw,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import { Label } from '@/components/ui/label';
import { Entity } from '@/types/entity';
import { entityService } from '@/services/entityService';
import { useEntityPermissions } from '@/hooks/useEntityPermissions';
import { APIErrorClass } from '@/types/api';
import toast from 'react-hot-toast';

interface DuplicateGroup {
  entities: Entity[];
  similarity: number;
  suggested_primary: string;
}

const isServiceUnavailableError = (error: unknown): boolean => {
  if (!(error instanceof APIErrorClass)) return false;
  const message = error.error.message?.toLowerCase() || '';
  return (
    error.error.status_code >= 500 ||
    message.includes('service unavailable') ||
    message.includes('circuit breaker')
  );
};

const isRetryablePollError = (error: unknown): boolean => {
  if (error instanceof APIErrorClass) {
    const statusCode = error.error.status_code;
    return [404, 429, 500, 502, 503, 504].includes(statusCode);
  }
  return true;
};

export const EntityMergeTool: React.FC = () => {
  const { canBulkEdit } = useEntityPermissions();
  const [loading, setLoading] = useState(false);
  const [duplicates, setDuplicates] = useState<DuplicateGroup[]>([]);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.85);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedGroups, setSelectedGroups] = useState<Set<number>>(new Set());
  const [error, setError] = useState<{ message: string; context: 'fetch' | 'merge' } | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState(0);
  const [jobStep, setJobStep] = useState('');

  useEffect(() => {
    if (!activeJobId) return;
    let consecutivePollFailures = 0;

    const poll = setInterval(async () => {
      try {
        const job = await entityService.getProcessingJob(activeJobId);
        consecutivePollFailures = 0;
        setJobProgress(job.progress_percentage || 0);
        setJobStep(job.current_step || 'Processing merge job');

        if (job.status === 'completed') {
          clearInterval(poll);
          setActiveJobId(null);
          setSelectedGroups(new Set());
          toast.success('Merge job completed');
          findDuplicates();
        }

        if (job.status === 'failed' || job.status === 'cancelled') {
          clearInterval(poll);
          setActiveJobId(null);
          setError({
            message: job.error_message || 'Merge job failed',
            context: 'merge',
          });
          toast.error('Merge job failed');
        }
      } catch (pollError) {
        if (isRetryablePollError(pollError) && consecutivePollFailures < 10) {
          consecutivePollFailures += 1;
          setJobStep('Waiting for job status...');
          return;
        }
        clearInterval(poll);
        setActiveJobId(null);
        setError({ message: 'Failed to fetch merge job status', context: 'merge' });
      }
    }, 2000);

    return () => clearInterval(poll);
  }, [activeJobId]);

  if (!canBulkEdit) {
    return (
      <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
        <CardHeader>
          <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
            <Lock className="w-4 h-4" />
            Entity Merge Tool
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="text-center py-12">
            <Lock className="w-12 h-12 mx-auto mb-4 text-[var(--terminal-text-dim)]" />
            <p className="text-sm font-mono text-[var(--terminal-text-dim)]">
              Entity merging is restricted to administrators only.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const findDuplicates = async () => {
    try {
      setLoading(true);
      setError(null);

      const PAGE_SIZE = 100;
      let offset = 0;
      let allEntities: any[] = [];
      let hasMore = true;

      while (hasMore) {
        const response = await entityService.getEntities(PAGE_SIZE, offset);
        const batch = response.entities;
        allEntities = allEntities.concat(batch);
        offset += PAGE_SIZE;
        hasMore = batch.length === PAGE_SIZE;
      }

      const entities = allEntities.map((e: any) => ({
        id: e.id,
        name: e.name,
        type: e.entity_type,
        confidence: e.confidence_score,
        confidence_score: e.confidence_score,
        extraction_method: e.extraction_method,
        position: e.position,
        context: e.context,
        metadata: e.metadata,
        created_at: e.created_at,
        updated_at: e.updated_at,
        source_document_id: e.source_document_id,
      }));

      const groups: DuplicateGroup[] = [];
      const processed = new Set<string>();
      const buckets = new Map<string, Entity[]>();

      for (const entity of entities) {
        const prefix = entity.name.toLowerCase().slice(0, 3).padEnd(3, '_');
        if (!buckets.has(prefix)) buckets.set(prefix, []);
        buckets.get(prefix)!.push(entity);
      }

      for (const [, bucket] of buckets) {
        for (let i = 0; i < bucket.length; i++) {
          if (processed.has(bucket[i].id)) continue;

          const similar: Entity[] = [bucket[i]];
          processed.add(bucket[i].id);

          for (let j = i + 1; j < bucket.length; j++) {
            if (processed.has(bucket[j].id)) continue;

            const similarity = calculateSimilarity(
              bucket[i].name.toLowerCase(),
              bucket[j].name.toLowerCase()
            );

            if (similarity >= similarityThreshold) {
              similar.push(bucket[j]);
              processed.add(bucket[j].id);
            }
          }

          if (similar.length > 1) {
            const sortedByConfidence = [...similar].sort(
              (a, b) => (b.confidence || 0) - (a.confidence || 0)
            );

            groups.push({
              entities: similar,
              similarity:
                similar.length > 2
                  ? 0.9
                  : calculateSimilarity(
                      similar[0].name.toLowerCase(),
                      similar[1].name.toLowerCase()
                    ),
              suggested_primary: sortedByConfidence[0].id,
            });
          }
        }
      }

      setDuplicates(groups);
      setSelectedGroups(new Set());
      toast.success(`Found ${groups.length} duplicate groups`);
    } catch (err) {
      if (isServiceUnavailableError(err)) {
        console.warn('Duplicate scan unavailable:', err);
      } else {
        console.error('Error finding duplicates:', err);
      }
      const message =
        isServiceUnavailableError(err)
          ? 'Knowledge graph is temporarily unavailable. Please try again shortly.'
          : err instanceof Error
          ? err.message
          : 'Failed to find duplicates';
      setError({ message, context: 'fetch' });
      toast.error('Failed to find duplicates');
    } finally {
      setLoading(false);
    }
  };

  const calculateSimilarity = (str1: string, str2: string): number => {
    const longer = str1.length > str2.length ? str1 : str2;
    const shorter = str1.length > str2.length ? str2 : str1;

    if (longer.length === 0) return 1.0;

    const editDistance = levenshteinDistance(longer, shorter);
    return (longer.length - editDistance) / longer.length;
  };

  const levenshteinDistance = (str1: string, str2: string): number => {
    const matrix: number[][] = [];

    for (let i = 0; i <= str2.length; i++) matrix[i] = [i];
    for (let j = 0; j <= str1.length; j++) matrix[0][j] = j;

    for (let i = 1; i <= str2.length; i++) {
      for (let j = 1; j <= str1.length; j++) {
        if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
          matrix[i][j] = matrix[i - 1][j - 1];
        } else {
          matrix[i][j] = Math.min(
            matrix[i - 1][j - 1] + 1,
            matrix[i][j - 1] + 1,
            matrix[i - 1][j] + 1
          );
        }
      }
    }

    return matrix[str2.length][str1.length];
  };

  const enqueueMergeJob = async (groups: DuplicateGroup[]) => {
    try {
      const payload = groups.map((group) => ({
        entities: group.entities.map((entity) => ({ id: entity.id, name: entity.name })),
        suggested_primary: group.suggested_primary,
      }));

      const response = await entityService.createMergeJob(payload);
      if (!response.job_id || response.job_id === 'None') {
        throw new Error('Merge job was not created. Please retry.');
      }
      setActiveJobId(response.job_id);
      setJobProgress(0);
      setJobStep('Merge job queued');
      toast.success('Merge job queued');
    } catch (err) {
      if (isServiceUnavailableError(err)) {
        console.warn('Merge unavailable:', err);
      } else {
        console.error('Error queueing merge job:', err);
      }
      setError({
        message:
          err instanceof Error
            ? err.message
            : 'Failed to queue merge job',
        context: 'merge',
      });
      toast.error('Failed to queue merge job');
    }
  };

  const handleMergeGroup = async (group: DuplicateGroup) => {
    const confirmed = window.confirm(
      `Merge ${group.entities.length} entities into "${
        group.entities.find((e) => e.id === group.suggested_primary)?.name
      }"?\n\nThis action cannot be undone.`
    );
    if (!confirmed) return;
    await enqueueMergeJob([group]);
  };

  const toggleGroupSelection = (index: number) => {
    setSelectedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const handleBatchMerge = async () => {
    if (selectedGroups.size === 0) {
      toast.error('No groups selected');
      return;
    }

    const confirmed = window.confirm(
      `Merge ${selectedGroups.size} selected groups?\n\nThis action cannot be undone.`
    );
    if (!confirmed) return;

    const selected = Array.from(selectedGroups)
      .sort((a, b) => a - b)
      .map((index) => duplicates[index])
      .filter(Boolean);

    await enqueueMergeJob(selected);
  };

  const filteredDuplicates = duplicates
    .map((group, index) => ({ group, index }))
    .filter(({ group }) =>
      group.entities.some((e) =>
        e.name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    );

  const visibleSelectedCount = filteredDuplicates.reduce(
    (count, { index }) => count + (selectedGroups.has(index) ? 1 : 0),
    0
  );
  const allVisibleSelected =
    filteredDuplicates.length > 0 &&
    visibleSelectedCount === filteredDuplicates.length;

  const handleToggleSelectAllVisible = () => {
    setSelectedGroups((prev) => {
      const next = new Set(prev);
      if (allVisibleSelected) {
        filteredDuplicates.forEach(({ index }) => next.delete(index));
      } else {
        filteredDuplicates.forEach(({ index }) => next.add(index));
      }
      return next;
    });
  };

  return (
    <div className="space-y-4">
      <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
        <CardHeader className="border-b border-[var(--terminal-border)] py-3">
          <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
            <GitMerge className="w-4 h-4" />
            Entity Merge Tool - Duplicate Detection
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-4">
          <div className="space-y-2">
            <Label className="text-xs font-mono text-[var(--terminal-text-dim)]">
              Similarity Threshold: {(similarityThreshold * 100).toFixed(0)}%
            </Label>
            <Slider
              value={[similarityThreshold * 100]}
              onValueChange={(value) => setSimilarityThreshold(value[0] / 100)}
              min={50}
              max={100}
              step={5}
              className="w-full"
            />
          </div>

          {duplicates.length > 0 && (
            <div className="space-y-2">
              <Label className="text-xs font-mono text-[var(--terminal-text-dim)]">
                Filter Duplicates
              </Label>
              <Input
                placeholder="Search duplicate groups..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="font-mono text-xs bg-[var(--terminal-bg)] border-[var(--terminal-border)] text-[var(--terminal-text)]"
              />
            </div>
          )}

          {activeJobId && (
            <div className="text-xs font-mono text-[var(--terminal-text-dim)] border border-[var(--terminal-border)] rounded-md p-2">
              <p>MERGE_JOB: {activeJobId}</p>
              <p>STATUS: {jobStep || 'Running'}</p>
              <p>PROGRESS: {Math.round(jobProgress)}%</p>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <Button
              onClick={findDuplicates}
              disabled={loading || !!activeJobId}
              className="font-mono text-xs font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)]"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  SCANNING...
                </>
              ) : (
                <>
                  <Search className="w-4 h-4 mr-2" />
                  FIND_DUPLICATES
                </>
              )}
            </Button>

            {filteredDuplicates.length > 0 && (
              <Button
                onClick={handleToggleSelectAllVisible}
                variant="outline"
                disabled={!!activeJobId}
                className="font-mono text-xs font-bold border-[var(--terminal-border)]"
              >
                {allVisibleSelected ? 'DESELECT_ALL' : 'SELECT_ALL'}
              </Button>
            )}

            {duplicates.length > 0 && selectedGroups.size > 0 && (
              <Button
                onClick={handleBatchMerge}
                variant="outline"
                disabled={!!activeJobId}
                className="font-mono text-xs font-bold border-[var(--terminal-border)]"
              >
                <GitMerge className="w-4 h-4 mr-2" />
                MERGE_SELECTED ({selectedGroups.size})
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-red-500/50 bg-red-950/30">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <XCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-mono font-bold text-red-400">
                  {error.context === 'fetch' ? 'Scan Failed' : 'Merge Failed'}
                </p>
                <p className="text-xs font-mono text-red-400/80 mt-1 break-words">
                  {error.message}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Button
                  onClick={() => {
                    setError(null);
                    if (error.context === 'fetch') findDuplicates();
                  }}
                  size="sm"
                  variant="outline"
                  className="font-mono text-[10px] border-red-500/50 text-red-400"
                >
                  <RefreshCw className="w-3 h-3 mr-1" />
                  RETRY
                </Button>
                <Button
                  onClick={() => setError(null)}
                  size="sm"
                  variant="ghost"
                  className="font-mono text-[10px] text-red-400/60 px-2"
                >
                  <X className="w-3 h-3" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {filteredDuplicates.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-mono font-bold text-[var(--terminal-text)]">
              Found {filteredDuplicates.length} Duplicate Group
              {filteredDuplicates.length > 1 ? 's' : ''}
            </h3>
          </div>

          {filteredDuplicates.map(({ group, index }) => (
            <Card key={index} className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
              <CardContent className="p-4">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selectedGroups.has(index)}
                      onChange={() => toggleGroupSelection(index)}
                      className="w-4 h-4"
                    />
                    <AlertTriangle className="w-4 h-4 text-[var(--amber-gold)]" />
                    <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                      {group.entities.length} similar entities
                    </span>
                    <Badge variant="outline" className="font-mono text-[10px] border-[var(--terminal-border)]">
                      {(group.similarity * 100).toFixed(0)}% match
                    </Badge>
                  </div>
                  <Button
                    onClick={() => handleMergeGroup(group)}
                    size="sm"
                    disabled={!!activeJobId}
                    className="font-mono text-[10px] bg-[var(--phosphor-green)] text-[var(--terminal-bg)]"
                  >
                    <GitMerge className="w-3 h-3 mr-1" />
                    MERGE
                  </Button>
                </div>

                <div className="space-y-2">
                  {group.entities.map((entity) => (
                    <div
                      key={entity.id}
                      className={`p-2 rounded-md border ${
                        entity.id === group.suggested_primary
                          ? 'border-[var(--phosphor-green)] bg-[var(--phosphor-green)]/10'
                          : 'border-[var(--terminal-border)] bg-[var(--terminal-bg)]'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-mono font-bold text-[var(--terminal-text)]">
                              {entity.name}
                            </span>
                            {entity.id === group.suggested_primary && (
                              <Badge
                                variant="outline"
                                className="font-mono text-[10px] bg-[var(--phosphor-green)] text-[var(--terminal-bg)] border-[var(--phosphor-green)]"
                              >
                                <CheckCircle2 className="w-3 h-3 mr-1" />
                                PRIMARY
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-3 mt-1 text-xs font-mono text-[var(--terminal-text-dim)]">
                            <span>{entity.type}</span>
                            <span>•</span>
                            <span>
                              Confidence: {((entity.confidence || 0) * 100).toFixed(0)}%
                            </span>
                            <span>•</span>
                            <span>{new Date(entity.created_at).toLocaleDateString()}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {!loading && duplicates.length === 0 && (
        <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
          <CardContent className="p-8 text-center">
            <GitMerge className="w-12 h-12 mx-auto mb-4 text-[var(--terminal-text-dim)]" />
            <p className="text-sm font-mono text-[var(--terminal-text)]">No duplicates found</p>
            <p className="text-xs font-mono text-[var(--terminal-text-dim)] mt-2">
              Click FIND_DUPLICATES to scan for similar entities
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
