/**
 * Focused Playwright config for Entities page E2E tests.
 *
 * Uses chromium only for speed, no global setup/teardown dependencies,
 * no custom reporters — just the built-in list + html reporters.
 *
 * Run with:
 *   npx playwright test --config tests/e2e/entities/playwright.entities.config.ts
 */

import { defineConfig, devices } from '@playwright/test';
import path from 'path';

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';

export default defineConfig({
  testDir: path.join(__dirname),
  testMatch: '**/*.spec.ts',

  // Individual test timeout — generous to allow slow KG API responses
  timeout: 60000,

  expect: {
    timeout: 15000,
  },

  // No retries locally; 1 retry on CI
  retries: process.env.CI ? 1 : 0,

  // Run tests serially (sequential) to avoid state conflicts
  workers: 1,
  fullyParallel: false,

  reporter: [
    ['list'],
    [
      'html',
      {
        outputFolder: path.join(
          __dirname,
          '../../../test-results/entities-report'
        ),
        open: 'never',
      },
    ],
  ],

  outputDir: path.join(__dirname, '../../../test-results/entities-artifacts'),

  use: {
    baseURL: BASE_URL,

    // Chromium only for speed
    ...devices['Desktop Chrome'],
    viewport: { width: 1280, height: 900 },

    // Capture artifacts on failure for debugging
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',

    actionTimeout: 15000,
    navigationTimeout: 30000,

    // Don't start a web server — assume frontend is already running
  },

  projects: [
    {
      name: 'chromium-entities',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 900 },
      },
    },
  ],
});
