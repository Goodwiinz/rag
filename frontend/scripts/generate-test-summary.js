#!/usr/bin/env node

/**
 * Generate comprehensive test summary from all test results
 */

const fs = require('fs');
const path = require('path');

function generateTestSummary(resultsDir) {
  try {
    const summary = {
      timestamp: new Date().toISOString(),
      totalTests: 0,
      totalPassed: 0,
      totalFailed: 0,
      totalSkipped: 0,
      suites: [],
      overall: 'unknown'
    };

    // Process all test result directories
    const testTypes = ['smoke', 'regression', 'accessibility', 'performance', 'visual'];

    testTypes.forEach(type => {
      const typeDir = path.join(resultsDir, `${type}-test-results-*`);
      const matchingDirs = fs.readdirSync(resultsDir)
        .filter(dir => dir.startsWith(`${type}-test-results`));

      matchingDirs.forEach(dir => {
        const resultsPath = path.join(resultsDir, dir, 'results.json');
        if (fs.existsSync(resultsPath)) {
          try {
            const results = JSON.parse(fs.readFileSync(resultsPath, 'utf8'));

            const suiteSummary = {
              type: type,
              directory: dir,
              totalTests: 0,
              passedTests: 0,
              failedTests: 0,
              skippedTests: 0,
              duration: 0,
              status: 'passed'
            };

            if (results.suites) {
              results.suites.forEach(suite => {
                suite.specs.forEach(spec => {
                  suiteSummary.totalTests++;
                  summary.totalTests++;

                  if (spec.ok) {
                    suiteSummary.passedTests++;
                    summary.totalPassed++;
                  } else {
                    suiteSummary.failedTests++;
                    summary.totalFailed++;
                    suiteSummary.status = 'failed';
                  }
                });
              });
            }

            summary.suites.push(suiteSummary);
          } catch (error) {
            console.warn(`Error processing ${dir}:`, error.message);
          }
        }
      });
    });

    // Determine overall status
    summary.overall = summary.totalFailed > 0 ? 'failed' : 'passed';

    // Generate HTML report
    const reportPath = path.join(resultsDir, '../test-summary.html');
    generateHTMLReport(summary, reportPath);

    // Generate JSON summary
    const jsonPath = path.join(resultsDir, '../test-summary.json');
    fs.writeFileSync(jsonPath, JSON.stringify(summary, null, 2));

    // Log to console
    console.log(`📊 Test Summary Generated:`);
    console.log(`  Total Tests: ${summary.totalTests}`);
    console.log(`  Passed: ${summary.totalPassed} ✅`);
    console.log(`  Failed: ${summary.totalFailed} ❌`);
    console.log(`  Overall Status: ${summary.overall.toUpperCase()}`);
    console.log(`  Report: ${reportPath}`);

    return summary;
  } catch (error) {
    console.error('Error generating test summary:', error);
    return null;
  }
}

