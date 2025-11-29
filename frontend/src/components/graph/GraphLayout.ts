// Graph Layout Algorithms for Knowledge Graph Visualization
import { Entity, Relationship } from '@/types/search';

export interface GraphNode extends Entity {
  x: number;
  y: number;
  vx?: number; // velocity for force simulation
  vy?: number; // velocity for force simulation
  fx?: number; // fixed position for force simulation
  fy?: number; // fixed position for force simulation
}

export interface GraphEdge extends Relationship {
  source: GraphNode;
  target: GraphNode;
}

export interface LayoutBounds {
  width: number;
  height: number;
  padding: number;
}

export interface LayoutOptions {
  bounds: LayoutBounds;
  iterations?: number;
  animate?: boolean;
}

// Force-Directed Layout Algorithm
export class ForceDirectedLayout {
  private nodes: GraphNode[] = [];
  private edges: GraphEdge[] = [];
  private options: LayoutOptions;

  // Force parameters
  private alpha = 1.0;
  private alphaDecay = 0.0228;
  private alphaMin = 0.001;
  private velocityDecay = 0.4;

  // Force strengths
  private centerForce = 0.1;
  private repelForce = 1000;
  private attractForce = 0.5;
  private linkDistance = 100;

  constructor(nodes: Entity[], edges: Relationship[], options: LayoutOptions) {
    this.options = options;
    this.initializeGraph(nodes, edges);
  }

  private initializeGraph(entities: Entity[], relationships: Relationship[]) {
    // Convert entities to nodes with random initial positions
    this.nodes = entities.map(entity => ({
      ...entity,
      x: Math.random() * this.options.bounds.width,
      y: Math.random() * this.options.bounds.height,
      vx: 0,
      vy: 0,
    }));

    // Convert relationships to edges with node references
    this.edges = relationships.map(rel => {
      const source = this.nodes.find(n => n.id === rel.source_entity_id);
      const target = this.nodes.find(n => n.id === rel.target_entity_id);

      if (!source || !target) {
        throw new Error(`Invalid relationship: ${rel.id}. Source or target not found.`);
      }

      return {
        ...rel,
        source,
        target,
      };
    });
  }

  // Center force - pulls nodes towards center
  private applyCenterForce() {
    const centerX = this.options.bounds.width / 2;
    const centerY = this.options.bounds.height / 2;

    this.nodes.forEach(node => {
      if (node.fx === undefined) {
        node.vx! += (centerX - node.x) * this.centerForce * this.alpha;
        node.vy! += (centerY - node.y) * this.centerForce * this.alpha;
      }
    });
  }

  // Repulsion force - pushes nodes away from each other
  private applyRepulsionForce() {
    for (let i = 0; i < this.nodes.length; i++) {
      for (let j = i + 1; j < this.nodes.length; j++) {
        const node1 = this.nodes[i];
        const node2 = this.nodes[j];

        if (!node1 || !node2) continue;

        const dx = node2.x - node1.x;
        const dy = node2.y - node1.y;
        const distance = Math.sqrt(dx * dx + dy * dy) || 1;

        const force = this.repelForce * this.alpha / (distance * distance);
        const fx = (dx / distance) * force;
        const fy = (dy / distance) * force;

        if (node1.fx === undefined) {
          node1.vx! -= fx;
          node1.vy! -= fy;
        }
        if (node2.fx === undefined) {
          node2.vx! += fx;
          node2.vy! += fy;
        }
      }
    }
  }

  // Attraction force - pulls connected nodes together
  private applyAttractionForce() {
    this.edges.forEach(edge => {
      const source = edge.source;
      const target = edge.target;

      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const distance = Math.sqrt(dx * dx + dy * dy) || 1;

      const force = (distance - this.linkDistance) * this.attractForce * edge.confidence * this.alpha;
      const fx = (dx / distance) * force;
      const fy = (dy / distance) * force;

      if (source.fx === undefined) {
        source.vx! += fx;
        source.vy! += fy;
      }
      if (target.fx === undefined) {
        target.vx! -= fx;
        target.vy! -= fy;
      }
    });
  }

  // Update node positions based on velocities
  private updatePositions() {
    this.nodes.forEach(node => {
      if (node.fx === undefined) {
        node.vx! *= this.velocityDecay;
        node.vy! *= this.velocityDecay;
        node.x += node.vx!;
        node.y += node.vy!;

        // Keep nodes within bounds
        node.x = Math.max(this.options.bounds.padding,
                    Math.min(this.options.bounds.width - this.options.bounds.padding, node.x));
        node.y = Math.max(this.options.bounds.padding,
                    Math.min(this.options.bounds.height - this.options.bounds.padding, node.y));
      }
    });
  }

