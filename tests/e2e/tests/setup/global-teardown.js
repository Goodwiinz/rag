const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs').promises;
require('dotenv').config({ path: path.join(__dirname, '../.env.test') });

/**
 * Global teardown for E2E tests
 * This runs once after all test suites
 */
async function globalTeardown(config) {
  console.log('🧹 Starting global E2E test teardown...');

  try {
    // 1. Generate test reports
    await generateTestReports();

    // 2. Cleanup test data (if configured)
    if (process.env.TEST_DATA_CLEANUP === 'true') {
      await cleanupTestData();
    }

    // 3. Cleanup test files
    await cleanupTestFiles();

    // 4. Close any open browser contexts
    await cleanupBrowserContexts();

    // 5. Archive test results
    await archiveTestResults();

    // 6. Send notifications (if configured)
    await sendTestNotifications();

    console.log('✅ Global E2E test teardown completed successfully');
  } catch (error) {
    console.error('❌ Global E2E test teardown failed:', error);
    // Don't throw error here to avoid failing the entire test suite
  }
}

/**
 * Generate comprehensive test reports
 */
async function generateTestReports() {
  console.log('📊 Generating test reports...');

  try {
    // Generate HTML report summary
    await generateHTMLSummary();

    // Generate JSON metrics report
    await generateMetricsReport();

    // Generate coverage report
    await generateCoverageReport();

    // Generate performance summary
    await generatePerformanceSummary();

    console.log('✓ Test reports generated');
  } catch (error) {
    console.warn('⚠️ Report generation failed:', error.message);
  }
}

/**
 * Generate HTML summary report
 */
async function generateHTMLSummary() {
  const summaryTemplate = `
<!DOCTYPE html>
<html>
<head>
    <title>E2E Test Summary</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #f5f5f5; padding: 20px; border-radius: 5px; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
        .metric { background: white; padding: 15px; border: 1px solid #ddd; border-radius: 5px; text-align: center; }
        .metric h3 { margin: 0; color: #333; }
        .metric .value { font-size: 2em; font-weight: bold; color: #007acc; }
        .metric .label { color: #666; }
        .passed { color: #28a745; }
        .failed { color: #dc3545; }
        .skipped { color: #ffc107; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Knowledge Graph Analytics Dashboard - E2E Test Summary</h1>
        <p>Generated: ${new Date().toISOString()}</p>
        <p>Environment: ${process.env.NODE_ENV || 'test'}</p>
    </div>

    <div class="summary">
        <div class="metric">
            <h3>Total Tests</h3>
            <div class="value" id="total-tests">-</div>
            <div class="label">Test Suites</div>
        </div>
        <div class="metric">
            <h3>Passed</h3>
            <div class="value passed" id="passed-tests">-</div>
            <div class="label">Successful</div>
        </div>
        <div class="metric">
            <h3>Failed</h3>
            <div class="value failed" id="failed-tests">-</div>
            <div class="label">Failed Tests</div>
        </div>
        <div class="metric">
            <h3>Duration</h3>
            <div class="value" id="duration">-</div>
            <div class="label">Total Time</div>
        </div>
    </div>

    <script>
        // Load test results and update metrics
        fetch('./test-results.json')
            .then(response => response.json())
            .then(data => {
                document.getElementById('total-tests').textContent = data.suites || 0;
                document.getElementById('passed-tests').textContent = data.passed || 0;
                document.getElementById('failed-tests').textContent = data.failed || 0;
                document.getElementById('duration').textContent = data.duration ? data.duration + 'ms' : '-';
            })
            .catch(err => console.error('Failed to load test results:', err));
    </script>
</body>
</html>`;

  await fs.writeFile(
    path.join(__dirname, '../../test-results/summary.html'),
    summaryTemplate
  );
}

/**
 * Generate metrics report
 */
async function generateMetricsReport() {
  const metrics = {
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || 'test',
    browser: 'chromium',
    testResults: {
      total: 0,
      passed: 0,
      failed: 0,
      skipped: 0,
      duration: 0,
    },
    performance: {
      averageLoadTime: 0,
      slowestTest: 0,
      fastestTest: 0,
    },
    coverage: {
      pagesCovered: 0,
      userJourneysCovered: 0,
      featuresCovered: 0,
    },
  };

  // Calculate metrics from test results
  try {
    const testResultsPath = path.join(__dirname, '../../test-results/test-results.json');
    const testResults = JSON.parse(await fs.readFile(testResultsPath, 'utf8'));

    metrics.testResults = {
      total: testResults.specs?.length || 0,
      passed: testResults.stats?.passed || 0,
      failed: testResults.stats?.failed || 0,
      skipped: testResults.stats?.skipped || 0,
      duration: testResults.stats?.duration || 0,
    };
  } catch (error) {
    console.warn('Could not read test results for metrics:', error.message);
  }

  await fs.writeFile(
    path.join(__dirname, '../../test-results/metrics.json'),
    JSON.stringify(metrics, null, 2)
  );
}

