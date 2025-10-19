#!/usr/bin/env node

/**
 * Check for performance regressions by comparing current results with baseline
 */

const fs = require('fs');
const path = require('path');

function checkPerformanceRegression(resultsPath) {
  try {
    const currentResults = JSON.parse(fs.readFileSync(resultsPath, 'utf8'));
    const baselinePath = path.join(path.dirname(resultsPath), '../baseline-performance.json');

    let baselineResults = null;
    if (fs.existsSync(baselinePath)) {
      baselineResults = JSON.parse(fs.readFileSync(baselinePath, 'utf8'));
    }

    // Extract performance metrics from current results
    const currentMetrics = extractMetrics(currentResults);
    const baselineMetrics = baselineResults ? extractMetrics(baselineResults) : null;

    // Compare metrics and detect regressions
    const regressions = [];
    const improvements = [];

    if (baselineMetrics) {
      Object.keys(currentMetrics).forEach(testName => {
        const current = currentMetrics[testName];
        const baseline = baselineMetrics[testName];

        if (baseline) {
          const regressionThreshold = 0.2; // 20% regression threshold
          const improvementThreshold = -0.1; // 10% improvement threshold

          const change = (current - baseline) / baseline;

          if (change > regressionThreshold) {
            regressions.push({
              test: testName,
              baseline: baseline,
              current: current,
              change: (change * 100).toFixed(1),
              severity: change > 0.5 ? 'critical' : change > 0.3 ? 'major' : 'minor'
            });
          } else if (change < improvementThreshold) {
            improvements.push({
              test: testName,
              baseline: baseline,
              current: current,
              change: (change * 100).toFixed(1)
            });
          }
        }
      });
    }

    // Generate report
    const report = {
      timestamp: new Date().toISOString(),
      currentMetrics: currentMetrics,
      baselineMetrics: baselineMetrics,
      regressions: regressions,
      improvements: improvements,
      summary: regressions.length > 0 ?
        `Found ${regressions.length} performance regression${regressions.length === 1 ? '' : 's'}` :
        'No performance regressions detected'
    };

    // Update baseline if no regressions and this is on main branch
    if (regressions.length === 0 && process.env.GITHUB_REF === 'refs/heads/main') {
      fs.writeFileSync(baselinePath, JSON.stringify(currentMetrics, null, 2));
      console.log('✅ Performance baseline updated');
    }

    // Log results
    if (regressions.length > 0) {
      console.log(`🚨 Performance Regressions Detected:`);
      regressions.forEach(regression => {
        console.log(`  - ${regression.test}: ${regression.baseline.toFixed(0)}ms → ${regression.current.toFixed(0)}ms (${regression.change}% ${regression.severity})`);
      });

      // Exit with error code for CI failures
      const criticalRegressions = regressions.filter(r => r.severity === 'critical');
      if (criticalRegressions.length > 0) {
        console.log(`\n❌ ${criticalRegressions.length} critical regression${criticalRegressions.length === 1 ? '' : 's'} detected`);
        process.exit(1);
      }
    }

    if (improvements.length > 0) {
      console.log(`\n🚀 Performance Improvements:`);
      improvements.forEach(improvement => {
        console.log(`  - ${improvement.test}: ${improvement.baseline.toFixed(0)}ms → ${improvement.current.toFixed(0)}ms (${improvement.change}%)`);
      });
    }

    if (regressions.length === 0) {
      console.log('✅ No performance regressions detected');
    }

    // Write report
    const reportPath = path.join(path.dirname(resultsPath), 'performance-regression-report.json');
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));

    return report;
  } catch (error) {
    console.error('Error checking performance regression:', error);
    return null;
  }
}

function extractMetrics(results) {
  const metrics = {};

  if (results.suites) {
    results.suites.forEach(suite => {
      suite.specs.forEach(spec => {
        if (spec.tests && spec.tests[0]) {
          const testResult = spec.tests[0].results[0];
          const duration = testResult.duration;

          // Create a unique key for the test
          const key = `${suite.title} > ${spec.title}`;
          metrics[key] = duration;
        }
      });
    });
  }

  return metrics;
}

// Main execution
if (require.main === module) {
  const resultsPath = process.argv[2];
  if (!resultsPath) {
    console.error('Please provide the path to the test results JSON file');
    process.exit(1);
  }

  checkPerformanceRegression(resultsPath);
}

module.exports = { checkPerformanceRegression };