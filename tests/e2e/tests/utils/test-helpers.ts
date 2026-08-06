import { expect, Page, BrowserContext, Locator, TestInfo } from '@playwright/test';
import path from 'path';
import fs from 'fs';
import { v4 as uuidv4 } from 'uuid';

/**
 * Test helper utilities for E2E testing
 */
export class TestHelpers {
  constructor(
    private page: Page,
    private context: BrowserContext,
    private testInfo?: TestInfo
  ) {}

  /**
   * Wait for page to be fully loaded and stable
   */
  async waitForPageLoad(timeout: number = 10000): Promise<void> {
    await this.page.waitForLoadState('networkidle', { timeout });
    await this.page.waitForLoadState('domcontentloaded', { timeout });

    // Wait for any loading indicators to disappear
    await this.page.waitForSelector('[data-testid="loading"]', { state: 'detached' }).catch(() => {});
    await this.page.waitForSelector('[data-testid="spinner"]', { state: 'detached' }).catch(() => {});
  }

  /**
   * Login with specific user credentials
   */
  async login(credentials: {
    email: string;
    password: string;
    expectedUrl?: string;
  }): Promise<void> {
    const { email, password, expectedUrl = '/dashboard' } = credentials;

    await this.page.goto('/login');
    await this.waitForPageLoad();

    // Fill login form
    await this.page.fill('[data-testid="email-input"]', email);
    await this.page.fill('[data-testid="password-input"]', password);
    await this.page.click('[data-testid="login-button"]');

    // Wait for navigation to expected page
    await this.page.waitForURL(`**${expectedUrl}`, { timeout: 20000 });
    await this.waitForPageLoad();

    // Verify login landed on an authenticated dashboard surface.
    await this.page.waitForSelector(
      [
        '[data-testid="analytics-nav-link"]',
        '[data-testid="user-menu"]',
        '[data-testid="dashboard-container"]',
      ].join(', '),
      { state: 'visible', timeout: 10000 }
    );
  }

  /**
   * Logout the current user
   */
  async logout(): Promise<void> {
    await this.page.click('[data-testid="user-menu"]');
    await this.page.click('[data-testid="logout-button"]');
    await this.page.waitForURL('/login', { timeout: 10000 });
  }

  /**
   * Take a screenshot with automatic naming
   */
  async takeScreenshot(name?: string): Promise<void> {
    const screenshotName = name || `screenshot-${Date.now()}`;
    const screenshotPath = path.join(
      this.testInfo?.outputDir || 'test-results/screenshots',
      `${screenshotName}.png`
    );

    await this.page.screenshot({
      path: screenshotPath,
      fullPage: true,
    });

    if (this.testInfo) {
      this.testInfo.attachments.push({
        name: screenshotName,
        path: screenshotPath,
        contentType: 'image/png',
      });
    }
  }

  /**
   * Expect an element to be visible with timeout
   */
  async expectElementVisible(selector: string, timeout: number = 5000): Promise<void> {
    const element = this.page.locator(selector);
    await element.waitFor({ state: 'visible', timeout });
    await expect(element).toBeVisible();
  }

  /**
   * Expect an element to be hidden
   */
  async expectElementHidden(selector: string, timeout: number = 5000): Promise<void> {
    const element = this.page.locator(selector);
    await element.waitFor({ state: 'hidden', timeout });
    await expect(element).toBeHidden();
  }

  /**
   * Wait for and click an element
   */
  async waitAndClick(selector: string, options?: { timeout?: number; force?: boolean }): Promise<void> {
    const element = this.page.locator(selector);
    await element.waitFor({ state: 'visible', timeout: options?.timeout });
    await element.click({ force: options?.force });
  }

  /**
   * Fill a form field with value
   */
  async fillField(selector: string, value: string): Promise<void> {
    const element = this.page.locator(selector);
    await element.fill(value);
  }

  /**
   * Select a dropdown option
   */
  async selectOption(selector: string, value: string): Promise<void> {
    const element = this.page.locator(selector);
    await element.selectOption(value);
  }

  /**
   * Upload a file
   */
  async uploadFile(selector: string, filePath: string): Promise<void> {
    const fileInput = this.page.locator(selector);
    await fileInput.setInputFiles(filePath);
  }

  /**
   * Wait for API response
   */
  async waitForApiResponse(urlPattern: string | RegExp, timeout: number = 30000): Promise<any> {
    return this.page.waitForResponse(
      response => urlPattern instanceof RegExp ? urlPattern.test(response.url()) : response.url().includes(urlPattern),
      { timeout }
    );
  }

