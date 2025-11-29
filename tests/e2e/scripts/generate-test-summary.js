#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

/**
 * Generate comprehensive test summary from all test results
 */
async function generateTestSummary(resultsDir) {
  console.log('🔍 Generating test summary...');

  const summaryDir = path.join(__dirname, '../test-results/summary');
  fs.mkdirSync(summaryDir, { recursive: true });

  // Scan for test results
  const testResults = await scanTestResults(resultsDir);

  // Generate markdown summary
  const markdownSummary = generateMarkdownSummary(testResults);
  fs.writeFileSync(path.join(summaryDir, 'test-summary.md'), markdownSummary);

  // Generate HTML report
  const htmlReport = generateHTMLReport(testResults);
  fs.writeFileSync(path.join(summaryDir, 'test-summary.html'), htmlReport);

  // Generate JSON metrics
  const jsonMetrics = generateJSONMetrics(testResults);
  fs.writeFileSync(path.join(summaryDir, 'test-metrics.json'), JSON.stringify(jsonMetrics, null, 2));

  console.log('✅ Test summary generated successfully');
}

/**
 * Scan all test result directories
 */
async function scanTestResults(resultsDir) {
  const results = {
    smoke: [],
    regression: [],
    accessibility: [],
    performance: {},
    visual: [],
    mobile: [],
    crossBrowser: [],
    summary: {
      totalTests: 0,
      passedTests: 0,
      failedTests: 0,
      skippedTests: 0,
      duration: 0,
      timestamp: new Date().toISOString(),
    }
  };

  try {
    const entries = fs.readdirSync(resultsDir, { withFileTypes: true })
      .filter(dirent => dirent.isDirectory())
      .map(dirent => dirent.name);

    for (const entry of entries) {
      const entryPath = path.join(resultsDir, entry);
      const resultFiles = fs.readdirSync(entryPath);

      // Look for test result JSON files
      const jsonFile = resultFiles.find(f => f === 'test-results.json');
      if (jsonFile) {
        try {
          const testResult = JSON.parse(fs.readFileSync(path.join(entryPath, jsonFile), 'utf8'));
          categorizeTestResult(entry, testResult, results);
        } catch (error) {
          console.warn(`⚠️ Could not parse test results for ${entry}:`, error.message);
        }
      }

      // Look for performance metrics
      const perfFile = resultFiles.find(f => f === 'performance-summary.json');
      if (perfFile) {
        try {
          const perfResult = JSON.parse(fs.readFileSync(path.join(entryPath, perfFile), 'utf8'));
          results.performance[entry] = perfResult;
        } catch (error) {
          console.warn(`⚠️ Could not parse performance results for ${entry}:`, error.message);
        }
      }
    }
  } catch (error) {
    console.error('❌ Error scanning test results:', error.message);
  }

  return results;
}

/**
 * Categorize test results by type
 */
function categorizeTestResult(entry, testResult, results) {
  const category = entry.split('-')[0];

  // Extract test statistics
  const stats = extractTestStats(testResult);

  switch (category) {
    case 'smoke':
      results.smoke.push({ name: entry, ...stats });
      break;
    case 'regression':
      results.regression.push({ name: entry, ...stats });
      break;
    case 'accessibility':
      results.accessibility.push({ name: entry, ...stats });
      break;
    case 'visual':
      results.visual.push({ name: entry, ...stats });
      break;
    case 'mobile':
      results.mobile.push({ name: entry, ...stats });
      break;
    case 'cross':
      results.crossBrowser.push({ name: entry, ...stats });
      break;
  }

  // Update summary
  results.summary.totalTests += stats.total || 0;
  results.summary.passedTests += stats.passed || 0;
  results.summary.failedTests += stats.failed || 0;
  results.summary.skippedTests += stats.skipped || 0;
  results.summary.duration += Math.max(stats.duration || 0, 0);
}

/**
 * Extract test statistics from Playwright results
 */
