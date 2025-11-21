import { Page } from '@playwright/test';

/**
 * Performance Monitor for E2E Testing
 *
 * Provides comprehensive performance monitoring capabilities:
 * - Page performance metrics
 * - Network request monitoring
 * - Memory usage tracking
 * - Custom measurement capabilities
 * - Performance threshold validation
 */

export interface PerformanceMetrics {
  duration: number;
  startTime: number;
  endTime: number;
  memoryUsage?: {
    usedJSHeapSize: number;
    totalJSHeapSize: number;
    jsHeapSizeLimit: number;
  };
  networkMetrics?: {
    totalRequests: number;
    totalBytesTransferred: number;
    averageResponseTime: number;
    failedRequests: number;
  };
  customMetrics?: Record<string, number>;
}

export interface MeasurementSession {
  id: string;
  name: string;
  startTime: number;
  endTime?: number;
  metrics: PerformanceMetrics;
  thresholds?: Record<string, number>;
}

export interface NetworkRequest {
  url: string;
  method: string;
  status: number;
  responseTime: number;
  size: number;
  timestamp: number;
  success: boolean;
}

export class PerformanceMonitor {
  private page: Page;
  private activeMeasurements: Map<string, MeasurementSession> = new Map();
  private networkRequests: NetworkRequest[] = [];
  private performanceEntries: any[] = [];
  private monitoringInterval?: NodeJS.Timeout;
  private isMonitoring = false;

  constructor(page: Page) {
    this.page = page;
    this.setupNetworkMonitoring();
    this.setupPerformanceMonitoring();
  }

  /**
   * Set up network request monitoring
   */
  private setupNetworkMonitoring(): void {
    // Intercept all network requests
    this.page.on('request', (request) => {
      const startTime = Date.now();

      // Store start time for later calculation
      (request as any).__startTime = startTime;
    });

    this.page.on('response', (response) => {
      const request = response.request();
      const startTime = (request as any).__startTime || Date.now();
      const responseTime = Date.now() - startTime;

      const networkRequest: NetworkRequest = {
        url: request.url(),
        method: request.method(),
        status: response.status(),
        responseTime,
        size: parseInt(response.headers()['content-length'] || '0'),
        timestamp: startTime,
        success: response.ok()
      };

      this.networkRequests.push(networkRequest);

      // Keep only last 1000 requests to prevent memory issues
      if (this.networkRequests.length > 1000) {
        this.networkRequests = this.networkRequests.slice(-1000);
      }
    });
  }

  /**
   * Set up performance monitoring
   */
  private setupPerformanceMonitoring(): void {
    // Monitor performance entries
    this.page.on('console', (msg) => {
      const text = msg.text();
      if (text.includes('performance:') || text.includes('metric:')) {
        // Parse custom performance messages
        try {
          const match = text.match(/(\w+):\s*(\d+(?:\.\d+)?)/);
          if (match) {
            const [, metric, value] = match;
            this.addCustomMetric(metric, parseFloat(value));
          }
        } catch (error) {
          // Ignore parsing errors
        }
      }
    });
  }

  /**
   * Start performance monitoring
   */
  async start(): Promise<void> {
    if (this.isMonitoring) {
      return;
    }

    this.isMonitoring = true;
    this.networkRequests = [];
    this.performanceEntries = [];

    // Start collecting performance entries
    await this.page.evaluate(() => {
      // Clear existing performance entries
      performance.clearResourceTimings();

      // Start observing performance entries
      if ('PerformanceObserver' in window) {
        const observer = new PerformanceObserver((list) => {
          const entries = list.getEntries();
          entries.forEach((entry) => {
            // Send entries to test context
            window.dispatchEvent(new CustomEvent('performance-entry', {
              detail: entry
            }));
          });
        });

        observer.observe({ entryTypes: ['navigation', 'resource', 'measure', 'paint'] });
      }
    });

    // Listen for performance entries
    this.page.on('console', (msg) => {
      // Handle performance entry events
    });

    // Start interval monitoring
    this.monitoringInterval = setInterval(async () => {
      await this.collectPerformanceData();
    }, 1000);
  }

  /**
   * Stop performance monitoring
   */
  async stop(): Promise<void> {
    if (!this.isMonitoring) {
      return;
    }

    this.isMonitoring = false;

    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
    }