  /**
   * Mock API response
   */
  async mockApiResponse(urlPattern: string, response: any, status: number = 200): Promise<void> {
    await this.page.route(urlPattern, route => {
      route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify(response),
      });
    });
  }

  /**
   * Get element text content
   */
  async getTextContent(selector: string): Promise<string> {
    const element = this.page.locator(selector);
    return await element.textContent() || '';
  }

  /**
   * Get element attribute value
   */
  async getAttribute(selector: string, attribute: string): Promise<string | null> {
    const element = this.page.locator(selector);
    return await element.getAttribute(attribute);
  }

  /**
   * Check if element exists
   */
  async elementExists(selector: string): Promise<boolean> {
    const element = this.page.locator(selector);
    return await element.count() > 0;
  }

  /**
   * Wait for WebSocket connection
   */
  async waitForWebSocket(urlPattern: string): Promise<WebSocket> {
    return this.page.waitForEvent('websocket', ws => ws.url().includes(urlPattern));
  }

  /**
   * Generate random test data
   */
  generateTestData(type: 'email' | 'name' | 'text' | 'number'): string {
    switch (type) {
      case 'email':
        return `test-${uuidv4()}@example.com`;
      case 'name':
        return `Test User ${uuidv4().slice(0, 8)}`;
      case 'text':
        return `Test text content ${uuidv4()}`;
      case 'number':
        return Math.floor(Math.random() * 1000).toString();
      default:
        return uuidv4();
    }
  }

  /**
   * Wait for element animation to complete
   */
  async waitForAnimation(selector: string): Promise<void> {
    const element = this.page.locator(selector);
    await element.waitForElementState('stable');
  }

  /**
   * Scroll element into view
   */
  async scrollIntoView(selector: string): Promise<void> {
    const element = this.page.locator(selector);
    await element.scrollIntoViewIfNeeded();
  }

  /**
   * Hover over element
   */
  async hover(selector: string): Promise<void> {
    const element = this.page.locator(selector);
    await element.hover();
  }

  /**
   * Double click element
   */
  async doubleClick(selector: string): Promise<void> {
    const element = this.page.locator(selector);
    await element.dblclick();
  }

  /**
   * Right click element
   */
  async rightClick(selector: string): Promise<void> {
    const element = this.page.locator(selector);
    await element.click({ button: 'right' });
  }

  /**
   * Drag and drop element
   */
  async dragAndDrop(sourceSelector: string, targetSelector: string): Promise<void> {
    const source = this.page.locator(sourceSelector);
    const target = this.page.locator(targetSelector);
    await source.dragTo(target);
  }

  /**
   * Handle file download
   */
  async handleDownload(action: () => Promise<void>): Promise<string> {
    const [download] = await Promise.all([
      this.page.waitForEvent('download'),
      action(),
    ]);

    const path = await download.path();
    return path;
  }

  /**
   * Handle multiple tabs/windows
   */
  async handleNewTab(action: () => Promise<void>): Promise<Page> {
    const [newPage] = await Promise.all([
      this.context.waitForEvent('page'),
      action(),
    ]);

    await newPage.waitForLoadState();
    return newPage;
  }

  /**
   * Get current URL
   */
  async getCurrentUrl(): Promise<string> {
    return this.page.url();
  }

  /**
   * Navigate to URL with wait
   */
  async navigateTo(url: string): Promise<void> {
    await this.page.goto(url);
    await this.waitForPageLoad();
  }

  /**
   * Reload page with wait
   */
  async reload(): Promise<void> {
    await this.page.reload();
    await this.waitForPageLoad();
  }

  /**
   * Go back in browser history
   */
  async goBack(): Promise<void> {
    await this.page.goBack();
    await this.waitForPageLoad();
  }

  /**
   * Go forward in browser history
   */
  async goForward(): Promise<void> {
    await this.page.goForward();
    await this.waitForPageLoad();
  }

  /**
   * Set viewport size
   */
  async setViewport(width: number, height: number): Promise<void> {
    await this.page.setViewportSize({ width, height });
  }

  /**
   * Emulate mobile device
   */
  async emulateMobile(device: 'iPhone' | 'Android' | 'Tablet'): Promise<void> {
    const devices = {
      iPhone: { viewport: { width: 375, height: 667 }, userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15' },
      Android: { viewport: { width: 360, height: 640 }, userAgent: 'Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36' },
      Tablet: { viewport: { width: 768, height: 1024 }, userAgent: 'Mozilla/5.0 (iPad; CPU OS 14_0 like Mac OS X) AppleWebKit/605.1.15' },
    };

    const config = devices[device];
    await this.page.setViewportSize(config.viewport);
    await this.page.setUserAgent(config.userAgent);
  }

  /**
   * Throttle network conditions
   */
  async throttleNetwork(type: 'slow3G' | 'fast3G' | 'offline'): Promise<void> {
    const conditions = {
      slow3G: {
        downloadThroughput: 500 * 1024 / 8,
        uploadThroughput: 500 * 1024 / 8,
        latency: 400 * 5,
      },
      fast3G: {
        downloadThroughput: 1.6 * 1024 * 1024 / 8,
        uploadThroughput: 750 * 1024 / 8,
        latency: 150 * 5,
      },
      offline: {
        downloadThroughput: 0,
        uploadThroughput: 0,
        latency: 0,
        offline: true,
      },
    };

    await this.context.route('**/*', route => route.continue());
    const client = await this.context.newCDPSession(this.page);
    await client.send('Network.emulateNetworkConditions', conditions[type]);
  }

  /**
   * Clear browser storage
   */
  async clearStorage(): Promise<void> {
    await this.context.clearCookies();
    await this.page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
  }

  /**
   * Get console logs
   */
  async getConsoleLogs(): Promise<any[]> {
    return await this.page.evaluate(() => {
      return (window as any).consoleLogs || [];
    });
  }

  /**
   * Get page performance metrics
   */
  async getPerformanceMetrics(): Promise<any> {
    const metrics = await this.page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      const paint = performance.getEntriesByType('paint');

      return {
        domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
        loadComplete: navigation.loadEventEnd - navigation.loadEventStart,
        firstPaint: paint.find(entry => entry.name === 'first-paint')?.startTime || 0,
        firstContentfulPaint: paint.find(entry => entry.name === 'first-contentful-paint')?.startTime || 0,
      };
    });

    return metrics;
  }

  /**
   * Add custom test marker
   */
  addTestMarker(name: string, value: any): void {
    if (this.testInfo) {
      this.testInfo.annotations.push({
        type: 'test-marker',
        description: `${name}: ${JSON.stringify(value)}`,
      });
    }
  }

  /**
   * Log test step
   */
  logStep(step: string): void {
    console.log(`🔍 [${this.testInfo?.title || 'Test'}] ${step}`);
    this.addTestMarker('step', step);
  }
}

