import { defineConfig, devices } from '@playwright/test';

const PORT = 3107;
const baseURL = `http://127.0.0.1:${PORT}`;

const viewports = [
  { name: '320', viewport: { width: 320, height: 900 } },
  { name: '768', viewport: { width: 768, height: 1024 } },
  { name: '1024', viewport: { width: 1024, height: 900 } },
  { name: '1440', viewport: { width: 1440, height: 1000 } },
];

export default defineConfig({
  testDir: './e2e/visual',
  testMatch: 'chat-response-renderer.spec.ts',
  outputDir: './test-results/response-layout',
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  snapshotPathTemplate:
    '{testDir}/__snapshots__/{testFilePath}/{arg}-{projectName}{ext}',
  expect: {
    timeout: 10_000,
    toHaveScreenshot: {
      animations: 'disabled',
      maxDiffPixelRatio: 0.001,
    },
  },
  use: {
    ...devices['Desktop Chrome'],
    baseURL,
    colorScheme: 'light',
    deviceScaleFactor: 1,
    trace: 'retain-on-failure',
  },
  projects: viewports.map(({ name, viewport }) => ({
    name: `chromium-${name}`,
    use: { viewport },
  })),
  webServer: {
    command: `env NEXT_PUBLIC_VISUAL_TEST_FIXTURES=1 NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321 NEXT_PUBLIC_SUPABASE_ANON_KEY=visual-test-anon-key corepack pnpm@10.18.2 exec next dev --hostname 127.0.0.1 --port ${PORT}`,
    url: `${baseURL}/visual-test/response-renderer`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
