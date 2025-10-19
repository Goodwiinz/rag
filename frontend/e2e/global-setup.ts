import { chromium, FullConfig } from '@playwright/test';
import path from 'path';
import fs from 'fs';

/**
 * Global setup for E2E test suite
 *
 * Responsibilities:
 * - Start backend services if needed
 * - Create test data directory structure
 * - Seed test database with initial data
 * - Generate test fixtures
 * - Verify all services are ready
 */

async function globalSetup(config: FullConfig) {
  console.log('🚀 Starting global E2E test setup...');

  // Create necessary directories
  const directories = [
    'test-results',
    'test-results/reports',
    'test-results/screenshots',
    'test-results/videos',
    'test-results/traces',
    'test-data',
    'test-data/files',
    'test-data/uploads',
    'test-data/fixtures'
  ];

  for (const dir of directories) {
    const fullPath = path.join(process.cwd(), dir);
    if (!fs.existsSync(fullPath)) {
      fs.mkdirSync(fullPath, { recursive: true });
      console.log(`📁 Created directory: ${fullPath}`);
    }
  }

  // Verify application is running
  const baseURL = config.webServer?.url || 'http://localhost:3000';
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log(`🔍 Checking application availability at ${baseURL}...`);

    // Wait for application to be ready with retries
    let attempts = 0;
    const maxAttempts = 30;
    let isReady = false;

    while (attempts < maxAttempts && !isReady) {
      try {
        const response = await page.goto(baseURL, {
          timeout: 5000
        });

        if (response && response.ok()) {
          // Check if the page is actually loaded
          const title = await page.title();
          if (title.includes('RAG') || title.includes('Multimodal')) {
            isReady = true;
            console.log('✅ Application is ready for testing');
          }
        }
      } catch (error) {
        attempts++;
        console.log(`⏳ Waiting for application... (attempt ${attempts}/${maxAttempts})`);
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
    }

    if (!isReady) {
      throw new Error(`Application not ready after ${maxAttempts} attempts`);
    }

    // Create test user if authentication is enabled
    if (process.env.E2E_CREATE_TEST_USER === 'true') {
      console.log('👤 Creating test user...');
      await createTestUser(page, baseURL);
    }

    // Verify backend services
    await verifyBackendServices(baseURL);

    console.log('✅ Global setup completed successfully');

  } catch (error) {
    console.error('❌ Global setup failed:', error);
    throw error;
  } finally {
    await context.close();
    await browser.close();
  }
}

/**
 * Create a test user for E2E testing
 */
async function createTestUser(page: any, baseURL: string) {
  try {
    // Navigate to registration page
    await page.goto(`${baseURL}/register`);

    // Fill registration form
    await page.fill('[data-testid="email-input"]', 'test@example.com');
    await page.fill('[data-testid="password-input"]', 'testpassword123');
    await page.fill('[data-testid="confirm-password-input"]', 'testpassword123');
    await page.fill('[data-testid="name-input"]', 'Test User');

    // Submit form
    await page.click('[data-testid="register-button"]');

    // Wait for successful registration
    await page.waitForURL(`${baseURL}/login`, { timeout: 10000 });

    console.log('✅ Test user created successfully');
  } catch (error) {
    console.warn('⚠️ Could not create test user (may already exist or registration disabled):', error);
  }
}

/**
 * Verify that backend services are responding
 */
async function verifyBackendServices(baseURL: string) {
  const services = [
    { name: 'API Gateway', url: `${baseURL.replace(':3000', ':8000')}/health` },
    { name: 'Document Service', url: `${baseURL.replace(':3000', ':8001')}/health` },
    { name: 'Search Service', url: `${baseURL.replace(':3000', ':8002')}/health` },
    { name: 'Graph Service', url: `${baseURL.replace(':3000', ':8003')}/health` },
    { name: 'Evaluation Service', url: `${baseURL.replace(':3000', ':8004')}/health` }
  ];

  for (const service of services) {
    try {
      const response = await fetch(service.url, {
        method: 'GET',
        timeout: 5000
      });

      if (response.ok) {
        console.log(`✅ ${service.name} is healthy`);
      } else {
        console.warn(`⚠️ ${service.name} responded with status: ${response.status}`);
      }
    } catch (error) {
      console.warn(`⚠️ Could not reach ${service.name}:`, error.message);
    }
  }
}

export default globalSetup;