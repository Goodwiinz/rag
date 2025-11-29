module.exports = {
  // The root of your source code, typically /src
  roots: ['<rootDir>/src'],

  // Test environment setup
  testEnvironment: 'jsdom',

  // Setup files
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.ts'],

  // Module file extensions for modules that your tests will use
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json', 'node'],

  // Transform files with these patterns
  transform: {
    '^.+\\.(ts|tsx)$': 'ts-jest',
  },

  // Module name mapping
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '\\.(css|less|scss|sass)$': 'identity-proxy'
  },

  // Patterns to ignore
  testPathIgnorePatterns: [
    '/node_modules/',
    '/build/',
    '/dist/',
    '/coverage/'
  ],

  // Coverage configuration
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/**/*.stories.{ts,tsx}',
    '!src/**/__tests__/**',
    '!src/**/__mocks__/**',
    '!src/setupTests.ts'
  ],

  // Coverage thresholds
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 70,
      lines: 70,
      statements: 70
    },
    // Component-specific thresholds
    './src/components/': {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    },
    // Utility-specific thresholds
    './src/utils/': {
      branches: 90,
      functions: 90,
      lines: 90,
      statements: 90
    },
    // Service-specific thresholds
    './src/services/': {
      branches: 85,
      functions: 85,
      lines: 85,
      statements: 85
    }
  },

  // Coverage reporters
  coverageReporters: [
    'text',
    'lcov',
    'html',
    'json-summary'
  ],

  // Coverage output directory
  coverageDirectory: 'coverage',

  // Test runner options
  testRunner: 'jest-runner',

  // Test match patterns
  testMatch: [
    '**/__tests__/**/*.(ts|tsx|js)',
    '**/*.(test|spec).(ts|tsx|js)'
  ],

  // Global setup and teardown
  globalSetup: undefined,
  globalTeardown: undefined,

  // Transform ignore patterns
  transformIgnorePatterns: [
    'node_modules/(?!(axios|react-query|@mui)/)',
    'build/',
    'dist/'
  ],

  // Test timeout
  testTimeout: 10000,

  // Verbose output
  verbose: false,

  // Test result processor - consolidated reporters
  reporters: [
    'default',
    ['jest-junit', { outputDirectory: 'coverage', outputName: 'junit.xml' }],
    ['jest-html-reporters', {
      publicPath: './coverage/html-report',
      filename: 'report.html',
      expand: true
    }]
  ],

  // Clear mocks between tests
  clearMocks: true,

  // Restore mocks after each test
  restoreMocks: true,

  // Error handling
  errorOnDeprecated: true,

  // Module caching
  cache: true,
  cacheDirectory: '<rootDir>/node_modules/.cache/jest',

  // Maximum number of concurrent workers
  maxWorkers: '50%',

  // Detect open handles
  detectOpenHandles: true,

  // Detect leaks
  detectLeaks: true,

  // Force exit after tests
  forceExit: false,

  // Run tests in watch mode
  watch: false,

  // Collect coverage only from changed files
  collectCoverageOnlyFrom: undefined,

  // Only run tests related to changed files
  watchPathIgnorePatterns: [
    '<rootDir>/node_modules/',
    '<rootDir>/build/',
    '<rootDir>/dist/',
    '<rootDir>/coverage/'
  ],

  // Custom test environment options
  testEnvironmentOptions: {
    url: 'http://localhost:3000'
  },

  // Custom matchers
  snapshotSerializers: []
};
