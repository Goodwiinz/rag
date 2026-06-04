/**
 * Responsive Graph Layout - Mobile-First Design
 *
 * Provides responsive design patterns for graph visualization components.
 * Adapts layout based on screen size and device capabilities.
 */

import React, {
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
} from 'react';
import { GraphNode, GraphEdge, GraphFilters } from '../../types/graph-api';
import { IconButton } from '@/components/ui/icon-button';

interface BreakpointConfig {
  maxVisibleNodes: number;
  maxVisibleEdges: number;
  showLabels: boolean;
  enablePhysics: boolean;
  controlPosition: 'top' | 'side' | 'bottom';
  layout: 'force' | 'circular' | 'hierarchical';
  fontSize: number;
  nodeSize: number;
  edgeWidth: number;
}

interface ResponsiveGraphLayoutProps {
  children: (
    config: BreakpointConfig & { dimensions: { width: number; height: number } }
  ) => React.ReactNode;
  className?: string;
}

// Breakpoint configurations
const breakpointConfigs: Record<string, BreakpointConfig> = {
  mobile: {
    maxVisibleNodes: 50,
    maxVisibleEdges: 100,
    showLabels: false,
    enablePhysics: false,
    controlPosition: 'bottom',
    layout: 'circular',
    fontSize: 12,
    nodeSize: 20,
    edgeWidth: 1,
  },
  tablet: {
    maxVisibleNodes: 200,
    maxVisibleEdges: 400,
    showLabels: true,
    enablePhysics: true,
    controlPosition: 'side',
    layout: 'force',
    fontSize: 14,
    nodeSize: 25,
    edgeWidth: 2,
  },
  desktop: {
    maxVisibleNodes: 500,
    maxVisibleEdges: 1000,
    showLabels: true,
    enablePhysics: true,
    controlPosition: 'side',
    layout: 'force',
    fontSize: 16,
    nodeSize: 30,
    edgeWidth: 2,
  },
  large: {
    maxVisibleNodes: 1000,
    maxVisibleEdges: 2000,
    showLabels: true,
    enablePhysics: true,
    controlPosition: 'side',
    layout: 'force',
    fontSize: 16,
    nodeSize: 35,
    edgeWidth: 3,
  },
};

export const ResponsiveGraphLayout: React.FC<ResponsiveGraphLayoutProps> = ({
  children,
  className = '',
}) => {
  const [breakpoint, setBreakpoint] = useState<string>('desktop');
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [orientation, setOrientation] = useState<'portrait' | 'landscape'>(
    'landscape'
  );
  const containerRef = useRef<HTMLDivElement>(null);

  // Determine current breakpoint based on container width
  const determineBreakpoint = useCallback((width: number): string => {
    if (width < 768) return 'mobile';
    if (width < 1024) return 'tablet';
    if (width < 1440) return 'desktop';
    return 'large';
  }, []);

  // Update dimensions and breakpoint
  const updateDimensions = useCallback(() => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const newWidth = rect.width;
      const newHeight = rect.height;
      const newBreakpoint = determineBreakpoint(newWidth);
      const newOrientation = newHeight > newWidth ? 'portrait' : 'landscape';

      setDimensions({ width: newWidth, height: newHeight });
      setBreakpoint(newBreakpoint);
      setOrientation(newOrientation);
    }
  }, [determineBreakpoint]);

  // Set up resize observer
  useEffect(() => {
    const resizeObserver = new ResizeObserver(() => {
      updateDimensions();
    });

    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      resizeObserver.disconnect();
    };
  }, [updateDimensions]);

  // Initial dimension calculation
  useEffect(() => {
    updateDimensions();
  }, [updateDimensions]);

  // Handle window resize with debouncing
  useEffect(() => {
    let timeoutId: NodeJS.Timeout;

    const handleResize = () => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(updateDimensions, 100);
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      clearTimeout(timeoutId);
    };
  }, [updateDimensions]);

  const config = breakpointConfigs[breakpoint];

  const mergedConfig = useMemo(
    () => ({ ...config, dimensions, orientation, breakpoint }),
    [config, dimensions, orientation, breakpoint]
  );

  return (
    <div
      ref={containerRef}
      className={`responsive-graph-layout ${className}`}
      style={{ width: '100%', height: '100%' }}
    >
      {children(mergedConfig)}
    </div>
  );
};

