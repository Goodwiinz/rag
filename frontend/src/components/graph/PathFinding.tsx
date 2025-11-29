import React, { useState, useCallback, useMemo } from 'react';
import {
  MapIcon,
  ArrowsRightLeftIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  ArrowPathIcon,
  EyeIcon,
  ArrowTopRightOnSquareIcon,
  DocumentTextIcon,
  UserGroupIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { Entity, Relationship } from '@/types/search';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

interface PathFindingProps {
  entities: Entity[];
  relationships: Relationship[];
  onEntityClick?: (entity: Entity) => void;
  onRelationshipClick?: (relationship: Relationship) => void;
  onDocumentClick?: (documentId: string) => void;
  className?: string;
  maxPaths?: number;
  maxDepth?: number;
}

interface PathResult {
  id: string;
  sourceEntity: Entity;
  targetEntity: Entity;
  path: Entity[];
  relationships: Relationship[];
  length: number;
  strength: number;
  confidence: number;
  pathType: 'shortest' | 'strongest' | 'most_reliable';
  algorithm: 'bfs' | 'dfs' | 'dijkstra' | 'astar';
  metadata: {
    totalWeight: number;
    exploredNodes: number;
    executionTimeMs: number;
    alternativePaths: number;
  };
}

interface PathFindingOptions {
  sourceEntityId: string;
  targetEntityId: string;
  algorithm: 'bfs' | 'dfs' | 'dijkstra' | 'astar';
  maxDepth: number;
  weightFunction: 'confidence' | 'strength' | 'recency' | 'composite';
  optimizeFor: 'length' | 'strength' | 'confidence' | 'time';
  includeAlternativePaths: boolean;
  maxPaths: number;
}

export const PathFinding: React.FC<PathFindingProps> = ({
  entities = [],
  relationships = [],
  onEntityClick,
  onRelationshipClick,
  onDocumentClick,
  className,
  maxPaths = 10,
  maxDepth = 6,
}) => {
  const [sourceEntity, setSourceEntity] = useState<Entity | null>(null);
  const [targetEntity, setTargetException] = useState<Entity | null>(null);
  const [options, setOptions] = useState<PathFindingOptions>({
    sourceEntityId: '',
    targetEntityId: '',
    algorithm: 'bfs',
    maxDepth,
    weightFunction: 'confidence',
    optimizeFor: 'length',
    includeAlternativePaths: true,
    maxPaths: maxPaths,
  });
  const [pathResults, setPathResults] = useState<PathResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedPath, setSelectedPath] = useState<PathResult | null>(null);
  const [searchHistory, setSearchHistory] = useState<Array<{
    source: Entity;
    target: Entity;
    timestamp: number;
    resultCount: number;
  }>>([]);

  // Build adjacency list for graph traversal
  const adjacencyList = useMemo(() => {
    const graph = new Map<string, Map<string, Relationship>>();

    relationships.forEach(rel => {
      if (!graph.has(rel.source_entity_id)) {
        graph.set(rel.source_entity_id, new Map());
      }
      if (!graph.has(rel.target_entity_id)) {
        graph.set(rel.target_entity_id, new Map());
      }

      // Add bidirectional edges
      graph.get(rel.source_entity_id)!.set(rel.target_entity_id, rel);
      graph.get(rel.target_entity_id)!.set(rel.source_entity_id, rel);
    });

    return graph;
  }, [relationships]);

  // Calculate edge weight based on selected function
  const calculateEdgeWeight = useCallback((relationship: Relationship, weightFunction: string): number => {
    switch (weightFunction) {
      case 'confidence':
        return 1 - relationship.confidence; // Invert so lower is better
      case 'strength':
        return 1 - relationship.weight;
      case 'recency':
        const daysSinceLastSeen = (Date.now() - new Date(relationship.last_seen).getTime()) / (1000 * 60 * 60 * 24);
        return daysSinceLastSeen / 365; // Normalize to years
      case 'composite':
        return (1 - relationship.confidence) * 0.4 + (1 - relationship.weight) * 0.4 + (1 - relationship.confidence) * 0.2;
      default:
        return 1;
    }
  }, []);

  // Calculate path strength
  const calculatePathStrength = useCallback((path: Entity[], relationships: Relationship[]): number => {
    if (relationships.length === 0) return 0;

    const avgConfidence = relationships.reduce((sum, rel) => sum + rel.confidence, 0) / relationships.length;
    const avgWeight = relationships.reduce((sum, rel) => sum + rel.weight, 0) / relationships.length;
    const recencyBonus = Math.min(1, relationships.reduce((sum, rel) => {
      const daysSince = (Date.now() - new Date(rel.last_seen).getTime()) / (1000 * 60 * 60 * 24);
      return sum + Math.max(0, 1 - daysSince / 30); // 30-day recency window
    }, 0) / relationships.length);

    return (avgConfidence * 0.5 + avgWeight * 0.3 + recencyBonus * 0.2);
  }, []);

  // BFS pathfinding
  const findPathBFS = useCallback((sourceId: string, targetId: string, maxDepth: number): PathResult | null => {
    const startTime = performance.now();
    const queue: Array<{ entity: Entity; path: Entity[]; relationships: Relationship[] }> = [
      { entity: entities.find(e => e.id === sourceId)!, path: [], relationships: [] }
    ];
    const visited = new Set<string>([sourceId]);
    let exploredNodes = 0;

    while (queue.length > 0) {
      const { entity, path, relationships } = queue.shift()!;
      exploredNodes++;

      const currentPath = [...path, entity];
      const currentRelationships = [...relationships];

      if (entity.id === targetId) {
        const endTime = performance.now();
        return {
          id: `bfs-${Date.now()}`,
          sourceEntity: entities.find(e => e.id === sourceId)!,
          targetEntity: entities.find(e => e.id === targetId)!,
          path: currentPath,
          relationships: currentRelationships,
          length: currentPath.length - 1,
          strength: calculatePathStrength(currentPath, currentRelationships),
          confidence: currentRelationships.reduce((sum, rel) => sum + rel.confidence, 0) / Math.max(currentRelationships.length, 1),
          pathType: 'shortest',
          algorithm: 'bfs',
          metadata: {
            totalWeight: currentRelationships.reduce((sum, rel) => sum + calculateEdgeWeight(rel, options.weightFunction), 0),
            exploredNodes,
            executionTimeMs: endTime - startTime,
            alternativePaths: 0,
          },
        };
      }

      if (currentPath.length > maxDepth) continue;

      const neighbors = adjacencyList.get(entity.id) || new Map();
      neighbors.forEach((relationship, neighborId) => {
        if (!visited.has(neighborId)) {
          visited.add(neighborId);
          const neighborEntity = entities.find(e => e.id === neighborId);
          if (neighborEntity) {
            queue.push({
              entity: neighborEntity,
              path: currentPath,
              relationships: [...currentRelationships, relationship],
            });
          }
        }
      });
    }

    return null;
  }, [entities, adjacencyList, calculatePathStrength, calculateEdgeWeight, options.weightFunction]);

  // Dijkstra's algorithm for shortest weighted path
  const findPathDijkstra = useCallback((sourceId: string, targetId: string, maxDepth: number): PathResult | null => {
    const startTime = performance.now();
    const distances = new Map<string, number>();
    const previous = new Map<string, { entity: Entity; relationship: Relationship | null }>();
    const unvisited = new Set<string>();
    let exploredNodes = 0;

    // Initialize distances
    entities.forEach(entity => {
      distances.set(entity.id, entity.id === sourceId ? 0 : Infinity);
      unvisited.add(entity.id);
    });

    while (unvisited.size > 0) {
      // Find unvisited node with minimum distance
      let currentId: string | null = null;
      let minDistance = Infinity;
      unvisited.forEach(id => {
        const distance = distances.get(id) || Infinity;
        if (distance < minDistance) {
          minDistance = distance;
          currentId = id;
        }
      });

      if (!currentId || minDistance === Infinity) break;
      if (currentId === targetId) break;
      if (distances.get(currentId)! > maxDepth * 2) break; // Prevent excessive exploration

      unvisited.delete(currentId);
      exploredNodes++;

      const currentEntity = entities.find(e => e.id === currentId)!;
      const neighbors = adjacencyList.get(currentId) || new Map();

      neighbors.forEach((relationship, neighborId) => {
        if (!unvisited.has(neighborId)) return;

        const edgeWeight = calculateEdgeWeight(relationship, options.weightFunction);
        const currentDistance = distances.get(currentId!) || 0;
        const altDistance = currentDistance + edgeWeight;

        if (altDistance < (distances.get(neighborId) || Infinity)) {
          distances.set(neighborId, altDistance);
          previous.set(neighborId, { entity: currentEntity, relationship });
        }
      });
    }

    // Reconstruct path
    if (distances.get(targetId) === Infinity) return null;

    const path: Entity[] = [];
    const relationships: Relationship[] = [];
    let currentId: string | undefined = targetId;

    while (currentId) {
      const prev = previous.get(currentId);
      if (!prev) break;

      path.unshift(entities.find(e => e.id === currentId)!);
      if (prev.relationship) {
        relationships.unshift(prev.relationship);
      }

      currentId = prev.entity.id;
    }

    const sourceEntity = entities.find(e => e.id === sourceId);
    if (sourceEntity) path.unshift(sourceEntity);

    const endTime = performance.now();
    return {
      id: `dijkstra-${Date.now()}`,
      sourceEntity: entities.find(e => e.id === sourceId)!,
      targetEntity: entities.find(e => e.id === targetId)!,
      path,
      relationships,
      length: path.length - 1,
      strength: calculatePathStrength(path, relationships),
      confidence: relationships.reduce((sum, rel) => sum + rel.confidence, 0) / Math.max(relationships.length, 1),
      pathType: 'shortest',
      algorithm: 'dijkstra',
      metadata: {
        totalWeight: distances.get(targetId) || 0,
        exploredNodes,
        executionTimeMs: endTime - startTime,
        alternativePaths: 0,
      },
    };
  }, [entities, adjacencyList, calculatePathStrength, calculateEdgeWeight, options.weightFunction]);

  // Find alternative paths
  const findAlternativePaths = useCallback((sourceId: string, targetId: string, primaryPath: PathResult, maxPaths: number): PathResult[] => {
    const alternatives: PathResult[] = [];
    const usedRelationships = new Set(primaryPath.relationships.map(r => r.id));

    // Try different algorithms and parameters to find alternatives
    const algorithms = ['bfs', 'dijkstra'] as const;
    const weightFunctions = ['confidence', 'strength', 'composite'] as const;

    for (const algorithm of algorithms) {
      for (const weightFunction of weightFunctions) {
        if (alternatives.length >= maxPaths - 1) break;

        const tempOptions = { ...options, algorithm, weightFunction };
        let path: PathResult | null = null;

        if (algorithm === 'bfs') {
          path = findPathBFS(sourceId, targetId, options.maxDepth);
        } else if (algorithm === 'dijkstra') {
          path = findPathDijkstra(sourceId, targetId, options.maxDepth);
        }

        if (path && path.id !== primaryPath.id) {
          // Check if this path is sufficiently different
          const pathRelationshipIds = new Set(path.relationships.map(r => r.id));
          const overlap = Array.from(usedRelationships).filter(id => pathRelationshipIds.has(id)).length;
          const overlapRatio = overlap / Math.max(usedRelationships.size, pathRelationshipIds.size);

          if (overlapRatio < 0.7) { // Less than 70% overlap
            alternatives.push(path);
          }
        }
      }
    }

    return alternatives;
  }, [findPathBFS, findPathDijkstra, options]);

  // Execute pathfinding
  const findPaths = useCallback(async () => {
    if (!sourceEntity || !targetEntity) return;

    setIsSearching(true);
    setPathResults([]);

    try {
      const results: PathResult[] = [];

      // Find primary path
      let primaryPath: PathResult | null = null;

      switch (options.algorithm) {
        case 'bfs':
          primaryPath = findPathBFS(sourceEntity.id, targetEntity.id, options.maxDepth);
          break;
        case 'dijkstra':
          primaryPath = findPathDijkstra(sourceEntity.id, targetEntity.id, options.maxDepth);
          break;
        default:
          primaryPath = findPathBFS(sourceEntity.id, targetEntity.id, options.maxDepth);
      }

      if (primaryPath) {
        results.push(primaryPath);

        // Find alternative paths if requested
        if (options.includeAlternativePaths && options.maxPaths > 1) {
          const alternatives = findAlternativePaths(
            sourceEntity.id,
            targetEntity.id,
            primaryPath,
            options.maxPaths - 1
          );
          results.push(...alternatives);
        }
      }

      setPathResults(results);

      // Add to search history
      if (results.length > 0) {
        setSearchHistory(prev => [
          {
            source: sourceEntity,
            target: targetEntity,
            timestamp: Date.now(),
            resultCount: results.length,
          },
          ...prev.slice(0, 9), // Keep last 10 searches
        ]);
      }
    } catch (error) {
      console.error('Pathfinding error:', error);
    } finally {
      setIsSearching(false);
    }
  }, [sourceEntity, targetEntity, options, findPathBFS, findPathDijkstra, findAlternativePaths]);

  // Get entity type color
  const getEntityTypeColor = (type: Entity['type']) => {
    const colors = {
      person: 'bg-blue-100 text-blue-800 border-blue-200',
      organization: 'bg-green-100 text-green-800 border-green-200',
      location: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      concept: 'bg-purple-100 text-purple-800 border-purple-200',
      date: 'bg-orange-100 text-orange-800 border-orange-200',
      product: 'bg-pink-100 text-pink-800 border-pink-200',
    };
    return colors[type] || 'bg-gray-100 text-gray-800 border-gray-200';
  };

  // Get path type icon
  const getPathTypeIcon = (type: PathResult['pathType']) => {
    switch (type) {
      case 'shortest':
        return MapIcon;
      case 'strongest':
        return CheckCircleIcon;
      case 'most_reliable':
        return ExclamationTriangleIcon;
      default:
        return MapIcon;
    }
  };

  // Get algorithm color
  const getAlgorithmColor = (algorithm: PathResult['algorithm']) => {
    switch (algorithm) {
      case 'bfs':
        return 'text-blue-600';
      case 'dfs':
        return 'text-green-600';
      case 'dijkstra':
        return 'text-purple-600';
      case 'astar':
        return 'text-orange-600';
      default:
        return 'text-gray-600';
    }
  };

  return (
    <div className={cn("space-y-6", className)}>
      {/* Pathfinding Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <MapIcon className="h-5 w-5 mr-2" />
            Path Finding & Relationship Discovery
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            {/* Entity Selection */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Source Entity */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Source Entity
                </label>
                {sourceEntity ? (
                  <div className="p-3 border rounded-lg bg-blue-50 border-blue-200">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Badge className={getEntityTypeColor(sourceEntity.type)}>
                          {sourceEntity.type}
                        </Badge>
                        <span className="font-medium">{sourceEntity.name}</span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSourceEntity(null)}
                      >
                        ×
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Select onValueChange={(value) => {
                    const entity = entities.find(e => e.id === value);
                    if (entity) setSourceEntity(entity);
                  }}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select source entity" />
                    </SelectTrigger>
                    <SelectContent>
                      {entities.map(entity => (
                        <SelectItem key={entity.id} value={entity.id}>
                          <div className="flex items-center space-x-2">
                            <Badge className={getEntityTypeColor(entity.type)}>
                              {entity.type}
                            </Badge>
                            <span>{entity.name}</span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>

              {/* Target Entity */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Target Entity
                </label>
                {targetEntity ? (
                  <div className="p-3 border rounded-lg bg-green-50 border-green-200">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Badge className={getEntityTypeColor(targetEntity.type)}>
                          {targetEntity.type}
                        </Badge>
                        <span className="font-medium">{targetEntity.name}</span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setTargetException(null)}
                      >
                        ×
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Select onValueChange={(value) => {
                    const entity = entities.find(e => e.id === value);
                    if (entity) setTargetException(entity);
                  }}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select target entity" />
                    </SelectTrigger>
                    <SelectContent>
                      {entities.map(entity => (
                        <SelectItem key={entity.id} value={entity.id}>
                          <div className="flex items-center space-x-2">
                            <Badge className={getEntityTypeColor(entity.type)}>
                              {entity.type}
                            </Badge>
                            <span>{entity.name}</span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>
            </div>

            {/* Algorithm Options */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Algorithm
                </label>
                <Select
                  value={options.algorithm}
                  onValueChange={(value: any) => setOptions(prev => ({ ...prev, algorithm: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="bfs">Breadth-First Search (BFS)</SelectItem>
                    <SelectItem value="dijkstra">Dijkstra's Algorithm</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Weight Function
                </label>
                <Select
                  value={options.weightFunction}
                  onValueChange={(value: any) => setOptions(prev => ({ ...prev, weightFunction: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="confidence">Confidence</SelectItem>
                    <SelectItem value="strength">Relationship Strength</SelectItem>
                    <SelectItem value="recency">Recency</SelectItem>
                    <SelectItem value="composite">Composite Score</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Max Depth
                </label>
                <Select
                  value={options.maxDepth.toString()}
                  onValueChange={(value) => setOptions(prev => ({ ...prev, maxDepth: parseInt(value) }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="3">3 hops</SelectItem>
                    <SelectItem value="5">5 hops</SelectItem>
                    <SelectItem value="10">10 hops</SelectItem>
                    <SelectItem value="15">15 hops</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Additional Options */}
            <div className="flex items-center space-x-4">
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={options.includeAlternativePaths}
                  onChange={(e) => setOptions(prev => ({ ...prev, includeAlternativePaths: e.target.checked }))}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">Find alternative paths</span>
              </label>

              <div className="flex items-center space-x-2">
                <label className="text-sm text-gray-700">Max paths:</label>
                <Select
                  value={options.maxPaths.toString()}
                  onValueChange={(value) => setOptions(prev => ({ ...prev, maxPaths: parseInt(value) }))}
                >
                  <SelectTrigger className="w-20">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">1</SelectItem>
                    <SelectItem value="3">3</SelectItem>
                    <SelectItem value="5">5</SelectItem>
                    <SelectItem value="10">10</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Search Button */}
            <Button
              onClick={findPaths}
              disabled={!sourceEntity || !targetEntity || isSearching}
              className="w-full"
              size="lg"
            >
              {isSearching ? (
                <div className="flex items-center space-x-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                  <span>Finding paths...</span>
                </div>
              ) : (
                <div className="flex items-center space-x-2">
                  <ArrowsRightLeftIcon className="h-4 w-4" />
                  <span>Find Paths</span>
                </div>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Path Results */}
      {pathResults.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Discovered Paths ({pathResults.length})</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setPathResults([])}
              >
                <ArrowPathIcon className="h-4 w-4 mr-2" />
                Clear
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {pathResults.map((path, index) => {
                const PathTypeIcon = getPathTypeIcon(path.pathType);
                const isPrimary = index === 0;

                return (
                  <div
                    key={path.id}
                    className={cn(
                      "border rounded-lg p-4 cursor-pointer hover:shadow-md transition-shadow",
                      isPrimary ? "border-blue-200 bg-blue-50" : "border-gray-200"
                    )}
                    onClick={() => setSelectedPath(path)}
                  >
                    {/* Path Header */}
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center space-x-3">
                        {isPrimary && (
                          <Badge className="bg-blue-100 text-blue-800">
                            Primary Path
                          </Badge>
                        )}
                        <div className="flex items-center space-x-2">
                          <PathTypeIcon className="h-4 w-4 text-gray-500" />
                          <span className="text-sm font-medium capitalize">{path.pathType} path</span>
                        </div>
                        <Badge className={getAlgorithmColor(path.algorithm)}>
                          {path.algorithm.toUpperCase()}
                        </Badge>
                      </div>

                      <div className="flex items-center space-x-4 text-sm text-gray-600">
                        <span>Length: {path.length} hops</span>
                        <span>Strength: {path.strength.toFixed(3)}</span>
                        <span>Confidence: {Math.round(path.confidence * 100)}%</span>
                        <Button variant="ghost" size="sm">
                          <EyeIcon className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    {/* Path Visualization */}
                    <div className="flex items-center space-x-2 overflow-x-auto">
                      {path.path.map((entity, idx) => (
                        <React.Fragment key={entity.id}>
                          <div className="flex items-center space-x-1">
                            <Badge className={getEntityTypeColor(entity.type)}>
                              {entity.type}
                            </Badge>
                            <span className="text-sm font-medium truncate max-w-32">
                              {entity.name}
                            </span>
                          </div>
                          {idx < path.path.length - 1 && (
                            <ArrowsRightLeftIcon className="h-4 w-4 text-gray-400 flex-shrink-0" />
                          )}
                        </React.Fragment>
                      ))}
                    </div>

                    {/* Path Metadata */}
                    <div className="flex items-center justify-between mt-3 pt-3 border-t text-xs text-gray-500">
                      <div className="flex items-center space-x-4">
                        <span>Weight: {path.metadata.totalWeight.toFixed(3)}</span>
                        <span>Explored: {path.metadata.exploredNodes} nodes</span>
                        <span>Time: {path.metadata.executionTimeMs.toFixed(2)}ms</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        {path.relationships.length > 0 && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              // Show relationships
                            }}
                          >
                            <DocumentTextIcon className="h-3 w-3 mr-1" />
                            {path.relationships.length} relationships
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Search History */}
      {searchHistory.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <ClockIcon className="h-5 w-5 mr-2" />
              Recent Searches
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {searchHistory.map((search, index) => (
                <div
                  key={search.timestamp}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100"
                  onClick={() => {
                    setSourceEntity(search.source);
                    setTargetException(search.target);
                  }}
                >
                  <div className="flex items-center space-x-2">
                    <Badge className={getEntityTypeColor(search.source.type)}>
                      {search.source.type}
                    </Badge>
                    <span className="font-medium">{search.source.name}</span>
                    <ArrowsRightLeftIcon className="h-4 w-4 text-gray-400" />
                    <Badge className={getEntityTypeColor(search.target.type)}>
                      {search.target.type}
                    </Badge>
                    <span className="font-medium">{search.target.name}</span>
                  </div>
                  <div className="flex items-center space-x-2 text-sm text-gray-500">
                    <span>{search.resultCount} paths</span>
                    <span>{new Date(search.timestamp).toLocaleTimeString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Path Detail Modal */}
      {selectedPath && (
        <Dialog open={!!selectedPath} onOpenChange={() => setSelectedPath(null)}>
          <DialogContent className="max-w-6xl">
            <DialogHeader>
              <DialogTitle className="flex items-center">
                <MapIcon className="h-5 w-5 mr-2" />
                Path Details: {selectedPath.sourceEntity.name} → {selectedPath.targetEntity.name}
              </DialogTitle>
            </DialogHeader>

            <div className="space-y-6">
              {/* Path Overview */}
              <div className="grid grid-cols-4 gap-4">
                <div className="text-center p-3 bg-gray-50 rounded-lg">
                  <div className="text-lg font-bold">{selectedPath.length}</div>
                  <div className="text-sm text-gray-500">Hops</div>
                </div>
                <div className="text-center p-3 bg-gray-50 rounded-lg">
                  <div className="text-lg font-bold">{selectedPath.strength.toFixed(3)}</div>
                  <div className="text-sm text-gray-500">Strength</div>
                </div>
                <div className="text-center p-3 bg-gray-50 rounded-lg">
                  <div className="text-lg font-bold">{Math.round(selectedPath.confidence * 100)}%</div>
                  <div className="text-sm text-gray-500">Confidence</div>
                </div>
                <div className="text-center p-3 bg-gray-50 rounded-lg">
                  <div className="text-lg font-bold">{selectedPath.metadata.executionTimeMs.toFixed(2)}ms</div>
                  <div className="text-sm text-gray-500">Time</div>
                </div>
              </div>

              {/* Detailed Path */}
              <div>
                <h4 className="font-medium text-gray-900 mb-3">Path Details</h4>
                <div className="space-y-3">
                  {selectedPath.path.map((entity, index) => {
                    const relationship = selectedPath.relationships[index];
                    return (
                      <div key={entity.id} className="flex items-center space-x-4">
                        <div className="flex-shrink-0 w-8 text-center">
                          <span className="text-sm font-bold text-gray-500">{index + 1}</span>
                        </div>

                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <Badge className={getEntityTypeColor(entity.type)}>
                              {entity.type}
                            </Badge>
                            <span className="font-medium">{entity.name}</span>
                          </div>
                          <div className="text-sm text-gray-500 mt-1">
                            {entity.mentions} mentions • {entity.document_ids.length} documents
                          </div>
                        </div>

                        {relationship && (
                          <div className="flex-shrink-0 text-right">
                            <Badge className="bg-blue-100 text-blue-800 mb-1">
                              {relationship.relationship_type}
                            </Badge>
                            <div className="text-xs text-gray-500">
                              {Math.round(relationship.confidence * 100)}% confidence
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Relationships */}
              {selectedPath.relationships.length > 0 && (
                <div>
                  <h4 className="font-medium text-gray-900 mb-3">Relationships in Path</h4>
                  <div className="space-y-2">
                    {selectedPath.relationships.map((relationship, index) => (
                      <div key={relationship.id} className="p-3 bg-gray-50 rounded-lg">
                        <div className="flex items-center justify-between">
                          <div>
                            <Badge className="bg-blue-100 text-blue-800 mb-2">
                              {relationship.relationship_type}
                            </Badge>
                            <p className="text-sm text-gray-700 italic">"{relationship.context}"</p>
                          </div>
                          <div className="text-right">
                            <div className="text-sm font-medium">
                              {Math.round(relationship.confidence * 100)}% confidence
                            </div>
                            <div className="text-xs text-gray-500">
                              Weight: {relationship.weight.toFixed(3)}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

export default PathFinding;