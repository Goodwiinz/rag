/**
 * Logging Service
 * Centralized logging for API requests, user actions, and system events
 */

import { errorTracker } from '@/utils/errorTracking';

export enum LogLevel {
  DEBUG = 'debug',
  INFO = 'info',
  WARN = 'warn',
  ERROR = 'error',
  FATAL = 'fatal'
}

export interface LogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  message: string;
  category: string;
  data?: Record<string, any>;
  userId?: string;
  sessionId?: string;
  requestId?: string;
  component?: string;
  action?: string;
}

export interface ApiLogEntry extends LogEntry {
  category: 'api';
  method: string;
  url: string;
  statusCode?: number;
  duration?: number;
  requestSize?: number;
  responseSize?: number;
}

export interface UserActionLogEntry extends LogEntry {
  category: 'user_action';
  action: string;
  details?: Record<string, any>;
  element?: string;
  page?: string;
}

export interface SystemLogEntry extends LogEntry {
  category: 'system';
  event: string;
  details?: Record<string, any>;
}

class LoggingService {
  private static instance: LoggingService;
  private logs: LogEntry[] = [];
  private maxLogs = 1000;
  private isEnabled = true;
  private logLevel = LogLevel.DEBUG;
  private logCategories: Set<string> = new Set(['all']);

  private constructor() {
    this.initializeFromStorage();
  }

  static getInstance(): LoggingService {
    if (!LoggingService.instance) {
      LoggingService.instance = new LoggingService();
    }
    return LoggingService.instance;
  }

  private initializeFromStorage() {
    try {
      const storedLogs = localStorage.getItem('applicationLogs');
      if (storedLogs) {
        this.logs = JSON.parse(storedLogs);
        this.trimLogs();
      }
    } catch (error) {
      console.warn('Failed to load logs from storage:', error);
    }
  }

