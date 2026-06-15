const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs').promises;
require('dotenv').config({ path: path.join(__dirname, '../.env.test') });

/**
 * Global setup for E2E tests
 * Simplified version that just creates directories and verifies services
 */
async function globalSetup(config) {
  console.log('🚀 Starting global E2E test setup...');

  try {
    // 1. Create test directories
    await createTestDirectories();

    // 2. Verify services are running
    await verifyServices();

    console.log('✅ Global E2E test setup completed successfully');
  } catch (error) {
    console.error('❌ Global E2E test setup failed:', error);
    // Don't throw - let tests handle service unavailability
  }
}

async function createTestDirectories() {
  const directories = [
    'test-results',
    'test-results/screenshots',
    'test-results/videos',
    'test-results/traces',
    'test-results/html-report',
    'test-results/json-report',
    'auth-states',
  ];

  for (const dir of directories) {
    try {
      await fs.mkdir(dir, { recursive: true });
    } catch (error) {
      // Directory already exists
    }
  }
}

async function verifyServices() {
  const services = [
    { name: 'Frontend', url: process.env.BASE_URL || 'http://localhost:3000' },
    { name: 'Backend API', url: process.env.API_BASE_URL || 'http://localhost:8000' },
  ];

  for (const service of services) {
    try {
      const response = await fetch(service.url, { method: 'GET' });
      if (response.ok) {
        console.log(`✓ ${service.name} is running`);
      }
    } catch (error) {
      console.warn(`⚠️ Could not verify ${service.name}: ${error.message}`);
    }
  }
}

module.exports = globalSetup;
