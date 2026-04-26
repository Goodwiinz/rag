import { format, parseISO, isAfter, isBefore, subDays, subHours, subMinutes } from 'date-fns';
import { AnalyticsMetric, TimeSeriesData, GraphNode, GraphEdge } from '@/store/analytics';

// Data transformation utilities

export const transformTimeSeriesData = (
  data: TimeSeriesData[],
  granularity: 'minute' | 'hour' | 'day' = 'hour',
  aggregation: 'sum' | 'average' | 'min' | 'max' = 'average'
): TimeSeriesData[] => {
  if (!data.length) return [];

  const groupedData = data.reduce((acc, point) => {
    const date = parseISO(point.timestamp);
    let key: string;

    switch (granularity) {
      case 'minute':
        key = format(date, 'yyyy-MM-dd HH:mm');
        break;
      case 'hour':
        key = format(date, 'yyyy-MM-dd HH:00');
        break;
      case 'day':
        key = format(date, 'yyyy-MM-dd');
        break;
      default:
        key = format(date, 'yyyy-MM-dd HH:00');
    }

    if (!acc[key]) {
      acc[key] = [];
    }
    acc[key].push(point.value);
    return acc;
  }, {} as Record<string, number[]>);

  return Object.entries(groupedData).map(([timestamp, values]) => {
    let aggregatedValue: number;

    switch (aggregation) {
      case 'sum':
        aggregatedValue = values.reduce((sum, val) => sum + val, 0);
        break;
      case 'average':
        aggregatedValue = values.reduce((sum, val) => sum + val, 0) / values.length;
        break;
      case 'min':
        aggregatedValue = Math.min(...values);
        break;
      case 'max':
        aggregatedValue = Math.max(...values);
        break;
      default:
        aggregatedValue = values.reduce((sum, val) => sum + val, 0) / values.length;
    }

    return {
      timestamp: new Date(timestamp).toISOString(),
      value: Math.round(aggregatedValue * 100) / 100, // Round to 2 decimal places
    };
  }).sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
};

export const calculateMetricTrend = (
  currentData: TimeSeriesData[],
  previousData: TimeSeriesData[]
): {
  direction: 'up' | 'down' | 'stable';
  percentage: number;
  change: number;
} => {
  if (!currentData.length || !previousData.length) {
    return { direction: 'stable', percentage: 0, change: 0 };
  }

  const currentAvg = currentData.reduce((sum, d) => sum + d.value, 0) / currentData.length;
  const previousAvg = previousData.reduce((sum, d) => sum + d.value, 0) / previousData.length;

  const change = currentAvg - previousAvg;
  const percentage = previousAvg !== 0 ? (change / previousAvg) * 100 : 0;

  let direction: 'up' | 'down' | 'stable';
  if (Math.abs(percentage) < 1) {
    direction = 'stable';
  } else if (percentage > 0) {
    direction = 'up';
  } else {
    direction = 'down';
  }

  return {
    direction,
    percentage: Math.abs(percentage),
    change: Math.round(change * 100) / 100,
  };
};

export const normalizeMetrics = (metrics: AnalyticsMetric[]): AnalyticsMetric[] => {
  if (!metrics.length) return [];

  // Find min and max values for normalization
  const numericMetrics = metrics.filter(m => typeof m.value === 'number');
  if (!numericMetrics.length) return metrics;

  const values = numericMetrics.map(m => m.value as number);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue;

  if (range === 0) return metrics; // All values are the same

  return metrics.map(metric => {
    if (typeof metric.value !== 'number') return metric;

    const normalizedValue = (metric.value - minValue) / range;
    return {
      ...metric,
      value: Math.round(normalizedValue * 1000) / 1000, // 3 decimal places
      metadata: {
        ...metric.metadata,
        originalValue: metric.value,
        minValue,
        maxValue,
      },
    };
  });
};

export const filterDataByTimeRange = (
  data: TimeSeriesData[],
  timeRange: { start: string; end: string }
): TimeSeriesData[] => {
  const start = parseISO(timeRange.start);
  const end = parseISO(timeRange.end);

  return data.filter(point => {
    const pointTime = parseISO(point.timestamp);
    return isAfter(pointTime, start) && isBefore(pointTime, end);
  });
};

