/**
 * Playwright configuration for NOUS critical-flow E2E tests.
 * Chromium only, no global setup dependency, targets localhost:3000.
 */
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e/nous-flows',
  timeout: 60_000,
  expect: { timeout: 15_000 },

  // No retries locally; one retry in CI to catch transient flakes
  retries: process.env.CI ? 1 : 0,

  // Run tests in one worker to avoid auth race conditions on the same browser session
  workers: 1,

  reporter: [
    ['list'],
    [
      'html',
      {
        // Must NOT be a subdirectory of outputDir to avoid the "clashes" warning
        outputFolder: 'playwright-nous-report',
        open: 'never',
      },
    ],
    [
      'junit',
      {
        outputFile: 'playwright-nous-junit.xml',
        stripANSIControlSequences: true,
      },
    ],
  ],

  outputDir: 'test-results',

  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:3000',
    actionTimeout: 15_000,
    navigationTimeout: 20_000,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'on-first-retry',
  },

  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 800 },
      },
    },
  ],

  // Reuse the already-running dev server; do NOT start a new one
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
