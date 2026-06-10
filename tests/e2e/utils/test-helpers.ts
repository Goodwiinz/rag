/**
 * E2E Test Helpers for Playwright
 * Shared utilities for all E2E test suites
 */

import { Page, BrowserContext, TestInfo, expect } from '@playwright/test';

export const TEST_DATA = {
  USERS: {
    ADMIN: {
      email: process.env.TEST_ADMIN_EMAIL || 'admin@multimodal-rag.com',
      password: process.env.TEST_ADMIN_PASSWORD || 'admin123',
      name: 'Admin User',
    },
    USER: {
      email: process.env.TEST_USER_EMAIL || 'demo@multimodal-rag.com',
      password: process.env.TEST_USER_PASSWORD || 'demo123',
      name: 'Demo User',
    },
    ORG_ADMIN: {
      email: process.env.TEST_ORG_ADMIN_EMAIL || 'lab-admin@multimodal-rag.com',
      password: process.env.TEST_ORG_ADMIN_PASSWORD || 'admin123',
      name: 'Lab Admin',
    },
  },
  ORG: {
    name: process.env.TEST_ORG_NAME || 'Test Organization',
    slug: process.env.TEST_ORG_SLUG || 'test-org',
  },
};

export const FRONTEND_URL = process.env.BASE_URL || 'http://localhost:3000';
export const API_URL = process.env.API_BASE_URL || 'http://localhost:8000';

export function createTestHelpers(page: Page, context: BrowserContext, testInfo: TestInfo) {
  const stepLogs: string[] = [];

  const logStep = (message: string) => {
    const entry = `[${testInfo.title}] ${message}`;
    stepLogs.push(entry);
    console.log(entry);
  };

  const navigateTo = async (path: string) => {
    const url = `${FRONTEND_URL}${path}`;
    logStep(`Navigating to ${url}`);
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
  };

  const expectElementVisible = async (selector: string, timeout = 10000) => {
    logStep(`Expecting ${selector} to be visible`);
    await expect(page.locator(selector)).toBeVisible({ timeout });
  };

  const expectElementHidden = async (selector: string, timeout = 10000) => {
    logStep(`Expecting ${selector} to be hidden`);
    await expect(page.locator(selector)).toBeHidden({ timeout });
  };

  const waitAndClick = async (selector: string, timeout = 10000) => {
    logStep(`Waiting and clicking ${selector}`);
    await page.locator(selector).waitFor({ state: 'visible', timeout });
    await page.click(selector);
  };

  const fillField = async (selector: string, value: string) => {
    logStep(`Filling ${selector} with "${value}"`);
    await page.fill(selector, value);
  };

  const login = async (credentials: { email: string; password: string }) => {
    logStep(`Logging in as ${credentials.email}`);
    await page.goto(`${FRONTEND_URL}/login`, { waitUntil: 'networkidle' });
    await page.waitForSelector('[data-testid="email-input"]', { timeout: 10000 });
    await page.fill('[data-testid="email-input"]', credentials.email);
    await page.fill('[data-testid="password-input"]', credentials.password);
    await page.click('[data-testid="login-button"]');
    // Wait for navigation to dashboard
    await page.waitForURL(/.*dashboard/, { timeout: 15000 });
    logStep('Login successful');
  };

  const takeScreenshot = async (name: string) => {
    const fileName = `${testInfo.title.replace(/\s+/g, '_')}_${name}`;
    logStep(`Taking screenshot: ${fileName}`);
    await page.screenshot({
      path: `test-results/screenshots/${fileName}.png`,
      fullPage: true,
    });
  };

  return {
    logStep,
    navigateTo,
    expectElementVisible,
    expectElementHidden,
    waitAndClick,
    fillField,
    login,
    takeScreenshot,
    page,
    context,
  };
}

export default createTestHelpers;