export const aggregateDataByPeriod = (
  data: TimeSeriesData[],
  period: 'hour' | 'day' | 'week' | 'month',
  aggregation: 'sum' | 'average' | 'min' | 'max' = 'average'
): TimeSeriesData[] => {
  if (!data.length) return [];

  const groupedData = data.reduce((acc, point) => {
    const date = parseISO(point.timestamp);
    let key: string;

    switch (period) {
      case 'hour':
        key = format(date, 'yyyy-MM-dd HH:00');
        break;
      case 'day':
        key = format(date, 'yyyy-MM-dd');
        break;
      case 'week':
        // Start of week (Monday)
        const startOfWeek = new Date(date);
        startOfWeek.setDate(date.getDate() - date.getDay() + 1);
        key = format(startOfWeek, 'yyyy-MM-dd');
        break;
      case 'month':
        key = format(date, 'yyyy-MM');
        break;
      default:
        key = format(date, 'yyyy-MM-dd');
    }

    if (!acc[key]) {
      acc[key] = [];
    }
    acc[key].push(point.value);
    return acc;
  }, {} as Record<string, number[]>);

  return Object.entries(groupedData).map(([timestamp, values]) => {
    let aggregatedValue: number;

    switch (aggregation) {
      case 'sum':
        aggregatedValue = values.reduce((sum, val) => sum + val, 0);
        break;
      case 'average':
        aggregatedValue = values.reduce((sum, val) => sum + val, 0) / values.length;
        break;
      case 'min':
        aggregatedValue = Math.min(...values);
        break;
      case 'max':
        aggregatedValue = Math.max(...values);
        break;
      default:
        aggregatedValue = values.reduce((sum, val) => sum + val, 0) / values.length;
    }

    return {
      timestamp: new Date(timestamp).toISOString(),
      value: Math.round(aggregatedValue * 100) / 100,
    };
  }).sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
};

// Graph data transformations
export const transformGraphDataForVisualization = (
  nodes: GraphNode[],
  edges: GraphEdge[],
  options: {
    layout?: 'force' | 'hierarchical' | 'circular';
    nodeSize?: 'uniform' | 'degree' | 'property';
    colorBy?: 'type' | 'property';
    maxSize?: number;
    minSize?: number;
  } = {}
): {
  nodes: Array<GraphNode & { x?: number; y?: number; size?: number; color?: string }>;
  edges: Array<GraphEdge & { width?: number; color?: string }>;
} => {
  const {
    layout = 'force',
    nodeSize = 'degree',
    colorBy = 'type',
    maxSize = 30,
    minSize = 5,
  } = options;

  // Calculate node degrees
  const nodeDegrees = nodes.reduce((acc, node) => {
    const degree = edges.filter(edge => edge.source === node.id || edge.target === node.id).length;
    acc[node.id] = degree;
    return acc;
  }, {} as Record<string, number>);

  // Find min/max degrees for normalization
  const degrees = Object.values(nodeDegrees);
  const minDegree = Math.min(...degrees);
  const maxDegree = Math.max(...degrees);
  const degreeRange = maxDegree - minDegree || 1;

  // Transform nodes
  const transformedNodes = nodes.map(node => {
    let size = minSize;
    let color = '#3b82f6'; // Default blue

    // Calculate size based on nodeSize option
    if (nodeSize === 'degree') {
      const normalizedDegree = (nodeDegrees[node.id] - minDegree) / degreeRange;
      size = minSize + (maxSize - minSize) * normalizedDegree;
    } else if (nodeSize === 'property' && node.properties.size) {
      size = Math.min(Math.max(node.properties.size, minSize), maxSize);
    }

    // Calculate color based on colorBy option
    if (colorBy === 'type') {
      const colorMap: Record<string, string> = {
        entity: '#3b82f6',
        concept: '#10b981',
        document: '#f59e0b',
        person: '#ef4444',
        organization: '#8b5cf6',
        location: '#ec4899',
        event: '#06b6d4',
      };
      color = colorMap[node.type] || '#6b7280';
    } else if (colorBy === 'property' && node.properties.color) {
      color = node.properties.color;
    }

    // Add layout positions if not present
    let x: number | undefined, y: number | undefined;
    if (layout === 'circular') {
      const angle = (nodes.indexOf(node) / nodes.length) * 2 * Math.PI;
      const radius = 200;
      x = Math.cos(angle) * radius;
      y = Math.sin(angle) * radius;
    } else if (layout === 'hierarchical') {
      // Simple hierarchical layout based on type
      const typeLevels: Record<string, number> = {
        entity: 0,
        concept: 1,
        document: 2,
        person: 1,
        organization: 1,
        location: 2,
        event: 3,
      };
      const level = typeLevels[node.type] || 0;
      x = (nodes.indexOf(node) % 5) * 100 - 200;
      y = level * 150;
    }

    return {
      ...node,
      x,
      y,
      size,
      color,
    };
  });

  // Transform edges
  const transformedEdges = edges.map(edge => {
    let width = 1;
    let color = '#9ca3af'; // Default gray

    if (edge.properties.weight) {
      width = Math.min(Math.max(edge.properties.weight, 1), 5);
    }

    const colorMap: Record<string, string> = {
      related_to: '#9ca3af',
      part_of: '#3b82f6',
      instance_of: '#10b981',
      located_in: '#f59e0b',
      created_by: '#ef4444',
      references: '#8b5cf6',
    };
    color = colorMap[edge.type] || '#9ca3af';

    return {
      ...edge,
      width,
      color,
    };
  });

  return {
    nodes: transformedNodes,
    edges: transformedEdges,
  };
};

