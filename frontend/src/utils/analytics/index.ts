// Data transformation utilities
export {
  transformTimeSeriesData,
  calculateMetricTrend,
  normalizeMetrics,
  filterDataByTimeRange,
  aggregateDataByPeriod,
  transformGraphDataForVisualization,
  calculateGraphStatistics,
  debounce,
  throttle,
  memoize,
  validateTimeSeriesData,
  sanitizeMetricName,
  formatMetricValue as formatRawMetricValue,
} from './dataTransformers';

// Chart utilities
export {
  getChartTheme,
  getDefaultChartOptions,
  formatChartLabel,
  getTimeSeriesChartConfig,
  getBarChartConfig,
  getPieChartConfig,
  getAreaChartConfig,
  getScatterChartConfig,
  getChartSize,
  getChartAnimationConfig,
  exportChartAsImage,
  exportChartDataAsCSV,
  generateColorPalette,
  interpolateColor,
} from './chartUtils';

// Formatting utilities
export {
  formatDate,
  formatDateTime,
  formatRelativeTime,
  formatTimeRange,
  isInTimeRange,
  formatNumber,
  formatLargeNumber,
  formatPercentage,
  formatBytes,
  formatDuration,
  truncateString,
  capitalizeWords,
  camelCaseToTitle,
  snakeCaseToTitle,
  kebabCaseToTitle,
  formatMetricValue,
  formatTrend,
  formatTrendIcon,
  formatStatus,
  formatUrl,
  formatFilePath,
  formatValidationErrors,
  formatSearchHighlight,
  formatCsvValue,
  formatJsonForExport,
} from './formatUtils';

// Combined utilities for common use cases

export const createDashboardConfig = (options: {
  autoRefresh?: boolean;
  refreshInterval?: number;
  theme?: 'light' | 'dark' | 'system';
  layout?: 'grid' | 'free';
}) => {
  return {
    autoRefresh: options.autoRefresh ?? true,
    refreshInterval: options.refreshInterval ?? 30000,
    theme: options.theme ?? 'system',
    layout: options.layout ?? 'grid',
  };
};

export const createWidgetConfig = (type: string, options: any = {}) => {
  const baseConfig = {
    type,
    title: options.title || `${type} Widget`,
    position: options.position || { x: 0, y: 0, width: 4, height: 3 },
    config: options.config || {},
    refreshInterval: options.refreshInterval || 30000,
  };

  switch (type) {
    case 'metric':
      return {
        ...baseConfig,
        config: {
          metricId: options.metricId,
          showTrend: options.showTrend ?? true,
          showSparkline: options.showSparkline ?? false,
          format: options.format || 'number',
          ...options.config,
        },
      };

    case 'chart':
      return {
        ...baseConfig,
        config: {
          chartType: options.chartType || 'line',
          metricIds: options.metricIds || [],
          timeRange: options.timeRange || { start: '-24h', end: 'now' },
          aggregation: options.aggregation || 'average',
          showLegend: options.showLegend ?? true,
          ...options.config,
        },
      };

    case 'graph':
      return {
        ...baseConfig,
        config: {
          nodeTypes: options.nodeTypes || [],
          edgeTypes: options.edgeTypes || [],
          layout: options.layout || 'force',
          nodeSize: options.nodeSize || 'degree',
          colorBy: options.colorBy || 'type',
          showLabels: options.showLabels ?? true,
          ...options.config,
        },
      };

    case 'table':
      return {
        ...baseConfig,
        config: {
          columns: options.columns || [],
          data: options.data || [],
          pagination: options.pagination ?? true,
          pageSize: options.pageSize || 10,
          sortable: options.sortable ?? true,
          filterable: options.filterable ?? true,
          ...options.config,
        },
      };

    default:
      return baseConfig;
  }
};