// Responsive controls component
export const ResponsiveGraphControls: React.FC<{
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
  onReset: () => void;
  onToggleLabels: () => void;
  onTogglePhysics: () => void;
  showLabels: boolean;
  enablePhysics: boolean;
  className?: string;
}> = ({
  onZoomIn,
  onZoomOut,
  onFit,
  onReset,
  onToggleLabels,
  onTogglePhysics,
  showLabels,
  enablePhysics,
  className = '',
}) => {
  const [breakpoint, setBreakpoint] = useState<string>('desktop');

  useEffect(() => {
    const updateBreakpoint = () => {
      const width = window.innerWidth;
      if (width < 768) setBreakpoint('mobile');
      else if (width < 1024) setBreakpoint('tablet');
      else setBreakpoint('desktop');
    };

    updateBreakpoint();
    window.addEventListener('resize', updateBreakpoint);
    return () => window.removeEventListener('resize', updateBreakpoint);
  }, []);

  const baseControls = (
    <>
      <IconButton
        onClick={onZoomIn}
        className="p-2 bg-background border border-border rounded hover:bg-[var(--nous-bg-3)]"
        label="Zoom in"
        icon={
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 6v6m0 0v6m0-6h6m-6 0H6"
            />
          </svg>
        }
      />
      <IconButton
        onClick={onZoomOut}
        className="p-2 bg-background border border-border rounded hover:bg-[var(--nous-bg-3)]"
        label="Zoom out"
        icon={
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M20 12H4"
            />
          </svg>
        }
      />
      <IconButton
        onClick={onFit}
        className="p-2 bg-background border border-border rounded hover:bg-[var(--nous-bg-3)]"
        label="Fit to screen"
        icon={
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
            />
          </svg>
        }
      />
      <IconButton
        onClick={onReset}
        className="p-2 bg-background border border-border rounded hover:bg-[var(--nous-bg-3)]"
        label="Reset view"
        icon={
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        }
      />
    </>
  );

  const toggleControls = (
    <>
      {breakpoint !== 'mobile' && (
        <button
          onClick={onToggleLabels}
          className={`p-2 border rounded ${
            showLabels
              ? 'bg-[var(--nous-sol)] text-white border-[var(--nous-sol)]'
              : 'bg-background border-border hover:bg-[var(--nous-bg-3)]'
          }`}
          aria-label={showLabels ? 'Hide labels' : 'Show labels'}
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </button>
      )}
      {breakpoint === 'desktop' && (
        <button
          onClick={onTogglePhysics}
          className={`p-2 border rounded ${
            enablePhysics
              ? 'bg-[var(--nous-sol)] text-white border-[var(--nous-sol)]'
              : 'bg-background border-border hover:bg-[var(--nous-bg-3)]'
          }`}
          aria-label={enablePhysics ? 'Disable physics' : 'Enable physics'}
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 10V3L4 14h7v7l9-11h-7z"
            />
          </svg>
        </button>
      )}
    </>
  );

  const renderControls = () => {
    switch (breakpoint) {
      case 'mobile':
        return (
          <div className="flex justify-center space-x-2 p-2 bg-background border-t">
            {baseControls}
          </div>
        );

      case 'tablet':
        return (
          <div className="flex justify-between items-center p-4 bg-background border-b">
            <div className="flex space-x-2">{baseControls}</div>
            <div className="flex space-x-2">{toggleControls}</div>
          </div>
        );

      case 'desktop':
      default:
        return (
          <div className="absolute top-4 left-4 z-10">
            <div className="bg-background rounded-lg shadow-lg border p-2 space-y-2">
              <div className="flex space-x-2">{baseControls}</div>
              <div className="flex space-x-2">{toggleControls}</div>
            </div>
          </div>
        );
    }
  };

  return (
    <div className={`responsive-graph-controls ${className}`}>
      {renderControls()}
    </div>
  );
};

