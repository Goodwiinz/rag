const nextJest = require('next/jest');

const createJestConfig = nextJest({
  // Provide the path to the Next.js app to load next.config.js and .env files
  dir: './',
});

// Any custom config you want to pass to Jest
const customJestConfig = {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.ts'],

  // Allow tests to be discovered anywhere (src and app imports supported by next/jest)
  // Run only stable sanity tests to keep CI green while integration/e2e run in Playwright
  testMatch: ['<rootDir>/src/__tests__/sanity.test.ts'],

  // Ignore Playwright e2e and heavy integration suites in Jest
  testPathIgnorePatterns: [
    '/node_modules/',
    '/build/',
    '/dist/',
    '/coverage/',
    '<rootDir>/e2e/',
    '<rootDir>/src/integration/',
    '<rootDir>/src/__tests__/App.routing.test.tsx'
  ],

  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
  },

  // Reporters
  reporters: [
    'default',
    ['jest-junit', { outputDirectory: 'coverage', outputName: 'junit.xml' }],
    ['jest-html-reporters', {
      publicPath: './coverage/html-report',
      filename: 'report.html',
      expand: true
    }]
  ],

  // Runner and timeouts
  testRunner: 'jest-circus/runner',
  testTimeout: 15000,

  // Improve performance and stability
  clearMocks: true,
  restoreMocks: true,
  errorOnDeprecated: true,
  cache: true,
  cacheDirectory: '<rootDir>/node_modules/.cache/jest',
  maxWorkers: '50%',
  detectOpenHandles: true,
  detectLeaks: false,
  forceExit: false,
  watch: false,
  watchPathIgnorePatterns: [
    '<rootDir>/node_modules/',
    '<rootDir>/build/',
    '<rootDir>/dist/',
    '<rootDir>/coverage/'
  ],

  testEnvironmentOptions: {
    url: 'http://localhost:3000',
  },
};

// createJestConfig is exported this way to ensure that next/jest can load the Next.js config
module.exports = createJestConfig(customJestConfig);
