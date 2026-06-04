/**
 * Graph Accessibility Provider - WCAG 2.1 AA Compliance
 *
 * Provides accessibility features for graph visualization components.
 * Ensures compliance with WCAG 2.1 AA standards.
 */

import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
} from 'react';
import { GraphNode, GraphEdge } from '../../types/graph-api';

interface AccessibilityContextValue {
  // High contrast mode
  highContrastMode: boolean;
  toggleHighContrast: () => void;

  // Keyboard navigation
  focusedNodeId: string | null;
  focusedEdgeId: string | null;
  setFocusedNode: (nodeId: string | null) => void;
  setFocusedEdge: (edgeId: string | null) => void;
  navigateGraph: (direction: 'up' | 'down' | 'left' | 'right') => void;

  // Screen reader support
  announceToScreenReader: (message: string) => void;
  getAccessibleNodeDescription: (node: GraphNode) => string;
  getAccessibleEdgeDescription: (edge: GraphEdge) => string;

  // Visual accessibility
  fontSize: 'small' | 'medium' | 'large';
  setFontSize: (size: 'small' | 'medium' | 'large') => void;
  reducedMotion: boolean;
  toggleReducedMotion: () => void;

  // Color blindness support
  colorBlindMode: 'normal' | 'protanopia' | 'deuteranopia' | 'tritanopia';
  setColorBlindMode: (
    mode: 'normal' | 'protanopia' | 'deuteranopia' | 'tritanopia'
  ) => void;
  getColorBlindPalette: () => Record<string, string>;
}

const AccessibilityContext = createContext<AccessibilityContextValue | null>(
  null
);

interface GraphAccessibilityProviderProps {
  children: React.ReactNode;
  nodes?: GraphNode[];
  edges?: GraphEdge[];
}

// Color blind friendly palettes
const colorBlindPalettes = {
  normal: {
    person: '#ff6b6b',
    organization: '#4dabf7',
    location: '#51cf66',
    event: '#ff922b',
    concept: '#9775fa',
    document: '#495057',
  },
  protanopia: {
    person: '#0066cc',
    organization: '#ff8c00',
    location: '#009944',
    event: '#cc0066',
    concept: '#6600cc',
    document: '#666666',
  },
  deuteranopia: {
    person: '#0066cc',
    organization: '#ff6600',
    location: '#00aa44',
    event: '#cc0066',
    concept: '#9933cc',
    document: '#666666',
  },
  tritanopia: {
    person: '#0066cc',
    organization: '#ff9900',
    location: '#00aa44',
    event: '#cc0066',
    concept: '#9933cc',
    document: '#666666',
  },
};

export const GraphAccessibilityProvider: React.FC<
  GraphAccessibilityProviderProps
