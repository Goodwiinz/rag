/**
 * Error Tracking and Logging Utility
 * Provides centralized error handling, logging, and monitoring for the frontend application
 */

interface ErrorContext {
  userId?: string;
  sessionId?: string;
  component?: string;
  action?: string;
  url?: string;
  userAgent?: string;
  timestamp?: string;
  additionalData?: Record<string, any>;
}

interface ErrorLog {
  id: string;
  level: 'debug' | 'info' | 'warn' | 'error' | 'fatal';
  message: string;
  error?: Error;
  context: ErrorContext;
  stackTrace?: string;
  timestamp: string;
  resolved: boolean;
}

interface PerformanceMetric {
  name: string;
  value: number;
  unit: string;
  timestamp: string;
  context?: ErrorContext;
}

class ErrorTracker {
  private static instance: ErrorTracker;
  private logs: ErrorLog[] = [];
  private metrics: PerformanceMetric[] = [];
  private maxLogs = 1000;
  private maxMetrics = 500;
  private isEnabled = true;

  private constructor() {
    this.initializeErrorHandling();
    this.setupPerformanceMonitoring();
  }

  static getInstance(): ErrorTracker {
    if (!ErrorTracker.instance) {
      ErrorTracker.instance = new ErrorTracker();
    }
    return ErrorTracker.instance;
  }

  private initializeErrorHandling() {
    // Global error handlers
    window.addEventListener('error', (event) => {
      this.captureError(event.error || new Error(event.message), {
        component: 'Global',
        action: 'UnhandledError',
        url: event.filename,
        additionalData: {
          lineno: event.lineno,
          colno: event.colno,
          stack: event.error?.stack
        }
      });
    });

    window.addEventListener('unhandledrejection', (event) => {
      this.captureError(
        new Error(`Unhandled promise rejection: ${event.reason}`),
        {
          component: 'Global',
          action: 'UnhandledPromiseRejection',
          additionalData: { reason: event.reason }
        }
      );
    });
  }

