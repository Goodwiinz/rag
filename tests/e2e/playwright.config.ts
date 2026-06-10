import { defineConfig, devices } from "@playwright/test";
import path from "path";
import dotenv from "dotenv";

// Load environment variables
dotenv.config({ path: path.join(__dirname, ".env.test") });

export default defineConfig({
  testDir: "./tests",

  /* Global test configuration */
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : 4,
  reporter: [
    ["html", { outputFolder: "playwright-report/html" }],
    ["json", { outputFile: "test-results/test-results.json" }],
    ["junit", { outputFile: "test-results/test-results.xml" }],
    ["list"],
    ["line"],
    ["github"],
  ],

  /* Global test timeout */
  timeout: 60 * 1000, // 60 seconds
  expect: {
    timeout: 10 * 1000, // 10 seconds
  },

  /* Global setup and teardown */
  globalSetup: require.resolve("./tests/setup/global-setup.js"),
  globalTeardown: require.resolve("./tests/setup/global-teardown.js"),

  /* Test artifacts */
  use: {
    /* Base URL for tests */
    baseURL: process.env.BASE_URL || "http://localhost:3000",

    /* Browser configuration */
    headless: process.env.HEADLESS !== "false",
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,
    video: "retain-on-failure",
    screenshot: {
      mode: "only-on-failure",
      fullPage: true,
    },
    trace: "retain-on-failure",

    /* Test context */
    actionTimeout: 10 * 1000,
    navigationTimeout: 30 * 1000,

    /* Network configuration */
    bypassCSP: true,
    userAgent: "RAG-E2E-Tests/1.0",

    /* Locale and timezone */
    locale: "en-US",
    timezoneId: "America/New_York",

    /* Color scheme and reduced motion */
    colorScheme: "light",
    reducedMotion: "reduce",
  },

  /* Configure projects for major browsers */
  projects: [
    /* Desktop browsers */
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
    },

    /* Mobile browsers */
    {
      name: "Mobile Chrome",
      use: { ...devices["Pixel 5"] },
      testIgnore: ["**/admin/**", "**/desktop-only/**"],
    },
    {
      name: "Mobile Safari",
      use: { ...devices["iPhone 12"] },
      testIgnore: ["**/admin/**", "**/desktop-only/**"],
    },
    {
      name: "Tablet",
      use: { ...devices["iPad Pro"] },
      testIgnore: ["**/mobile-only/**"],
    },

    /* Specialized test suites */
    {
      name: "accessibility",
      testMatch: "**/accessibility/**/*.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
      },
    },

    {
      name: "visual-regression",
      testMatch: "**/visual/**/*.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        screenshot: {
          mode: "only-on-failure",
          fullPage: true,
          animations: "disabled",
        },
      },
    },

    {
      name: "performance",
      testMatch: "**/performance/**/*.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: {
          args: [
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
          ],
        },
      },
    },

    {
      name: "multi-tenant",
      testMatch: "**/multi-tenant/**/*.spec.ts",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],

  /* Web server - only used locally, not in CI */
  webServer: process.env.CI
    ? undefined
    : {
        command: "npm run dev",
        url: "http://localhost:3000",
        cwd: "../../frontend",
        reuseExistingServer: true,
        timeout: 120 * 1000,
        stdout: "pipe",
        stderr: "pipe",
      },

  /* Output directory */
  outputDir: "test-results/",

  /* Test metadata */
  metadata: {
    "Test Environment": process.env.NODE_ENV || "test",
    "Test Suite": "Knowledge Graph Analytics Dashboard E2E",
    "Browser Version": process.env.BROWSER_VERSION || "latest",
    OS: process.platform,
    "Test Date": new Date().toISOString(),
  },
});
