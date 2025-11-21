import { test as base, expect, Page } from '@playwright/test';
import { WebSocketTestUtils } from '../utils/websocket-test-utils';
import { DocumentProcessor } from '../utils/document-processor';
import { TestDataManager } from '../utils/test-data-manager';
import { PerformanceMonitor } from '../utils/performance-monitor';

/**
 * Enhanced test fixtures for comprehensive E2E testing
 *
 * Provides:
 * - WebSocket testing utilities
 * - Document processing helpers
 * - Test data management
 * - Performance monitoring
 * - Real-time status tracking
 */

interface EnhancedTestFixture {
  page: Page;
  webSocketUtils: WebSocketTestUtils;
  documentProcessor: DocumentProcessor;
  testDataManager: TestDataManager;
  performanceMonitor: PerformanceMonitor;
}

interface AuthenticatedTestFixture extends EnhancedTestFixture {
  authenticatedPage: Page;
  authToken: string;
  userId: string;
}

export const test = base.extend<EnhancedTestFixture>({
  // WebSocket testing utilities
  webSocketUtils: async ({ page }, use) => {
    const wsUtils = new WebSocketTestUtils(page);
    await use(wsUtils);
    await wsUtils.cleanup();
  },

  // Document processing utilities
  documentProcessor: async ({ page, webSocketUtils }, use) => {
    const processor = new DocumentProcessor(page, webSocketUtils);
    await use(processor);
    await processor.cleanup();
  },

  // Test data manager
  testDataManager: async ({ page }, use) => {
    const dataManager = new TestDataManager(page);
    await use(dataManager);
    await dataManager.cleanup();
  },

  // Performance monitor
  performanceMonitor: async ({ page }, use) => {
    const monitor = new PerformanceMonitor(page);
    await monitor.start();
    await use(monitor);
    await monitor.stop();
  },
});

// Authenticated test fixture extension
export const authenticatedTest = test.extend<AuthenticatedTestFixture>({
  authenticatedPage: async ({ page, testDataManager }, use) => {
    // Authenticate the page
    const { token, userId } = await testDataManager.authenticateUser(page);

    // Set auth token in localStorage
    await page.evaluate(({ token, userId }) => {
      localStorage.setItem('auth_token', token);
      localStorage.setItem('user_id', userId);
    }, { token, userId });

    await use(page);
  },

  authToken: async ({ authenticatedPage, testDataManager }) => {
    return await testDataManager.getStoredToken(authenticatedPage);
  },

  userId: async ({ authenticatedPage, testDataManager }) => {
    return await testDataManager.getStoredUserId(authenticatedPage);
  },
});

// Custom expect matchers for enhanced assertions
expect.extend({
  // Assert WebSocket connection status
  async toHaveWebSocketConnection(received: Page, expectedStatus: 'connected' | 'disconnected' | 'error') {
    const wsUtils = new WebSocketTestUtils(received);
    const actualStatus = await wsUtils.getConnectionStatus();

    if (actualStatus === expectedStatus) {
      return {
        message: () => `WebSocket connection status is ${expectedStatus}`,
        pass: true,
      };
    }

    return {
      message: () => `Expected WebSocket connection status to be ${expectedStatus}, but got ${actualStatus}`,
      pass: false,
    };
  },

  // Assert document processing status
  async toHaveProcessingStatus(received: Page, documentId: string, expectedStatus: string) {
    const docProcessor = new DocumentProcessor(received);
    const actualStatus = await docProcessor.getProcessingStatus(documentId);

    if (actualStatus === expectedStatus) {
      return {
        message: () => `Document ${documentId} has processing status ${expectedStatus}`,
        pass: true,
      };
    }

    return {
      message: () => `Expected document ${documentId} to have processing status ${expectedStatus}, but got ${actualStatus}`,
      pass: false,
    };
  },

  // Assert real-time updates received
  async toReceiveRealTimeUpdates(received: Page, documentId: string, expectedUpdates: string[]) {
    const wsUtils = new WebSocketTestUtils(received);
    const receivedUpdates = await wsUtils.getDocumentUpdates(documentId);

    const missingUpdates = expectedUpdates.filter(update => !receivedUpdates.includes(update));

    if (missingUpdates.length === 0) {
      return {
        message: () => `Document ${documentId} received all expected real-time updates`,
        pass: true,
      };
    }

    return {
      message: () => `Document ${documentId} missed real-time updates: ${missingUpdates.join(', ')}`,
      pass: false,
    };
  },

  // Assert performance metrics within threshold
  async toHavePerformanceMetric(received: Page, metric: string, threshold: number) {
    const perfMonitor = new PerformanceMonitor(received);
    const actualValue = await perfMonitor.getMetric(metric);

    if (actualValue <= threshold) {
      return {
        message: () => `Performance metric ${metric} is within threshold (${actualValue} <= ${threshold})`,
        pass: true,
      };
    }

    return {
      message: () => `Performance metric ${metric} exceeds threshold (${actualValue} > ${threshold})`,
      pass: false,
    };
  },
});

export { expect };