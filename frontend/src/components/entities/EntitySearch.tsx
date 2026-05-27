/**
 * EntitySearch Component
 * Comprehensive graph search with path finding capabilities
 */

import React, { useState } from 'react';
import { Search, Loader2, GitBranch, Network, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { Entity } from '@/types/entity';
import { entityService } from '@/services/entityService';
import toast from 'react-hot-toast';

interface SearchResultEntity {
  id: string;
  name: string;
  entity_type: string;
  confidence_score: number;
  metadata?: Record<string, any>;
}

interface SearchResultRelationship {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relationship_type: string;
  strength: number;
}

interface SearchResultPath {
  nodes: Array<{
    entity_id: string;
    entity_name: string;
    entity_type: string;
  }>;
  edges: Array<{
    relationship_type: string;
    strength: number;
  }>;
  length: number;
  total_strength: number;
}

interface GraphSearchResponse {
  query: string;
  entities: SearchResultEntity[];
  relationships: SearchResultRelationship[];
  paths: SearchResultPath[];
  total_entities: number;
  total_relationships: number;
  total_paths: number;
  search_time: number;
}

interface EntitySearchProps {
  onEntityClick?: (entityId: string) => void;
}

export const EntitySearch: React.FC<EntitySearchProps> = ({ onEntityClick }) => {
  const [query, setQuery] = useState('');
  const [maxDepth, setMaxDepth] = useState(3);
  const [minStrength, setMinStrength] = useState(0.1);
  const [maxResults, setMaxResults] = useState(50);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<GraphSearchResponse | null>(null);

  const handleSearch = async () => {
    if (!query.trim()) {
      toast.error('Please enter a search query');
      return;
    }

    try {
      setLoading(true);
      const searchResults = await entityService.searchGraph({
        query: query.trim(),
        max_depth: maxDepth,
        min_strength: minStrength,
        max_results: maxResults,
      });

      setResults(searchResults);

      if (searchResults.total_entities === 0) {
        toast('No results found', { icon: '🔍' });
      } else {
        toast.success(
          `Found ${searchResults.total_entities} entities, ${searchResults.total_relationships} relationships, ${searchResults.total_paths} paths`
        );
      }
    } catch (error) {
      console.error('Error searching graph:', error);
      toast.error('Failed to search graph');
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <div className="space-y-4">
      {/* Search Controls */}
      <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
        <CardHeader className="border-b border-[var(--terminal-border)] py-3">
          <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
            <Search className="w-4 h-4" />
            Comprehensive Graph Search
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 space-y-4">
          {/* Search Input */}
          <div className="space-y-2">
            <Label className="text-xs font-mono text-[var(--terminal-text-dim)]">
              Search Query
            </Label>
            <Input
              placeholder="Search entities, relationships, and paths..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={handleKeyPress}
              className="font-mono text-sm bg-[var(--terminal-bg)] border-[var(--terminal-border)] text-[var(--terminal-text)]"
            />
          </div>

          {/* Search Parameters */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Max Depth */}
            <div className="space-y-2">
              <Label className="text-xs font-mono text-[var(--terminal-text-dim)]">
                Max Path Depth: {maxDepth}
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

            {/* Max Results */}
            <div className="space-y-2">
              <Label className="text-xs font-mono text-[var(--terminal-text-dim)]">
                Max Results: {maxResults}
              </Label>
              <Slider
                value={[maxResults]}
                onValueChange={(value) => setMaxResults(value[0])}
                min={10}
                max={200}
                step={10}
                className="w-full"
              />
            </div>
          </div>

          {/* Search Button */}
          <Button
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            className="w-full font-mono text-xs font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_15px_var(--phosphor-green-glow)]"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                SEARCHING_GRAPH...
              </>
            ) : (
              <>
                <Search className="w-4 h-4 mr-2" />
                SEARCH_GRAPH
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Search Results */}
      {results && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
              <CardContent className="p-4">
                <div className="text-xs font-mono text-[var(--terminal-text-dim)] mb-1">
                  ENTITIES
                </div>
                <div className="text-2xl font-mono font-bold text-[var(--phosphor-green)]">
                  {results.total_entities}
                </div>
              </CardContent>
            </Card>

            <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
              <CardContent className="p-4">
                <div className="text-xs font-mono text-[var(--terminal-text-dim)] mb-1">
                  RELATIONSHIPS
                </div>
                <div className="text-2xl font-mono font-bold text-[var(--cyan)]">
                  {results.total_relationships}
                </div>
              </CardContent>
            </Card>

            <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
              <CardContent className="p-4">
                <div className="text-xs font-mono text-[var(--terminal-text-dim)] mb-1">
                  PATHS
                </div>
                <div className="text-2xl font-mono font-bold text-[var(--amber-gold)]">
                  {results.total_paths}
                </div>
              </CardContent>
            </Card>

            <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
              <CardContent className="p-4">
                <div className="text-xs font-mono text-[var(--terminal-text-dim)] mb-1 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  SEARCH TIME
                </div>
                <div className="text-2xl font-mono font-bold text-[var(--purple)]">
                  {results.search_time.toFixed(2)}s
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Entities */}
          {results.entities.length > 0 && (
            <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
              <CardHeader className="border-b border-[var(--terminal-border)] py-3">
                <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
                  <Network className="w-4 h-4" />
                  Found Entities ({results.entities.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {results.entities.slice(0, 12).map((entity) => (
                    <button
                      key={entity.id}
                      onClick={() => onEntityClick?.(entity.id)}
                      className="p-3 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)] hover:border-[var(--phosphor-green)] transition-colors text-left"
                    >
                      <div className="text-sm font-mono font-bold text-[var(--terminal-text)]">
                        {entity.name}
                      </div>
                      <div className="text-xs font-mono text-[var(--terminal-text-dim)] mt-1">
                        {entity.entity_type}
                      </div>
                      <div className="text-xs font-mono text-[var(--amber-gold)] mt-1">
                        Confidence: {(entity.confidence_score * 100).toFixed(1)}%
                      </div>
                    </button>
                  ))}
                </div>
                {results.entities.length > 12 && (
                  <p className="text-xs font-mono text-[var(--terminal-text-dim)] mt-3 text-center">
                    + {results.entities.length - 12} more entities
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Paths */}
          {results.paths.length > 0 && (
            <Card className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]">
              <CardHeader className="border-b border-[var(--terminal-border)] py-3">
                <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--terminal-text-dim)] flex items-center gap-2">
                  <GitBranch className="w-4 h-4" />
                  Discovered Paths ({results.paths.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-3">
                {results.paths.slice(0, 5).map((path, index) => (
                  <div
                    key={index}
                    className="border border-[var(--terminal-border)] rounded-lg p-3 bg-[var(--terminal-bg)]"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                        Path #{index + 1}
                      </span>
                      <div className="flex gap-4 text-xs font-mono">
                        <span className="text-[var(--terminal-text-dim)]">
                          Length: <span className="text-[var(--phosphor-green)]">{path.length}</span>
                        </span>
                        <span className="text-[var(--terminal-text-dim)]">
                          Strength:{' '}
                          <span className="text-[var(--amber-gold)]">
                            {path.total_strength.toFixed(2)}
                          </span>
                        </span>
                      </div>
                    </div>
                    <div className="text-xs font-mono text-[var(--terminal-text)]">
                      {path.nodes.map((node, i) => (
                        <React.Fragment key={i}>
                          <span className="text-[var(--phosphor-green)]">{node.entity_name}</span>
                          {i < path.edges.length && (
                            <span className="text-[var(--terminal-text-dim)] mx-2">
                              →[{path.edges[i].relationship_type}]→
                            </span>
                          )}
                        </React.Fragment>
                      ))}
                    </div>
                  </div>
                ))}
                {results.paths.length > 5 && (
                  <p className="text-xs font-mono text-[var(--terminal-text-dim)] text-center">
                    + {results.paths.length - 5} more paths
                  </p>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
};
