#!/usr/bin/env node

/**
 * Process accessibility test results and generate summary
 */

const fs = require('fs');
const path = require('path');

function processAccessibilityResults(resultsPath) {
  try {
    const results = JSON.parse(fs.readFileSync(resultsPath, 'utf8'));

    if (!results.violations || results.violations.length === 0) {
      console.log('✅ No accessibility violations found!');
      return {
        totalViolations: 0,
        violations: [],
        summary: 'All accessibility tests passed'
      };
    }

    const violations = results.violations;
    const summary = {
      totalViolations: violations.length,
      violations: violations.map(violation => ({
        rule: violation.id,
        impact: violation.impact,
        description: violation.description,
        helpUrl: violation.helpUrl,
        nodes: violation.nodes.length
      })),
      summary: `Found ${violations.length} accessibility violations`
    };

    // Generate detailed report
    const reportPath = path.dirname(resultsPath) + '/accessibility-report.html';
    generateAccessibilityReport(violations, reportPath);

    // Log summary to console
    console.log(`🚨 Accessibility violations found: ${summary.totalViolations}`);
    violations.forEach(violation => {
      console.log(`  - ${violation.id}: ${violation.description} (${violation.impact})`);
    });

    return summary;
  } catch (error) {
    console.error('Error processing accessibility results:', error);
    return {
      totalViolations: -1,
      violations: [],
      summary: 'Error processing accessibility results'
    };
  }
}

function generateAccessibilityReport(violations, reportPath) {
  const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Accessibility Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f5f5f5; padding: 20px; border-radius: 5px; }
        .violation { background-color: #ffebee; border: 1px solid #f44336; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .impact-critical { border-left: 5px solid #d32f2f; }
        .impact-serious { border-left: 5px solid #f57c00; }
        .impact-moderate { border-left: 5px solid #fbc02d; }
        .impact-minor { border-left: 5px solid #388e3c; }
        .code { background-color: #f5f5f5; padding: 10px; border-radius: 3px; font-family: monospace; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Accessibility Test Report</h1>
        <p>Generated: ${new Date().toISOString()}</p>
        <p>Total Violations: ${violations.length}</p>
    </div>

    ${violations.map(violation => `
        <div class="violation impact-${violation.impact}">
            <h3>${violation.id} - ${violation.impact.toUpperCase()}</h3>
            <p>${violation.description}</p>
            <p><strong>Help:</strong> <a href="${violation.helpUrl}" target="_blank">${violation.help}</a></p>
            <p><strong>Affected Elements:</strong> ${violation.nodes.length}</p>
        </div>
    `).join('')}

    <script>
        // Add interactive features
        document.querySelectorAll('.violation').forEach(v => {
            v.style.cursor = 'pointer';
            v.addEventListener('click', () => {
                v.classList.toggle('expanded');
            });
        });
    </script>
</body>
</html>`;

  fs.writeFileSync(reportPath, html);
  console.log(`Accessibility report generated: ${reportPath}`);
}

// Main execution
if (require.main === module) {
  const resultsPath = process.argv[2];
  if (!resultsPath) {
    console.error('Please provide the path to the test results JSON file');
    process.exit(1);
  }

  const summary = processAccessibilityResults(resultsPath);

  // Write summary to file
  const summaryPath = path.dirname(resultsPath) + '/accessibility-summary.json';
  fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2));

  console.log(`Accessibility summary written to: ${summaryPath}`);
}

module.exports = { processAccessibilityResults };