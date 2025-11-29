/**
 * Unit tests for error tracking utility
 */

import { errorTracker } from '../errorTracking';

// Mock console methods
const mockConsoleError = jest.spyOn(console, 'error').mockImplementation();
const mockConsoleWarn = jest.spyOn(console, 'warn').mockImplementation();
const mockConsoleInfo = jest.spyOn(console, 'info').mockImplementation();
const mockConsoleDebug = jest.spyOn(console, 'debug').mockImplementation();

// Mock localStorage
const mockLocalStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
  key: jest.fn(),
  length: 0
};

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
  writable: true
});

// Mock navigator
Object.defineProperty(window, 'navigator', {
  value: {
    userAgent: 'Mozilla/5.0 (Test Browser)'
  },
  writable: true
});

// Mock location
Object.defineProperty(window, 'location', {
  value: {
    href: 'http://localhost:3000'
  },
  writable: true
});

describe('ErrorTracker', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset localStorage mock
    mockLocalStorage.getItem.mockReturnValue(null);
    mockLocalStorage.setItem.mockImplementation(() => {});
    mockLocalStorage.removeItem.mockImplementation(() => {});
  });

  describe('Singleton Pattern', () => {
    it('returns the same instance', () => {
      const instance1 = errorTracker;
      const instance2 = errorTracker;
      expect(instance1).toBe(instance2);
    });
  });

  describe('Error Logging', () => {
    it('logs debug messages', () => {
      errorTracker.debug('Test debug message', { key: 'value' });

      expect(mockLocalStorage.getItem).toHaveBeenCalledWith('userId');
      expect(mockLocalStorage.setItem).toHaveBeenCalled();
    });

    it('logs info messages', () => {
      errorTracker.info('Test info message', { key: 'value' });

      expect(mockLocalStorage.setItem).toHaveBeenCalled();
    });

    it('logs warning messages', () => {
      errorTracker.warn('Test warning message', { key: 'value' });

      expect(mockLocalStorage.setItem).toHaveBeenCalled();
    });

    it('logs error messages', () => {
      const error = new Error('Test error');
      errorTracker.error('Test error message', error, { key: 'value' });

      expect(mockLocalStorage.setItem).toHaveBeenCalled();
    });

    it('logs fatal messages', () => {
      const error = new Error('Test fatal error');
      errorTracker.fatal('Test fatal error message', error, { key: 'value' });

      expect(mockLocalStorage.setItem).toHaveBeenCalled();
    });
  });

  describe('Error Capture', () => {
    it('captures errors with context', () => {
      const error = new Error('Test error');
      const context = { component: 'TestComponent', action: 'testAction' };

      errorTracker.captureError(error, context);

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        'errorLogs',
        expect.stringContaining('"level":"error"')
      );
    });

    it('captures exceptions', () => {
      errorTracker.captureException('Test exception', { component: 'TestComponent' });

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        'errorLogs',
        expect.stringContaining('"level":"error"')
      );
    });

    it('captures component errors', () => {
      const error = new Error('Component error');
      const errorInfo = { componentStack: 'Test stack trace' };

      errorTracker.captureComponentError('TestComponent', error, errorInfo);

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        'errorLogs',
        expect.stringContaining('"component":"TestComponent"')
      );
    });

    it('captures API errors', () => {
      const error = new Error('API error');

      errorTracker.captureApiError('/api/test', 'GET', 500, error);

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        'errorLogs',
        expect.stringContaining('"action":"RequestFailed"')
      );
    });
  });

  describe('Performance Tracking', () => {
    it('tracks metrics', () => {
      errorTracker.trackMetric('test_metric', 100, 'ms', { key: 'value' });

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        'performanceMetrics',
        expect.stringContaining('"name":"test_metric"')
      );
    });

    it('tracks search queries', () => {
      errorTracker.trackQuery('test query', 5, 1500, true);

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        'performanceMetrics',
        expect.stringContaining('"name":"search_response_time"')
      );
    });

    it('tracks document uploads', () => {
      const file = new File(['test'], 'test.pdf', { type: 'application/pdf' });
      errorTracker.trackDocumentUpload('test.pdf', 1024, true);

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        'performanceMetrics',
        expect.stringContaining('"action":"UploadSuccess"')
      );
    });
  });

  describe('User Interaction Tracking', () => {
    it('tracks user actions', () => {
      errorTracker.trackUserAction('click', { element: 'button', id: 'test-button' });

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        'applicationLogs',
        expect.stringContaining('"action":"click"')
      );
    });

    it('tracks user actions with page context', () => {
      errorTracker.trackUserAction('search', { query: 'test query' }, 'search-input', '/search');

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        'applicationLogs',
        expect.stringContaining('"page":"/search"')
      );
    });
  });

  describe('Log Retrieval', () => {
    it('retrieves all logs', () => {
      // Add some test logs
      errorTracker.info('Test message 1');
      errorTracker.error('Test message 2');

      const logs = errorTracker.getLogs();

      expect(logs).toHaveLength(2);
      expect(logs[0].message).toBe('Test message 1');
      expect(logs[1].message).toBe('Test message 2');
    });

    it('retrieves logs by level', () => {
      errorTracker.info('Info message');
      errorTracker.error('Error message');

      const errorLogs = errorTracker.getLogs('error');

      expect(errorLogs).toHaveLength(1);
      expect(errorLogs[0].message).toBe('Error message');
    });

    it('retrieves logs with limit', () => {
      // Add multiple logs
      for (let i = 0; i < 5; i++) {
        errorTracker.info(`Message ${i}`);
      }

      const limitedLogs = errorTracker.getLogs(undefined, 3);

      expect(limitedLogs).toHaveLength(3);
    });
  });

  describe('Metrics Retrieval', () => {
    it('retrieves all metrics', () => {
      errorTracker.trackMetric('metric1', 100, 'ms');
      errorTracker.trackMetric('metric2', 200, 'ms');

      const metrics = errorTracker.getMetrics();

      expect(metrics).toHaveLength(2);
      expect(metrics[0].name).toBe('metric1');
      expect(metrics[1].name).toBe('metric2');
    });

    it('retrieves metrics by name', () => {
      errorTracker.trackMetric('search_time', 150, 'ms');
      errorTracker.trackMetric('upload_time', 2000, 'ms');

      const searchMetrics = errorTracker.getMetrics('search_time');

      expect(searchMetrics).toHaveLength(1);
      expect(searchMetrics[0].name).toBe('search_time');
    });

    it('retrieves metrics with limit', () => {
      for (let i = 0; i < 5; i++) {
        errorTracker.trackMetric(`metric${i}`, i * 100, 'ms');
      }

      const limitedMetrics = errorTracker.getMetrics(undefined, 3);

      expect(limitedMetrics).toHaveLength(3);
    });
  });

  describe('Analytics', () => {
    it('calculates error statistics', () => {
      errorTracker.info('Info message');
      errorTracker.warn('Warning message');
      errorTracker.error('Error message 1');
      errorTracker.error('Error message 2');

      const stats = errorTracker.getErrorStats();

      expect(stats.total).toBe(4);
      expect(stats.byLevel.info).toBe(1);
      expect(stats.byLevel.warn).toBe(1);
      expect(stats.byLevel.error).toBe(2);
    });

    it('calculates performance statistics', () => {
      errorTracker.trackMetric('metric1', 100, 'ms');
      errorTracker.trackMetric('metric1', 200, 'ms');
      errorTracker.trackMetric('metric2', 50, 'ms');

      const stats = errorTracker.getPerformanceStats();

      expect(stats.total).toBe(3);
      expect(stats.byName.metric1.count).toBe(2);
      expect(stats.byName.metric1.avg).toBe(150);
      expect(stats.byName.metric1.min).toBe(100);
      expect(stats.byName.metric1.max).toBe(200);
    });
  });

  describe('Maintenance', () => {
    it('clears logs', () => {
      errorTracker.info('Test message');
      expect(errorTracker.getLogs()).toHaveLength(1);

      errorTracker.clearLogs();

      expect(errorTracker.getLogs()).toHaveLength(0);
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('errorLogs');
    });

    it('clears metrics', () => {
      errorTracker.trackMetric('test_metric', 100, 'ms');
      expect(errorTracker.getMetrics()).toHaveLength(1);

      errorTracker.clearMetrics();

      expect(errorTracker.getMetrics()).toHaveLength(0);
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('performanceMetrics');
    });

    it('enables/disables tracking', () => {
      errorTracker.setEnabled(false);

      // Should not track when disabled
      errorTracker.info('Test message');
      expect(mockLocalStorage.setItem).not.toHaveBeenCalled();

      errorTracker.setEnabled(true);

      // Should track when enabled
      errorTracker.info('Test message');
      expect(mockLocalStorage.setItem).toHaveBeenCalled();
    });
  });

  describe('Export', () => {
    it('exports logs to JSON', () => {
      errorTracker.info('Test message');
      errorTracker.error('Error message', new Error('Test error'));

      const exportedLogs = errorTracker.exportLogs();

      expect(exportedLogs).toContain('"level":"info"');
      expect(exportedLogs).toContain('"level":"error"');
      expect(exportedLogs).toContain('"message":"Test message"');
      expect(exportedLogs).toContain('"message":"Error message"');
    });

    it('exports metrics to JSON', () => {
      errorTracker.trackMetric('test_metric', 100, 'ms');

      const exportedMetrics = errorTracker.exportMetrics();

      expect(exportedMetrics).toContain('"name":"test_metric"');
      expect(exportedMetrics).toContain('"value":100');
      expect(exportedMetrics).toContain('"unit":"ms"');
    });
  });

  describe('Health Check', () => {
    it('returns health status', () => {
      const health = errorTracker.healthCheck();

      expect(health).toHaveProperty('enabled');
      expect(health).toHaveProperty('logsCount');
      expect(health).toHaveProperty('metricsCount');
      expect(health).toHaveProperty('lastLog');
      expect(health).toHaveProperty('lastMetric');
    });
  });

  describe('Context Generation', () => {
    it('generates user ID from localStorage', () => {
      mockLocalStorage.getItem.mockImplementation((key) => {
        if (key === 'userId') return 'test-user-123';
        return null;
      });

      const health = errorTracker.healthCheck();

      expect(mockLocalStorage.getItem).toHaveBeenCalledWith('userId');
    });

    it('generates session ID from sessionStorage', () => {
      const mockSessionStorage = {
        getItem: jest.fn(),
        setItem: jest.fn(),
        removeItem: jest.fn(),
        clear: jest.fn()
      };

      Object.defineProperty(window, 'sessionStorage', {
        value: mockSessionStorage,
        writable: true
      });

      errorTracker.info('Test message');

      expect(mockSessionStorage.getItem).toHaveBeenCalledWith('sessionId');
    });
  });

  describe('Error Handling', () => {
    it('handles localStorage errors gracefully', () => {
      mockLocalStorage.setItem.mockImplementation(() => {
        throw new Error('Storage full');
      });

      // Should not throw
      expect(() => {
        errorTracker.info('Test message');
      }).not.toThrow();
    });

    it('handles circular objects in context', () => {
      const circularObject: any = { name: 'test' };
      circularObject.self = circularObject;

      // Should not throw
      expect(() => {
        errorTracker.info('Test message', { data: circularObject });
      }).not.toThrow();
    });
  });

  describe('Performance Optimization', () => {
    it('limits stored logs', () => {
      // Add more than max limit logs
      for (let i = 0; i < 1005; i++) {
        errorTracker.info(`Message ${i}`);
      }

      const logs = errorTracker.getLogs();
      expect(logs.length).toBeLessThanOrEqual(1000);
    });

    it('limits stored metrics', () => {
      // Add more than max limit metrics
      for (let i = 0; i < 505; i++) {
        errorTracker.trackMetric(`metric${i}`, i, 'ms');
      }

      const metrics = errorTracker.getMetrics();
      expect(metrics.length).toBeLessThanOrEqual(500);
    });
  });
});