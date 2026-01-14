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
import { entityService } from '@/services/entityService';
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

      // Fetch related entities using service with retry
      const relatedEntities = await entityService.getRelatedEntities(
        centralEntity.id,
        depth,
        minStrength,
        maxNodes
      );

      // Include central entity
      const allEntities = [centralEntity, ...relatedEntities];
      setEntities(allEntities);

      // Fetch relationships for all entities using service with retry
      const allEntityIds = allEntities.map(e => e.id);
      const relationshipPromises = allEntityIds.map(entityId =>
        entityService.getEntityRelationships(entityId)
      );

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