    // Collect final performance data
    await this.collectPerformanceData();
  }

  /**
   * Collect performance data from the page
   */
  private async collectPerformanceData(): Promise<void> {
    try {
      const entries = await this.page.evaluate(() => {
        if ('performance' in window) {
          return performance.getEntries();
        }
        return [];
      });

      this.performanceEntries.push(...entries);

      // Keep only last 1000 entries
      if (this.performanceEntries.length > 1000) {
        this.performanceEntries = this.performanceEntries.slice(-1000);
      }
    } catch (error) {
      console.warn('Could not collect performance data:', error);
    }
  }

  /**
   * Start a custom measurement
   */
  async startMeasurement(name: string, thresholds?: Record<string, number>): Promise<string> {
    const id = `measurement_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const startTime = Date.now();

    // Create performance mark in the page
    await this.page.evaluate((measurementId) => {
      performance.mark(`${measurementId}-start`);
    }, id);

    const session: MeasurementSession = {
      id,
      name,
      startTime,
      metrics: {
        duration: 0,
        startTime,
        endTime: startTime,
        customMetrics: {}
      },
      thresholds
    };

    this.activeMeasurements.set(id, session);

    return id;
  }

  /**
   * Stop a measurement and return metrics
   */
  async stopMeasurement(measurementId: string): Promise<PerformanceMetrics> {
    const session = this.activeMeasurements.get(measurementId);
    if (!session) {
      throw new Error(`Measurement ${measurementId} not found`);
    }

    const endTime = Date.now();
    const duration = endTime - session.startTime;

    // Create performance mark and measure in the page
    await this.page.evaluate((id) => {
      performance.mark(`${id}-end`);
      performance.measure(id, `${id}-start`, `${id}-end`);
    }, measurementId);

    // Get memory usage
    const memoryUsage = await this.getMemoryUsage();

    // Get network metrics for this measurement period
    const networkMetrics = this.getNetworkMetricsForPeriod(session.startTime, endTime);

    const metrics: PerformanceMetrics = {
      duration,
      startTime: session.startTime,
      endTime,
      memoryUsage,
      networkMetrics,
      customMetrics: session.metrics.customMetrics
    };

    session.endTime = endTime;
    session.metrics = metrics;

    // Remove from active measurements
    this.activeMeasurements.delete(measurementId);

    return metrics;
  }

  /**
   * Get current memory usage
   */
  async getMemoryUsage(): Promise<{
    usedJSHeapSize: number;
    totalJSHeapSize: number;
    jsHeapSizeLimit: number;
  } | null> {
    try {
      return await this.page.evaluate(() => {
        if ('memory' in performance) {
          const memory = (performance as any).memory;
          return {
            usedJSHeapSize: memory.usedJSHeapSize,
            totalJSHeapSize: memory.totalJSHeapSize,
            jsHeapSizeLimit: memory.jsHeapSizeLimit
          };
        }
        return null;
      });
    } catch (error) {
      return null;
    }
  }

  /**
   * Get network metrics for a specific time period
   */
  private getNetworkMetricsForPeriod(startTime: number, endTime: number): {
    totalRequests: number;
    totalBytesTransferred: number;
    averageResponseTime: number;
    failedRequests: number;
  } {
    const periodRequests = this.networkRequests.filter(
      request => request.timestamp >= startTime && request.timestamp <= endTime
    );

    const successfulRequests = periodRequests.filter(req => req.success);
    const failedRequests = periodRequests.filter(req => !req.success);

    return {
      totalRequests: periodRequests.length,
      totalBytesTransferred: periodRequests.reduce((sum, req) => sum + req.size, 0),
      averageResponseTime: successfulRequests.length > 0
        ? successfulRequests.reduce((sum, req) => sum + req.responseTime, 0) / successfulRequests.length
        : 0,
      failedRequests: failedRequests.length
    };
  }

  /**
   * Add custom metric
   */
  addCustomMetric(name: string, value: number): void {
    // Add to current active measurements
    for (const session of this.activeMeasurements.values()) {
      if (!session.metrics.customMetrics) {
        session.metrics.customMetrics = {};
      }
      session.metrics.customMetrics[name] = value;
    }
  }

  /**
   * Get specific performance metric
   */
  async getMetric(metricName: string): Promise<number> {
    try {
      switch (metricName) {
        case 'firstContentfulPaint':
          return await this.getFirstContentfulPaint();
        case 'largestContentfulPaint':
          return await this.getLargestContentfulPaint();
        case 'cumulativeLayoutShift':
          return await this.getCumulativeLayoutShift();
        case 'firstInputDelay':
          return await this.getFirstInputDelay();
        case 'timeToInteractive':
          return await this.getTimeToInteractive();
        default:
          return await this.getCustomMetric(metricName);
      }
    } catch (error) {
      console.warn(`Could not get metric ${metricName}:`, error);
      return 0;
    }
  }

  /**
   * Get First Contentful Paint time
   */
  private async getFirstContentfulPaint(): Promise<number> {
    return await this.page.evaluate(() => {
      const entries = performance.getEntriesByName('first-contentful-paint', 'paint');
      return entries.length > 0 ? Math.round(entries[0].startTime) : 0;
    });
  }

  /**
   * Get Largest Contentful Paint time
   */
  private async getLargestContentfulPaint(): Promise<number> {
    return await this.page.evaluate(() => {
      return new Promise((resolve) => {
        if (!('PerformanceObserver' in window)) {
          resolve(0);
          return;
        }

        const observer = new PerformanceObserver((list) => {
          const entries = list.getEntries();
          const lastEntry = entries[entries.length - 1];
          resolve(Math.round(lastEntry.startTime));
        });

        observer.observe({ entryTypes: ['largest-contentful-paint'] });

        // Fallback timeout
        setTimeout(() => resolve(0), 5000);
      });
    });
  }

  /**
   * Get Cumulative Layout Shift
   */
  private async getCumulativeLayoutShift(): Promise<number> {
    return await this.page.evaluate(() => {
      return new Promise((resolve) => {
        if (!('PerformanceObserver' in window)) {
          resolve(0);
          return;
        }

        let clsValue = 0;
        const observer = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (!(entry as any).hadRecentInput) {
              clsValue += (entry as any).value;
            }
          }
        });

        observer.observe({ entryTypes: ['layout-shift'] });

        setTimeout(() => {
          observer.disconnect();
          resolve(Math.round(clsValue * 1000) / 1000);
        }, 2000);
      });
    });
  }

  /**
   * Get First Input Delay
   */
  private async getFirstInputDelay(): Promise<number> {
    return await this.page.evaluate(() => {
      return new Promise((resolve) => {
        if (!('PerformanceObserver' in window)) {
          resolve(0);
          return;
        }

        const observer = new PerformanceObserver((list) => {
          const entries = list.getEntries();
          if (entries.length > 0) {
            const firstEntry = entries[0];
            resolve(Math.round((firstEntry as any).processingStart - firstEntry.startTime));
            observer.disconnect();
          }
        });

        observer.observe({ entryTypes: ['first-input'] });

        // Fallback timeout
        setTimeout(() => {
          resolve(0);
        }, 5000);
      });
    });
  }

  /**
   * Get Time to Interactive
   */
  private async getTimeToInteractive(): Promise<number> {
    return await this.page.evaluate(() => {
      // Simplified TTI calculation
      const entries = performance.getEntriesByType('navigation');
      if (entries.length > 0) {
        const navEntry = entries[0] as PerformanceNavigationTiming;
        return Math.round(
          navEntry.loadEventEnd - navEntry.fetchStart
        );
      }
      return 0;
    });
  }

  /**
   * Get custom metric
   */
  private async getCustomMetric(metricName: string): Promise<number> {
    return await this.page.evaluate((name) => {
      // Look for custom marks/measures
      const entries = performance.getEntriesByName(name, 'measure');
      if (entries.length > 0) {
        return Math.round(entries[entries.length - 1].duration);
      }

      // Check for custom properties
      if ((window as any)[`customMetric_${name}`]) {
        return (window as any)[`customMetric_${name}`];
      }

      return 0;
    }, metricName);
  }

  /**
   * Check performance against thresholds
   */
  validateThresholds(metrics: PerformanceMetrics, thresholds: Record<string, number>): {
    passed: boolean;
    violations: Array<{ metric: string; actual: number; threshold: number; passed: boolean }>;
  } {
    const violations = [];
    let passed = true;

    for (const [metric, threshold] of Object.entries(thresholds)) {
      let actual = 0;

      switch (metric) {
        case 'duration':
          actual = metrics.duration;
          break;
        case 'memoryUsage':
          actual = metrics.memoryUsage?.usedJSHeapSize || 0;
          break;
        case 'averageResponseTime':
          actual = metrics.networkMetrics?.averageResponseTime || 0;
          break;
        case 'failedRequests':
          actual = metrics.networkMetrics?.failedRequests || 0;
          break;
        default:
          actual = metrics.customMetrics?.[metric] || 0;
      }

      const metricPassed = actual <= threshold;
      if (!metricPassed) {
        passed = false;
      }

      violations.push({
        metric,
        actual,
        threshold,
        passed: metricPassed
      });
    }

    return { passed, violations };
  }

  /**
   * Get performance report
   */
  getPerformanceReport(): {
    summary: {
      totalRequests: number;
      averageResponseTime: number;
      failedRequests: number;
      totalBytesTransferred: number;
    };
    metrics: PerformanceMetrics[];
    thresholds: Record<string, number>[];
  } {
    const summary = {
      totalRequests: this.networkRequests.length,
      averageResponseTime: this.networkRequests.length > 0
        ? this.networkRequests.reduce((sum, req) => sum + req.responseTime, 0) / this.networkRequests.length
        : 0,
      failedRequests: this.networkRequests.filter(req => !req.success).length,
      totalBytesTransferred: this.networkRequests.reduce((sum, req) => sum + req.size, 0)
    };

    return {
      summary,
      metrics: Array.from(this.activeMeasurements.values()).map(session => session.metrics),
      thresholds: Array.from(this.activeMeasurements.values())
        .filter(session => session.thresholds)
        .map(session => session.thresholds!)
    };
  }

  /**
   * Clear performance data
   */
  clearData(): void {
    this.networkRequests = [];
    this.performanceEntries = [];
    this.activeMeasurements.clear();
  }

  /**
   * Get network request details
   */
  getNetworkRequests(): NetworkRequest[] {
    return [...this.networkRequests];
  }

  /**
   * Get performance entries
   */
  getPerformanceEntries(): any[] {
    return [...this.performanceEntries];
  }
}