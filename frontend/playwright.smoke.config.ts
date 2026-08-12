/**
 * Playwright configuration for the post-deploy agent-chat smoke test.
 *
 * Runs against an already-deployed environment only — no webServer, no
 * global setup. Requires SMOKE_BASE_URL (or BASE_URL) plus SMOKE_USER_EMAIL
 * and SMOKE_USER_PASSWORD; the spec skips itself when they are absent, so
 * this config is safe to invoke unconditionally from CI.
 *
 *   SMOKE_BASE_URL=https://goodwiinz.tech \
 *   SMOKE_USER_EMAIL=... SMOKE_USER_PASSWORD=... \
 *   npx playwright test --config=playwright.smoke.config.ts
 */
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e/smoke',
  // Agent turns include real model latency; budget generously per test.
  timeout: 300_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-smoke-report' }]],
  use: {
    baseURL: process.env.SMOKE_BASE_URL?.trim() || process.env.BASE_URL?.trim() || '',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