function generateHTMLReport(summary, reportPath) {
  const passRate = summary.totalTests > 0 ? (summary.totalPassed / summary.totalTests * 100).toFixed(1) : 0;
  const failRate = summary.totalTests > 0 ? (summary.totalFailed / summary.totalTests * 100).toFixed(1) : 0;

  const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E2E Test Summary Report</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            line-height: 1.6;
        }
        .container { max-width: 1200px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 8px 8px 0 0;
            text-align: center;
        }
        .header h1 { margin: 0; font-size: 2.5em; font-weight: 300; }
        .header p { margin: 10px 0 0 0; opacity: 0.9; }
        .content { padding: 30px; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .metric-card {
            background: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
            border-left: 4px solid #2196f3;
        }
        .metric-card.success { border-left-color: #4caf50; }
        .metric-card.error { border-left-color: #f44336; }
        .metric-card.warning { border-left-color: #ff9800; }
        .metric-number { font-size: 2.5em; font-weight: bold; margin: 10px 0; }
        .metric-label { color: #666; font-size: 0.9em; text-transform: uppercase; letter-spacing: 1px; }
        .progress-container { margin: 20px 0; }
        .progress-bar {
            background: #e0e0e0;
            height: 30px;
            border-radius: 15px;
            overflow: hidden;
            position: relative;
        }
        .progress-fill {
            background: linear-gradient(90deg, #4caf50, #45a049);
            height: 100%;
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }
        .progress-fill.error { background: linear-gradient(90deg, #f44336, #d32f2f); }
        .suites { margin-top: 30px; }
        .suite-card {
            background: #fafafa;
            padding: 20px;
            margin: 15px 0;
            border-radius: 8px;
            border-left: 4px solid #2196f3;
        }
        .suite-card.passed { border-left-color: #4caf50; }
        .suite-card.failed { border-left-color: #f44336; }
        .suite-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .suite-title { font-size: 1.2em; font-weight: 600; }
        .suite-status {
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: bold;
            text-transform: uppercase;
        }
        .suite-status.passed { background: #e8f5e8; color: #2e7d32; }
        .suite-status.failed { background: #ffebee; color: #c62828; }
        .suite-metrics { display: flex; gap: 20px; flex-wrap: wrap; }
        .suite-metric { display: flex; align-items: center; gap: 8px; }
        .overall-status {
            text-align: center;
            padding: 30px;
            margin: 20px 0;
            border-radius: 8px;
            font-size: 1.5em;
            font-weight: bold;
        }
        .overall-status.passed {
            background: linear-gradient(135deg, #4caf50, #45a049);
            color: white;
        }
        .overall-status.failed {
            background: linear-gradient(135deg, #f44336, #d32f2f);
            color: white;
        }
        .timestamp { text-align: center; color: #666; margin-top: 20px; font-size: 0.9em; }
        @media (max-width: 768px) {
            .metrics { grid-template-columns: 1fr; }
            .suite-metrics { flex-direction: column; gap: 10px; }
            .header h1 { font-size: 2em; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>E2E Test Results</h1>
            <p>Multimodal Enterprise RAG System</p>
        </div>

        <div class="content">
            <div class="overall-status ${summary.overall}">
                ${summary.overall === 'passed' ? '🎉 All Tests Passed!' : '❌ Some Tests Failed'}
            </div>

            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-label">Total Tests</div>
                    <div class="metric-number">${summary.totalTests}</div>
                </div>
                <div class="metric-card success">
                    <div class="metric-label">Passed</div>
                    <div class="metric-number">${summary.totalPassed}</div>
                </div>
                <div class="metric-card error">
                    <div class="metric-label">Failed</div>
                    <div class="metric-number">${summary.totalFailed}</div>
                </div>
                <div class="metric-card ${summary.overall === 'passed' ? 'success' : 'error'}">
                    <div class="metric-label">Pass Rate</div>
                    <div class="metric-number">${passRate}%</div>
                </div>
            </div>

            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress-fill ${summary.totalFailed > 0 ? 'error' : ''}" style="width: ${passRate}%">
                        ${passRate}% Complete
                    </div>
                </div>
            </div>

            <div class="suites">
                <h2>Test Suite Results</h2>
                ${summary.suites.map(suite => `
                    <div class="suite-card ${suite.status}">
                        <div class="suite-header">
                            <div class="suite-title">${suite.type.charAt(0).toUpperCase() + suite.type.slice(1)} Tests</div>
                            <div class="suite-status ${suite.status}">${suite.status}</div>
                        </div>
                        <div class="suite-metrics">
                            <div class="suite-metric">
                                <span>📊</span>
                                <span>Total: ${suite.totalTests}</span>
                            </div>
                            <div class="suite-metric">
                                <span>✅</span>
                                <span>Passed: ${suite.passedTests}</span>
                            </div>
                            <div class="suite-metric">
                                <span>❌</span>
                                <span>Failed: ${suite.failedTests}</span>
                            </div>
                            <div class="suite-metric">
                                <span>⏱️</span>
                                <span>${(suite.duration / 1000).toFixed(1)}s</span>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>

            <div class="timestamp">
                Report generated on ${new Date(summary.timestamp).toLocaleString()}
            </div>
        </div>
    </div>

    <script>
        // Add interactive features
        document.addEventListener('DOMContentLoaded', function() {
            // Animate progress bars
            setTimeout(() => {
                const progressFills = document.querySelectorAll('.progress-fill');
                progressFills.forEach(fill => {
                    const width = fill.style.width;
                    fill.style.width = '0%';
                    setTimeout(() => {
                        fill.style.width = width;
                    }, 100);
                });
            }, 500);

            // Add click interactions to suite cards
            const suiteCards = document.querySelectorAll('.suite-card');
            suiteCards.forEach(card => {
                card.style.cursor = 'pointer';
                card.addEventListener('click', () => {
                    card.style.transform = 'scale(0.98)';
                    setTimeout(() => {
                        card.style.transform = 'scale(1)';
                    }, 100);
                });
            });
        });
    </script>
</body>
</html>`;

  fs.writeFileSync(reportPath, html);
  console.log(`HTML report generated: ${reportPath}`);
}

// Main execution
if (require.main === module) {
  const resultsDir = process.argv[2];
  if (!resultsDir) {
    console.error('Please provide the path to the test results directory');
    process.exit(1);
  }

  generateTestSummary(resultsDir);
}

module.exports = { generateTestSummary };