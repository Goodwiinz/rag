/**
 * Performance Monitoring and Analytics Utility
 * Tracks application performance, user interactions, and business metrics
 */

import { errorTracker } from './errorTracking';
import { loggingService } from '@/services/loggingService';

interface PerformanceMetric {
  name: string;
  value: number;
  unit: string;
  timestamp: number;
  context?: Record<string, any>;
  tags?: string[];
}

interface WebVitals {
  LCP?: number; // Largest Contentful Paint
  FID?: number; // First Input Delay
  CLS?: number; // Cumulative Layout Shift
  FCP?: number; // First Contentful Paint
  TTFB?: number; // Time to First Byte
  INP?: number; // Interaction to Next Paint
}

interface UserInteraction {
  type: string;
  element: string;
  timestamp: number;
  duration?: number;
  metadata?: Record<string, any>;
}

interface PageLoadMetrics {
  navigationStart: number;
  domContentLoaded: number;
  loadComplete: number;
  domInteractive: number;
  firstContentfulPaint?: number;
  largestContentfulPaint?: number;
}

interface ResourceTiming {
  name: string;
  type: string;
  duration: number;
  size: number;
  cached: boolean;
}

class PerformanceMonitor {
  private static instance: PerformanceMonitor;
  private metrics: PerformanceMetric[] = [];
  private interactions: UserInteraction[] = [];
  private resources: ResourceTiming[] = [];
  private webVitals: WebVitals = {};
  private pageLoadMetrics: PageLoadMetrics | null = null;
  private isEnabled = true;
  private maxMetrics = 1000;
  private maxInteractions = 500;
  private observationStartTime = Date.now();

  private constructor() {
    this.initializeMonitoring();
  }

  static getInstance(): PerformanceMonitor {
    if (!PerformanceMonitor.instance) {
      PerformanceMonitor.instance = new PerformanceMonitor();
    }
    return PerformanceMonitor.instance;
  }

  private initializeMonitoring() {
    // Wait for page to load
    if (document.readyState === 'complete') {
      this.startMonitoring();
    } else {
      window.addEventListener('load', () => {
        setTimeout(() => this.startMonitoring(), 0);
      });
    }
  }

  private startMonitoring() {
    this.collectPageLoadMetrics();
    this.observeWebVitals();
    this.observeResources();
    this.observeLongTasks();
    this.observeInteractions();
    this.schedulePeriodicReports();
  }

  private collectPageLoadMetrics() {
    if (!performance.timing) return;

    const timing = performance.timing;
    this.pageLoadMetrics = {
      navigationStart: timing.navigationStart,
      domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
      loadComplete: timing.loadEventEnd - timing.navigationStart,
      domInteractive: timing.domInteractive - timing.navigationStart
    };

    // Log page load metrics
    this.recordMetric('page_load_time', this.pageLoadMetrics.loadComplete, 'ms', {
      event: 'page_load_complete'
    });

    this.recordMetric('dom_content_loaded', this.pageLoadMetrics.domContentLoaded, 'ms', {
      event: 'dom_content_loaded'
    });

    this.recordMetric('dom_interactive', this.pageLoadMetrics.domInteractive, 'ms', {
      event: 'dom_interactive'
    });

    loggingService.logPerformance('page_load', this.pageLoadMetrics.loadComplete, {
      domContentLoaded: this.pageLoadMetrics.domContentLoaded,
      domInteractive: this.pageLoadMetrics.domInteractive
    });
  }

  private observeWebVitals() {
    // FCP - First Contentful Paint
    this.observePaintTiming('first-contentful-paint', (value) => {
      this.webVitals.FCP = value;
      this.recordMetric('first_contentful_paint', value, 'ms', { vitals: true });
    });

    // LCP - Largest Contentful Paint
    if ('PerformanceObserver' in window) {
      try {
        const lcpObserver = new PerformanceObserver((list) => {
          const entries = list.getEntries();
          const lastEntry = entries[entries.length - 1];
          if (lastEntry) {
            this.webVitals.LCP = lastEntry.startTime;
            this.recordMetric('largest_contentful_paint', lastEntry.startTime, 'ms', {
              vitals: true,
              element: (lastEntry as any).element?.tagName || 'unknown'
            });
          }
        });
        lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });
      } catch (e) {
        console.warn('LCP monitoring not supported:', e);
      }

