import { defineConfig, devices } from '@playwright/test';
import { injectAxe, checkA11y } from 'axe-playwright';

export default defineConfig({
  testDir: './tests/accessibility',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : 2,
  reporter: [
    ['html', { outputFolder: 'test-results/accessibility-report' }],
    ['json', { outputFile: 'test-results/accessibility-results.json' }],
    ['list'],
  ],

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    headless: true,
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,

    // Accessibility testing setup
    beforeScreenshot: async (page) => {
      // Wait for any dynamic content to load
      await page.waitForLoadState('networkidle');
    },
  },

  projects: [
    {
      name: 'accessibility-chrome',
      use: {
        ...devices['Desktop Chrome'],
      },
      testMatch: '**/*.spec.ts',
      dependencies: ['setup-accessibility'],
    },

    {
      name: 'setup-accessibility',
      testMatch: '**/setup-accessibility.spec.ts',
      teardown: 'teardown-accessibility',
    },

    {
      name: 'teardown-accessibility',
      testMatch: '**/teardown-accessibility.spec.ts',
    },
  ],

  // Global setup for accessibility testing
  globalSetup: async (config) => {
    console.log('🔍 Setting up accessibility testing...');
  },

  // Custom test fixtures
  testOptions: {
    // Custom accessibility testing fixtures
    accessibilityTesting: true,
  },
});