> = ({ children, nodes = [], edges = [] }) => {
  const [highContrastMode, setHighContrastMode] = useState(false);
  const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null);
  const [focusedEdgeId, setFocusedEdgeId] = useState<string | null>(null);
  const [fontSize, setFontSize] = useState<'small' | 'medium' | 'large'>(
    'medium'
  );
  const [reducedMotion, setReducedMotion] = useState(false);
  const [colorBlindMode, setColorBlindMode] = useState<
    'normal' | 'protanopia' | 'deuteranopia' | 'tritanopia'
  >('normal');

  const announcementRef = useRef<HTMLDivElement>(null);
  const navigationMapRef = useRef<Map<string, string[]>>(new Map());

  // Detect user's accessibility preferences
  useEffect(() => {
    // Check for reduced motion preference
    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(motionQuery.matches);

    const handleMotionChange = (e: MediaQueryListEvent) => {
      setReducedMotion(e.matches);
    };

    motionQuery.addEventListener('change', handleMotionChange);

    // Check for high contrast preference
    const contrastQuery = window.matchMedia('(prefers-contrast: high)');
    setHighContrastMode(contrastQuery.matches);

    const handleContrastChange = (e: MediaQueryListEvent) => {
      setHighContrastMode(e.matches);
    };

    contrastQuery.addEventListener('change', handleContrastChange);

    return () => {
      motionQuery.removeEventListener('change', handleMotionChange);
      contrastQuery.removeEventListener('change', handleContrastChange);
    };
  }, []);

  // Build navigation map for keyboard navigation
  useEffect(() => {
    const map = new Map<string, string[]>();

    // Create adjacency relationships for navigation
    edges.forEach((edge) => {
      if (!map.has(edge.source)) {
        map.set(edge.source, []);
      }
      if (!map.has(edge.target)) {
        map.set(edge.target, []);
      }
      map.get(edge.source)!.push(edge.target);
      map.get(edge.target)!.push(edge.source);
    });

    navigationMapRef.current = map;
  }, [edges]);

  // Keyboard navigation
  const navigateGraph = useCallback(
    (direction: 'up' | 'down' | 'left' | 'right') => {
      if (!focusedNodeId && !focusedEdgeId) {
        // If nothing is focused, focus the first node
        if (nodes.length > 0) {
          setFocusedNodeId(nodes[0].id);
        }
        return;
      }

      if (focusedNodeId) {
        const neighbors = navigationMapRef.current.get(focusedNodeId) || [];
        if (neighbors.length > 0) {
          // Simple navigation: cycle through neighbors
          const currentIndex = neighbors.indexOf(focusedNodeId);
          const nextIndex =
            direction === 'right'
              ? (currentIndex + 1) % neighbors.length
              : (currentIndex - 1 + neighbors.length) % neighbors.length;
          setFocusedNodeId(neighbors[nextIndex]);
        }
      }
    },
    [focusedNodeId, focusedEdgeId, nodes]
  );

  // Screen reader announcements
  const announceToScreenReader = useCallback((message: string) => {
    if (announcementRef.current) {
      announcementRef.current.textContent = message;
      // Trigger screen reader to read the message
      announcementRef.current.style.display = 'none';
      announcementRef.current.offsetHeight; // Force reflow
      announcementRef.current.style.display = 'block';
    }
  }, []);

  // Accessible descriptions for screen readers
  const getAccessibleNodeDescription = useCallback(
    (node: GraphNode): string => {
      const relationshipCount = edges.filter(
        (e) => e.source === node.id || e.target === node.id
      ).length;
      return `${node.label}, ${node.type} entity, confidence: ${(node.confidence * 100).toFixed(1)}%, ${relationshipCount} relationships`;
    },
    [edges]
  );

  const getAccessibleEdgeDescription = useCallback(
    (edge: GraphEdge): string => {
      const sourceNode = nodes.find((n) => n.id === edge.source);
      const targetNode = nodes.find((n) => n.id === edge.target);
      const sourceLabel = sourceNode?.label || edge.source;
      const targetLabel = targetNode?.label || edge.target;
      return `${edge.type} relationship from ${sourceLabel} to ${targetLabel}, weight: ${edge.weight.toFixed(2)}, confidence: ${(edge.confidence * 100).toFixed(1)}%`;
    },
    [nodes]
  );

  // Toggle functions
  const toggleHighContrast = useCallback(() => {
    setHighContrastMode((prev) => !prev);
  }, []);

  const toggleReducedMotion = useCallback(() => {
    setReducedMotion((prev) => !prev);
  }, []);

  // Color blind mode utilities
  const getColorBlindPalette = useCallback(() => {
    return colorBlindPalettes[colorBlindMode];
  }, [colorBlindMode]);

  const contextValue: AccessibilityContextValue = {
    highContrastMode,
    toggleHighContrast,
    focusedNodeId,
    focusedEdgeId,
    setFocusedNode: setFocusedNodeId,
    setFocusedEdge: setFocusedEdgeId,
    navigateGraph,
    announceToScreenReader,
    getAccessibleNodeDescription,
    getAccessibleEdgeDescription,
    fontSize,
    setFontSize,
    reducedMotion,
    toggleReducedMotion,
    colorBlindMode,
    setColorBlindMode,
    getColorBlindPalette,
  };

  return (
    <AccessibilityContext.Provider value={contextValue}>
      {children}

      {/* Screen reader announcements (visually hidden) */}
      <div
        ref={announcementRef}
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      />

      {/* Global accessibility styles */}
      <style jsx>{`
        :global(.high-contrast) {
          filter: contrast(1.5);
        }

        :global(.reduced-motion *) {
          animation-duration: 0.01ms !important;
          animation-iteration-count: 1 !important;
          transition-duration: 0.01ms !important;
        }

        :global(.font-small) {
          font-size: 14px;
        }

        :global(.font-medium) {
          font-size: 16px;
        }

        :global(.font-large) {
          font-size: 18px;
        }

        :global(.sr-only) {
          position: absolute !important;
          width: 1px !important;
          height: 1px !important;
          padding: 0 !important;
          margin: -1px !important;
          overflow: hidden !important;
          clip: rect(0, 0, 0, 0) !important;
          white-space: nowrap !important;
          border: 0 !important;
        }
      `}</style>
    </AccessibilityContext.Provider>
  );
};