      // FID - First Input Delay
      try {
        const fidObserver = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (entry.entryType === 'first-input') {
              this.webVitals.FID = (entry as any).processingStart - entry.startTime;
              this.recordMetric('first_input_delay', this.webVitals.FID, 'ms', {
                vitals: true,
                inputType: (entry as any).name
              });
            }
          }
        });
        fidObserver.observe({ entryTypes: ['first-input'] });
      } catch (e) {
        console.warn('FID monitoring not supported:', e);
      }

      // CLS - Cumulative Layout Shift
      try {
        let clsValue = 0;
        const clsObserver = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (!(entry as any).hadRecentInput) {
              clsValue += (entry as any).value;
              this.webVitals.CLS = clsValue;
              this.recordMetric('cumulative_layout_shift', clsValue, 'score', {
                vitals: true
              });
            }
          }
        });
        clsObserver.observe({ entryTypes: ['layout-shift'] });
      } catch (e) {
        console.warn('CLS monitoring not supported:', e);
      }

      // INP - Interaction to Next Paint
      try {
        const inpObserver = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (entry.entryType === 'event') {
              const inp = (entry as any).processingStart - entry.startTime;
              this.webVitals.INP = Math.max(this.webVitals.INP || 0, inp);
              this.recordMetric('interaction_to_next_paint', inp, 'ms', {
                vitals: true,
                interactionType: (entry as any).name
              });
            }
          }
        });
        inpObserver.observe({ entryTypes: ['event'] });
      } catch (e) {
        console.warn('INP monitoring not supported:', e);
      }
    }

    // TTFB - Time to First Byte
    if (performance.timing) {
      const ttfb = performance.timing.responseStart - performance.timing.navigationStart;
      this.webVitals.TTFB = ttfb;
      this.recordMetric('time_to_first_byte', ttfb, 'ms', { vitals: true });
    }
  }

  private observePaintTiming(name: string, callback: (value: number) => void) {
    if ('PerformanceObserver' in window) {
      try {
        const observer = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (entry.name === name) {
              callback(entry.startTime);
              observer.disconnect();
            }
          }
        });
        observer.observe({ entryTypes: ['paint'] });
      } catch (e) {
        console.warn(`${name} monitoring not supported:`, e);
      }
    }
  }

  private observeResources() {
    if ('PerformanceObserver' in window) {
      try {
        const resourceObserver = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (entry.entryType === 'resource') {
              const resource = entry as PerformanceResourceTiming;
              const resourceInfo: ResourceTiming = {
                name: resource.name,
                type: this.getResourceType(resource.name),
                duration: resource.duration,
                size: resource.transferSize || 0,
                cached: resource.transferSize === 0 && resource.decodedBodySize > 0
              };

              this.resources.push(resourceInfo);
              this.trimResources();

              // Log slow resources
              if (resource.duration > 2000) {
                this.recordMetric('slow_resource', resource.duration, 'ms', {
                  resourceType: resourceInfo.type,
                  resourceName: resource.name,
                  cached: resourceInfo.cached
                });

                loggingService.warn('Slow resource detected', {
                  name: resource.name,
                  duration: resource.duration,
                  type: resourceInfo.type,
                  cached: resourceInfo.cached
                });
              }
            }
          }
        });
        resourceObserver.observe({ entryTypes: ['resource'] });
      } catch (e) {
        console.warn('Resource monitoring not supported:', e);
      }
    }
  }

  private getResourceType(url: string): string {
    if (url.includes('.css')) return 'stylesheet';
    if (url.includes('.js')) return 'script';
    if (url.match(/\.(jpg|jpeg|png|gif|webp|svg)$/i)) return 'image';
    if (url.match(/\.(woff|woff2|ttf|eot)$/i)) return 'font';
    if (url.includes('/api/')) return 'api';
    return 'other';
  }

  private observeLongTasks() {
    if ('PerformanceObserver' in window) {
      try {
        const longTaskObserver = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (entry.entryType === 'longtask') {
              this.recordMetric('long_task', entry.duration, 'ms', {
                startTime: entry.startTime
              });

              loggingService.warn('Long task detected', {
                duration: entry.duration,
                startTime: entry.startTime
              });
            }
          }
        });
        longTaskObserver.observe({ entryTypes: ['longtask'] });
      } catch (e) {
        console.warn('Long task monitoring not supported:', e);
      }
    }
  }

  private observeInteractions() {
    // Track clicks
    document.addEventListener('click', (event) => {
      const target = event.target as HTMLElement;
      this.recordInteraction('click', target.tagName.toLowerCase(), {
        id: target.id,
        className: target.className,
        textContent: target.textContent?.substring(0, 50)
      });
    }, { passive: true });

    // Track form submissions
    document.addEventListener('submit', (event) => {
      const target = event.target as HTMLFormElement;
      this.recordInteraction('form_submit', 'form', {
        id: target.id,
        action: target.action,
        method: target.method
      });
    });

    // Track input interactions
    document.addEventListener('input', (event) => {
      const target = event.target as HTMLInputElement;
      this.recordInteraction('input', target.tagName.toLowerCase(), {
        type: target.type,
        id: target.id,
        name: target.name
      });
    }, { passive: true });
  }

  private schedulePeriodicReports() {
    // Send performance data every 30 seconds
    setInterval(() => {
      this.flushMetrics();
    }, 30000);

    // Send session data when page is hidden
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        this.flushMetrics();
      }
    });

    // Send session data when page is unloaded
    window.addEventListener('beforeunload', () => {
      this.flushMetrics();
    });
  }

  private recordInteraction(type: string, element: string, metadata?: Record<string, any>) {
    const interaction: UserInteraction = {
      type,
      element,
      timestamp: Date.now(),
      metadata
    };

    this.interactions.push(interaction);
    this.trimInteractions();
  }

  private trimMetrics() {
    if (this.metrics.length > this.maxMetrics) {
      this.metrics = this.metrics.slice(-this.maxMetrics);
    }
  }

  private trimInteractions() {
    if (this.interactions.length > this.maxInteractions) {
      this.interactions = this.interactions.slice(-this.maxInteractions);
    }
  }

  private trimResources() {
    if (this.resources.length > this.maxMetrics) {
      this.resources = this.resources.slice(-this.maxMetrics);
    }
  }

  private async flushMetrics() {
    if (this.metrics.length === 0 && this.interactions.length === 0) return;

    try {
      const sessionData = {
        sessionId: errorTracker.getSessionId(),
        userId: errorTracker.getUserId(),
        duration: Date.now() - this.observationStartTime,
        metrics: this.metrics.slice(),
        interactions: this.interactions.slice(),
        webVitals: this.webVitals,
        pageLoadMetrics: this.pageLoadMetrics,
        timestamp: Date.now()
      };

      // Store in localStorage for debugging
      localStorage.setItem('performanceSession', JSON.stringify(sessionData));

      // In a real implementation, send to analytics service
      console.log('Performance data flushed:', sessionData);

      // Clear sent data
      this.metrics = [];
      this.interactions = [];

    } catch (error) {
      errorTracker.error('Failed to flush performance metrics', error as Error);
    }
  }

  // Public API methods
  recordMetric(name: string, value: number, unit: string, context?: Record<string, any>, tags?: string[]) {
    if (!this.isEnabled) return;

    const metric: PerformanceMetric = {
      name,
      value,
      unit,
      timestamp: Date.now(),
      context,
      tags
    };

    this.metrics.push(metric);
    this.trimMetrics();

    // Also track in error tracker
    errorTracker.trackMetric(name, value, unit, context);
  }

  // Measure execution time of functions
  measureAsync<T>(name: string, fn: () => Promise<T>, context?: Record<string, any>): Promise<T> {
    const startTime = performance.now();

    return fn().then(
      result => {
        const duration = performance.now() - startTime;
        this.recordMetric(name, duration, 'ms', { ...context, success: true });
        return result;
      },
      error => {
        const duration = performance.now() - startTime;
        this.recordMetric(`${name}_error`, duration, 'ms', { ...context, success: false, error: error.message });
        throw error;
      }
    );
  }

  // Measure synchronous functions
  measure<T>(name: string, fn: () => T, context?: Record<string, any>): T {
    const startTime = performance.now();
    try {
      const result = fn();
      const duration = performance.now() - startTime;
      this.recordMetric(name, duration, 'ms', { ...context, success: true });
      return result;
    } catch (error) {
      const duration = performance.now() - startTime;
      this.recordMetric(`${name}_error`, duration, 'ms', { ...context, success: false, error: (error as Error).message });
      throw error;
    }
  }

  // Timer for custom measurements
  startTimer(name: string, context?: Record<string, any>): () => void {
    const startTime = performance.now();

    return () => {
      const duration = performance.now() - startTime;
      this.recordMetric(name, duration, 'ms', context);
    };
  }

  // API performance tracking
  trackApiCall(method: string, url: string, fn: () => Promise<any>): Promise<any> {
    return this.measureAsync(`api_${method.toLowerCase()}`, fn, {
      method,
      url,
      type: 'api_call'
    });
  }

  // Component render performance
  trackComponentRender(componentName: string, renderFn: () => void): void {
    this.measure(`component_render_${componentName}`, renderFn, {
      component: componentName,
      type: 'component_render'
    });
  }

  // Search performance tracking
  trackSearchPerformance(query: string, searchFn: () => Promise<any>): Promise<any> {
    return this.measureAsync('search_query', searchFn, {
      query,
      type: 'search'
    });
  }

  // Document processing performance
  trackDocumentProcessing(fileName: string, processingFn: () => Promise<any>): Promise<any> {
    return this.measureAsync('document_processing', processingFn, {
      fileName,
      type: 'document_processing'
    });
  }

  // Memory usage tracking
  trackMemoryUsage() {
    if ('memory' in performance) {
      const memory = (performance as any).memory;

      this.recordMetric('memory_used', memory.usedJSHeapSize, 'bytes', {
        type: 'memory'
      });

      this.recordMetric('memory_total', memory.totalJSHeapSize, 'bytes', {
        type: 'memory'
      });

      this.recordMetric('memory_limit', memory.jsHeapSizeLimit, 'bytes', {
        type: 'memory'
      });
    }
  }

  // Connection quality tracking
  trackConnectionQuality() {
    if ('connection' in navigator) {
      const connection = (navigator as any).connection;

      this.recordMetric('connection_effective_type', this.getConnectionTypeValue(connection.effectiveType), 'type', {
        type: 'connection'
      });

      this.recordMetric('connection_downlink', connection.downlink, 'mbps', {
        type: 'connection'
      });

      this.recordMetric('connection_rtt', connection.rtt, 'ms', {
        type: 'connection'
      });
    }
  }

  private getConnectionTypeValue(type: string): number {
    const types: Record<string, number> = {
      'slow-2g': 0,
      '2g': 1,
      '3g': 2,
      '4g': 3
    };
    return types[type] || 0;
  }

  // Retrieval methods
  getMetrics(name?: string, limit?: number): PerformanceMetric[] {
    let filtered = this.metrics;

    if (name) {
      filtered = filtered.filter(metric => metric.name === name);
    }

    if (limit) {
      filtered = filtered.slice(-limit);
    }

    return filtered;
  }

  getInteractions(type?: string, limit?: number): UserInteraction[] {
    let filtered = this.interactions;

    if (type) {
      filtered = filtered.filter(interaction => interaction.type === type);
    }

    if (limit) {
      filtered = filtered.slice(-limit);
    }

    return filtered;
  }

  getResources(type?: string, limit?: number): ResourceTiming[] {
    let filtered = this.resources;

    if (type) {
      filtered = filtered.filter(resource => resource.type === type);
    }

    if (limit) {
      filtered = filtered.slice(-limit);
    }

    return filtered;
  }

  getWebVitals(): WebVitals {
    return { ...this.webVitals };
  }

  getPageLoadMetrics(): PageLoadMetrics | null {
    return this.pageLoadMetrics;
  }

  // Analytics methods
  getPerformanceReport() {
    const report = {
      session: {
        duration: Date.now() - this.observationStartTime,
        startTime: this.observationStartTime,
        userId: errorTracker.getUserId(),
        sessionId: errorTracker.getSessionId()
      },
      webVitals: this.webVitals,
      pageLoadMetrics: this.pageLoadMetrics,
      metrics: {
        total: this.metrics.length,
        byName: {} as Record<string, { count: number; avg: number; min: number; max: number }>,
        slowest: this.getSlowestMetrics(5),
        recent: this.metrics.slice(-10)
      },
      interactions: {
        total: this.interactions.length,
        byType: {} as Record<string, number>,
        recent: this.interactions.slice(-10)
      },
      resources: {
        total: this.resources.length,
        byType: {} as Record<string, number>,
        slowest: this.getSlowestResources(5),
        cached: this.resources.filter(r => r.cached).length
      }
    };

    // Aggregate metrics by name
    this.metrics.forEach(metric => {
      if (!report.metrics.byName[metric.name]) {
        report.metrics.byName[metric.name] = { count: 0, avg: 0, min: Infinity, max: -Infinity };
      }
      const stats = report.metrics.byName[metric.name]!;
      stats.count++;
      stats.avg = (stats.avg * (stats.count - 1) + metric.value) / stats.count;
      stats.min = Math.min(stats.min, metric.value);
      stats.max = Math.max(stats.max, metric.value);
    });

    // Aggregate interactions by type
    this.interactions.forEach(interaction => {
      report.interactions.byType[interaction.type] = (report.interactions.byType[interaction.type] || 0) + 1;
    });

    // Aggregate resources by type
    this.resources.forEach(resource => {
      report.resources.byType[resource.type] = (report.resources.byType[resource.type] || 0) + 1;
    });

    return report;
  }

  private getSlowestMetrics(count: number): PerformanceMetric[] {
    return this.metrics
      .filter(metric => metric.unit === 'ms')
      .sort((a, b) => b.value - a.value)
      .slice(0, count);
  }

  private getSlowestResources(count: number): ResourceTiming[] {
    return this.resources
      .sort((a, b) => b.duration - a.duration)
      .slice(0, count);
  }

  // Performance scoring
  getPerformanceScore(): number {
    let score = 100;

    // Web Vitals scoring
    if (this.webVitals.LCP && this.webVitals.LCP > 2500) score -= 20;
    if (this.webVitals.FID && this.webVitals.FID > 100) score -= 15;
    if (this.webVitals.CLS && this.webVitals.CLS > 0.1) score -= 15;
    if (this.webVitals.INP && this.webVitals.INP > 200) score -= 15;
    if (this.webVitals.TTFB && this.webVitals.TTFB > 600) score -= 10;

    // Page load scoring
    if (this.pageLoadMetrics && this.pageLoadMetrics.loadComplete > 3000) score -= 15;

    // Error rate scoring
    const errorRate = this.metrics.filter(m => m.name.includes('error')).length / Math.max(this.metrics.length, 1);
    score -= errorRate * 20;

    return Math.max(0, Math.round(score));
  }

  // Configuration methods
  setEnabled(enabled: boolean) {
    this.isEnabled = enabled;
  }

  isMonitoringEnabled(): boolean {
    return this.isEnabled;
  }

  // Export methods
  exportMetrics(): string {
    return JSON.stringify(this.getPerformanceReport(), null, 2);
  }

  // Health check
  healthCheck() {
    return {
      enabled: this.isEnabled,
      metricsCount: this.metrics.length,
      interactionsCount: this.interactions.length,
      resourcesCount: this.resources.length,
      observationStartTime: this.observationStartTime,
      sessionDuration: Date.now() - this.observationStartTime,
      performanceScore: this.getPerformanceScore(),
      webVitals: this.webVitals
    };
  }
}

// Export singleton instance
export const performanceMonitor = PerformanceMonitor.getInstance();

// Convenience exports
export const {
  recordMetric,
  measureAsync,
  measure,
  startTimer,
  trackApiCall,
  trackComponentRender,
  trackSearchPerformance,
  trackDocumentProcessing,
  trackMemoryUsage,
  trackConnectionQuality
} = performanceMonitor;