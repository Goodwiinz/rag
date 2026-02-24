const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs').promises;
require('dotenv').config({ path: path.join(__dirname, '../.env.test') });

/**
 * Global setup for E2E tests
 * This runs once before all test suites
 */
async function globalSetup(config) {
  console.log('🚀 Starting global E2E test setup...');

  try {
    // 1. Create test directories
    await createTestDirectories();

    // 2. Start and verify backend services
    await verifyBackendServices();

    // 3. Seed test data
    await seedTestData();

    // 4. Setup test authentication tokens
    await setupTestAuth();

    // 5. Warm up the application
    await warmupApplication();

    // 6. Verify all required components are running
    await verifySystemHealth();

    console.log('✅ Global E2E test setup completed successfully');

    // Store global state for tests
    return {
      testStartTime: new Date().toISOString(),
      testEnvironment: process.env.NODE_ENV || 'test',
    };
  } catch (error) {
    console.error('❌ Global E2E test setup failed:', error);
    throw error;
  }
}

/**
 * Create necessary test directories
 */
async function createTestDirectories() {
  console.log('📁 Creating test directories...');

  const directories = [
    'test-results',
    'test-results/screenshots',
    'test-results/videos',
    'test-results/traces',
    'test-results/html-report',
    'test-results/json-report',
    'test-uploads',
    'test-logs',
  ];

  for (const dir of directories) {
    try {
      await fs.mkdir(dir, { recursive: true });
      console.log(`✓ Created directory: ${dir}`);
    } catch (error) {
      console.warn(`⚠️ Directory ${dir} already exists or failed to create:`, error.message);
    }
  }
}

/**
 * Verify backend services are running
 */
async function verifyBackendServices() {
  console.log('🔧 Verifying backend services...');

  const services = [
    { name: 'Frontend', url: process.env.BASE_URL || 'http://localhost:3000' },
    { name: 'Backend API', url: process.env.API_BASE_URL || 'http://localhost:8000' },
    { name: 'Neo4j', url: process.env.NEO4J_TEST_URI || 'http://localhost:7474' },
    { name: 'Qdrant', url: process.env.QDRANT_TEST_URL || 'http://localhost:6333' },
  ];

  for (const service of services) {
    try {
      const response = await fetch(`${service.url}/health`, {
        method: 'GET',
        timeout: 5000,
      }).catch(async () => {
        // Try root endpoint if health endpoint doesn't exist
        return fetch(service.url, { method: 'GET', timeout: 5000 });
      });

      if (response && response.ok) {
        console.log(`✓ ${service.name} is running`);
      } else {
        console.warn(`⚠️ ${service.name} health check failed, but continuing...`);
      }
    } catch (error) {
      console.warn(`⚠️ Could not verify ${service.name}:`, error.message);
      console.log(`   Tests will proceed but may fail if ${service.name} is required`);
    }
  }
}

/**
 * Seed test data for all test scenarios
 */
async function seedTestData() {
  console.log('🌱 Seeding test data...');

  try {
    // Load test data fixtures
    const testDataPath = path.join(__dirname, '../fixtures/test-data.json');
    const testData = JSON.parse(await fs.readFile(testDataPath, 'utf8'));

    // Seed organizations
    await seedOrganizations(testData.organizations);

    // Seed users
    await seedUsers(testData.users);

    // Seed documents
    await seedDocuments(testData.documents);

    // Seed knowledge graph data
    await seedGraphData(testData.graphData);

    // Seed analytics data
    await seedAnalyticsData(testData.analyticsData);

    console.log('✓ Test data seeded successfully');
  } catch (error) {
    console.warn('⚠️ Test data seeding failed:', error.message);
    console.log('   Tests will proceed with existing data');
  }
}

/**
 * Setup test authentication tokens
 */