// Hook to use accessibility context
export const useGraphAccessibility = () => {
  const context = useContext(AccessibilityContext);
  if (!context) {
    throw new Error(
      'useGraphAccessibility must be used within a GraphAccessibilityProvider'
    );
  }
  return context;
};

// Accessible graph node component
export const AccessibleGraphNode: React.FC<{
  node: GraphNode;
  isFocused?: boolean;
  onSelect?: () => void;
  className?: string;
}> = ({ node, isFocused = false, onSelect, className = '' }) => {
  const {
    focusedNodeId,
    setFocusedNode,
    announceToScreenReader,
    getAccessibleNodeDescription,
    getColorBlindPalette,
  } = useGraphAccessibility();

  const handleClick = useCallback(() => {
    setFocusedNode(node.id);
    announceToScreenReader(`Selected ${getAccessibleNodeDescription(node)}`);
    onSelect?.();
  }, [
    node.id,
    setFocusedNode,
    announceToScreenReader,
    getAccessibleNodeDescription,
    onSelect,
  ]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      switch (event.key) {
        case 'Enter':
        case ' ':
          event.preventDefault();
          handleClick();
          break;
        case 'ArrowUp':
        case 'ArrowDown':
        case 'ArrowLeft':
        case 'ArrowRight':
          event.preventDefault();
          // Navigation will be handled by parent component
          break;
      }
    },
    [handleClick]
  );

  const palette = getColorBlindPalette();
  const nodeColor = palette[node.type] || palette.document;

  return (
    <div
      role="button"
      tabIndex={isFocused ? 0 : -1}
      aria-label={getAccessibleNodeDescription(node)}
      aria-describedby={`node-${node.id}-details`}
      className={`graph-node ${className} ${isFocused ? 'ring-2 ring-[var(--nous-sol)]' : ''}`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      style={{
        backgroundColor: nodeColor,
        cursor: 'pointer',
      }}
    >
      <div id={`node-${node.id}-details`} className="sr-only">
        Node with ID {node.id}, type {node.type}, confidence{' '}
        {(node.confidence * 100).toFixed(1)}%
      </div>
    </div>
  );
};