  private generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
  }

  private shouldLog(level: LogLevel, category: string): boolean {
    if (!this.isEnabled) return false;

    // Check log level
    const levels = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARN, LogLevel.ERROR, LogLevel.FATAL];
    const currentLevelIndex = levels.indexOf(this.logLevel);
    const messageLevelIndex = levels.indexOf(level);

    if (messageLevelIndex < currentLevelIndex) return false;

    // Check category filter
    if (!this.logCategories.has('all') && !this.logCategories.has(category)) {
      return false;
    }

    return true;
  }

  private addLog(entry: Omit<LogEntry, 'id' | 'timestamp'>): void {
    if (!this.shouldLog(entry.level, entry.category)) return;

    const logEntry: LogEntry = {
      id: this.generateId(),
      timestamp: new Date().toISOString(),
      userId: errorTracker.getUserId(),
      sessionId: errorTracker.getSessionId(),
      ...entry
    };

    this.logs.push(logEntry);
    this.trimLogs();
    this.persistLogs();

    // Send to external service
    this.sendToService(logEntry);

    // Console output for development
    if (process.env.NODE_ENV === 'development') {
      this.logToConsole(logEntry);
    }
  }

  private trimLogs() {
    if (this.logs.length > this.maxLogs) {
      this.logs = this.logs.slice(-this.maxLogs);
    }
  }

  private persistLogs() {
    try {
      // Keep only last 500 logs in localStorage to save space
      const logsToStore = this.logs.slice(-500);
      localStorage.setItem('applicationLogs', JSON.stringify(logsToStore));
    } catch (error) {
      console.warn('Failed to persist logs:', error);
      // Clear old logs if storage is full
      try {
        localStorage.removeItem('applicationLogs');
      } catch (clearError) {
        console.warn('Failed to clear logs from storage:', clearError);
      }
    }
  }

  private logToConsole(entry: LogEntry) {
    const logMethod = entry.level === LogLevel.FATAL ? 'error' :
                     entry.level === LogLevel.ERROR ? 'error' :
                     entry.level === LogLevel.WARN ? 'warn' :
                     entry.level === LogLevel.INFO ? 'info' : 'debug';

    console[logMethod](`[${entry.category.toUpperCase()}] ${entry.message}`, {
      data: entry.data,
      component: entry.component,
      action: entry.action,
      userId: entry.userId
    });
  }

  private async sendToService(entry: LogEntry) {
    // In a real implementation, this would send to your logging service
    // For now, we'll batch and store locally
    try {
      const pendingLogs = JSON.parse(localStorage.getItem('pendingLogs') || '[]');
      pendingLogs.push(entry);

      // Keep only last 100 pending logs
      if (pendingLogs.length > 100) {
        pendingLogs.splice(0, pendingLogs.length - 100);
      }

      localStorage.setItem('pendingLogs', JSON.stringify(pendingLogs));

      // Simulate sending to service (in real app, this would be a batch send)
      if (pendingLogs.length >= 10) {
        this.flushPendingLogs();
      }
    } catch (error) {
      console.warn('Failed to queue log for sending:', error);
    }
  }

  private async flushPendingLogs() {
    try {
      const pendingLogs = JSON.parse(localStorage.getItem('pendingLogs') || '[]');
      if (pendingLogs.length === 0) return;

      // Simulate API call to send logs
      // In a real implementation, this would be an actual API call
      console.log('Flushing logs to service:', pendingLogs.length, 'entries');

      // Clear sent logs
      localStorage.removeItem('pendingLogs');
    } catch (error) {
      console.warn('Failed to flush pending logs:', error);
    }
  }

  // Public API methods
  debug(message: string, data?: Record<string, any>, context?: Partial<LogEntry>) {
    this.addLog({
      level: LogLevel.DEBUG,
      message,
      data,
      category: 'debug',
      ...context
    });
  }

  info(message: string, data?: Record<string, any>, context?: Partial<LogEntry>) {
    this.addLog({
      level: LogLevel.INFO,
      message,
      data,
      category: 'info',
      ...context
    });
  }

  warn(message: string, data?: Record<string, any>, context?: Partial<LogEntry>) {
    this.addLog({
      level: LogLevel.WARN,
      message,
      data,
      category: 'warning',
      ...context
    });
  }

  error(message: string, data?: Record<string, any>, context?: Partial<LogEntry>) {
    this.addLog({
      level: LogLevel.ERROR,
      message,
      data,
      category: 'error',
      ...context
    });
  }

  fatal(message: string, data?: Record<string, any>, context?: Partial<LogEntry>) {
    this.addLog({
      level: LogLevel.FATAL,
      message,
      data,
      category: 'fatal',
      ...context
    });
  }

  // API logging
  logApiRequest(method: string, url: string, requestId?: string): string {
    const id = requestId || this.generateId();
    this.addLog({
      level: LogLevel.INFO,
      message: `API Request: ${method} ${url}`,
      category: 'api',
      requestId: id,
      action: 'api_request',
      data: {
        method,
        url,
        timestamp: new Date().toISOString()
      }
    });
    return id;
  }

  logApiResponse(
    requestId: string,
    method: string,
    url: string,
    statusCode: number,
    duration: number,
    requestSize?: number,
    responseSize?: number
  ) {
    const level = statusCode >= 400 ? LogLevel.ERROR : LogLevel.INFO;
    const message = `API Response: ${method} ${url} - ${statusCode} (${duration}ms)`;

    this.addLog({
      level,
      message,
      category: 'api',
      action: 'api_response',
      data: {
        method,
        url,
        statusCode,
        duration,
        requestSize,
        responseSize,
        success: statusCode < 400
      }
    });
  }

  logApiError(requestId: string, method: string, url: string, error: Error, duration?: number) {
    this.addLog({
      level: LogLevel.ERROR,
      message: `API Error: ${method} ${url} - ${error.message}`,
      category: 'api',
      action: 'api_error',
      data: {
        method,
        url,
        error: error.message,
        stack: error.stack,
        duration
      }
    });
  }

  // User action logging
  logUserAction(action: string, details?: Record<string, any>, element?: string, page?: string) {
    this.addLog({
      level: LogLevel.INFO,
      message: `User Action: ${action}`,
      category: 'user_action',
      action,
      data: {
        details,
        element,
        page: page || window.location.pathname
      }
    });
  }

  // System event logging
  logSystemEvent(event: string, details?: Record<string, any>, level: LogLevel = LogLevel.INFO) {
    this.addLog({
      level,
      message: `System Event: ${event}`,
      category: 'system',
      action: 'system_event',
      data: {
        event,
        details
      }
    });
  }

  // Performance logging
  logPerformance(event: string, duration: number, details?: Record<string, any>) {
    this.addLog({
      level: LogLevel.INFO,
      message: `Performance: ${event} - ${duration}ms`,
      category: 'performance',
      action: 'performance',
      data: { event, duration, ...details }
    });
  }

  // Query and search logging
  logSearchQuery(query: string, resultsCount: number, responseTime: number, filters?: Record<string, any>) {
    this.addLog({
      level: LogLevel.INFO,
      message: `Search Query: "${query}" - ${resultsCount} results (${responseTime}ms)`,
      category: 'search',
      action: 'search_query',
      data: {
        query,
        resultsCount,
        responseTime,
        filters
      }
    });
  }

  // Document logging
  logDocumentUpload(fileName: string, fileSize: number, status: 'started' | 'completed' | 'failed', error?: Error) {
    const level = status === 'failed' ? LogLevel.ERROR : LogLevel.INFO;
    const message = `Document Upload: ${fileName} - ${status}`;

    this.addLog({
      level,
      message,
      category: 'document',
      action: 'document_upload',
      data: {
        fileName,
        fileSize,
        status,
        error: error?.message
      }
    });
  }

  // Retrieval methods
  getLogs(
    level?: LogLevel,
    category?: string,
    component?: string,
    limit?: number,
    offset?: number
  ): LogEntry[] {
    let filteredLogs = [...this.logs];

    if (level) {
      filteredLogs = filteredLogs.filter(log => log.level === level);
    }

    if (category) {
      filteredLogs = filteredLogs.filter(log => log.category === category);
    }

    if (component) {
      filteredLogs = filteredLogs.filter(log => log.component === component);
    }

    // Sort by timestamp (newest first)
    filteredLogs.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

    if (offset) {
      filteredLogs = filteredLogs.slice(offset);
    }

    if (limit) {
      filteredLogs = filteredLogs.slice(0, limit);
    }

    return filteredLogs;
  }

  getLogsByTimeRange(startDate: Date, endDate: Date): LogEntry[] {
    const startTime = startDate.getTime();
    const endTime = endDate.getTime();

    return this.logs.filter(log => {
      const logTime = new Date(log.timestamp).getTime();
      return logTime >= startTime && logTime <= endTime;
    });
  }

  getLogsByUserId(userId: string): LogEntry[] {
    return this.logs.filter(log => log.userId === userId);
  }

  getLogsBySessionId(sessionId: string): LogEntry[] {
    return this.logs.filter(log => log.sessionId === sessionId);
  }

  // Analytics methods
  getLogStats() {
    const stats = {
      total: this.logs.length,
      byLevel: {} as Record<LogLevel, number>,
      byCategory: {} as Record<string, number>,
      byComponent: {} as Record<string, number>,
      recent: this.logs.filter(log =>
        new Date(log.timestamp).getTime() > Date.now() - 24 * 60 * 60 * 1000
      ).length,
      apiRequests: 0,
      apiErrors: 0,
      userActions: 0,
      avgResponseTime: 0
    };

    let totalResponseTime = 0;
    let responseTimeCount = 0;

    this.logs.forEach(log => {
      // Count by level
      stats.byLevel[log.level] = (stats.byLevel[log.level] || 0) + 1;

      // Count by category
      stats.byCategory[log.category] = (stats.byCategory[log.category] || 0) + 1;

      // Count by component
      if (log.component) {
        stats.byComponent[log.component] = (stats.byComponent[log.component] || 0) + 1;
      }

      // API stats
      if (log.category === 'api') {
        stats.apiRequests++;
        if (log.level === LogLevel.ERROR) {
          stats.apiErrors++;
        }
        if (log.data?.duration) {
          totalResponseTime += log.data.duration;
          responseTimeCount++;
        }
      }

      // User action stats
      if (log.category === 'user_action') {
        stats.userActions++;
      }
    });

    stats.avgResponseTime = responseTimeCount > 0 ? totalResponseTime / responseTimeCount : 0;

    return stats;
  }

  // Configuration methods
  setLogLevel(level: LogLevel) {
    this.logLevel = level;
  }

  getLogLevel(): LogLevel {
    return this.logLevel;
  }

  setLogCategories(categories: string[]) {
    this.logCategories = new Set(categories);
  }

  addLogCategory(category: string) {
    this.logCategories.add(category);
  }

  removeLogCategory(category: string) {
    this.logCategories.delete(category);
  }

  setEnabled(enabled: boolean) {
    this.isEnabled = enabled;
  }

  isLoggingEnabled(): boolean {
    return this.isEnabled;
  }

  // Maintenance methods
  clearLogs() {
    this.logs = [];
    localStorage.removeItem('applicationLogs');
    localStorage.removeItem('pendingLogs');
  }

  clearOldLogs(olderThanDays: number) {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - olderThanDays);

    const initialCount = this.logs.length;
    this.logs = this.logs.filter(log => new Date(log.timestamp) >= cutoffDate);

    if (this.logs.length < initialCount) {
      this.persistLogs();
      console.log(`Cleared ${initialCount - this.logs.length} old log entries`);
    }
  }

  // Export methods
  exportLogs(format: 'json' | 'csv' = 'json'): string {
    if (format === 'csv') {
      const headers = ['id', 'timestamp', 'level', 'category', 'message', 'component', 'action', 'userId'];
      const csvRows = [headers.join(',')];

      this.logs.forEach(log => {
        const row = [
          log.id,
          log.timestamp,
          log.level,
          log.category,
          `"${log.message.replace(/"/g, '""')}"`,
          log.component || '',
          log.action || '',
          log.userId || ''
        ];
        csvRows.push(row.join(','));
      });

      return csvRows.join('\n');
    }

    return JSON.stringify(this.logs, null, 2);
  }

  // Health check
  healthCheck() {
    return {
      enabled: this.isEnabled,
      logLevel: this.logLevel,
      logsCount: this.logs.length,
      categories: Array.from(this.logCategories),
      pendingLogsCount: JSON.parse(localStorage.getItem('pendingLogs') || '[]').length,
      lastLog: this.logs.length > 0 ? this.logs[this.logs.length - 1]?.timestamp : null
    };
  }
}

// Export singleton instance
export const loggingService = LoggingService.getInstance();

// Convenience exports
export const {
  debug,
  info,
  warn,
  error,
  fatal,
  logApiRequest,
  logApiResponse,
  logApiError,
  logUserAction,
  logSystemEvent,
  logPerformance,
  logSearchQuery,
  logDocumentUpload
} = loggingService;