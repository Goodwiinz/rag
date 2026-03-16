import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/performance',
  fullyParallel: false, // Performance tests should run sequentially
  forbidOnly: !!process.env.CI,
  retries: 0, // No retries for performance tests
  workers: 1, // Single worker for consistent performance measurements
  reporter: [
    ['html', { outputFolder: 'playwright-report/performance' }],
    ['json', { outputFile: 'test-results/performance-results.json' }],
    ['line'],
  ],

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    headless: true,
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,

    // Performance-specific settings
    launchOptions: {
      args: [
        '--disable-web-security',
        '--disable-features=IsolateOrigins,site-per-process',
        '--disable-dev-shm-usage',
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-gpu',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-renderer-backgrounding',
        '--disable-extensions',
        '--disable-plugins',
        '--disable-default-apps',
        '--disable-translate',
        '--disable-infobars',
        '--mute-audio',
      ],
    },

    // Performance monitoring
    navigationTimeout: 60 * 1000, // 60 seconds
    actionTimeout: 30 * 1000, // 30 seconds
  },

  projects: [
    {
      name: 'performance-chrome',
      use: {
        ...devices['Desktop Chrome'],
        // Chrome DevTools Protocol access for performance metrics
        channel: 'chrome',
      },
    },
  ],

  // Performance test hooks
  globalSetup: async (config) => {
    console.log('🚀 Setting up performance testing environment...');

    // Warm up the server to eliminate cold start effects
    await warmupServer();

    console.log('✅ Performance testing environment ready');
  },

  // Custom test options for performance testing
  testOptions: {
    // Performance thresholds (can be overridden per test)
    performanceThresholds: {
      'page-load': 3000, // 3 seconds
      'first-contentful-paint': 1500, // 1.5 seconds
      'largest-contentful-paint': 2500, // 2.5 seconds
      'cumulative-layout-shift': 0.1,
      'first-input-delay': 100, // 100ms
      'time-to-interactive': 5000, // 5 seconds
    },

    // Enable detailed performance collection
    collectPerformanceMetrics: true,
  },
});

async function warmupServer() {
  // Perform a few warmup requests to eliminate cold start effects
  const warmupRequests = 3;
  const baseURL = process.env.BASE_URL || 'http://localhost:3000';

  console.log(`🔥 Warming up server with ${warmupRequests} requests...`);

  for (let i = 0; i < warmupRequests; i++) {
    try {
      const response = await fetch(`${baseURL}/`);
      console.log(`Warmup request ${i + 1}: ${response.status}`);
    } catch (error) {
      console.warn(`Warmup request ${i + 1} failed:`, error.message);
    }

    // Wait between requests
    await new Promise(resolve => setTimeout(resolve, 1000));
  }

  console.log('✅ Server warmup complete');
}