// Accessible graph edge component
export const AccessibleGraphEdge: React.FC<{
  edge: GraphEdge;
  isFocused?: boolean;
  onSelect?: () => void;
  className?: string;
}> = ({ edge, isFocused = false, onSelect, className = '' }) => {
  const {
    focusedEdgeId,
    setFocusedEdge,
    announceToScreenReader,
    getAccessibleEdgeDescription,
  } = useGraphAccessibility();

  const handleClick = useCallback(() => {
    setFocusedEdge(edge.id);
    announceToScreenReader(`Selected ${getAccessibleEdgeDescription(edge)}`);
    onSelect?.();
  }, [
    edge.id,
    setFocusedEdge,
    announceToScreenReader,
    getAccessibleEdgeDescription,
    onSelect,
  ]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      switch (event.key) {
        case 'Enter':
        case ' ':
          event.preventDefault();
          handleClick();
          break;
      }
    },
    [handleClick]
  );

  return (
    <div
      role="button"
      tabIndex={isFocused ? 0 : -1}
      aria-label={getAccessibleEdgeDescription(edge)}
      className={`graph-edge ${className} ${isFocused ? 'ring-2 ring-[var(--nous-sol)]' : ''}`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      style={{
        cursor: 'pointer',
      }}
    />
  );
};

// Accessibility controls panel
export const AccessibilityControls: React.FC<{ className?: string }> = ({
  className = '',
}) => {
  const {
    highContrastMode,
    toggleHighContrast,
    fontSize,
    setFontSize,
    reducedMotion,
    toggleReducedMotion,
    colorBlindMode,
    setColorBlindMode,
  } = useGraphAccessibility();

  return (
    <div className={`p-4 bg-[var(--nous-bg-2)] rounded-lg ${className}`}>
      <h3 className="text-lg font-semibold mb-4">Accessibility Options</h3>

      <div className="space-y-4">
        {/* High Contrast */}
        <div className="flex items-center justify-between">
          <label htmlFor="high-contrast" className="text-sm font-medium">
            High Contrast
          </label>
          <button
            id="high-contrast"
            type="button"
            role="switch"
            aria-checked={highContrastMode}
            onClick={toggleHighContrast}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              highContrastMode
                ? 'bg-[var(--nous-sol)]'
                : 'bg-[var(--nous-bg-3)]'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-background transition-transform ${
                highContrastMode ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        {/* Font Size */}
        <div>
          <label className="text-sm font-medium mb-2 block">Font Size</label>
          <div className="flex space-x-2">
            {(['small', 'medium', 'large'] as const).map((size) => (
              <button
                key={size}
                onClick={() => setFontSize(size)}
                className={`px-3 py-1 rounded text-sm ${
                  fontSize === size
                    ? 'bg-[var(--nous-sol)] text-white'
                    : 'bg-[var(--nous-bg-2)] text-foreground hover:bg-[var(--nous-bg-3)]'
                }`}
              >
                {size.charAt(0).toUpperCase() + size.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Reduced Motion */}
        <div className="flex items-center justify-between">
          <label htmlFor="reduced-motion" className="text-sm font-medium">
            Reduced Motion
          </label>
          <button
            id="reduced-motion"
            type="button"
            role="switch"
            aria-checked={reducedMotion}
            onClick={toggleReducedMotion}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              reducedMotion ? 'bg-[var(--nous-sol)]' : 'bg-[var(--nous-bg-3)]'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-background transition-transform ${
                reducedMotion ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        {/* Color Blind Mode */}
        <div>
          <label className="text-sm font-medium mb-2 block">
            Color Vision Support
          </label>
          <div className="grid grid-cols-2 gap-2">
            {(
              ['normal', 'protanopia', 'deuteranopia', 'tritanopia'] as const
            ).map((mode) => (
              <button
                key={mode}
                onClick={() => setColorBlindMode(mode)}
                className={`px-3 py-1 rounded text-sm capitalize ${
                  colorBlindMode === mode
                    ? 'bg-[var(--nous-sol)] text-white'
                    : 'bg-[var(--nous-bg-2)] text-foreground hover:bg-[var(--nous-bg-3)]'
                }`}
              >
                {mode === 'normal' ? 'Normal' : mode}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default GraphAccessibilityProvider;