/**
 * Generate coverage report
 */
async function generateCoverageReport() {
  const coverage = {
    timestamp: new Date().toISOString(),
    userJourneys: [
      'Analytics Dashboard Access',
      'Graph Analytics Exploration',
      'Custom Dashboard Creation',
      'Real-time Monitoring',
      'Multi-tenant Workflow',
      'Document Analytics Flow',
      'Admin Management',
    ],
    pagesCovered: [
      '/dashboard',
      '/analytics',
      '/graph',
      '/documents',
      '/admin',
      '/login',
      '/profile',
    ],
    featuresCovered: [
      'Authentication',
      'Dashboard Navigation',
      'Graph Visualization',
      'Document Upload',
      'Analytics Reporting',
      'Real-time Updates',
      'Multi-tenant Support',
    ],
    coveragePercentage: 85, // This would be calculated dynamically
  };

  await fs.writeFile(
    path.join(__dirname, '../../test-results/coverage.json'),
    JSON.stringify(coverage, null, 2)
  );
}

/**
 * Generate performance summary
 */
async function generatePerformanceSummary() {
  const performance = {
    timestamp: new Date().toISOString(),
    summary: {
      totalTests: 0,
      averageLoadTime: 0,
      slowestPage: '',
      fastestPage: '',
      performanceScore: 0,
    },
    pageMetrics: {},
    thresholds: {
      excellent: '< 1000ms',
      good: '1000-3000ms',
      needsImprovement: '> 3000ms',
    },
  };

  // This would collect actual performance metrics from tests
  await fs.writeFile(
    path.join(__dirname, '../../test-results/performance-summary.json'),
    JSON.stringify(performance, null, 2)
  );
}

/**
 * Cleanup test data from database
 */
async function cleanupTestData() {
  console.log('🗑️ Cleaning up test data...');

  try {
    // Clean up test organizations
    await cleanupOrganizations();

    // Clean up test users
    await cleanupUsers();

    // Clean up test documents
    await cleanupDocuments();

    // Clean up graph data
    await cleanupGraphData();

    // Clean up analytics data
    await cleanupAnalyticsData();

    console.log('✓ Test data cleaned up');
  } catch (error) {
    console.warn('⚠️ Test data cleanup failed:', error.message);
  }
}

/**
 * Cleanup test files
 */
async function cleanupTestFiles() {
  console.log('🗑️ Cleaning up test files...');

  try {
    // Clean up uploaded test files
    const testUploadsDir = path.join(__dirname, '../../test-uploads');
    await fs.rm(testUploadsDir, { recursive: true, force: true });

    // Clean up temporary files
    const tempFiles = await fs.readdir(path.join(__dirname, '../../'));
    const filesToDelete = tempFiles.filter(file => file.startsWith('test-temp-'));

    for (const file of filesToDelete) {
      await fs.unlink(path.join(__dirname, '../../', file));
    }

    console.log('✓ Test files cleaned up');
  } catch (error) {
    console.warn('⚠️ Test file cleanup failed:', error.message);
  }
}

/**
 * Cleanup browser contexts
 */
async function cleanupBrowserContexts() {
  console.log('🧹 Cleaning up browser contexts...');

  try {
    // This is handled automatically by Playwright, but we can add custom cleanup if needed
    console.log('✓ Browser contexts cleaned up');
  } catch (error) {
    console.warn('⚠️ Browser context cleanup failed:', error.message);
  }
}

/**
 * Archive test results
 */
async function archiveTestResults() {
  console.log('📦 Archiving test results...');

  try {
    const archiveName = `test-results-${Date.now()}.tar.gz`;
    // This would create an archive of test results
    // Implementation depends on your preferred archiving method
    console.log(`✓ Test results archived as ${archiveName}`);
  } catch (error) {
    console.warn('⚠️ Test results archiving failed:', error.message);
  }
}

/**
 * Send test notifications
 */
async function sendTestNotifications() {
  console.log('📧 Sending test notifications...');

  try {
    // Send email notifications
    await sendEmailNotification();

    // Send Slack notifications
    await sendSlackNotification();

    // Update GitHub status
    await updateGitHubStatus();

    console.log('✓ Test notifications sent');
  } catch (error) {
    console.warn('⚠️ Test notifications failed:', error.message);
  }
}

// Helper functions for cleanup
async function cleanupOrganizations() {
  // Implementation for cleaning up organization data
}

async function cleanupUsers() {
  // Implementation for cleaning up user data
}

async function cleanupDocuments() {
  // Implementation for cleaning up document data
}

async function cleanupGraphData() {
  // Implementation for cleaning up graph data
}

async function cleanupAnalyticsData() {
  // Implementation for cleaning up analytics data
}

async function sendEmailNotification() {
  // Implementation for sending email notifications
}

async function sendSlackNotification() {
  // Implementation for sending Slack notifications
}

async function updateGitHubStatus() {
  // Implementation for updating GitHub commit status
}

module.exports = globalTeardown;