export const validateWidgetConfig = (config: any): { isValid: boolean; errors: string[] } => {
  const errors: string[] = [];

  if (!config.type) {
    errors.push('Widget type is required');
  }

  if (!config.title) {
    errors.push('Widget title is required');
  }

  if (!config.position) {
    errors.push('Widget position is required');
  } else {
    if (typeof config.position.x !== 'number' || config.position.x < 0) {
      errors.push('Invalid X position');
    }
    if (typeof config.position.y !== 'number' || config.position.y < 0) {
      errors.push('Invalid Y position');
    }
    if (typeof config.position.width !== 'number' || config.position.width <= 0) {
      errors.push('Invalid width');
    }
    if (typeof config.position.height !== 'number' || config.position.height <= 0) {
      errors.push('Invalid height');
    }
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
};

export const generateRandomId = (prefix: string = 'analytics'): string => {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
};

export const debounceAsync = <T extends (...args: any[]) => Promise<any>>(
  func: T,
  wait: number
): (...args: Parameters<T>) => Promise<ReturnType<T>> => {
  let timeout: NodeJS.Timeout;
  let lastResolve: ((value: any) => void) | null = null;
  let lastReject: ((reason: any) => void) | null = null;

  return (...args: Parameters<T>) => {
    return new Promise<ReturnType<T>>((resolve, reject) => {
      // Cancel previous request
      if (timeout) {
        clearTimeout(timeout);
        if (lastReject) {
          lastReject(new Error('Debounced'));
        }
      }

      lastResolve = resolve;
      lastReject = reject;

      timeout = setTimeout(async () => {
        try {
          const result = await func(...args);
          if (lastResolve) {
            lastResolve(result);
          }
        } catch (error) {
          if (lastReject) {
            lastReject(error);
          }
        }
      }, wait);
    });
  };
};

export const throttleAsync = <T extends (...args: any[]) => Promise<any>>(
  func: T,
  wait: number
): (...args: Parameters<T>) => Promise<ReturnType<T>> => {
  let lastCall = 0;
  let pendingPromise: Promise<ReturnType<T>> | null = null;

  return (...args: Parameters<T>) => {
    const now = Date.now();

    if (now - lastCall >= wait) {
      lastCall = now;
      pendingPromise = func(...args);
      return pendingPromise;
    }

    return pendingPromise || Promise.resolve(null as any);
  };
};

export const createPerformanceMonitor = () => {
  const metrics = new Map<string, number[]>();

  const record = (name: string, duration: number) => {
    if (!metrics.has(name)) {
      metrics.set(name, []);
    }
    metrics.get(name)!.push(duration);

    // Keep only last 100 measurements
    const measurements = metrics.get(name)!;
    if (measurements.length > 100) {
      measurements.shift();
    }
  };

  const getStats = (name: string) => {
    const measurements = metrics.get(name) || [];
    if (measurements.length === 0) {
      return { count: 0, min: 0, max: 0, avg: 0, p95: 0 };
    }

    const sorted = [...measurements].sort((a, b) => a - b);
    const count = measurements.length;
    const min = sorted[0];
    const max = sorted[count - 1];
    const avg = measurements.reduce((sum, val) => sum + val, 0) / count;
    const p95Index = Math.floor(count * 0.95);
    const p95 = sorted[p95Index];

    return { count, min, max, avg, p95 };
  };

  const getAllStats = () => {
    const allStats: Record<string, any> = {};
    for (const name of metrics.keys()) {
      allStats[name] = getStats(name);
    }
    return allStats;
  };

  const clear = (name?: string) => {
    if (name) {
      metrics.delete(name);
    } else {
      metrics.clear();
    }
  };

  return {
    record,
    getStats,
    getAllStats,
    clear,
  };
};

export const createErrorHandler = (defaultMessage: string = 'An error occurred') => {
  return (error: any, context?: string) => {
    console.error(`Analytics Error${context ? ` in ${context}` : ''}:`, error);

    // Log to external service if available
    if (typeof window !== 'undefined' && (window as any).analytics?.logError) {
      (window as any).analytics.logError(error, context);
    }

    // Return user-friendly message
    if (error?.response?.data?.message) {
      return error.response.data.message;
    }
    if (error?.message) {
      return error.message;
    }
    return defaultMessage;
  };
};

export const createLocalStorage = <T>(key: string, defaultValue: T) => {
  const getValue = (): T => {
    if (typeof window === 'undefined') return defaultValue;

    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : defaultValue;
    } catch (error) {
      console.error(`Error reading localStorage key "${key}":`, error);
      return defaultValue;
    }
  };

  const setValue = (value: T) => {
    if (typeof window === 'undefined') return;

    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.error(`Error setting localStorage key "${key}":`, error);
    }
  };

  const removeValue = () => {
    if (typeof window === 'undefined') return;

    try {
      window.localStorage.removeItem(key);
    } catch (error) {
      console.error(`Error removing localStorage key "${key}":`, error);
    }
  };

  return {
    get: getValue,
    set: setValue,
    remove: removeValue,
  };
};

export const detectDevice = () => {
  if (typeof window === 'undefined') {
    return { isMobile: false, isTablet: false, isDesktop: true };
  }

  const width = window.innerWidth;
  const isMobile = width < 768;
  const isTablet = width >= 768 && width < 1024;
  const isDesktop = width >= 1024;

  return {
    isMobile,
    isTablet,
    isDesktop,
    width,
    height: window.innerHeight,
  };
};

export const createResponsiveConfig = () => {
  const device = detectDevice();

  const gridColumns = device.isMobile ? 12 : device.isTablet ? 16 : 24;
  const defaultWidgetSize = device.isMobile
    ? { width: 12, height: 3 }
    : device.isTablet
      ? { width: 8, height: 4 }
      : { width: 6, height: 4 };

  const chartHeight = device.isMobile ? 200 : 300;
  const itemsPerPage = device.isMobile ? 5 : device.isTablet ? 10 : 20;

  return {
    device,
    gridColumns,
    defaultWidgetSize,
    chartHeight,
    itemsPerPage,
  };
};