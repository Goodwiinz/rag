import { FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';

/**
 * Global teardown for E2E test suite
 *
 * Responsibilities:
 * - Clean up test data
 * - Generate test reports summary
 * - Archive test results
 * - Clean up temporary files
 */

async function globalTeardown(config: FullConfig) {
  console.log('🧹 Starting global E2E test teardown...');

  try {
    // Generate test summary report
    await generateTestSummary();

    // Clean up temporary test files
    await cleanupTempFiles();

    // Archive test results if needed
    if (process.env.E2E_ARCHIVE_RESULTS === 'true') {
      await archiveTestResults();
    }

    console.log('✅ Global teardown completed successfully');

  } catch (error) {
    console.error('❌ Global teardown failed:', error);
  }
}

/**
 * Generate a test summary report
 */
async function generateTestSummary() {
  const reportsPath = path.join(process.cwd(), 'test-results', 'reports');
  const resultsPath = path.join(reportsPath, 'results.json');

  try {
    if (fs.existsSync(resultsPath)) {
      const results = JSON.parse(fs.readFileSync(resultsPath, 'utf8'));

      const summary = {
        timestamp: new Date().toISOString(),
        total: results.suites?.reduce((acc: number, suite: any) => acc + suite.specs.length, 0) || 0,
        passed: results.suites?.reduce((acc: number, suite: any) =>
          acc + suite.specs.filter((spec: any) => spec.ok).length, 0) || 0,
        failed: results.suites?.reduce((acc: number, suite: any) =>
          acc + suite.specs.filter((spec: any) => !spec.ok).length, 0) || 0,
        duration: results.suites?.reduce((acc: number, suite: any) =>
          acc + suite.specs.reduce((suiteAcc: number, spec: any) => suiteAcc + (spec.tests?.[0]?.results?.[0]?.duration || 0), 0), 0) || 0
      };

      const summaryPath = path.join(reportsPath, 'summary.json');
      fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2));

      console.log(`📊 Test summary generated: ${summaryPath}`);
      console.log(`   Total tests: ${summary.total}`);
      console.log(`   Passed: ${summary.passed}`);
      console.log(`   Failed: ${summary.failed}`);
      console.log(`   Duration: ${(summary.duration / 1000).toFixed(2)}s`);
    }
  } catch (error) {
    console.warn('⚠️ Could not generate test summary:', error);
  }
}

/**
 * Clean up temporary test files
 */
async function cleanupTempFiles() {
  const tempDirs = [
    path.join(process.cwd(), 'test-data', 'uploads'),
    path.join(process.cwd(), 'test-data', 'temp')
  ];

  for (const tempDir of tempDirs) {
    try {
      if (fs.existsSync(tempDir)) {
        const files = fs.readdirSync(tempDir);
        for (const file of files) {
          const filePath = path.join(tempDir, file);
          const stats = fs.statSync(filePath);

          // Remove files older than 1 hour
          if (Date.now() - stats.mtime.getTime() > 3600000) {
            if (stats.isDirectory()) {
              fs.rmSync(filePath, { recursive: true });
            } else {
              fs.unlinkSync(filePath);
            }
          }
        }
        console.log(`🧹 Cleaned temporary files in: ${tempDir}`);
      }
    } catch (error) {
      console.warn(`⚠️ Could not clean directory ${tempDir}:`, error);
    }
  }
}

/**
 * Archive test results for long-term storage
 */
async function archiveTestResults() {
  const archivePath = path.join(process.cwd(), 'test-results', 'archives');
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const archiveName = `e2e-results-${timestamp}`;

  try {
    if (!fs.existsSync(archivePath)) {
      fs.mkdirSync(archivePath, { recursive: true });
    }

    // In a real implementation, you might use a library like archiver
    // For now, we'll just create a marker file
    const markerPath = path.join(archivePath, `${archiveName}.json`);
    const archiveInfo = {
      timestamp: new Date().toISOString(),
      testResultsPath: path.join(process.cwd(), 'test-results'),
      environment: process.env.NODE_ENV || 'test',
      ci: process.env.CI === 'true'
    };

    fs.writeFileSync(markerPath, JSON.stringify(archiveInfo, null, 2));
    console.log(`📦 Archive marker created: ${markerPath}`);

  } catch (error) {
    console.warn('⚠️ Could not archive test results:', error);
  }
}

export default globalTeardown;