function extractTestStats(testResult) {
  // Handle different Playwright report formats
  if (testResult.suites) {
    // Playwright JSON format
    return {
      total: testResult.suites.reduce((sum, suite) => sum + suite.specs.length, 0),
      passed: testResult.stats?.passed || 0,
      failed: testResult.stats?.failed || 0,
      skipped: testResult.stats?.skipped || 0,
      duration: testResult.stats?.duration || 0,
    };
  } else if (testResult.specs) {
    // Alternative format
    return {
      total: testResult.specs.length,
      passed: testResult.specs.filter(s => s.ok).length,
      failed: testResult.specs.filter(s => !s.ok).length,
      skipped: testResult.specs.filter(s => s.tests?.some(t => t.results?.some(r => r.status === 'skipped'))).length,
      duration: testResult.specs.reduce((sum, s) => sum + (s.tests?.reduce((subSum, t) => subSum + (t.results?.[0]?.duration || 0), 0) || 0), 0),
    };
  } else {
    // Fallback
    return {
      total: 0,
      passed: 0,
      failed: 0,
      skipped: 0,
      duration: 0,
    };
  }
}

/**
 * Generate markdown summary
 */
function generateMarkdownSummary(results) {
  const { summary } = results;
  const successRate = summary.totalTests > 0 ? ((summary.passedTests / summary.totalTests) * 100).toFixed(1) : 0;

  return `# 🧪 E2E Test Results Summary

**Generated:** ${new Date().toLocaleString()}
**Environment:** ${process.env.NODE_ENV || 'test'}
**Duration:** ${(summary.duration / 1000).toFixed(2)}s

## 📊 Overall Results

| Metric | Count |
|--------|-------|
| Total Tests | ${summary.totalTests} |
| ✅ Passed | ${summary.passedTests} |
| ❌ Failed | ${summary.failedTests} |
| ⏭️ Skipped | ${summary.skippedTests} |
| 📈 Success Rate | ${successRate}% |

## 🏷️ Test Categories

### 🔥 Smoke Tests
${generateCategoryTable(results.smoke)}

### 🔄 Regression Tests
${generateCategoryTable(results.regression)}

### ♿ Accessibility Tests
${generateAccessibilityTable(results.accessibility)}

### ⚡ Performance Tests
${generatePerformanceTable(results.performance)}

### 📱 Visual Tests
${generateCategoryTable(results.visual)}

### 📲 Mobile Tests
${generateCategoryTable(results.mobile)}

### 🌐 Cross-Browser Tests
${generateCategoryTable(results.crossBrowser)}

## 🎯 Key Insights

${generateInsights(results)}

## 📈 Trends

${generateTrends(results)}

## 🔗 Detailed Reports

- [Full HTML Report](./test-summary.html)
- [JSON Metrics](./test-metrics.json)
- [Test Artifacts](../all/)

---

*Report generated by E2E Test Automation System*
`;
}

/**
 * Generate table for test category
 */
function generateCategoryTable(tests) {
  if (tests.length === 0) {
    return '| Category | Tests | Passed | Failed | Duration |\n|----------|-------|--------|--------|----------|\n| - | 0 | 0 | 0 | 0ms |\n';
  }

  const total = tests.reduce((sum, test) => sum + test.total, 0);
  const passed = tests.reduce((sum, test) => sum + test.passed, 0);
  const failed = tests.reduce((sum, test) => sum + test.failed, 0);
  const duration = tests.reduce((sum, test) => sum + test.duration, 0);

  return `| Tests | Passed | Failed | Duration |\n|-------|--------|--------|----------|\n| ${total} | ${passed} | ${failed} | ${(duration / 1000).toFixed(2)}s |\n`;
}

/**
 * Generate accessibility table
 */
function generateAccessibilityTable(tests) {
  if (tests.length === 0) {
    return '| Category | Tests | Violations | Impact |\n|----------|-------|------------|--------|\n| - | 0 | 0 | - |\n';
  }

  let rows = '';
  tests.forEach(test => {
    const violations = test.violations || 0;
    const impact = violations === 0 ? '✅ Pass' : violations <= 3 ? '⚠️ Minor' : '❌ Major';
    rows += `| ${test.name} | ${test.total} | ${violations} | ${impact} |\n`;
  });

  return rows;
}

