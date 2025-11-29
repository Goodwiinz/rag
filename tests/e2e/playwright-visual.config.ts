import { defineConfig, devices } from '@playwright/test';
import path from 'path';

export default defineConfig({
  testDir: './tests/visual',
  fullyParallel: false, // Visual tests should run sequentially
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1, // Visual tests should run with single worker for consistency
  reporter: [
    ['html', { outputFolder: 'test-results/visual-report' }],
    ['json', { outputFile: 'test-results/visual-results.json' }],
  ],

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    headless: true,
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,

    // Visual regression specific settings
    screenshot: {
      mode: 'only-on-failure',
      fullPage: true,
      animations: 'disabled',
      caret: 'hide'
    },

    // Disable animations and transitions for consistent screenshots
    colorScheme: 'light',
    reducedMotion: 'reduce',

    // Ensure consistent rendering
    deviceScaleFactor: 1,
    hasTouch: false,

    // Wait for stable state
    waitForSelectorTimeout: 5000,
  },

  projects: [
    {
      name: 'visual-chrome',
      use: {
        ...devices['Desktop Chrome'],
        // Ensure consistent browser version
        channel: 'chrome',
      },
    },
  ],

  // Update screenshots when needed
  updateSnapshots: process.env.UPDATE_SNAPSHOTS === 'true' ? 'all' : 'missing',
});