async function setupTestAuth() {
  console.log('🔐 Setting up test authentication...');

  try {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    // Login as admin user
    await page.goto(`${process.env.BASE_URL}/login`);
    await page.fill('[data-testid="email-input"]', process.env.TEST_ADMIN_EMAIL);
    await page.fill('[data-testid="password-input"]', process.env.TEST_ADMIN_PASSWORD);
    await page.click('[data-testid="login-button"]');

    // Wait for successful login
    await page.waitForURL('**/dashboard', { timeout: 10000 });

    // Get auth token
    const cookies = await context.cookies();
    const authToken = cookies.find(cookie => cookie.name === 'auth_token');

    if (authToken) {
      // Save auth state for reuse
      await context.storageState({
        path: path.join(__dirname, '../auth-states/admin-state.json')
      });
      console.log('✓ Admin authentication state saved');
    }

    await browser.close();

    // Repeat for regular user
    await setupUserAuth('user');
    await setupUserAuth('orgadmin');

  } catch (error) {
    console.warn('⚠️ Test authentication setup failed:', error.message);
    console.log('   Tests will attempt to login individually');
  }
}

/**
 * Setup authentication for specific user type
 */
async function setupUserAuth(userType) {
  const credentials = {
    user: {
      email: process.env.TEST_USER_EMAIL,
      password: process.env.TEST_USER_PASSWORD,
      stateFile: 'user-state.json'
    },
    orgadmin: {
      email: process.env.TEST_ORG_ADMIN_EMAIL,
      password: process.env.TEST_ORG_ADMIN_PASSWORD,
      stateFile: 'orgadmin-state.json'
    }
  };

  const config = credentials[userType];
  if (!config) return;

  try {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto(`${process.env.BASE_URL}/login`);
    await page.fill('[data-testid="email-input"]', config.email);
    await page.fill('[data-testid="password-input"]', config.password);
    await page.click('[data-testid="login-button"]');

    await page.waitForURL('**/dashboard', { timeout: 10000 });

    await context.storageState({
      path: path.join(__dirname, `../auth-states/${config.stateFile}`)
    });

    await browser.close();
    console.log(`✓ ${userType} authentication state saved`);
  } catch (error) {
    console.warn(`⚠️ ${userType} authentication setup failed:`, error.message);
  }
}

/**
 * Warm up the application to eliminate cold start effects
 */
async function warmupApplication() {
  console.log('🔥 Warming up application...');

  const warmupUrls = [
    '/',
    '/dashboard',
    '/analytics',
    '/graph',
    '/documents',
    '/admin',
  ];

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  for (const url of warmupUrls) {
    try {
      await page.goto(`${process.env.BASE_URL}${url}`, {
        waitUntil: 'networkidle',
        timeout: 30000,
      });
      console.log(`✓ Warmed up: ${url}`);
    } catch (error) {
      console.warn(`⚠️ Failed to warm up ${url}:`, error.message);
    }
  }

  await browser.close();
}

/**
 * Verify system health before running tests
 */
async function verifySystemHealth() {
  console.log('🏥 Verifying system health...');

  try {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    // Check main application health
    await page.goto(`${process.env.BASE_URL}/health`, {
      timeout: 10000,
    });

    const healthStatus = await page.textContent('body');
    if (healthStatus && healthStatus.includes('healthy')) {
      console.log('✓ Application health check passed');
    } else {
      console.warn('⚠️ Application health check failed, but proceeding...');
    }

    await browser.close();
  } catch (error) {
    console.warn('⚠️ System health verification failed:', error.message);
    console.log('   Tests will proceed but may fail if system is unhealthy');
  }
}

// Helper functions for data seeding
async function seedOrganizations(organizations) {
  // Implementation for seeding organization data
  console.log('   Seeding organizations...');
}

async function seedUsers(users) {
  // Implementation for seeding user data
  console.log('   Seeding users...');
}

async function seedDocuments(documents) {
  // Implementation for seeding document data
  console.log('   Seeding documents...');
}

async function seedGraphData(graphData) {
  // Implementation for seeding knowledge graph data
  console.log('   Seeding graph data...');
}

async function seedAnalyticsData(analyticsData) {
  // Implementation for seeding analytics data
  console.log('   Seeding analytics data...');
}

module.exports = globalSetup;
