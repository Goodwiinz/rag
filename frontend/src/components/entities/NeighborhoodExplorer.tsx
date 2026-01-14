/**
 * NeighborhoodExplorer Component
 * Explores the neighborhood of an entity with depth control
 */

import React, { useState, useEffect } from 'react';
import { Layers, Loader2, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { Entity } from '@/types/entity';
import toast from 'react-hot-toast';
import { EntityGraph } from './EntityGraph';

interface NeighborhoodExplorerProps {
  centralEntity: Entity;
  onEntityClick?: (entity: Entity) => void;
}

export const NeighborhoodExplorer: React.FC<NeighborhoodExplorerProps> = ({
  centralEntity,
  onEntityClick,
}) => {
  const [depth, setDepth] = useState(2);
  const [minStrength, setMinStrength] = useState(0.1);
  const [maxNodes, setMaxNodes] = useState(50);
  const [loading, setLoading] = useState(false);
  const [entities, setEntities] = useState<Entity[]>([centralEntity]);
  const [relationships, setRelationships] = useState<any[]>([]);

  const fetchNeighborhood = async () => {
    try {
      setLoading(true);

      // Fetch related entities
      const response = await fetch(
        `/api/knowledge-graph/entities/${centralEntity.id}/related?max_depth=${depth}&min_strength=${minStrength}&limit=${maxNodes}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to fetch neighborhood');
      }

      const relatedEntities = await response.json();
      
      // Convert backend format to frontend Entity format
      const convertedEntities: Entity[] = relatedEntities.map((e: any) => ({
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

      // Include central entity
      const allEntities = [centralEntity, ...convertedEntities];
      setEntities(allEntities);

      // Fetch relationships for all entities
      const allEntityIds = allEntities.map(e => e.id);
      const relationshipPromises = allEntityIds.map(async (entityId) => {
        const relResponse = await fetch(
          `/api/knowledge-graph/entities/${entityId}/relationships`,
          {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`,
            },
          }
        );
        if (relResponse.ok) {
          return await relResponse.json();
        }
        return [];
      });

      const relationshipArrays = await Promise.all(relationshipPromises);
      const allRelationships = relationshipArrays.flat();

      // Filter to only include relationships between entities in our set
      const entityIdSet = new Set(allEntityIds);
      const filteredRelationships = allRelationships
        .filter((rel: any) =>
          entityIdSet.has(rel.source_entity_id) && entityIdSet.has(rel.target_entity_id)
        )
        .map((rel: any) => ({
          id: rel.id,
          source: rel.source_entity_id,
          target: rel.target_entity_id,
          type: rel.relationship_type,
          weight: rel.strength,
          strength: rel.strength,
          confidence: rel.confidence_score,
          context: rel.context,
          metadata: rel.metadata
        }));

      setRelationships(filteredRelationships);

      toast.success(`Found ${convertedEntities.length} related entities`);
    } catch (error) {
      console.error('Error fetching neighborhood:', error);
      toast.error('Failed to fetch neighborhood');
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    fetchNeighborhood();
  }, [centralEntity.id]);

  return (
    <div className="space-y-4">
      {/* Controls */}
      <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
        <CardHeader className="border-b border-[var(--terminal-border)] py-3">
          <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
            <Layers className="w-4 h-4" />
            Neighborhood of: {centralEntity.name}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Depth Control */}
            <div className="space-y-2">
              <Label className="text-xs font-mono text-[var(--terminal-text-dim)]">
                Depth: {depth} hop{depth > 1 ? 's' : ''}
              </Label>
              <Slider
                value={[depth]}
                onValueChange={(value) => setDepth(value[0])}
                min={1}
                max={5}
                step={1}
                className="w-full"
              />
            </div>

            {/* Min Strength */}
            <div className="space-y-2">
              <Label className="text-xs font-mono text-[var(--terminal-text-dim)]">
                Min Strength: {minStrength.toFixed(2)}
              </Label>
              <Slider
                value={[minStrength * 100]}
                onValueChange={(value) => setMinStrength(value[0] / 100)}
                min={0}
                max={100}
                step={5}
                className="w-full"
              />
            </div>

            {/* Max Nodes */}
            <div className="space-y-2">
              <Label className="text-xs font-mono text-[var(--terminal-text-dim)]">
                Max Nodes: {maxNodes}
              </Label>
              <Slider
                value={[maxNodes]}
                onValueChange={(value) => setMaxNodes(value[0])}
                min={10}
                max={200}
                step={10}
                className="w-full"
              />
            </div>
          </div>

          <Button
            onClick={fetchNeighborhood}
            disabled={loading}
            className="w-full font-mono text-xs font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_15px_var(--phosphor-green-glow)]"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                LOADING_NEIGHBORHOOD...
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4 mr-2" />
                REFRESH_NEIGHBORHOOD
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
          <CardContent className="p-4">
            <div className="text-xs font-mono text-[var(--terminal-text-dim)] mb-1">
              ENTITIES
            </div>
            <div className="text-2xl font-mono font-bold text-[var(--phosphor-green)]">
              {entities.length}
            </div>
          </CardContent>
        </Card>
        <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
          <CardContent className="p-4">
            <div className="text-xs font-mono text-[var(--terminal-text-dim)] mb-1">
              RELATIONSHIPS
            </div>
            <div className="text-2xl font-mono font-bold text-[var(--cyan)]">
              {relationships.length}
            </div>
          </CardContent>
        </Card>
        <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
          <CardContent className="p-4">
            <div className="text-xs font-mono text-[var(--terminal-text-dim)] mb-1">
              DEPTH
            </div>
            <div className="text-2xl font-mono font-bold text-[var(--amber-gold)]">
              {depth}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Graph Visualization */}
      {!loading && entities.length > 0 && (
        <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
          <CardContent className="p-4">
            <EntityGraph
              entities={entities}
              relationships={relationships}
              onEntityClick={onEntityClick}
              height={600}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
};
