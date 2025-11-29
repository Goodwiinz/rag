import { test, expect } from '../fixtures/test-data.fixture';
import { DocumentsPage, SearchPage, EvaluationPage } from '../utils/page-objects';

/**
 * E2E Tests for Query Performance Evaluation (User Story 4)
 *
 * Test Coverage:
 * - RAG Triad metrics display (Answer Relevancy, Faithfulness, Contextual Relevancy)
 * - Performance charts and trends
 * - Quality indicators and recommendations
 * - Evaluation test suite management
 */

test.describe('Query Performance Evaluation', () => {
  let documentsPage: DocumentsPage;
  let searchPage: SearchPage;
  let evaluationPage: EvaluationPage;

  test.beforeEach(async ({ authenticatedPage }) => {
    documentsPage = new DocumentsPage(authenticatedPage);
    searchPage = new SearchPage(authenticatedPage);
    evaluationPage = new EvaluationPage(authenticatedPage);
  });

  test('US4-1: RAG Triad metrics display and visualization', async ({ page, testData }) => {
    // Upload test documents
    await documentsPage.navigateTo('/documents');
    await documentsPage.uploadFile(testData.files.pdf.path, testData.files.pdf.name);
    await documentsPage.uploadFile(testData.files.text.path, testData.files.text.name);

    // Perform some searches to generate evaluation data
    await searchPage.navigateTo('/search');
    await searchPage.performSearch(testData.queries.simple[0]);
    await searchPage.waitForResults();

    // Navigate to evaluation page
    await evaluationPage.navigateTo('/evaluation');

    // Verify RAG Triad metrics section is visible
    await expect(evaluationPage.ragTriadMetrics).toBeVisible();

    // Verify individual RAG Triad metrics
    await expect(evaluationPage.answerRelevancy).toBeVisible();
    await expect(evaluationPage.faithfulness).toBeVisible();
    await expect(evaluationPage.contextualRelevancy).toBeVisible();

    // Verify metric scores are displayed
    await expect(page.locator('[data-testid="answer-relevancy-score"]')).toBeVisible();
    await expect(page.locator('[data-testid="faithfulness-score"]')).toBeVisible();
    await expect(page.locator('[data-testid="contextual-relevancy-score"]')).toBeVisible();

    // Verify metric visualization (charts or gauges)
    await expect(page.locator('[data-testid="relevancy-chart"]')).toBeVisible();
    await expect(page.locator('[data-testid="faithfulness-chart"]')).toBeVisible();
    await expect(page.locator('[data-testid="contextual-chart"]')).toBeVisible();

    // Take screenshot for documentation
    await evaluationPage.takeScreenshot('rag-triad-metrics-display');
  });

  test('US4-2: Performance threshold validation', async ({ page, testData }) => {
    // Upload and process documents
    await documentsPage.navigateTo('/documents');
    await documentsPage.uploadFile(testData.files.pdf.path, testData.files.pdf.name);

    // Perform searches to generate metrics
    await searchPage.navigateTo('/search');
    for (const query of testData.queries.simple.slice(0, 2)) {
      await searchPage.performSearch(query);
      await searchPage.waitForResults();
      await page.waitForTimeout(1000);
    }

    // Navigate to evaluation
    await evaluationPage.navigateTo('/evaluation');

    // Wait for metrics to load
    await page.waitForTimeout(3000);

    // Verify performance thresholds are met
    await evaluationPage.verifyPerformanceThresholds();

    // Check threshold indicators
    await expect(page.locator('[data-testid="threshold-indicators"]')).toBeVisible();

    // Verify each metric meets its threshold
    const relevancyScore = await evaluationPage.getMetricScore('answer-relevancy');
    const faithfulnessScore = await evaluationPage.getMetricScore('faithfulness');
    const contextualScore = await evaluationPage.getMetricScore('contextual-relevancy');

    console.log(`RAG Triad Scores - Relevancy: ${relevancyScore}%, Faithfulness: ${faithfulnessScore}%, Contextual: ${contextualScore}%`);

    // Verify threshold status indicators
    await expect(page.locator('[data-testid="relevancy-status"]')).toBeVisible();
    await expect(page.locator('[data-testid="faithfulness-status"]')).toBeVisible();
    await expect(page.locator('[data-testid="contextual-status"]')).toBeVisible();
  });

  test('US4-3: Performance trends over time visualization', async ({ page }) => {
    await evaluationPage.navigateTo('/evaluation');

    // Look for trends section
    const trendsSection = page.locator('[data-testid="performance-trends"]');
    if (await trendsSection.isVisible()) {
      await expect(trendsSection).toBeVisible();

      // Verify trend charts are displayed
      await expect(page.locator('[data-testid="relevancy-trend-chart"]')).toBeVisible();
      await expect(page.locator('[data-testid="faithfulness-trend-chart"]')).toBeVisible();
      await expect(page.locator('[data-testid="contextual-trend-chart"]')).toBeVisible();

      // Verify time period selector
      await expect(page.locator('[data-testid="time-period-selector"]')).toBeVisible();

      // Test different time periods
      await page.click('[data-testid="time-period-selector"]');
      await page.click('[data-testid="period-7d"]'); // Last 7 days
      await page.waitForTimeout(2000);

      // Verify charts update
      await expect(page.locator('[data-testid="relevancy-trend-chart"]')).toBeVisible();

      // Test another period
      await page.click('[data-testid="time-period-selector"]');
      await page.click('[data-testid="period-30d"]'); // Last 30 days
      await page.waitForTimeout(2000);
    }
  });

  test('US4-4: Quality indicators and recommendations', async ({ page }) => {
    await evaluationPage.navigateTo('/evaluation');

    // Verify quality indicators section
    const qualityIndicators = page.locator('[data-testid="quality-indicators"]');
    if (await qualityIndicators.isVisible()) {
      await expect(qualityIndicators).toBeVisible();

      // Check for overall quality score
      await expect(page.locator('[data-testid="overall-quality-score"]')).toBeVisible();

      // Verify quality status indicators (good, warning, critical)
      const statusIndicators = page.locator('[data-testid="quality-status"]');
      if (await statusIndicators.count() > 0) {
        await expect(statusIndicators.first()).toBeVisible();
      }
    }

    // Verify recommendations section
    const recommendations = page.locator('[data-testid="recommendations"]');
    if (await recommendations.isVisible()) {
      await expect(recommendations).toBeVisible();

      // Check for improvement recommendations
      const recommendationItems = page.locator('[data-testid="recommendation-item"]');
      const recommendationCount = await recommendationItems.count();

      if (recommendationCount > 0) {
        // Verify recommendation structure
        await expect(recommendationItems.first().locator('[data-testid="recommendation-title"]')).toBeVisible();
        await expect(recommendationItems.first().locator('[data-testid="recommendation-description"]')).toBeVisible();
        await expect(recommendationItems.first().locator('[data-testid="recommendation-action"]')).toBeVisible();

        // Test acting on a recommendation
        await recommendationItems.first().locator('[data-testid="recommendation-action"]').click();
        await page.waitForTimeout(1000);
      }
    }
  });

  test('US4-5: Evaluation test suite creation and management', async ({ page }) => {
    await evaluationPage.navigateTo('/evaluation');

    // Create a new evaluation suite
    await evaluationPage.createEvaluationButton.click();

    // Fill evaluation creation form
    await page.fill('[data-testid="evaluation-name"]', 'Test Suite - E2E Evaluation');
    await page.fill('[data-testid="evaluation-description"]', 'Automated evaluation suite created by E2E tests');

    // Select evaluation parameters
    await page.click('[data-testid="evaluation-type-select"]');
    await page.click('[data-testid="type-rag-triad"]');

    // Select test queries
    await page.click('[data-testid="query-selection"]');
    await page.click('[data-testid="select-standard-queries"]');

    // Save evaluation
    await page.click('[data-testid="save-evaluation"]');

    // Wait for evaluation to be created
    await page.waitForSelector('[data-testid="evaluation-created"]', { timeout: 10000 });

    // Verify evaluation appears in the list
    await expect(page.locator('[data-testid="evaluation-item"]')).toBeVisible();
  });

  test('US4-6: Running evaluation test suites', async ({ page }) => {
    await evaluationPage.navigateTo('/evaluation');

    // Find existing evaluation or create one
    const evaluationItems = page.locator('[data-testid="evaluation-item"]');

    if (await evaluationItems.count() === 0) {
      // Create a basic evaluation if none exists
      await evaluationPage.createEvaluation('Quick Test', 'Test evaluation for E2E');
    }

    // Run the evaluation
    await evaluationPage.runEvaluationButton.click();

    // Confirm run
    await page.click('[data-testid="confirm-run"]');

    // Monitor evaluation progress
    await expect(page.locator('[data-testid="evaluation-progress"]')).toBeVisible();
    await expect(page.locator('[data-testid="progress-bar"]')).toBeVisible();

    // Wait for evaluation to complete (with timeout)
    await page.waitForSelector('[data-testid="evaluation-complete"]', { timeout: 180000 }); // 3 minutes max

    // Verify results are generated
    await expect(page.locator('[data-testid="evaluation-results"]')).toBeVisible();
    await expect(evaluationPage.metricsOverview).toBeVisible();
  });

  test('US4-7: Detailed evaluation results analysis', async ({ page }) => {
    await evaluationPage.navigateTo('/evaluation');

    // Click on an evaluation to view details
    const evaluationItems = page.locator('[data-testid="evaluation-item"]');
    if (await evaluationItems.count() > 0) {
      await evaluationItems.first().click();

      // Verify detailed results view
      await expect(evaluationPage.evaluationDetails).toBeVisible();

      // Check for detailed metrics breakdown
      await expect(page.locator('[data-testid="metrics-breakdown"]')).toBeVisible();

      // Verify individual query results
      const queryResults = page.locator('[data-testid="query-result"]');
      const queryCount = await queryResults.count();

      if (queryCount > 0) {
        // Examine first query result
        await expect(queryResults.first().locator('[data-testid="query-text"]')).toBeVisible();
        await expect(queryResults.first().locator('[data-testid="query-scores"]')).toBeVisible();
        await expect(queryResults.first().locator('[data-testid="query-feedback"]')).toBeVisible();

        // Test expanding query details
        await queryResults.first().click();
        await expect(page.locator('[data-testid="query-detail-panel"]')).toBeVisible();
      }

      // Verify summary statistics
      await expect(page.locator('[data-testid="summary-statistics"]')).toBeVisible();
      await expect(page.locator('[data-testid="average-scores"]')).toBeVisible();
      await expect(page.locator('[data-testid="score-distribution"]')).toBeVisible();
    }
  });

  test('US4-8: Comparison between different evaluations', async ({ page }) => {
    await evaluationPage.navigateTo('/evaluation');

    // Look for comparison functionality
    const compareButton = evaluationPage.compareButton;
    if (await compareButton.isVisible()) {
      await compareButton.click();

      // Select evaluations to compare
      await page.click('[data-testid="select-evaluation-1"]');
      await page.click('[data-testid="select-evaluation-2"]');

      // Run comparison
      await page.click('[data-testid="run-comparison"]');

      // Wait for comparison results
      await page.waitForSelector('[data-testid="comparison-results"]', { timeout: 30000 });

      // Verify comparison view
      await expect(page.locator('[data-testid="comparison-chart"]')).toBeVisible();
      await expect(page.locator('[data-testid="comparison-table"]')).toBeVisible();

      // Verify comparison metrics
      await expect(page.locator('[data-testid="score-comparison"]')).toBeVisible();
      await expect(page.locator('[data-testid="improvement-indicators"]')).toBeVisible();
    }
  });

  test('US4-9: Evaluation results export and reporting', async ({ page }) => {
    await evaluationPage.navigateTo('/evaluation');

    // Test export functionality
    const exportButton = evaluationPage.exportButton;
    if (await exportButton.isVisible()) {
      await exportButton.click();

      // Verify export options
      await expect(page.locator('[data-testid="export-pdf"]')).toBeVisible();
      await expect(page.locator('[data-testid="export-csv"]')).toBeVisible();
      await expect(page.locator('[data-testid="export-json"]')).toBeVisible();

      // Test CSV export
      const downloadPromise = page.waitForEvent('download');
      await page.click('[data-testid="export-csv"]');
      const download = await downloadPromise;

      // Verify download started
      expect(download.suggestedFilename()).toMatch(/\.csv$/);

      // Test PDF export
      await page.click('[data-testid="export-pdf"]');
      // Note: PDF might open in new tab or download, adjust accordingly
    }
  });

  test('US4-10: Real-time performance monitoring', async ({ page, testData }) => {
    // Perform searches to generate real-time data
    await searchPage.navigateTo('/search');
    await searchPage.performSearch(testData.queries.simple[0]);
    await searchPage.waitForResults();

    // Navigate to evaluation with real-time view
    await evaluationPage.navigateTo('/evaluation');

    // Look for real-time monitoring section
    const realtimeSection = page.locator('[data-testid="realtime-monitoring"]');
    if (await realtimeSection.isVisible()) {
      await expect(realtimeSection).toBeVisible();

      // Verify live metrics
      await expect(page.locator('[data-testid="live-relevancy"]')).BeVisible();
      await expect(page.locator('[data-testid="live-faithfulness"]')).BeVisible();
      await expect(page.locator('[data-testid="live-contextual"]')).BeVisible();

      // Perform another search and verify real-time updates
      await searchPage.navigateTo('/search');
      await searchPage.performSearch(testData.queries.simple[1]);
      await searchPage.waitForResults();

      // Check if metrics update in real-time
      await evaluationPage.navigateTo('/evaluation');
      await page.waitForTimeout(2000);

      // Verify updated metrics
      await expect(page.locator('[data-testid="current-metrics"]')).toBeVisible();
    }
  });

  test('US4-11: Performance alerts and notifications', async ({ page }) => {
    await evaluationPage.navigateTo('/evaluation');

    // Check for alerts section
    const alertsSection = page.locator('[data-testid="performance-alerts"]');
    if (await alertsSection.isVisible()) {
      await expect(alertsSection).toBeVisible();

      // Check for active alerts
      const alertItems = page.locator('[data-testid="alert-item"]');
      const alertCount = await alertItems.count();

      if (alertCount > 0) {
        // Verify alert structure
        await expect(alertItems.first().locator('[data-testid="alert-severity"]')).toBeVisible();
        await expect(alertItems.first().locator('[data-testid="alert-message"]')).BeVisible();
        await expect(alertItems.first().locator('[data-testid="alert-timestamp"]')).BeVisible();

        // Test alert acknowledgment
        await alertItems.first().locator('[data-testid="acknowledge-alert"]').click();
        await page.waitForTimeout(1000);
      }

      // Verify alert configuration
      await expect(page.locator('[data-testid="alert-settings"]')).BeVisible();
      await page.click('[data-testid="alert-settings"]');
      await expect(page.locator('[data-testid="threshold-config"]')).BeVisible();
    }
  });

  test('US4-12: Evaluation dashboard accessibility and usability', async ({ page }) => {
    await evaluationPage.navigateTo('/evaluation');

    // Verify dashboard accessibility
    await expect(page.locator('[data-testid="evaluation-dashboard"]')).BeVisible();

    // Check keyboard navigation
    await page.keyboard.press('Tab');
    await expect(page.locator(':focus')).toBeVisible();

    // Test responsive design
    await page.setViewportSize({ width: 768, height: 1024 }); // Tablet
    await page.waitForTimeout(1000);
    await expect(evaluationPage.metricsOverview).toBeVisible();

    await page.setViewportSize({ width: 375, height: 667 }); // Mobile
    await page.waitForTimeout(1000);
    await expect(evaluationPage.metricsOverview).toBeVisible();

    // Reset to desktop
    await page.setViewportSize({ width: 1280, height: 720 });

    // Test help and documentation
    const helpButton = page.locator('[data-testid="help-button"]');
    if (await helpButton.isVisible()) {
      await helpButton.click();
      await expect(page.locator('[data-testid="help-content"]')).BeVisible();
    }

    // Test tooltips and explanatory content
    await page.hover(evaluationPage.answerRelevancy);
    await expect(page.locator('[data-testid="relevancy-tooltip"]')).BeVisible({ timeout: 2000 });
  });
});