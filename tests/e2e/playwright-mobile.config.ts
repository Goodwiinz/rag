import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/mobile',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : 3,
  reporter: [
    ['html', { outputFolder: 'playwright-report/mobile' }],
    ['json', { outputFile: 'test-results/mobile-results.json' }],
    ['line'],
  ],

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    headless: true,
    ignoreHTTPSErrors: true,

    // Mobile-specific settings
    screenshot: {
      mode: 'only-on-failure',
      fullPage: true,
    },

    // Touch gestures
    hasTouch: true,

    // Network conditions for mobile testing
    offline: false,
    // Slow 3G simulation can be enabled per test
  },

  projects: [
    // Mobile devices
    {
      name: 'mobile-chrome-android',
      use: {
        ...devices['Pixel 5'],
        // Android-specific settings
        userAgent: 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.85 Mobile Safari/537.36',
      },
      testIgnore: ['**/desktop-only/**'],
    },

    {
      name: 'mobile-safari-ios',
      use: {
        ...devices['iPhone 12'],
        // iOS-specific settings
        isMobile: true,
        hasTouch: true,
      },
      testIgnore: ['**/desktop-only/**'],
    },

    {
      name: 'tablet-ipad',
      use: {
        ...devices['iPad Pro'],
        // Tablet-specific settings
        viewport: { width: 1024, height: 1366 },
        isMobile: true,
        hasTouch: true,
      },
      testIgnore: ['**/mobile-only/**'],
    },

    // Responsive design testing
    {
      name: 'responsive-desktop',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1920, height: 1080 },
      },
      testMatch: '**/responsive/**/*.spec.ts',
    },

    {
      name: 'responsive-laptop',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1366, height: 768 },
      },
      testMatch: '**/responsive/**/*.spec.ts',
    },

    {
      name: 'responsive-tablet',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 768, height: 1024 },
      },
      testMatch: '**/responsive/**/*.spec.ts',
    },

    {
      name: 'responsive-mobile',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 375, height: 667 },
      },
      testMatch: '**/responsive/**/*.spec.ts',
    },
  ],
});