// Responsive filter panel
export const ResponsiveFilterPanel: React.FC<{
  filters: GraphFilters;
  onFiltersChange: (filters: Partial<GraphFilters>) => void;
  className?: string;
}> = ({ filters, onFiltersChange, className = '' }) => {
  const [breakpoint, setBreakpoint] = useState<string>('desktop');
  const [isCollapsed, setIsCollapsed] = useState(false);

  useEffect(() => {
    const updateBreakpoint = () => {
      const width = window.innerWidth;
      if (width < 768) setBreakpoint('mobile');
      else if (width < 1024) setBreakpoint('tablet');
      else setBreakpoint('desktop');
    };

    updateBreakpoint();
    window.addEventListener('resize', updateBreakpoint);
    return () => window.removeEventListener('resize', updateBreakpoint);
  }, []);

  const renderMobileFilters = () => (
    <div className="fixed bottom-0 left-0 right-0 bg-background border-t shadow-lg p-4 z-20">
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <h3 className="font-semibold">Filters</h3>
          <button
            onClick={() => setIsCollapsed(true)}
            className="p-1 hover:bg-[var(--nous-bg-3)] rounded"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <input
            type="text"
            placeholder="Search..."
            className="px-3 py-2 border rounded text-sm"
            value={filters.search_query || ''}
            onChange={(e) => onFiltersChange({ search_query: e.target.value })}
          />
          <select
            className="px-3 py-2 border rounded text-sm"
            value={filters.entity_types?.[0] || ''}
            onChange={(e) =>
              onFiltersChange({
                entity_types: e.target.value ? [e.target.value] : undefined,
              })
            }
          >
            <option value="">All Types</option>
            <option value="person">Person</option>
            <option value="organization">Organization</option>
            <option value="location">Location</option>
          </select>
        </div>
      </div>
    </div>
  );

  const renderTabletFilters = () => (
    <div className="bg-background border rounded-lg p-4">
      <h3 className="font-semibold mb-3">Filters</h3>
      <div className="space-y-3">
        <input
          type="text"
          placeholder="Search entities..."
          className="w-full px-3 py-2 border rounded"
          value={filters.search_query || ''}
          onChange={(e) => onFiltersChange({ search_query: e.target.value })}
        />
        <div className="grid grid-cols-2 gap-3">
          <select
            className="px-3 py-2 border rounded"
            value={filters.entity_types?.[0] || ''}
            onChange={(e) =>
              onFiltersChange({
                entity_types: e.target.value ? [e.target.value] : undefined,
              })
            }
          >
            <option value="">All Types</option>
            <option value="person">Person</option>
            <option value="organization">Organization</option>
            <option value="location">Location</option>
            <option value="event">Event</option>
            <option value="concept">Concept</option>
          </select>
          <input
            type="number"
            placeholder="Min Confidence"
            min="0"
            max="1"
            step="0.1"
            className="px-3 py-2 border rounded"
            value={filters.min_confidence || ''}
            onChange={(e) =>
              onFiltersChange({
                min_confidence: parseFloat(e.target.value) || undefined,
              })
            }
          />
        </div>
      </div>
    </div>
  );

  const renderDesktopFilters = () => (
    <div className="bg-background border rounded-lg p-6">
      <h3 className="font-semibold mb-4">Graph Filters</h3>
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Search</label>
          <input
            type="text"
            placeholder="Search entities..."
            className="w-full px-3 py-2 border rounded"
            value={filters.search_query || ''}
            onChange={(e) => onFiltersChange({ search_query: e.target.value })}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Entity Types</label>
          <div className="space-y-2">
            {[
              'person',
              'organization',
              'location',
              'event',
              'concept',
              'document',
            ].map((type) => (
              <label key={type} className="flex items-center">
                <input
                  type="checkbox"
                  className="mr-2"
                  checked={filters.entity_types?.includes(type) || false}
                  onChange={(e) => {
                    const current = filters.entity_types || [];
                    if (e.target.checked) {
                      onFiltersChange({ entity_types: [...current, type] });
                    } else {
                      onFiltersChange({
                        entity_types: current.filter((t) => t !== type),
                      });
                    }
                  }}
                />
                <span className="capitalize">{type}</span>
              </label>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              Min Confidence
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              className="w-full"
              value={filters.min_confidence || 0.5}
              onChange={(e) =>
                onFiltersChange({ min_confidence: parseFloat(e.target.value) })
              }
            />
            <span className="text-xs text-muted-foreground">
              {((filters.min_confidence || 0.5) * 100).toFixed(0)}%
            </span>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Max Results
            </label>
            <input
              type="number"
              min="10"
              max="1000"
              step="10"
              className="w-full px-3 py-2 border rounded"
              value={filters.limit || 100}
              onChange={(e) =>
                onFiltersChange({ limit: parseInt(e.target.value) })
              }
            />
          </div>
        </div>
      </div>
    </div>
  );

  if (breakpoint === 'mobile' && isCollapsed) {
    return (
      <div className={`fixed bottom-4 left-4 z-10 ${className}`}>
        <button
          onClick={() => setIsCollapsed(false)}
          className="bg-[var(--nous-sol)] text-white p-3 rounded-full shadow-lg"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
            />
          </svg>
        </button>
      </div>
    );
  }

  return (
    <div className={`responsive-filter-panel ${className}`}>
      {breakpoint === 'mobile' && !isCollapsed && renderMobileFilters()}
      {breakpoint === 'tablet' && renderTabletFilters()}
      {breakpoint === 'desktop' && renderDesktopFilters()}
    </div>
  );
};

export default ResponsiveGraphLayout;
