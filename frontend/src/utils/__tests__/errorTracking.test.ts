/**
 * Unit tests for error tracking utility
 */

import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { errorTracker } from '../errorTracking';

const mockConsoleError = vi.spyOn(console, 'error').mockImplementation();
const mockConsoleWarn = vi.spyOn(console, 'warn').mockImplementation();
const mockConsoleInfo = vi.spyOn(console, 'info').mockImplementation();
const mockConsoleDebug = vi.spyOn(console, 'debug').mockImplementation();

const mockLocalStorage = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
  key: vi.fn(),
  length: 0,
};

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
  writable: true,
});

Object.defineProperty(window, 'navigator', {
  value: {
    userAgent: 'Mozilla/5.0 (Test Browser)',
  },
  writable: true,
});

// jsdom defines location as non-configurable; delete first to avoid
// "Cannot redefine property" when running under jest-environment-jsdom >=30.
delete (window as any).location;
(window as any).location = { href: 'http://localhost:3000' };

describe('ErrorTracker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    errorTracker.setEnabled(true);
    errorTracker.clearLogs();
    errorTracker.clearMetrics();

    mockLocalStorage.getItem.mockReturnValue(null);
    mockLocalStorage.setItem.mockImplementation(() => {});
    mockLocalStorage.removeItem.mockImplementation(() => {});

    // Clear singleton state before each test
    errorTracker.clearLogs();
    errorTracker.clearMetrics();
    errorTracker.setEnabled(true);
  });

  afterAll(() => {
    mockConsoleError.mockRestore();
    mockConsoleWarn.mockRestore();
    mockConsoleInfo.mockRestore();
    mockConsoleDebug.mockRestore();
  });

  it('is a singleton', () => {
    expect(errorTracker).toBe(errorTracker);
  });

  it('stores logs in memory and localStorage', () => {
    errorTracker.info('Test info');
    errorTracker.error('Test error', new Error('boom'));

    const logs = errorTracker.getLogs();
    expect(logs).toHaveLength(2);
    expect(logs[0].level).toBe('info');
    expect(logs[1].level).toBe('error');

    expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
      'errorLogs',
      expect.any(String)
    );
  });

  it('stores performance metrics in memory and localStorage', () => {
    errorTracker.trackMetric('latency', 150, 'ms');

    const metrics = errorTracker.getMetrics();
    expect(metrics).toHaveLength(1);
    expect(metrics[0].name).toBe('latency');

    expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
      'performanceMetrics',
      expect.any(String)
    );
  });

  it('tracks document upload success as informational log', () => {
    errorTracker.trackDocumentUpload('test.pdf', 1024, true);

    expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
      'errorLogs',
      expect.stringContaining('"UploadSuccess"')
    );
  });

  it('tracks user actions as informational log', () => {
    errorTracker.trackUserAction('click', { element: 'button' });

    expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
      'errorLogs',
      expect.stringContaining('"action":"click"')
    );
  });

  it('filters logs and metrics correctly', () => {
    errorTracker.info('info');
    errorTracker.warn('warn');
    errorTracker.error('error');

    errorTracker.trackMetric('m1', 100, 'ms');
    errorTracker.trackMetric('m2', 200, 'ms');

    expect(errorTracker.getLogs('error')).toHaveLength(1);
    expect(errorTracker.getLogs(undefined, 2)).toHaveLength(2);

    expect(errorTracker.getMetrics('m1')).toHaveLength(1);
    expect(errorTracker.getMetrics(undefined, 1)).toHaveLength(1);
  });

  it('calculates analytics correctly', () => {
    errorTracker.info('i1');
    errorTracker.warn('w1');
    errorTracker.error('e1');

    errorTracker.trackMetric('metricA', 100, 'ms');
    errorTracker.trackMetric('metricA', 200, 'ms');

    const errorStats = errorTracker.getErrorStats();
    expect(errorStats.total).toBe(3);
    expect(errorStats.byLevel.info).toBe(1);
    expect(errorStats.byLevel.warn).toBe(1);
    expect(errorStats.byLevel.error).toBe(1);

    const perfStats = errorTracker.getPerformanceStats();
    expect(perfStats.total).toBe(2);
    expect(perfStats.byName.metricA.count).toBe(2);
    expect(perfStats.byName.metricA.avg).toBe(150);
  });

  it('clears logs and metrics', () => {
    errorTracker.info('x');
    errorTracker.trackMetric('y', 1, 'ms');

    errorTracker.clearLogs();
    errorTracker.clearMetrics();

    expect(errorTracker.getLogs()).toHaveLength(0);
    expect(errorTracker.getMetrics()).toHaveLength(0);
    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('errorLogs');
    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith(
      'performanceMetrics'
    );
  });

  it('exports logs and metrics to JSON', () => {
    errorTracker.info('Test message');
    errorTracker.trackMetric('test_metric', 100, 'ms');

    const exportedLogs = errorTracker.exportLogs();
    const exportedMetrics = errorTracker.exportMetrics();

    expect(exportedLogs).toContain('"message": "Test message"');
    expect(exportedMetrics).toContain('"name": "test_metric"');
  });

  it('handles localStorage errors gracefully', () => {
    mockLocalStorage.setItem.mockImplementation(() => {
      throw new Error('Storage full');
    });

    expect(() => errorTracker.info('Test message')).not.toThrow();
  });

  it('health check returns expected shape', () => {
    const health = errorTracker.healthCheck();

    expect(health).toHaveProperty('enabled');
    expect(health).toHaveProperty('logsCount');
    expect(health).toHaveProperty('metricsCount');
    expect(health).toHaveProperty('lastLog');
    expect(health).toHaveProperty('lastMetric');
  });
});