/**
 * Create test helpers instance
 */
export function createTestHelpers(page: Page, context: BrowserContext, testInfo?: TestInfo): TestHelpers {
  return new TestHelpers(page, context, testInfo);
}

/**
 * Common test data and selectors
 */
export const TEST_DATA = {
  USERS: {
    ADMIN: {
      email: process.env.TEST_ADMIN_EMAIL || 'admin@test.com',
      password: process.env.TEST_ADMIN_PASSWORD || 'REDACTED456',
    },
    REGULAR: {
      email: process.env.TEST_USER_EMAIL || 'user@test.com',
      password: process.env.TEST_USER_PASSWORD || 'user123456',
    },
    ORG_ADMIN: {
      email: process.env.TEST_ORG_ADMIN_EMAIL || 'orgadmin@test.com',
      password: process.env.TEST_ORG_ADMIN_PASSWORD || 'orgREDACTED456',
    },
  },
  ORGANIZATIONS: {
    PRIMARY: process.env.TEST_ORG_ID || 'test-org-123',
    SECONDARY: process.env.TEST_ORG_2_ID || 'test-org-456',
  },
  SELECTORS: {
    LOGIN: {
      EMAIL_INPUT: '[data-testid="email-input"]',
      PASSWORD_INPUT: '[data-testid="password-input"]',
      LOGIN_BUTTON: '[data-testid="login-button"]',
      ERROR_MESSAGE: '[data-testid="login-error"]',
    },
    DASHBOARD: {
      CONTAINER: '[data-testid="dashboard-container"]',
      USER_MENU: '[data-testid="user-menu"]',
      LOGOUT_BUTTON: '[data-testid="logout-button"]',
    },
    ANALYTICS: {
      DASHBOARD: '[data-testid="analytics-dashboard"]',
      METRIC_CARD: '[data-testid="metric-card"]',
      CHART: '[data-testid="chart"]',
      FILTER: '[data-testid="filter"]',
    },
    GRAPH: {
      VIEWER: '[data-testid="graph-viewer"]',
      NODE: '[data-testid="graph-node"]',
      EDGE: '[data-testid="graph-edge"]',
      FILTER_PANEL: '[data-testid="graph-filter-panel"]',
    },
    DOCUMENTS: {
      UPLOAD_ZONE: '[data-testid="upload-zone"]',
      DOCUMENT_LIST: '[data-testid="document-list"]',
      DOCUMENT_CARD: '[data-testid="document-card"]',
    },
  },
  TIMEOUTS: {
    SHORT: 2000,
    MEDIUM: 5000,
      LONG: 10000,
      EXTRA_LONG: 30000,
  },
  VIEWPORTS: {
    DESKTOP: { width: 1280, height: 720 },
    TABLET: { width: 768, height: 1024 },
    MOBILE: { width: 375, height: 667 },
    WIDESCREEN: { width: 1920, height: 1080 },
  },
};