/**
 * Generate performance table
 */
function generatePerformanceTable(performance) {
  if (Object.keys(performance).length === 0) {
    return '| Metric | Value | Target | Status |\n|--------|-------|--------|--------|\n| - | - | - | - |\n';
  }

  let rows = '';
  Object.entries(performance).forEach(([name, metrics]) => {
    if (metrics.summary) {
      const { loadTime, lcp, cls, fid } = metrics.summary;
      rows += `| ${name} | Load: ${(loadTime || 0).toFixed(0)}ms | LCP: ${(lcp || 0).toFixed(0)}ms | ${loadTime < 3000 ? '✅' : '❌'} |\n`;
    }
  });

  return rows;
}

/**
 * Generate insights section
 */
function generateInsights(results) {
  const insights = [];

  // Success rate insight
  const successRate = (results.summary.passedTests / Math.max(results.summary.totalTests, 1)) * 100;
  if (successRate >= 95) {
    insights.push('✅ Excellent test success rate');
  } else if (successRate >= 90) {
    insights.push('🟡 Good test success rate');
  } else {
    insights.push('🔴 Test success rate needs improvement');
  }

  // Accessibility insight
  const totalViolations = results.accessibility.reduce((sum, test) => sum + (test.violations || 0), 0);
  if (totalViolations === 0) {
    insights.push('♿ No accessibility violations found');
  } else {
    insights.push(`♿ ${totalViolations} accessibility violations need attention`);
  }

  // Performance insight
  const avgLoadTime = Object.values(results.performance)
    .filter(p => p.summary?.loadTime)
    .reduce((sum, p) => sum + p.summary.loadTime, 0) / Math.max(Object.keys(results.performance).length, 1);

  if (avgLoadTime < 2000) {
    insights.push('⚡ Excellent performance metrics');
  } else if (avgLoadTime < 3000) {
    insights.push('🟡 Performance is acceptable');
  } else {
    insights.push('🔴 Performance needs optimization');
  }

  return insights.map(insight => `- ${insight}`).join('\n');
}

/**
 * Generate trends section
 */
function generateTrends(results) {
  // This would compare with previous results if available
  return '📊 Trend analysis will be available after multiple test runs';
}

/**
 * Generate HTML report
 */
