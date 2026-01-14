/**
 * PathFinder Component
 * Allows users to find paths between two entities
 */

import React, { useState } from 'react';
import { Search, ArrowRight, GitBranch, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { Entity } from '@/types/entity';
import { entityService } from '@/services/entityService';
import toast from 'react-hot-toast';

interface PathNode {
  entity_id: string;
  entity_name: string;
  entity_type: string;
}

interface PathEdge {
  relationship_type: string;
  strength: number;
}

interface GraphPath {
  nodes: PathNode[];
  edges: PathEdge[];
  length: number;
  total_strength: number;
}

interface PathFinderProps {
  entities: Entity[];
  onEntityClick?: (entityId: string) => void;
}

export const PathFinder: React.FC<PathFinderProps> = ({ entities, onEntityClick }) => {
  const [sourceId, setSourceId] = useState('');
  const [targetId, setTargetId] = useState('');
  const [maxDepth, setMaxDepth] = useState(3);
  const [minStrength, setMinStrength] = useState(0.1);
  const [paths, setPaths] = useState<GraphPath[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState({ source: '', target: '' });

  // Filter entities for autocomplete
  const filteredSourceEntities = entities.filter(e =>
    e.name.toLowerCase().includes(searchQuery.source.toLowerCase())
  ).slice(0, 10);

  const filteredTargetEntities = entities.filter(e =>
    e.name.toLowerCase().includes(searchQuery.target.toLowerCase())
  ).slice(0, 10);

  const handleFindPaths = async () => {
    if (!sourceId || !targetId) {
      toast.error('Please select both source and target entities');
      return;
    }

    if (sourceId === targetId) {
      toast.error('Source and target must be different entities');
      return;
    }

    try {
      setLoading(true);
      const response = await fetch(
        `/api/knowledge-graph/paths/${sourceId}/${targetId}?max_depth=${maxDepth}&min_strength=${minStrength}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to find paths');
      }

      const foundPaths = await response.json();
      setPaths(foundPaths);

      if (foundPaths.length === 0) {
        toast('No paths found between these entities', { icon: '🔍' });
      } else {
        toast.success(`Found ${foundPaths.length} path${foundPaths.length > 1 ? 's' : ''}`);
      }
    } catch (error) {
      console.error('Error finding paths:', error);
      toast.error('Failed to find paths');
      setPaths([]);
    } finally {
      setLoading(false);
    }
  };

  const getEntityName = (entityId: string): string => {
    const entity = entities.find(e => e.id === entityId);
    return entity?.name || entityId;
  };

  return (
    <div className="space-y-4">
      {/* Path Finder Controls */}
      <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
        <CardHeader className="border-b border-[var(--terminal-border)] py-3">
          <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
            <GitBranch className="w-4 h-4" />
            Path Finder - How are entities connected?
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-4">
          {/* Entity Selection */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Source Entity */}
            <div className="space-y-2">
              <Label className="text-xs font-mono text-[var(--terminal-text-dim)]">
                Source Entity
              </Label>
              <Input
                placeholder="Search source entity..."
                value={searchQuery.source}
                onChange={(e) => setSearchQuery({ ...searchQuery, source: e.target.value })}
                className="font-mono text-xs bg-[var(--terminal-bg)] border-[var(--terminal-border)] text-[var(--terminal-text)]"
              />
              {searchQuery.source && filteredSourceEntities.length > 0 && (
                <div className="max-h-40 overflow-y-auto border border-[var(--terminal-border)] rounded-md bg-[var(--terminal-bg)]">
                  {filteredSourceEntities.map(entity => (
                    <button
                      key={entity.id}
                      onClick={() => {
                        setSourceId(entity.id);
                        setSearchQuery({ ...searchQuery, source: entity.name });
                      }}
                      className="w-full text-left px-3 py-2 text-xs font-mono hover:bg-[var(--terminal-elevated)] transition-colors"
                    >
                      <div className="text-[var(--terminal-text)]">{entity.name}</div>
                      <div className="text-[var(--terminal-text-dim)]">{entity.type}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Target Entity */}
            <div className="space-y-2">
              <Label className="text-xs font-mono text-[var(--terminal-text-dim)]">
                Target Entity
              </Label>
              <Input
                placeholder="Search target entity..."
                value={searchQuery.target}
                onChange={(e) => setSearchQuery({ ...searchQuery, target: e.target.value })}
                className="font-mono text-xs bg-[var(--terminal-bg)] border-[var(--terminal-border)] text-[var(--terminal-text)]"
              />
              {searchQuery.target && filteredTargetEntities.length > 0 && (
                <div className="max-h-40 overflow-y-auto border border-[var(--terminal-border)] rounded-md bg-[var(--terminal-bg)]">
                  {filteredTargetEntities.map(entity => (
                    <button
                      key={entity.id}
                      onClick={() => {
                        setTargetId(entity.id);
                        setSearchQuery({ ...searchQuery, target: entity.name });
                      }}
                      className="w-full text-left px-3 py-2 text-xs font-mono hover:bg-[var(--terminal-elevated)] transition-colors"
                    >
                      <div className="text-[var(--terminal-text)]">{entity.name}</div>
                      <div className="text-[var(--terminal-text-dim)]">{entity.type}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Parameters */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Max Depth */}
            <div className="space-y-2">
              <Label className="text-xs font-mono text-[var(--terminal-text-dim)]">
                Max Depth: {maxDepth}
              </Label>
              <Slider
                value={[maxDepth]}
                onValueChange={(value) => setMaxDepth(value[0])}
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
          </div>

          {/* Find Button */}
          <Button
            onClick={handleFindPaths}
            disabled={loading || !sourceId || !targetId}
            className="w-full font-mono text-xs font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_15px_var(--phosphor-green-glow)]"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                SEARCHING_PATHS...
              </>
            ) : (
              <>
                <Search className="w-4 h-4 mr-2" />
                FIND_PATHS
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Path Results */}
      {paths.length > 0 && (
        <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
          <CardHeader className="border-b border-[var(--terminal-border)] py-3">
            <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)]">
              Found {paths.length} Path{paths.length > 1 ? 's' : ''}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-3">
            {paths.map((path, pathIndex) => (
              <div
                key={pathIndex}
                className="border border-[var(--terminal-border)] rounded-lg p-3 bg-[var(--terminal-bg)]"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                    Path #{pathIndex + 1}
                  </span>
                  <div className="flex gap-4 text-xs font-mono">
                    <span className="text-[var(--terminal-text-dim)]">
                      Length: <span className="text-[var(--phosphor-green)]">{path.length}</span>
                    </span>
                    <span className="text-[var(--terminal-text-dim)]">
                      Strength: <span className="text-[var(--amber-gold)]">
                        {path.total_strength.toFixed(2)}
                      </span>
                    </span>
                  </div>
                </div>

                {/* Path Visualization */}
                <div className="flex items-center gap-2 flex-wrap">
                  {path.nodes.map((node, nodeIndex) => (
                    <React.Fragment key={nodeIndex}>
                      {/* Entity Node */}
                      <button
                        onClick={() => onEntityClick?.(node.entity_id)}
                        className="px-3 py-1.5 rounded-md bg-[var(--terminal-elevated)] border border-[var(--terminal-border)] hover:border-[var(--phosphor-green)] transition-colors"
                      >
                        <div className="text-xs font-mono text-[var(--terminal-text)]">
                          {node.entity_name}
                        </div>
                        <div className="text-[10px] font-mono text-[var(--terminal-text-dim)]">
                          {node.entity_type}
                        </div>
                      </button>

                      {/* Relationship Edge */}
                      {nodeIndex < path.edges.length && (
                        <div className="flex items-center gap-1 text-xs font-mono text-[var(--terminal-text-dim)]">
                          <ArrowRight className="w-4 h-4" />
                          <span className="text-[10px]">
                            {path.edges[nodeIndex].relationship_type}
                            <span className="text-[var(--amber-gold)] ml-1">
                              ({path.edges[nodeIndex].strength.toFixed(2)})
                            </span>
                          </span>
                          <ArrowRight className="w-4 h-4" />
                        </div>
                      )}
                    </React.Fragment>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
};
