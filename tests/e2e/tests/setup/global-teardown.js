const path = require('path');
const fs = require('fs').promises;

/**
 * Global teardown for E2E tests
 * Simplified version that cleans up test files
 */
async function globalTeardown(config) {
  console.log('🧹 Starting global E2E test teardown...');

  try {
    // Clean up test directories
    await cleanupTestFiles();
    console.log('✅ Global E2E test teardown completed successfully');
  } catch (error) {
    console.error('❌ Global E2E test teardown failed:', error);
  }
}

async function cleanupTestFiles() {
  try {
    const testUploadsDir = path.join(__dirname, '../../test-uploads');
    await fs.rm(testUploadsDir, { recursive: true, force: true });
  } catch (error) {
    // Directory might not exist
  }
}

module.exports = globalTeardown;
