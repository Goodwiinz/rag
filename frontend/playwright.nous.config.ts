/**
 * Playwright configuration for NOUS critical-flow E2E tests.
 * Chromium only, no global setup dependency. Targets BASE_URL when supplied,
 * otherwise reuses or starts the local frontend on localhost:3000.
 */
import { defineConfig, devices } from '@playwright/test';

const externalBaseUrl = process.env.BASE_URL?.trim() || undefined;
const localBaseUrl = 'http://localhost:3000';

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
    baseURL: externalBaseUrl ?? localBaseUrl,
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

  // An external BASE_URL is already hosted. For local runs, keep the repo's
  // pinned pnpm toolchain and reuse an existing dev server when available.
  webServer: externalBaseUrl
    ? undefined
    : {
        command: 'corepack pnpm@10.18.2 run dev',
        url: localBaseUrl,
        reuseExistingServer: true,
        timeout: 30_000,
      },
});
