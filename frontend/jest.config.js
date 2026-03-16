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
  // Include sanity tests, component unit tests, service tests, and store tests
  testMatch: [
    '<rootDir>/src/__tests__/sanity.test.ts',
    '<rootDir>/src/components/**/__tests__/**/*.test.{ts,tsx}',
    '<rootDir>/src/services/__tests__/**/*.test.{ts,tsx}',
    '<rootDir>/src/store/__tests__/**/*.test.{ts,tsx}',
    '<rootDir>/src/hooks/__tests__/**/*.test.{ts,tsx}',
    '<rootDir>/src/utils/__tests__/**/*.test.{ts,tsx}',
  ],

  // Ignore Playwright e2e and heavy integration suites in Jest
  testPathIgnorePatterns: [
    '/node_modules/',
    '/build/',
    '/dist/',
    '/coverage/',
    '<rootDir>/e2e/',
    '<rootDir>/src/integration/',
    '<rootDir>/src/__tests__/App.routing.test.tsx',
    '/\\.worktrees/',
    '/\\.venv/',
  ],

  moduleNameMapper: {
    '^@test/(.*)$': '<rootDir>/src/test/$1',
    '^@/(.*)$': '<rootDir>/src/$1',
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
    // Removed manual mappings for react/react-dom/react-router-dom to rely on standard resolution
    // which should work in both local and CI environments if dependencies are installed correctly.
  },

  // Reporters
  reporters: [
    'default',
    ['jest-junit', { outputDirectory: 'coverage', outputName: 'junit.xml' }],
    [
      'jest-html-reporters',
      {
        publicPath: './coverage/html-report',
        filename: 'report.html',
        expand: true,
      },
    ],
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
    '<rootDir>/coverage/',
  ],

  testEnvironmentOptions: {
    url: 'http://localhost:3000',
  },

  // Coverage configuration
  collectCoverageFrom: [
    'src/components/**/*.{ts,tsx}',
    'src/hooks/**/*.{ts,tsx}',
    'src/services/**/*.{ts,tsx}',
    'src/store/**/*.{ts,tsx}',
    'src/utils/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/**/*.stories.{ts,tsx}',
    '!src/**/index.{ts,tsx}',
    '!src/components/ui/**',
  ],
  coverageThreshold: {
    global: {
      statements: 8,
      branches: 7,
      functions: 7,
      lines: 9,
    },
  },
};

// createJestConfig is exported this way to ensure that next/jest can load the Next.js config
// We override testPathIgnorePatterns after next/jest processes the config to prevent
// next/jest from dropping our custom ignore patterns.
const baseConfig = createJestConfig(customJestConfig);
module.exports = async () => {
  const config = await baseConfig();
  config.testPathIgnorePatterns = [
    '/node_modules/',
    '/\\.worktrees/',
    '/\\.venv/',
    '/build/',
    '/dist/',
    '/coverage/',
    '/e2e/',
    '/src/integration/',
    'App\\.routing\\.test\\.tsx$',
  ];
  return config;
};
