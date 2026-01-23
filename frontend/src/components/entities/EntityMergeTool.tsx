/**
 * EntityMergeTool Component
 * Identifies and merges duplicate entities in the knowledge graph
 */

import React, { useState, useEffect } from 'react';
import { GitMerge, Loader2, AlertTriangle, CheckCircle2, Search, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import { Label } from '@/components/ui/label';
import { Entity } from '@/types/entity';
import { entityService } from '@/services/entityService';
import { useEntityPermissions } from '@/hooks/useEntityPermissions';
import toast from 'react-hot-toast';

interface DuplicateGroup {
  entities: Entity[];
  similarity: number;
  suggested_primary: string;
}

export const EntityMergeTool: React.FC = () => {
  const { canBulkEdit, isAdmin } = useEntityPermissions();
  const [loading, setLoading] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [duplicates, setDuplicates] = useState<DuplicateGroup[]>([]);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.85);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedGroups, setSelectedGroups] = useState<Set<number>>(new Set());

  // Show admin-only notice if user lacks permissions
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
            <p className="text-xs font-mono text-[var(--terminal-text-dim)] mt-2">
              Contact your system administrator for access.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const findDuplicates = async () => {
    try {
      setLoading(true);
      
      // Fetch all entities
      const response = await entityService.getEntities(1000, 0);
      const entities = response.entities.map((e: any) => ({
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
        source_document_id: e.source_document_id
      }));

      // Find duplicates using name similarity
      const groups: DuplicateGroup[] = [];
      const processed = new Set<string>();

      for (let i = 0; i < entities.length; i++) {
        if (processed.has(entities[i].id)) continue;

        const similar: Entity[] = [entities[i]];
        processed.add(entities[i].id);

        for (let j = i + 1; j < entities.length; j++) {
          if (processed.has(entities[j].id)) continue;

          const similarity = calculateSimilarity(
            entities[i].name.toLowerCase(),
            entities[j].name.toLowerCase()
          );

          if (similarity >= similarityThreshold) {
            similar.push(entities[j]);
            processed.add(entities[j].id);
          }
        }

        if (similar.length > 1) {
          // Choose entity with highest confidence as primary
          const sortedByConfidence = [...similar].sort(
            (a, b) => (b.confidence || 0) - (a.confidence || 0)
          );

          groups.push({
            entities: similar,
            similarity: similar.length > 2 ? 0.9 : calculateSimilarity(
              similar[0].name.toLowerCase(),
              similar[1].name.toLowerCase()
            ),
            suggested_primary: sortedByConfidence[0].id,
          });
        }
      }

      setDuplicates(groups);
      toast.success(`Found ${groups.length} duplicate groups`);
    } catch (error) {
      console.error('Error finding duplicates:', error);
      toast.error('Failed to find duplicates');
    } finally {
      setLoading(false);
    }
  };

  const calculateSimilarity = (str1: string, str2: string): number => {
    // Levenshtein distance-based similarity
    const longer = str1.length > str2.length ? str1 : str2;
    const shorter = str1.length > str2.length ? str2 : str1;
    
    if (longer.length === 0) return 1.0;
    
    const editDistance = levenshteinDistance(longer, shorter);
    return (longer.length - editDistance) / longer.length;
  };

  const levenshteinDistance = (str1: string, str2: string): number => {
    const matrix: number[][] = [];

    for (let i = 0; i <= str2.length; i++) {
      matrix[i] = [i];
    }

    for (let j = 0; j <= str1.length; j++) {
      matrix[0][j] = j;
    }

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

  const handleMergeGroup = async (group: DuplicateGroup, groupIndex: number) => {
    const confirmed = window.confirm(
      `Merge ${group.entities.length} entities into "${
        group.entities.find(e => e.id === group.suggested_primary)?.name
      }"?\n\nThis will:\n- Keep the primary entity\n- Transfer all relationships\n- Delete duplicate entities\n\nThis action cannot be undone.`
    );

    if (!confirmed) return;

    try {
      const primaryEntity = group.entities.find(e => e.id === group.suggested_primary);
      const duplicateIds = group.entities
        .filter(e => e.id !== group.suggested_primary)
        .map(e => e.id);

      // For each duplicate, transfer relationships and delete
      for (const duplicateId of duplicateIds) {
        // Get relationships of duplicate
        const relationships = await entityService.getEntityRelationships(duplicateId);

        // Create new relationships pointing to primary
        for (const rel of relationships) {
          const newRelData: any = {
            source_entity_id: rel.source === duplicateId ? group.suggested_primary : rel.source,
            target_entity_id: rel.target === duplicateId ? group.suggested_primary : rel.target,
            relationship_type: rel.type,
            strength: rel.strength,
            confidence_score: rel.confidence,
            context: rel.context,
            metadata: rel.metadata,
          };

          try {
            await entityService.createRelationship(newRelData);
          } catch (error) {
            // Ignore duplicate relationship errors
            console.warn('Duplicate relationship:', error);
          }
        }

        // Delete the duplicate entity
        await entityService.deleteEntity(duplicateId);
      }

      toast.success(`Merged ${group.entities.length} entities successfully`);

      // Remove this group from the list
      setDuplicates(prev => prev.filter((_, i) => i !== groupIndex));
    } catch (error) {
      console.error('Error merging entities:', error);
      toast.error('Failed to merge entities');
    }
  };

  const toggleGroupSelection = (index: number) => {
    setSelectedGroups(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
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

    let successCount = 0;
    let errorCount = 0;

    for (const index of Array.from(selectedGroups).sort((a, b) => b - a)) {
      try {
        await handleMergeGroup(duplicates[index], index);
        successCount++;
      } catch (error) {
        errorCount++;
      }
    }

    toast.success(`Batch merge complete: ${successCount} succeeded, ${errorCount} failed`);
    setSelectedGroups(new Set());
  };

  const filteredDuplicates = duplicates.filter(group =>
    group.entities.some(e =>
      e.name.toLowerCase().includes(searchQuery.toLowerCase())
    )
  );

  return (
    <div className="space-y-4">
      {/* Controls */}
      <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
        <CardHeader className="border-b border-[var(--terminal-border)] py-3">
          <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
            <GitMerge className="w-4 h-4" />
            Entity Merge Tool - Duplicate Detection
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-4">
          {/* Similarity Threshold */}
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
            <p className="text-xs font-mono text-[var(--terminal-text-dim)]">
              Higher threshold = stricter matching (fewer duplicates)
            </p>
          </div>

          {/* Search Bar */}
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

          {/* Action Buttons */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <Button
              onClick={findDuplicates}
              disabled={loading}
              className="font-mono text-xs font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_15px_var(--phosphor-green-glow)]"
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

            {duplicates.length > 0 && selectedGroups.size > 0 && (
              <Button
                onClick={handleBatchMerge}
                variant="outline"
                className="font-mono text-xs font-bold border-[var(--terminal-border)] hover:bg-[var(--terminal-elevated)]"
              >
                <GitMerge className="w-4 h-4 mr-2" />
                MERGE_SELECTED ({selectedGroups.size})
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Duplicate Groups */}
      {filteredDuplicates.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-mono font-bold text-[var(--terminal-text)]">
              Found {filteredDuplicates.length} Duplicate Group{filteredDuplicates.length > 1 ? 's' : ''}
            </h3>
          </div>

          {filteredDuplicates.map((group, groupIndex) => (
            <Card
              key={groupIndex}
              className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]"
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selectedGroups.has(groupIndex)}
                      onChange={() => toggleGroupSelection(groupIndex)}
                      className="w-4 h-4"
                    />
                    <AlertTriangle className="w-4 h-4 text-[var(--amber-gold)]" />
                    <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                      {group.entities.length} similar entities
                    </span>
                    <Badge
                      variant="outline"
                      className="font-mono text-[10px] border-[var(--terminal-border)]"
                    >
                      {(group.similarity * 100).toFixed(0)}% match
                    </Badge>
                  </div>
                  <Button
                    onClick={() => handleMergeGroup(group, groupIndex)}
                    size="sm"
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
                            <span>Confidence: {((entity.confidence || 0) * 100).toFixed(0)}%</span>
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

      {/* Empty State */}
      {!loading && duplicates.length === 0 && (
        <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
          <CardContent className="p-8 text-center">
            <GitMerge className="w-12 h-12 mx-auto mb-4 text-[var(--terminal-text-dim)]" />
            <p className="text-sm font-mono text-[var(--terminal-text)]">
              No duplicates found
            </p>
            <p className="text-xs font-mono text-[var(--terminal-text-dim)] mt-2">
              Click FIND_DUPLICATES to scan for similar entities
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