  // Single simulation step
  private simulateStep() {
    this.applyCenterForce();
    this.applyRepulsionForce();
    this.applyAttractionForce();
    this.updatePositions();
    this.alpha *= (1 - this.alphaDecay);
  }

  // Run the layout simulation
  public layout(): { nodes: GraphNode[], edges: GraphEdge[] } {
    const iterations = this.options.iterations || 300;

    for (let i = 0; i < iterations && this.alpha > this.alphaMin; i++) {
      this.simulateStep();
    }

    return {
      nodes: this.nodes,
      edges: this.edges,
    };
  }

  // Get layout progress (for animation)
  public getProgress(): number {
    return Math.max(0, Math.min(1, 1 - (this.alpha - this.alphaMin) / (1.0 - this.alphaMin)));
  }
}

// Hierarchical Layout Algorithm
export class HierarchicalLayout {
  private nodes: GraphNode[] = [];
  private edges: GraphEdge[] = [];
  private options: LayoutOptions;

  // Layout parameters
  private levelHeight = 150;
  private nodeSpacing = 120;
  private levels: Map<string, number> = new Map();

  constructor(nodes: Entity[], edges: Relationship[], options: LayoutOptions) {
    this.options = options;
    this.initializeGraph(nodes, edges);
    this.calculateLevels();
  }

  private initializeGraph(entities: Entity[], relationships: Relationship[]) {
    // Convert entities to nodes
    this.nodes = entities.map(entity => ({
      ...entity,
      x: 0,
      y: 0,
    }));

    // Convert relationships to edges
    this.edges = relationships.map(rel => {
      const source = this.nodes.find(n => n.id === rel.source_entity_id);
      const target = this.nodes.find(n => n.id === rel.target_entity_id);

      if (!source || !target) {
        throw new Error(`Invalid relationship: ${rel.id}. Source or target not found.`);
      }

      return {
        ...rel,
        source,
        target,
      };
    });
  }

  // Calculate hierarchical levels using topological sorting
  private calculateLevels() {
    // Build adjacency list
    const inDegree = new Map<string, number>();
    const adjacency = new Map<string, string[]>();

    this.nodes.forEach(node => {
      inDegree.set(node.id, 0);
      adjacency.set(node.id, []);
    });

    this.edges.forEach(edge => {
      adjacency.get(edge.source.id)!.push(edge.target.id);
      inDegree.set(edge.target.id, (inDegree.get(edge.target.id) || 0) + 1);
    });

    // Topological sort to determine levels
    const queue: string[] = [];
    inDegree.forEach((degree, nodeId) => {
      if (degree === 0) {
        queue.push(nodeId);
        this.levels.set(nodeId, 0);
      }
    });

    while (queue.length > 0) {
      const currentId = queue.shift()!;
      const currentLevel = this.levels.get(currentId) || 0;

      adjacency.get(currentId)!.forEach(neighborId => {
        const newLevel = currentLevel + 1;
        const currentNeighborLevel = this.levels.get(neighborId) || 0;

        if (newLevel > currentNeighborLevel) {
          this.levels.set(neighborId, newLevel);
        }

        const neighborDegree = (inDegree.get(neighborId) || 0) - 1;
        inDegree.set(neighborId, neighborDegree);

        if (neighborDegree === 0) {
          queue.push(neighborId);
        }
      });
    }

    // Handle cycles by assigning remaining nodes to level 0
    this.nodes.forEach(node => {
      if (!this.levels.has(node.id)) {
        this.levels.set(node.id, 0);
      }
    });
  }

  // Position nodes within each level
  private positionNodes() {
    const nodesByLevel = new Map<number, GraphNode[]>();

    // Group nodes by level
    this.levels.forEach((level, nodeId) => {
      if (!nodesByLevel.has(level)) {
        nodesByLevel.set(level, []);
      }
      const node = this.nodes.find(n => n.id === nodeId);
      if (node) {
        nodesByLevel.get(level)!.push(node);
      }
    });

    // Position nodes within each level
    nodesByLevel.forEach((nodes, level) => {
      const levelWidth = nodes.length * this.nodeSpacing;
      const startX = (this.options.bounds.width - levelWidth) / 2;
      const y = this.options.bounds.padding + level * this.levelHeight;

      nodes.forEach((node, index) => {
        node.x = startX + index * this.nodeSpacing;
        node.y = y;
      });
    });
  }

  // Run the layout
  public layout(): { nodes: GraphNode[], edges: GraphEdge[] } {
    this.positionNodes();

    return {
      nodes: this.nodes,
      edges: this.edges,
    };
  }
}