export const calculateGraphStatistics = (nodes: GraphNode[], edges: GraphEdge[]) => {
  const nodeCount = nodes.length;
  const edgeCount = edges.length;

  // Node type distribution
  const nodeTypes = nodes.reduce((acc, node) => {
    acc[node.type] = (acc[node.type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  // Edge type distribution
  const edgeTypes = edges.reduce((acc, edge) => {
    acc[edge.type] = (acc[edge.type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  // Calculate degrees
  const degrees = nodes.map(node =>
    edges.filter(edge => edge.source === node.id || edge.target === node.id).length
  );

  const averageDegree = degrees.length > 0
    ? degrees.reduce((sum, degree) => sum + degree, 0) / degrees.length
    : 0;

  const maxDegree = Math.max(...degrees, 0);
  const minDegree = Math.min(...degrees, 0);

  // Graph density (ratio of actual edges to possible edges)
  const possibleEdges = (nodeCount * (nodeCount - 1)) / 2;
  const density = possibleEdges > 0 ? edgeCount / possibleEdges : 0;

  return {
    nodeCount,
    edgeCount,
    nodeTypes,
    edgeTypes,
    averageDegree: Math.round(averageDegree * 100) / 100,
    maxDegree,
    minDegree,
    density: Math.round(density * 10000) / 10000, // 4 decimal places
  };
};

// Performance utilities
export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void => {
  let timeout: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
};

export const throttle = <T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void => {
  let inThrottle: boolean;
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, wait);
    }
  };
};

export const memoize = <T extends (...args: any[]) => any>(
  func: T,
  keyGenerator?: (...args: Parameters<T>) => string
): T => {
  const cache = new Map<string, ReturnType<T>>();

  return ((...args: Parameters<T>) => {
    const key = keyGenerator ? keyGenerator(...args) : JSON.stringify(args);

    if (cache.has(key)) {
      return cache.get(key);
    }

    const result = func(...args);
    cache.set(key, result);
    return result;
  }) as T;
};

// Data validation utilities
export const validateTimeSeriesData = (data: TimeSeriesData[]): TimeSeriesData[] => {
  return data.filter(point => {
    return (
      point.timestamp &&
      !isNaN(new Date(point.timestamp).getTime()) &&
      typeof point.value === 'number' &&
      !isNaN(point.value)
    );
  });
};

export const sanitizeMetricName = (name: string): string => {
  return name
    .replace(/[^a-zA-Z0-9_-]/g, '_')
    .replace(/^[^a-zA-Z_]/, '_')
    .toLowerCase();
};

export const formatMetricValue = (
  value: number,
  unit?: string,
  precision: number = 2
): string => {
  if (unit === 'bytes' || unit === 'B') {
    const bytes = value;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 B';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(precision)} ${sizes[i]}`;
  }

  if (unit === 'percentage' || unit === '%') {
    return `${(value * 100).toFixed(precision)}%`;
  }

  if (unit === 'duration' || unit === 'ms') {
    if (value < 1000) {
      return `${value.toFixed(precision)}ms`;
    } else if (value < 60000) {
      return `${(value / 1000).toFixed(precision)}s`;
    } else {
      const minutes = value / 60000;
      return `${minutes.toFixed(precision)}m`;
    }
  }

  // Default formatting
  const formatted = value.toLocaleString(undefined, {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  });

  return unit ? `${formatted} ${unit}` : formatted;
};