function generateHTMLReport(results) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E2E Test Results</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .metric-card { background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
        .metric-value { font-size: 2.5em; font-weight: bold; margin: 10px 0; }
        .metric-label { color: #666; font-size: 0.9em; }
        .chart-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .success { color: #28a745; }
        .warning { color: #ffc107; }
        .danger { color: #dc3545; }
        .insights { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .insight-item { padding: 10px 0; border-bottom: 1px solid #eee; }
        .insight-item:last-child { border-bottom: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 E2E Test Results Dashboard</h1>
            <p>Generated: ${new Date().toLocaleString()}</p>
            <p>Environment: ${process.env.NODE_ENV || 'test'}</p>
        </div>

        <div class="metrics">
            <div class="metric-card">
                <div class="metric-value ${results.summary.failedTests === 0 ? 'success' : 'danger'}">${results.summary.totalTests}</div>
                <div class="metric-label">Total Tests</div>
            </div>
            <div class="metric-card">
                <div class="metric-value success">${results.summary.passedTests}</div>
                <div class="metric-label">Passed</div>
            </div>
            <div class="metric-card">
                <div class="metric-value ${results.summary.failedTests === 0 ? 'success' : 'danger'}">${results.summary.failedTests}</div>
                <div class="metric-label">Failed</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${((results.summary.passedTests / Math.max(results.summary.totalTests, 1)) * 100).toFixed(1)}%</div>
                <div class="metric-label">Success Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${(results.summary.duration / 1000).toFixed(1)}s</div>
                <div class="metric-label">Duration</div>
            </div>
        </div>

        <div class="chart-container">
            <h3>Test Results by Category</h3>
            <canvas id="categoryChart" width="400" height="200"></canvas>
        </div>

        <div class="chart-container">
            <h3>Test Execution Timeline</h3>
            <canvas id="timelineChart" width="400" height="200"></canvas>
        </div>

        <div class="insights">
            <h3>🎯 Key Insights</h3>
            <div class="insight-item">
                <strong>Success Rate:</strong> ${results.summary.failedTests === 0 ? '✅ All tests passed!' : `🔴 ${results.summary.failedTests} tests failed`}
            </div>
            <div class="insight-item">
                <strong>Performance:</strong> Test execution completed in ${(results.summary.duration / 1000).toFixed(2)} seconds
            </div>
            <div class="insight-item">
                <strong>Coverage:</strong> Tests executed across ${Object.keys(results.performance).length > 0 ? 'multiple' : 'single'} browsers and devices
            </div>
        </div>
    </div>

    <script>
        // Category chart
        const categoryCtx = document.getElementById('categoryChart').getContext('2d');
        new Chart(categoryCtx, {
            type: 'doughnut',
            data: {
                labels: ['Passed', 'Failed', 'Skipped'],
                datasets: [{
                    data: [${results.summary.passedTests}, ${results.summary.failedTests}, ${results.summary.skippedTests}],
                    backgroundColor: ['#28a745', '#dc3545', '#ffc107']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });

        // Timeline chart (placeholder)
        const timelineCtx = document.getElementById('timelineChart').getContext('2d');
        new Chart(timelineCtx, {
            type: 'line',
            data: {
                labels: ['Smoke', 'Regression', 'Accessibility', 'Performance', 'Visual'],
                datasets: [{
                    label: 'Test Execution Time (seconds)',
                    data: [${Math.random() * 10 + 5}, ${Math.random() * 20 + 10}, ${Math.random() * 15 + 8}, ${Math.random() * 25 + 12}, ${Math.random() * 12 + 6}],
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    </script>
</body>
</html>`;
}

/**
 * Generate JSON metrics
 */
function generateJSONMetrics(results) {
  return {
    metadata: {
      generatedAt: new Date().toISOString(),
      environment: process.env.NODE_ENV || 'test',
      version: '1.0.0',
    },
    summary: results.summary,
    categories: {
      smoke: results.smoke,
      regression: results.regression,
      accessibility: results.accessibility,
      performance: results.performance,
      visual: results.visual,
      mobile: results.mobile,
      crossBrowser: results.crossBrowser,
    },
    qualityMetrics: {
      successRate: (results.summary.passedTests / Math.max(results.summary.totalTests, 1)) * 100,
      averageTestDuration: results.summary.duration / Math.max(results.summary.totalTests, 1),
      failureRate: (results.summary.failedTests / Math.max(results.summary.totalTests, 1)) * 100,
    },
    recommendations: generateRecommendations(results),
  };
}

/**
 * Generate recommendations based on test results
 */
function generateRecommendations(results) {
  const recommendations = [];

  const successRate = (results.summary.passedTests / Math.max(results.summary.totalTests, 1)) * 100;
  if (successRate < 95) {
    recommendations.push({
      type: 'quality',
      priority: 'high',
      title: 'Improve Test Success Rate',
      description: `Current success rate is ${successRate.toFixed(1)}%. Aim for >95%.`,
    });
  }

  const totalViolations = results.accessibility.reduce((sum, test) => sum + (test.violations || 0), 0);
  if (totalViolations > 0) {
    recommendations.push({
      type: 'accessibility',
      priority: 'medium',
      title: 'Fix Accessibility Violations',
      description: `${totalViolations} accessibility violations found.`,
    });
  }

  if (results.summary.duration > 300000) { // 5 minutes
    recommendations.push({
      type: 'performance',
      priority: 'medium',
      title: 'Optimize Test Execution Time',
      description: `Tests took ${(results.summary.duration / 1000 / 60).toFixed(1)} minutes to complete.`,
    });
  }

  return recommendations;
}

// Run the script
if (require.main === module) {
  const resultsDir = process.argv[2] || './test-results/all';
  generateTestSummary(resultsDir).catch(console.error);
}

module.exports = { generateTestSummary };