// Circular Layout Algorithm
export class CircularLayout {
  private nodes: GraphNode[] = [];
  private edges: GraphEdge[] = [];
  private options: LayoutOptions;

  constructor(nodes: Entity[], edges: Relationship[], options: LayoutOptions) {
    this.options = options;
    this.initializeGraph(nodes, edges);
  }

  private initializeGraph(entities: Entity[], relationships: Relationship[]) {
    // Convert entities to nodes
    this.nodes = entities.map(entity => ({
      ...entity,
      x: 0,
      y: 0,
    }));

    // Convert relationships to edges
    this.edges = relationships.map(rel => {
      const source = this.nodes.find(n => n.id === rel.source_entity_id);
      const target = this.nodes.find(n => n.id === rel.target_entity_id);

      if (!source || !target) {
        throw new Error(`Invalid relationship: ${rel.id}. Source or target not found.`);
      }

      return {
        ...rel,
        source,
        target,
      };
    });
  }

  // Position nodes in a circle
  public layout(): { nodes: GraphNode[], edges: GraphEdge[] } {
    const centerX = this.options.bounds.width / 2;
    const centerY = this.options.bounds.height / 2;
    const radius = Math.min(
      (this.options.bounds.width - 2 * this.options.bounds.padding) / 2,
      (this.options.bounds.height - 2 * this.options.bounds.padding) / 2
    );

    const angleStep = (2 * Math.PI) / this.nodes.length;

    this.nodes.forEach((node, index) => {
      const angle = index * angleStep - Math.PI / 2; // Start from top
      node.x = centerX + radius * Math.cos(angle);
      node.y = centerY + radius * Math.sin(angle);
    });

    return {
      nodes: this.nodes,
      edges: this.edges,
    };
  }
}

// Layout factory function
export function createLayout(
  type: 'force' | 'hierarchical' | 'circular',
  nodes: Entity[],
  edges: Relationship[],
  options: LayoutOptions
) {
  switch (type) {
    case 'force':
      return new ForceDirectedLayout(nodes, edges, options);
    case 'hierarchical':
      return new HierarchicalLayout(nodes, edges, options);
    case 'circular':
      return new CircularLayout(nodes, edges, options);
    default:
      throw new Error(`Unknown layout type: ${type}`);
  }
}

// Utility functions for layout calculations
export const LayoutUtils = {
  // Calculate bounding box of nodes
  getBoundingBox(nodes: GraphNode[]): { minX: number; minY: number; maxX: number; maxY: number } {
    const xs = nodes.map(n => n.x);
    const ys = nodes.map(n => n.y);

    return {
      minX: Math.min(...xs),
      minY: Math.min(...ys),
      maxX: Math.max(...xs),
      maxY: Math.max(...ys),
    };
  },

  // Calculate center point of nodes
  getCenter(nodes: GraphNode[]): { x: number; y: number } {
    const bounds = this.getBoundingBox(nodes);
    return {
      x: (bounds.minX + bounds.maxX) / 2,
      y: (bounds.minY + bounds.maxY) / 2,
    };
  },

  // Scale and translate nodes to fit within bounds
  fitToBounds(
    nodes: GraphNode[],
    bounds: LayoutBounds
  ): GraphNode[] {
    const nodeBounds = this.getBoundingBox(nodes);
    const nodeWidth = nodeBounds.maxX - nodeBounds.minX;
    const nodeHeight = nodeBounds.maxY - nodeBounds.minY;

    const availableWidth = bounds.width - 2 * bounds.padding;
    const availableHeight = bounds.height - 2 * bounds.padding;

    const scaleX = availableWidth / nodeWidth;
    const scaleY = availableHeight / nodeHeight;
    const scale = Math.min(scaleX, scaleY, 2); // Limit max scale to 2x

    const center = this.getCenter(nodes);
    const targetCenter = {
      x: bounds.width / 2,
      y: bounds.height / 2,
    };

    return nodes.map(node => ({
      ...node,
      x: targetCenter.x + (node.x - center.x) * scale,
      y: targetCenter.y + (node.y - center.y) * scale,
    }));
  },

  // Get node size based on confidence and mentions
  getNodeSize(node: GraphNode, baseSize: number = 8): number {
    const confidenceFactor = 0.5 + (node.confidence * 0.5); // 0.5 to 1.0
    const mentionsFactor = Math.log(1 + node.mentions) / Math.log(10); // Logarithmic scaling
    return baseSize * confidenceFactor * mentionsFactor;
  },

  // Get edge width based on confidence and weight
  getEdgeWidth(edge: GraphEdge, baseWidth: number = 1): number {
    return baseWidth + (edge.confidence * edge.weight * 2);
  },
};