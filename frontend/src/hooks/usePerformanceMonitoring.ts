/**
 * React hooks for performance monitoring
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import { performanceMonitor } from '@/utils/performanceMonitoring';
import { errorTracker } from '@/utils/errorTracking';
import { loggingService } from '@/services/loggingService';

// Hook for measuring component render performance
export const useRenderPerformance = (componentName: string) => {
  const renderCount = useRef(0);
  const renderStartTime = useRef<number>(0);

  useEffect(() => {
    // Set start time on mount to avoid SSR crash (performance is undefined in Node)
    renderStartTime.current = typeof performance !== 'undefined' ? performance.now() : Date.now();
  }, []);

  useEffect(() => {
    // Measure render time
    const renderEndTime = typeof performance !== 'undefined' ? performance.now() : Date.now();
    const renderDuration = renderEndTime - renderStartTime.current;

    renderCount.current++;

    // Track render performance with actual duration
    performanceMonitor.recordMetric(
      `component_render_time_${componentName}`,
      renderDuration,
      'ms',
      { component: componentName }
    );

    // Track render count
    performanceMonitor.recordMetric(
      `component_render_count_${componentName}`,
      renderCount.current,
      'count',
      { component: componentName }
    );

    // Warn about slow renders
    if (renderDuration > 16) {
      loggingService.warn(`Component ${componentName} took ${renderDuration.toFixed(2)}ms to render (exceeds 16ms budget)`, {
        component: componentName,
        renderDuration
      });
    }

    // Warn about excessive re-renders
    if (renderCount.current > 50) {
      loggingService.warn(`Component ${componentName} has rendered ${renderCount.current} times`, {
        component: componentName,
        renderCount: renderCount.current
      });
    }

    // Reset start time for next render
    renderStartTime.current = performance.now();
  });
};

// Hook for measuring async operations
export const useAsyncPerformance = () => {
  const measureAsync = useCallback(<T,>(
    name: string,
    fn: () => Promise<T>,
    context?: Record<string, any>
  ) => {
    return performanceMonitor.measureAsync(name, fn, context);
  }, []);

  return { measureAsync };
};

// Hook for tracking user interactions
export const useInteractionTracking = (componentName: string) => {
  const trackInteraction = useCallback((
    action: string,
    element?: string,
    metadata?: Record<string, any>
  ) => {
    loggingService.logUserAction(action, metadata, element, undefined);

    performanceMonitor.recordMetric(
      `user_interaction_${action}`,
      1,
      'count',
      { component: componentName, element, ...metadata }
    );
  }, [componentName]);

  return { trackInteraction };
};

// Hook for API performance monitoring
export const useApiPerformance = () => {
  const trackApiCall = useCallback(async <T,>(
    method: string,
    url: string,
    apiCall: () => Promise<T>
  ): Promise<T> => {
    const requestId = loggingService.logApiRequest(method, url);

    try {
      const result = await performanceMonitor.trackApiCall(method, url, apiCall);

      loggingService.logApiResponse(
        requestId,
        method,
        url,
        200,
        0 // This would be calculated by the trackApiCall method
      );

      return result;
    } catch (error) {
      loggingService.logApiError(requestId, method, url, error as Error);
      throw error;
    }
  }, []);

  return { trackApiCall };
};

// Hook for search performance monitoring
export const useSearchPerformance = () => {
  const trackSearch = useCallback(async <T,>(
    query: string,
    searchFn: () => Promise<T>
  ): Promise<T> => {
    const startTime = Date.now();

    try {
      const result = await performanceMonitor.trackSearchPerformance(query, searchFn);

      const duration = Date.now() - startTime;
      loggingService.logSearchQuery(query, 0, duration); // resultsCount would be determined by the search function

      return result;
    } catch (error) {
      const duration = Date.now() - startTime;
      loggingService.error(`Search query failed: ${query}`, error as Error);

      performanceMonitor.recordMetric('search_error', duration, 'ms', {
        query,
        error: (error as Error).message
      });

      throw error;
    }
  }, []);

  return { trackSearch };
};

// Hook for performance metrics dashboard
export const usePerformanceMetrics = (updateInterval: number = 5000) => {
  const [metrics, setMetrics] = useState(() => performanceMonitor.getPerformanceReport());
  const [score, setScore] = useState(() => performanceMonitor.getPerformanceScore());

  useEffect(() => {
    const interval = setInterval(() => {
      setMetrics(performanceMonitor.getPerformanceReport());
      setScore(performanceMonitor.getPerformanceScore());
    }, updateInterval);

    return () => clearInterval(interval);
  }, [updateInterval]);

  return { metrics, score };
};

// Hook for memory monitoring
export const useMemoryMonitoring = (interval: number = 10000) => {
  const [memoryStats, setMemoryStats] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    const trackMemory = () => {
      performanceMonitor.trackMemoryUsage();

      if ('memory' in performance) {
        const memory = (performance as any).memory;
        setMemoryStats({
          used: memory.usedJSHeapSize,
          total: memory.totalJSHeapSize,
          limit: memory.jsHeapSizeLimit,
          usage: (memory.usedJSHeapSize / memory.jsHeapSizeLimit) * 100
        });
      }
    };

    trackMemory();
    const intervalId = setInterval(trackMemory, interval);

    return () => clearInterval(intervalId);
  }, [interval]);

  return memoryStats;
};

// Hook for connection quality monitoring
export const useConnectionMonitoring = () => {
  const [connectionInfo, setConnectionInfo] = useState<Record<string, any> | null>(null);

  useEffect(() => {
    const updateConnectionInfo = () => {
      performanceMonitor.trackConnectionQuality();

      if ('connection' in navigator) {
        const connection = (navigator as any).connection;
        setConnectionInfo({
          effectiveType: connection.effectiveType,
          downlink: connection.downlink,
          rtt: connection.rtt,
          saveData: connection.saveData
        });
      }
    };

    updateConnectionInfo();

    if ('connection' in navigator) {
      const connection = (navigator as any).connection;
      connection.addEventListener('change', updateConnectionInfo);

      return () => {
        connection.removeEventListener('change', updateConnectionInfo);
      };
    }

    return undefined;
  }, []);

  return connectionInfo;
};

// Hook for performance-based feature flags
export const usePerformanceBasedFeatures = () => {
  const [featureFlags, setFeatureFlags] = useState({
    animations: true,
    heavyFeatures: true,
    highQualityImages: true,
    realTimeUpdates: true
  });

  useEffect(() => {
    const updateFeatureFlags = () => {
      const score = performanceMonitor.getPerformanceScore();
      const webVitals = performanceMonitor.getWebVitals();
      const connectionInfo = (navigator as any).connection;

      // Disable animations on low-end devices or slow connections
      const animations = score > 70 &&
                        (!webVitals.INP || webVitals.INP < 200) &&
                        (!connectionInfo || connectionInfo.effectiveType !== 'slow-2g' && connectionInfo.effectiveType !== '2g');

      // Disable heavy features on very low performance
      const heavyFeatures = score > 50;

      // Use lower quality images on slow connections
      const highQualityImages = !connectionInfo ||
                              connectionInfo.effectiveType !== 'slow-2g' &&
                              connectionInfo.effectiveType !== '2g' &&
                              (!connectionInfo.downlink || connectionInfo.downlink > 1);

      // Disable real-time updates on slow connections
      const realTimeUpdates = !connectionInfo ||
                             connectionInfo.effectiveType !== 'slow-2g' &&
                             connectionInfo.effectiveType !== '2g';

      setFeatureFlags({
        animations,
        heavyFeatures,
        highQualityImages,
        realTimeUpdates
      });
    };

    updateFeatureFlags();

    const intervalId = setInterval(updateFeatureFlags, 30000); // Update every 30 seconds

    return () => clearInterval(intervalId);
  }, []);

  return featureFlags;
};

// Hook for performance budget monitoring
export const usePerformanceBudget = (budgets: Record<string, number>) => {
  const [budgetViolations, setBudgetViolations] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const checkBudgets = () => {
      const metrics = performanceMonitor.getPerformanceReport();
      const violations: Record<string, boolean> = {};

      Object.entries(budgets).forEach(([metric, limit]) => {
        const metricData = metrics.metrics.byName[metric];
        if (metricData && metricData.avg > limit) {
          violations[metric] = true;

          loggingService.warn(`Performance budget exceeded for ${metric}`, {
            metric,
            limit,
            actual: metricData.avg,
            avg: metricData.avg
          });
        }
      });

      setBudgetViolations(violations);
    };

    checkBudgets();
    const intervalId = setInterval(checkBudgets, 10000);

    return () => clearInterval(intervalId);
  }, [budgets]);

  return budgetViolations;
};

// Hook for performance profiling
export const usePerformanceProfiler = (componentName: string) => {
  const profileStart = useRef<number | null>(null);
  const [isProfiling, setIsProfiling] = useState(false);

  const startProfiling = useCallback(() => {
    profileStart.current = performance.now();
    setIsProfiling(true);

    loggingService.info(`Performance profiling started for ${componentName}`, {
      component: componentName,
      action: 'profiling_start'
    });
  }, [componentName]);

  const stopProfiling = useCallback(() => {
    if (profileStart.current === null) return;

    const duration = performance.now() - profileStart.current;
    profileStart.current = null;
    setIsProfiling(false);

    performanceMonitor.recordMetric(`profile_${componentName}`, duration, 'ms', {
      component: componentName,
      type: 'profile'
    });

    loggingService.info(`Performance profiling stopped for ${componentName}`, {
      component: componentName,
      action: 'profiling_stop',
      data: { duration }
    });

    return duration;
  }, [componentName]);

  const profileFunction = useCallback(<T,>(
    fn: () => T,
    name?: string
  ): T => {
    const profileName = name || `${componentName}_${Date.now()}`;
    return performanceMonitor.measure(profileName, fn, {
      component: componentName,
      type: 'profile'
    });
  }, [componentName]);

  return {
    startProfiling,
    stopProfiling,
    profileFunction,
    isProfiling
  };
};

// Hook for lazy loading performance
export const useLazyLoadingPerformance = () => {
  const trackLazyLoad = useCallback((
    componentName: string,
    loadFn: () => Promise<any>
  ) => {
    const startTime = performance.now();

    return performanceMonitor.measureAsync(
      `lazy_load_${componentName}`,
      loadFn,
      { component: componentName, type: 'lazy_load' }
    ).then(
      result => {
        const duration = performance.now() - startTime;
        loggingService.info(`Component ${componentName} loaded successfully`, {
          component: componentName,
          action: 'lazy_load_success',
          data: { duration }
        });
        return result;
      },
      error => {
        const duration = performance.now() - startTime;
        loggingService.error(`Failed to load component ${componentName}`, error as Error, {
          component: componentName,
          action: 'lazy_load_error',
          data: { duration }
        });
        throw error;
      }
    );
  }, []);

  return { trackLazyLoad };
};

// Hook for performance health monitoring
export const usePerformanceHealth = () => {
  const [health, setHealth] = useState(() => performanceMonitor.healthCheck());

  useEffect(() => {
    const updateHealth = () => {
      const currentHealth = performanceMonitor.healthCheck();
      setHealth(currentHealth);

      // Log health issues
      if (currentHealth.performanceScore < 50) {
        loggingService.warn('Performance health score is low', {
          score: currentHealth.performanceScore,
          health: currentHealth
        });
      }

      // Check for memory issues
      if ('memory' in performance) {
        const memory = (performance as any).memory;
        const usagePercent = (memory.usedJSHeapSize / memory.jsHeapSizeLimit) * 100;

        if (usagePercent > 80) {
          loggingService.warn('High memory usage detected', {
            usage: usagePercent,
            used: memory.usedJSHeapSize,
            limit: memory.jsHeapSizeLimit
          });
        }
      }
    };

    updateHealth();
    const intervalId = setInterval(updateHealth, 15000); // Check every 15 seconds

    return () => clearInterval(intervalId);
  }, []);

  return health;
};