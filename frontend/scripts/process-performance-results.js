#!/usr/bin/env node

/**
 * Process performance test results and generate summary
 */

const fs = require('fs');
const path = require('path');

function processPerformanceResults(resultsPath) {
  try {
    const results = JSON.parse(fs.readFileSync(resultsPath, 'utf8'));

    // Extract performance metrics from test results
    const metrics = {
      totalTests: results.suites?.reduce((acc, suite) => acc + suite.specs.length, 0) || 0,
      passedTests: results.suites?.reduce((acc, suite) =>
        acc + suite.specs.filter(spec => spec.ok).length, 0) || 0,
      failedTests: results.suites?.reduce((acc, suite) =>
        acc + suite.specs.filter(spec => !spec.ok).length, 0) || 0,
      performanceMetrics: []
    };

    // Collect performance data from test results
    results.suites?.forEach(suite => {
      suite.specs.forEach(spec => {
        if (spec.tests && spec.tests[0]) {
          const testResult = spec.tests[0].results[0];
          const duration = testResult.duration;

          metrics.performanceMetrics.push({
            test: spec.title,
            duration: duration,
            status: spec.ok ? 'passed' : 'failed',
            suite: suite.title
          });
        }
      });
    });

    // Calculate performance statistics
    const durations = metrics.performanceMetrics
      .filter(m => m.status === 'passed')
      .map(m => m.duration);

    const stats = durations.length > 0 ? {
      average: durations.reduce((a, b) => a + b, 0) / durations.length,
      min: Math.min(...durations),
      max: Math.max(...durations),
      median: durations.sort((a, b) => a - b)[Math.floor(durations.length / 2)]
    } : { average: 0, min: 0, max: 0, median: 0 };

    metrics.statistics = stats;

    // Check for performance regressions
    const slowTests = metrics.performanceMetrics
      .filter(m => m.duration > 5000) // Tests taking more than 5 seconds
      .sort((a, b) => b.duration - a.duration);

    const summary = {
      ...metrics,
      slowTests: slowTests.slice(0, 10), // Top 10 slowest tests
      summary: `Performance tests: ${metrics.passedTests}/${metrics.totalTests} passed. Average duration: ${stats.average.toFixed(0)}ms`
    };

    // Generate performance report
    const reportPath = path.dirname(resultsPath) + '/performance-report.html';
    generatePerformanceReport(summary, reportPath);

    // Log summary to console
    console.log(`📊 Performance Test Results:`);
    console.log(`  Total tests: ${metrics.totalTests}`);
    console.log(`  Passed: ${metrics.passedTests}`);
    console.log(`  Failed: ${metrics.failedTests}`);
    console.log(`  Average duration: ${stats.average.toFixed(0)}ms`);
    console.log(`  Slowest test: ${stats.max.toFixed(0)}ms`);

    if (slowTests.length > 0) {
      console.log(`\n🐌 Slowest tests (>5s):`);
      slowTests.slice(0, 5).forEach(test => {
        console.log(`  - ${test.test}: ${test.duration.toFixed(0)}ms`);
      });
    }

    return summary;
  } catch (error) {
    console.error('Error processing performance results:', error);
    return {
      totalTests: 0,
      passedTests: 0,
      failedTests: 0,
      performanceMetrics: [],
      summary: 'Error processing performance results'
    };
  }
}

function generatePerformanceReport(data, reportPath) {
  const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Performance Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f5f5f5; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .metric { background-color: #e3f2fd; border: 1px solid #2196f3; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .slow-test { background-color: #fff3e0; border: 1px solid #ff9800; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .chart { margin: 20px 0; }
        .status-passed { color: #4caf50; }
        .status-failed { color: #f44336; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f5f5f5; }
        .progress-bar { background-color: #e0e0e0; height: 20px; border-radius: 10px; overflow: hidden; }
        .progress-fill { background-color: #4caf50; height: 100%; transition: width 0.3s ease; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Performance Test Report</h1>
        <p>Generated: ${new Date().toISOString()}</p>
        <div class="progress-bar">
            <div class="progress-fill" style="width: ${(data.passedTests / data.totalTests * 100).toFixed(1)}%"></div>
        </div>
        <p>Test Pass Rate: ${(data.passedTests / data.totalTests * 100).toFixed(1)}%</p>
    </div>

    <div class="metric">
        <h2>Performance Statistics</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Total Tests</td><td>${data.totalTests}</td></tr>
            <tr><td>Passed</td><td class="status-passed">${data.passedTests}</td></tr>
            <tr><td>Failed</td><td class="status-failed">${data.failedTests}</td></tr>
            <tr><td>Average Duration</td><td>${data.statistics.average.toFixed(0)}ms</td></tr>
            <tr><td>Fastest Test</td><td>${data.statistics.min.toFixed(0)}ms</td></tr>
            <tr><td>Slowest Test</td><td>${data.statistics.max.toFixed(0)}ms</td></tr>
            <tr><td>Median Duration</td><td>${data.statistics.median.toFixed(0)}ms</td></tr>
        </table>
    </div>

    ${data.slowTests.length > 0 ? `
    <div class="slow-test">
        <h2>Slowest Tests (>5 seconds)</h2>
        <table>
            <tr><th>Test</th><th>Suite</th><th>Duration</th><th>Status</th></tr>
            ${data.slowTests.map(test => `
                <tr>
                    <td>${test.test}</td>
                    <td>${test.suite}</td>
                    <td>${test.duration.toFixed(0)}ms</td>
                    <td class="status-${test.status}">${test.status}</td>
                </tr>
            `).join('')}
        </table>
    </div>
    ` : ''}

    <div class="metric">
        <h2>All Test Results</h2>
        <table>
            <tr><th>Test</th><th>Suite</th><th>Duration</th><th>Status</th></tr>
            ${data.performanceMetrics.map(test => `
                <tr>
                    <td>${test.test}</td>
                    <td>${test.suite}</td>
                    <td>${test.duration.toFixed(0)}ms</td>
                    <td class="status-${test.status}">${test.status}</td>
                </tr>
            `).join('')}
        </table>
    </div>

    <script>
        // Add interactive features
        document.addEventListener('DOMContentLoaded', function() {
            // Sort tables
            const tables = document.querySelectorAll('table');
            tables.forEach(table => {
                const headers = table.querySelectorAll('th');
                headers.forEach((header, index) => {
                    header.style.cursor = 'pointer';
                    header.addEventListener('click', () => {
                        sortTable(table, index);
                    });
                });
            });
        });

        function sortTable(table, columnIndex) {
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));

            rows.sort((a, b) => {
                const aValue = a.cells[columnIndex].textContent.trim();
                const bValue = b.cells[columnIndex].textContent.trim();
                return aValue.localeCompare(bValue);
            });

            rows.forEach(row => tbody.appendChild(row));
        }
    </script>
</body>
</html>`;

  fs.writeFileSync(reportPath, html);
  console.log(`Performance report generated: ${reportPath}`);
}

// Main execution
if (require.main === module) {
  const resultsPath = process.argv[2];
  if (!resultsPath) {
    console.error('Please provide the path to the test results JSON file');
    process.exit(1);
  }

  const summary = processPerformanceResults(resultsPath);

  // Write summary to file
  const summaryPath = path.dirname(resultsPath) + '/performance-summary.json';
  fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2));

  console.log(`Performance summary written to: ${summaryPath}`);
}

module.exports = { processPerformanceResults };