  private setupPerformanceMonitoring() {
    // Monitor Core Web Vitals
    // Note: In a real implementation, you would install and import the web-vitals library
    // import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals';
    // Then call this.monitorPerformanceMetrics() which would use those functions
    // For now, we just set up resource and long task monitoring

    // Monitor resource loading
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.entryType === 'resource') {
          const resource = entry as PerformanceResourceTiming;
          if (resource.duration > 5000) { // Log slow resources
            this.warn('Slow resource detected', {
              component: 'Performance',
              action: 'ResourceLoad',
              additionalData: {
                name: resource.name,
                duration: resource.duration,
                size: resource.transferSize
              }
            });
          }
        }
      }
    });

    observer.observe({ entryTypes: ['resource'] });

    // Monitor long tasks
    if ('PerformanceObserver' in window) {
      const longTaskObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          this.warn('Long task detected', {
            component: 'Performance',
            action: 'LongTask',
            additionalData: {
              duration: entry.duration,
              startTime: entry.startTime
            }
          });
        }
      });

      try {
        longTaskObserver.observe({ entryTypes: ['longtask'] });
      } catch (e) {
        // Long task API might not be supported
        this.debug('Long task monitoring not supported');
      }
    }
  }

  private generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
  }

  private getCurrentContext(): ErrorContext {
    return {
      userId: this.getUserId(),
      sessionId: this.getSessionId(),
      url: window.location.href,
      userAgent: navigator.userAgent,
      timestamp: new Date().toISOString()
    };
  }

  getUserId(): string {
    // In a real app, this would come from authentication context
    return localStorage.getItem('userId') || 'anonymous';
  }

  getSessionId(): string {
    let sessionId = sessionStorage.getItem('sessionId');
    if (!sessionId) {
      sessionId = this.generateId();
      sessionStorage.setItem('sessionId', sessionId);
    }
    return sessionId;
  }

  private addLog(level: ErrorLog['level'], message: string, error?: Error, context?: Partial<ErrorContext>) {
    if (!this.isEnabled) return;

    const fullContext: ErrorContext = {
      ...this.getCurrentContext(),
      ...context
    };

    const log: ErrorLog = {
      id: this.generateId(),
      level,
      message,
      error,
      context: fullContext,
      stackTrace: error?.stack,
      timestamp: fullContext.timestamp || new Date().toISOString(),
      resolved: false
    };

    this.logs.push(log);
    this.trimLogs();

    // Send to external service if configured
    this.sendToService(log);

    // Console output for development
    if (process.env.NODE_ENV === 'development') {
      this.logToConsole(level, message, error, fullContext);
    }
  }

  private trimLogs() {
    if (this.logs.length > this.maxLogs) {
      this.logs = this.logs.slice(-this.maxLogs);
    }
  }

  private trimMetrics() {
    if (this.metrics.length > this.maxMetrics) {
      this.metrics = this.metrics.slice(-this.maxMetrics);
    }
  }

  private logToConsole(level: string, message: string, error?: Error, context?: ErrorContext) {
    const logMethod = level === 'error' || level === 'fatal' ? 'error' :
                     level === 'warn' ? 'warn' :
                     level === 'info' ? 'info' : 'debug';

    console[logMethod](`[${level.toUpperCase()}] ${message}`, {
      error,
      context
    });
  }

  private async sendToService(log: ErrorLog) {
    // In a real implementation, this would send to services like Sentry, LogRocket, etc.
    // For now, we'll simulate with a local storage backup
    try {
      const existingLogs = JSON.parse(localStorage.getItem('errorLogs') || '[]');
      existingLogs.push(log);

      // Keep only last 100 logs in localStorage
      if (existingLogs.length > 100) {
        existingLogs.splice(0, existingLogs.length - 100);
      }

      localStorage.setItem('errorLogs', JSON.stringify(existingLogs));
    } catch (e) {
      // Fallback if localStorage is full or unavailable
      console.warn('Failed to store error log locally:', e);
    }
  }

  // Public API methods
  debug(message: string, context?: Partial<ErrorContext>) {
    this.addLog('debug', message, undefined, context);
  }

  info(message: string, context?: Partial<ErrorContext>) {
    this.addLog('info', message, undefined, context);
  }

  warn(message: string, context?: Partial<ErrorContext>) {
    this.addLog('warn', message, undefined, context);
  }

  error(message: string, error?: Error, context?: Partial<ErrorContext>) {
    this.addLog('error', message, error, context);
  }

  fatal(message: string, error?: Error, context?: Partial<ErrorContext>) {
    this.addLog('fatal', message, error, context);
  }

  captureError(error: Error, context?: Partial<ErrorContext>) {
    this.addLog('error', error.message, error, context);
  }

  captureException(error: any, context?: Partial<ErrorContext>) {
    const errorObj = error instanceof Error ? error : new Error(String(error));
    this.addLog('error', errorObj.message, errorObj, context);
  }

  // Performance monitoring
  trackMetric(name: string, value: number, unit: string, context?: Partial<ErrorContext>) {
    const metric: PerformanceMetric = {
      name,
      value,
      unit,
      timestamp: new Date().toISOString(),
      context: { ...this.getCurrentContext(), ...context }
    };

    this.metrics.push(metric);
    this.trimMetrics();

    // Send to analytics service
    this.sendMetric(metric);
  }

  private async sendMetric(metric: PerformanceMetric) {
    try {
      const existingMetrics = JSON.parse(localStorage.getItem('performanceMetrics') || '[]');
      existingMetrics.push(metric);

      if (existingMetrics.length > 50) {
        existingMetrics.splice(0, existingMetrics.length - 50);
      }

      localStorage.setItem('performanceMetrics', JSON.stringify(existingMetrics));
    } catch (e) {
      console.warn('Failed to store performance metric locally:', e);
    }
  }

  // Component-specific error boundary helper
  captureComponentError(componentName: string, error: Error, errorInfo?: any) {
    this.captureError(error, {
      component: componentName,
      action: 'ComponentError',
      additionalData: { errorInfo }
    });
  }

  // API error tracking
  captureApiError(url: string, method: string, status: number, error?: Error) {
    this.captureError(error || new Error(`API ${method} ${url} failed with status ${status}`), {
      component: 'API',
      action: 'RequestFailed',
      additionalData: { url, method, status }
    });
  }

  // User interaction tracking
  trackUserAction(action: string, details?: Record<string, any>) {
    this.info(`User action: ${action}`, {
      component: 'UserInteraction',
      action,
      additionalData: details
    });
  }

  // Query and search tracking
  trackQuery(query: string, resultsCount: number, responseTime: number, success: boolean) {
    this.trackMetric('search_response_time', responseTime, 'milliseconds', {
      component: 'Search',
      action: 'Query'
    });

    if (!success) {
      this.error(`Search query failed: ${query}`, undefined, {
        component: 'Search',
        action: 'QueryFailed',
        additionalData: { query, responseTime }
      });
    } else {
      this.info(`Search query successful: ${query}`, {
        component: 'Search',
        action: 'QuerySuccess',
        additionalData: { query, resultsCount, responseTime }
      });
    }
  }

  // Document upload tracking
  trackDocumentUpload(fileName: string, fileSize: number, success: boolean, error?: Error) {
    if (!success) {
      this.captureError(error || new Error(`Document upload failed: ${fileName}`), {
        component: 'DocumentUpload',
        action: 'UploadFailed',
        additionalData: { fileName, fileSize }
      });
    } else {
      this.info(`Document uploaded successfully: ${fileName}`, {
        component: 'DocumentUpload',
        action: 'UploadSuccess',
        additionalData: { fileName, fileSize }
      });
    }
  }

  // Retrieval methods for debugging
  getLogs(level?: ErrorLog['level'], limit?: number): ErrorLog[] {
    let filteredLogs = this.logs;
    if (level) {
      filteredLogs = filteredLogs.filter(log => log.level === level);
    }
    if (limit) {
      filteredLogs = filteredLogs.slice(-limit);
    }
    return filteredLogs;
  }

  getMetrics(name?: string, limit?: number): PerformanceMetric[] {
    let filteredMetrics = this.metrics;
    if (name) {
      filteredMetrics = filteredMetrics.filter(metric => metric.name === name);
    }
    if (limit) {
      filteredMetrics = filteredMetrics.slice(-limit);
    }
    return filteredMetrics;
  }

  // Analytics methods
  getErrorStats() {
    const stats = {
      total: this.logs.length,
      byLevel: {} as Record<string, number>,
      byComponent: {} as Record<string, number>,
      recent: this.logs.filter(log =>
        new Date(log.timestamp).getTime() > Date.now() - 24 * 60 * 60 * 1000
      ).length
    };

    this.logs.forEach(log => {
      stats.byLevel[log.level] = (stats.byLevel[log.level] || 0) + 1;
      const component = log.context.component || 'Unknown';
      stats.byComponent[component] = (stats.byComponent[component] || 0) + 1;
    });

    return stats;
  }

  getPerformanceStats() {
    const stats = {
      total: this.metrics.length,
      byName: {} as Record<string, { count: number; avg: number; min: number; max: number }>,
      recent: this.metrics.filter(metric =>
        new Date(metric.timestamp).getTime() > Date.now() - 24 * 60 * 60 * 1000
      ).length
    };

    this.metrics.forEach(metric => {
      if (!stats.byName[metric.name]) {
        stats.byName[metric.name] = { count: 0, avg: 0, min: Infinity, max: -Infinity };
      }
      const nameStats = stats.byName[metric.name]!;
      nameStats.count++;
      nameStats.avg = (nameStats.avg * (nameStats.count - 1) + metric.value) / nameStats.count;
      nameStats.min = Math.min(nameStats.min, metric.value);
      nameStats.max = Math.max(nameStats.max, metric.value);
    });

    return stats;
  }

  // Maintenance methods
  clearLogs() {
    this.logs = [];
    localStorage.removeItem('errorLogs');
  }

  clearMetrics() {
    this.metrics = [];
    localStorage.removeItem('performanceMetrics');
  }

  setEnabled(enabled: boolean) {
    this.isEnabled = enabled;
  }

  isTrackingEnabled(): boolean {
    return this.isEnabled;
  }

  // Export data for analysis
  exportLogs(): string {
    return JSON.stringify(this.logs, null, 2);
  }

  exportMetrics(): string {
    return JSON.stringify(this.metrics, null, 2);
  }

  // Health check
  healthCheck() {
    return {
      enabled: this.isEnabled,
      logsCount: this.logs.length,
      metricsCount: this.metrics.length,
      lastLog: this.logs.length > 0 ? this.logs[this.logs.length - 1]!.timestamp : null,
      lastMetric: this.metrics.length > 0 ? this.metrics[this.metrics.length - 1]!.timestamp : null
    };
  }
}

// Export singleton instance
export const errorTracker = ErrorTracker.getInstance();

// Convenience exports
export const { debug, info, warn, error, fatal, captureError, captureException } = errorTracker;
export const useErrorTracking = () => errorTracker;