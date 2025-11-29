import { test, expect } from '@playwright/test';
import { createTestHelpers, TEST_DATA } from '../utils/test-helpers';

test.describe('Real-time Monitoring - User Journey', () => {
  let helpers: ReturnType<typeof createTestHelpers>;

  test.beforeEach(async ({ page, context, browserName }, testInfo) => {
    helpers = createTestHelpers(page, context, testInfo);
    helpers.logStep(`Starting real-time monitoring test on ${browserName}`);

    // Login as admin for full monitoring access
    await helpers.login(TEST_DATA.USERS.ADMIN);
  });

  test.describe('Real-time Dashboard Access', () => {
    test('should access and display real-time metrics', async ({ page }) => {
      helpers.logStep('Testing real-time dashboard access and metrics display');

      // Step 1: Navigate to real-time monitoring dashboard
      await helpers.waitAndClick('[data-testid="real-time-nav-link"]');
      await helpers.expectElementVisible('[data-testid="real-time-dashboard"]');
      helpers.logStep('Successfully navigated to real-time dashboard');

      // Step 2: Verify WebSocket connection status
      await helpers.expectElementVisible('[data-testid="connection-status"]');
      const connectionStatus = await helpers.getTextContent('[data-testid="connection-status"]');
      expect(connectionStatus).toContain('Connected');
      helpers.logStep('WebSocket connection established');

      // Step 3: Verify real-time metrics are displayed
      await helpers.expectElementVisible('[data-testid="live-metric-card"]');
      const liveMetrics = page.locator('[data-testid="live-metric-card"]');
      await expect(liveMetrics).toHaveCount.greaterThan(0);
      helpers.logStep(`Found ${await liveMetrics.count()} live metrics`);

      // Step 4: Verify timestamp updates
      const timestampElement = page.locator('[data-testid="last-update-timestamp"]');
      await expect(timestampElement).toBeVisible();
      const initialTimestamp = await helpers.getTextContent('[data-testid="last-update-timestamp"]');
      helpers.logStep(`Initial timestamp: ${initialTimestamp}`);

      // Step 5: Wait for metrics to update
      await page.waitForTimeout(3000);
      const updatedTimestamp = await helpers.getTextContent('[data-testid="last-update-timestamp"]');
      expect(updatedTimestamp).not.toBe(initialTimestamp);
      helpers.logStep(`Updated timestamp: ${updatedTimestamp}`);

      // Step 6: Verify real-time indicators
      await helpers.expectElementVisible('[data-testid="real-time-indicator"]');
      await helpers.expectElementVisible('[data-testid="pulse-animation"]');
      helpers.logStep('Real-time indicators are visible');

      await helpers.takeScreenshot('real-time-dashboard-loaded');
    });

    test('should handle WebSocket connection lifecycle', async ({ page }) => {
      helpers.logStep('Testing WebSocket connection lifecycle');

      // Navigate to real-time dashboard
      await helpers.waitAndClick('[data-testid="real-time-nav-link"]');
      await helpers.expectElementVisible('[data-testid="real-time-dashboard"]');

      // Step 1: Monitor connection establishment
      await helpers.expectElementVisible('[data-testid="connection-status"]');
      await helpers.expectElementVisible('[data-testid="connecting-indicator"]');

      // Wait for connection to establish
      await helpers.expectElementVisible('[data-testid="connected-indicator"]');
      await helpers.expectElementHidden('[data-testid="connecting-indicator"]');
      helpers.logStep('WebSocket connection established successfully');

      // Step 2: Test connection interruption handling
      await page.evaluate(() => {
        // Simulate connection interruption
        window.dispatchEvent(new Event('offline'));
      });

      await helpers.expectElementVisible('[data-testid="disconnected-indicator"]');
      await helpers.expectElementVisible('[data-testid="reconnecting-indicator"]');
      helpers.logStep('Connection interruption handled correctly');

      // Step 3: Test automatic reconnection
      await page.evaluate(() => {
        window.dispatchEvent(new Event('online'));
      });

      await helpers.expectElementVisible('[data-testid="connected-indicator"]');
      await helpers.expectElementHidden('[data-testid="disconnected-indicator"]');
      helpers.logStep('Automatic reconnection successful');

      // Step 4: Test manual reconnection
      await helpers.waitAndClick('[data-testid="manual-reconnect-button"]');
      await helpers.expectElementVisible('[data-testid="reconnecting-indicator"]');
      await page.waitForTimeout(2000);
      await helpers.expectElementVisible('[data-testid="connected-indicator"]');
      helpers.logStep('Manual reconnection successful');
    });

    test('should display different types of real-time data', async ({ page }) => {
      helpers.logStep('Testing different types of real-time data display');

      await helpers.waitAndClick('[data-testid="real-time-nav-link"]');
      await helpers.expectElementVisible('[data-testid="real-time-dashboard"]');

      // Step 1: Test live metrics cards
      const metricCards = page.locator('[data-testid="live-metric-card"]');
      await expect(metricCards).toHaveCount.greaterThan(0);

      // Verify metric card components
      for (let i = 0; i < Math.min(await metricCards.count(), 3); i++) {
        const card = metricCards.nth(i);
        await expect(card.locator('[data-testid="metric-label"]')).toBeVisible();
        await expect(card.locator('[data-testid="metric-value"]')).toBeVisible();
        await expect(card.locator('[data-testid="metric-trend"]')).toBeVisible();
      }
      helpers.logStep('Live metric cards verified');

      // Step 2: Test real-time charts
      const realtimeCharts = page.locator('[data-testid="realtime-chart"]');
      if (await realtimeCharts.count() > 0) {
        await expect(realtimeCharts.first()).toBeVisible();
        await expect(realtimeCharts.first().locator('svg')).toBeVisible();
        helpers.logStep('Real-time charts displayed');

        // Verify chart data updates
        const chartData = await realtimeCharts.first()
          .locator('[data-testid="chart-data-points"]')
          .count();
        await page.waitForTimeout(2000);
        const updatedChartData = await realtimeCharts.first()
          .locator('[data-testid="chart-data-points"]')
          .count();

        // Chart should update with new data points
        expect(updatedChartData).toBeGreaterThan(chartData);
        helpers.logStep('Chart data updated in real-time');
      }

      // Step 3: Test activity feed
      const activityFeed = page.locator('[data-testid="activity-feed"]');
      if (await activityFeed.count() > 0) {
        await expect(activityFeed).toBeVisible();
        const initialActivities = await activityFeed
          .locator('[data-testid="activity-item"]')
          .count();

        // Wait for new activities
        await page.waitForTimeout(3000);
        const updatedActivities = await activityFeed
          .locator('[data-testid="activity-item"]')
          .count();

        expect(updatedActivities).toBeGreaterThan(initialActivities);
        helpers.logStep('Activity feed updated in real-time');
      }

      // Step 4: Test system status indicators
      await helpers.expectElementVisible('[data-testid="system-status"]');
      const statusIndicators = page.locator('[data-testid="status-indicator"]');
      await expect(statusIndicators).toHaveCount.greaterThan(0);

      for (let i = 0; i < await statusIndicators.count(); i++) {
        const indicator = statusIndicators.nth(i);
        await expect(indicator.locator('[data-testid="status-label"]')).toBeVisible();
        await expect(indicator.locator('[data-testid="status-value"]')).toBeVisible();
      }
      helpers.logStep('System status indicators verified');
    });
  });

  test.describe('Real-time Alerts and Notifications', () => {
    test('should trigger and display real-time alerts', async ({ page }) => {
      helpers.logStep('Testing real-time alert triggering and display');

      await helpers.waitAndClick('[data-testid="real-time-nav-link"]');
      await helpers.expectElementVisible('[data-testid="real-time-dashboard"]');

      // Step 1: Trigger a test alert
      await helpers.waitAndClick('[data-testid="trigger-test-alert"]');
      await helpers.expectElementVisible('[data-testid="alert-notification"]');
      helpers.logStep('Test alert triggered successfully');

      // Step 2: Verify alert content
      const alertTitle = await helpers.getTextContent('[data-testid="alert-title"]');
      const alertMessage = await helpers.getTextContent('[data-testid="alert-message"]');
      const alertSeverity = await helpers.getAttribute('[data-testid="alert-notification"]', 'data-severity');

      expect(alertTitle).toBeTruthy();
      expect(alertMessage).toBeTruthy();
      expect(['info', 'warning', 'error', 'success']).toContain(alertSeverity);
      helpers.logStep(`Alert displayed: ${alertTitle} (${alertSeverity})`);

      // Step 3: Test alert interactions
      await helpers.waitAndClick('[data-testid="alert-acknowledge"]');
      await helpers.expectElementHidden('[data-testid="alert-notification"]');
      helpers.logStep('Alert acknowledged and dismissed');

      // Step 4: Check alert history
      await helpers.waitAndClick('[data-testid="alert-history-tab"]');
      await helpers.expectElementVisible('[data-testid="alert-history-list"]');

      const historyItems = page.locator('[data-testid="alert-history-item"]');
      await expect(historyItems).toHaveCount.greaterThan(0);

      const recentAlert = historyItems.first();
      await expect(recentAlert.locator('[data-testid="alert-history-title"]')).toContainText(alertTitle);
      await expect(recentAlert.locator('[data-testid="alert-history-timestamp"]')).toBeVisible();
      helpers.logStep('Alert history updated correctly');

      // Step 5: Test alert filtering
      await helpers.selectOption('[data-testid="alert-filter-severity"]', 'warning');
      await page.waitForTimeout(1000);

      const filteredAlerts = page.locator('[data-testid="alert-history-item"]');
      await expect(filteredAlerts).toHaveCount.greaterThan(0);
      helpers.logStep('Alert filtering working correctly');
    });

    test('should handle threshold-based alerts', async ({ page }) => {
      helpers.logStep('Testing threshold-based alert system');

      await helpers.waitAndClick('[data-testid="real-time-nav-link"]');
      await helpers.expectElementVisible('[data-testid="real-time-dashboard"]');

      // Step 1: Configure alert thresholds
      await helpers.waitAndClick('[data-testid="alert-settings-tab"]');
      await helpers.expectElementVisible('[data-testid="alert-threshold-settings"]');

      // Set up a test threshold
      await helpers.fillField('[data-testid="threshold-metric"]', 'cpu_usage');
      await helpers.fillField('[data-testid="threshold-value"]', '80');
      await helpers.selectOption('[data-testid="threshold-operator"]', 'greater_than');
      await helpers.waitAndClick('[data-testid="save-threshold"]');
      helpers.logStep('Alert threshold configured');

      // Step 2: Simulate threshold breach
      await helpers.waitAndClick('[data-testid="simulate-threshold-breach"]');
      await page.waitForTimeout(2000);

      // Check for threshold alert
      await helpers.expectElementVisible('[data-testid="threshold-alert"]');
      const thresholdAlertMessage = await helpers.getTextContent('[data-testid="threshold-alert-message"]');
      expect(thresholdAlertMessage).toContain('cpu_usage');
      expect(thresholdAlertMessage).toContain('threshold');
      helpers.logStep('Threshold alert triggered correctly');

      // Step 3: Test alert escalation
      await page.waitForTimeout(5000); // Wait for escalation
      const escalatedAlert = page.locator('[data-testid="escalated-alert"]');
      if (await escalatedAlert.count() > 0) {
        await expect(escalatedAlert).toBeVisible();
        helpers.logStep('Alert escalated as expected');
      }

      // Step 4: Test alert resolution
      await helpers.waitAndClick('[data-testid="resolve-threshold-alert"]');
      await helpers.expectElementHidden('[data-testid="threshold-alert"]');
      helpers.logStep('Alert resolved successfully');
    });

    test('should support alert notifications across channels', async ({ page }) => {
      helpers.logStep('Testing multi-channel alert notifications');

      await helpers.waitAndClick('[data-testid="real-time-nav-link"]');
      await helpers.expectElementVisible('[data-testid="real-time-dashboard"]');

      // Step 1: Configure notification channels
      await helpers.waitAndClick('[data-testid="notification-channels-tab"]');
      await helpers.expectElementVisible('[data-testid="notification-settings"]');

      // Enable email notifications
      await helpers.waitAndClick('[data-testid="enable-email-notifications"]');
      await helpers.fillField('[data-testid="notification-email"]', 'test@example.com');

      // Enable webhook notifications
      await helpers.waitAndClick('[data-testid="enable-webhook-notifications"]');
      await helpers.fillField('[data-testid="webhook-url"]', 'https://example.com/webhook');

      await helpers.waitAndClick('[data-testid="save-notification-settings"]');
      helpers.logStep('Notification channels configured');

      // Step 2: Trigger test notification
      await helpers.waitAndClick('[data-testid="trigger-test-notification"]');
      await helpers.expectElementVisible('[data-testid="notification-sent-indicator"]');
      helpers.logStep('Test notification sent');

      // Step 3: Verify notification delivery status
      await helpers.waitAndClick('[data-testid="notification-status-tab"]');
      await helpers.expectElementVisible('[data-testid="notification-delivery-status"]');

      const emailStatus = page.locator('[data-testid="email-notification-status"]');
      const webhookStatus = page.locator('[data-testid="webhook-notification-status"]');

      await expect(emailStatus).toBeVisible();
      await expect(webhookStatus).toBeVisible();

      const emailStatusText = await helpers.getTextContent('[data-testid="email-notification-status"]');
      const webhookStatusText = await helpers.getTextContent('[data-testid="webhook-notification-status"]');

      expect(emailStatusText).toMatch(/sent|delivered|failed/);
      expect(webhookStatusText).toMatch(/sent|delivered|failed/);
      helpers.logStep(`Notification status - Email: ${emailStatusText}, Webhook: ${webhookStatusText}`);

      // Step 4: Test notification templates
      await helpers.waitAndClick('[data-testid="notification-templates-tab"]');
      await helpers.expectElementVisible('[data-testid="notification-template-editor"]');

      await helpers.selectOption('[data-testid="template-type"]', 'alert');
      await helpers.fillField('[data-testid="template-subject"]', 'Test Alert Notification');
      await helpers.fillField('[data-testid="template-body"]', 'Alert: {{alert_title}} - {{alert_message}}');

      await helpers.waitAndClick('[data-testid="preview-template"]');
      await helpers.expectElementVisible('[data-testid="template-preview"]');
      helpers.logStep('Notification template preview working');
    });
  });

  test.describe('Real-time Performance Monitoring', () => {
    test('should monitor and display system performance metrics', async ({ page }) => {
      helpers.logStep('Testing real-time performance monitoring');

      await helpers.waitAndClick('[data-testid="real-time-nav-link"]');
      await helpers.expectElementVisible('[data-testid="real-time-dashboard"]');

      // Step 1: Navigate to performance monitoring
      await helpers.waitAndClick('[data-testid="performance-monitoring-tab"]');
      await helpers.expectElementVisible('[data-testid="performance-metrics"]');

      // Step 2: Verify CPU monitoring
      await helpers.expectElementVisible('[data-testid="cpu-usage-gauge"]');
      const cpuValue = await helpers.getTextContent('[data-testid="cpu-usage-value"]');
      expect(cpuValue).toMatch(/\d+%/);
      helpers.logStep(`CPU usage: ${cpuValue}`);

      // Step 3: Verify memory monitoring
      await helpers.expectElementVisible('[data-testid="memory-usage-gauge"]');
      const memoryValue = await helpers.getTextContent('[data-testid="memory-usage-value"]');
      expect(memoryValue).toMatch(/\d+%|\d+MB|\d+GB/);
      helpers.logStep(`Memory usage: ${memoryValue}`);

      // Step 4: Verify network monitoring
      await helpers.expectElementVisible('[data-testid="network-traffic-chart"]');
      const networkChart = page.locator('[data-testid="network-traffic-chart"]');
      await expect(networkChart.locator('svg')).toBeVisible();
      helpers.logStep('Network traffic chart displayed');

      // Step 5: Verify response time monitoring
      await helpers.expectElementVisible('[data-testid="response-time-chart"]');
      const responseTimeValue = await helpers.getTextContent('[data-testid="avg-response-time"]');
      expect(responseTimeValue).toMatch(/\d+ms/);
      helpers.logStep(`Average response time: ${responseTimeValue}`);

      // Step 6: Test performance alerts
      await helpers.waitAndClick('[data-testid="simulate-high-cpu"]');
      await page.waitForTimeout(2000);

      const performanceAlert = page.locator('[data-testid="performance-alert"]');
      if (await performanceAlert.count() > 0) {
        await expect(performanceAlert).toBeVisible();
        const alertMessage = await helpers.getTextContent('[data-testid="performance-alert-message"]');
        expect(alertMessage).toContain('CPU');
        helpers.logStep('Performance alert triggered for high CPU');
      }
    });

    test('should provide performance historical data and trends', async ({ page }) => {
      helpers.logStep('Testing performance historical data and trends');

      await helpers.waitAndClick('[data-testid="real-time-nav-link"]');
      await helpers.waitAndClick('[data-testid="performance-history-tab"]');
      await helpers.expectElementVisible('[data-testid="performance-history"]');

      // Step 1: Test time range selection
      await helpers.selectOption('[data-testid="time-range-select"]', '1h');
      await page.waitForTimeout(1000);

      await helpers.expectElementVisible('[data-testid="performance-history-chart"]');
      helpers.logStep('1 hour performance history loaded');

      // Step 2: Test different time ranges
      const timeRanges = ['24h', '7d', '30d'];

      for (const range of timeRanges) {
        await helpers.selectOption('[data-testid="time-range-select"]', range);
        await page.waitForTimeout(1000);

        const chartData = page.locator('[data-testid="chart-data-points"]');
        await expect(chartData).toHaveCount.greaterThan(0);
        helpers.logStep(`${range} performance history loaded`);
      }

      // Step 3: Test performance trend analysis
      await helpers.waitAndClick('[data-testid="trend-analysis-tab"]');
      await helpers.expectElementVisible('[data-testid="performance-trends"]');

      const trendIndicators = page.locator('[data-testid="trend-indicator"]');
      await expect(trendIndicators).toHaveCount.greaterThan(0);

      for (let i = 0; i < await trendIndicators.count(); i++) {
        const indicator = trendIndicators.nth(i);
        await expect(indicator.locator('[data-testid="trend-metric"]')).toBeVisible();
        await expect(indicator.locator('[data-testid="trend-direction"]')).toBeVisible();
        await expect(indicator.locator('[data-testid="trend-percentage"]')).toBeVisible();
      }
      helpers.logStep('Performance trend analysis completed');

      // Step 4: Test performance comparisons
      await helpers.waitAndClick('[data-testid="performance-comparison-tab"]');
      await helpers.expectElementVisible('[data-testid="performance-comparison"]');

      await helpers.selectOption('[data-testid="comparison-period"]', 'day-over-day');
      await page.waitForTimeout(1000);

      const comparisonResults = page.locator('[data-testid="comparison-result"]');
      await expect(comparisonResults).toHaveCount.greaterThan(0);
      helpers.logStep('Performance comparison completed');
    });
  });

  test.describe('Real-time Error Monitoring', () => {
    test('should monitor and display application errors in real-time', async ({ page }) => {
      helpers.logStep('Testing real-time error monitoring');

      await helpers.waitAndClick('[data-testid="real-time-nav-link"]');
      await helpers.expectElementVisible('[data-testid="real-time-dashboard"]');

      // Step 1: Navigate to error monitoring
      await helpers.waitAndClick('[data-testid="error-monitoring-tab"]');
      await helpers.expectElementVisible('[data-testid="error-dashboard"]');

      // Step 2: Simulate an application error
      await helpers.waitAndClick('[data-testid="simulate-error"]');
      await page.waitForTimeout(2000);

      // Step 3: Verify error appears in monitoring dashboard
      await helpers.expectElementVisible('[data-testid="error-item"]');
      const errorItems = page.locator('[data-testid="error-item"]');
      await expect(errorItems).toHaveCount.greaterThan(0);

      const recentError = errorItems.first();
      await expect(recentError.locator('[data-testid="error-timestamp"]')).toBeVisible();
      await expect(recentError.locator('[data-testid="error-message"]')).toBeVisible();
      await expect(recentError.locator('[data-testid="error-severity"]')).toBeVisible();

      const errorMessage = await helpers.getTextContent('[data-testid="error-message"]');
      expect(errorMessage).toContain('Simulated error');
      helpers.logStep(`Error detected: ${errorMessage}`);

      // Step 4: Test error categorization
      await helpers.selectOption('[data-testid="error-category-filter"]', 'javascript');
      await page.waitForTimeout(500);

      const categorizedErrors = page.locator('[data-testid="error-item"]');
      await expect(categorizedErrors).toHaveCount.greaterThan(0);
      helpers.logStep('Error categorization working');

      // Step 5: Test error resolution tracking
      await helpers.waitAndClick('[data-testid="resolve-error"]');
      await page.waitForTimeout(1000);

      const resolvedStatus = await recentError.getAttribute('data-resolved');
      expect(resolvedStatus).toBe('true');
      helpers.logStep('Error resolution tracked');

      // Step 6: Test error rate monitoring
      await helpers.expectElementVisible('[data-testid="error-rate-chart"]');
      const errorRateChart = page.locator('[data-testid="error-rate-chart"]');
      await expect(errorRateChart.locator('svg')).toBeVisible();
      helpers.logStep('Error rate chart displayed');
    });

    test('should provide error analytics and insights', async ({ page }) => {
      helpers.logStep('Testing error analytics and insights');

      await helpers.waitAndClick('[data-testid="real-time-nav-link"]');
      await helpers.waitAndClick('[data-testid="error-analytics-tab"]');
      await helpers.expectElementVisible('[data-testid="error-analytics"]');

      // Step 1: Test error frequency analysis
      await helpers.expectElementVisible('[data-testid="error-frequency-chart"]');
      const frequencyChart = page.locator('[data-testid="error-frequency-chart"]');
      await expect(frequencyChart.locator('svg')).toBeVisible();
      helpers.logStep('Error frequency analysis displayed');

      // Step 2: Test error impact assessment
      await helpers.expectElementVisible('[data-testid="error-impact-metrics"]');
      const impactMetrics = page.locator('[data-testid="impact-metric"]');
      await expect(impactMetrics).toHaveCount.greaterThan(0);

      for (let i = 0; i < await impactMetrics.count(); i++) {
        const metric = impactMetrics.nth(i);
        await expect(metric.locator('[data-testid="impact-label"]')).toBeVisible();
        await expect(metric.locator('[data-testid="impact-value"]')).toBeVisible();
      }
      helpers.logStep('Error impact assessment completed');

      // Step 3: Test error correlation analysis
      await helpers.waitAndClick('[data-testid="error-correlation-tab"]');
      await helpers.expectElementVisible('[data-testid="error-correlation"]');

      const correlationResults = page.locator('[data-testid="correlation-result"]');
      if (await correlationResults.count() > 0) {
        await expect(correlationResults.first()).toBeVisible();
        helpers.logStep('Error correlation analysis completed');
      }

      // Step 4: Test error reporting
      await helpers.waitAndClick('[data-testid="error-reports-tab"]');
      await helpers.expectElementVisible('[data-testid="error-report-generator"]');

      await helpers.selectOption('[data-testid="report-format"]', 'pdf');
      await helpers.waitAndClick('[data-testid="generate-report"]');

      const download = await page.waitForEvent('download');
      expect(download.suggestedFilename()).toMatch(/\.pdf$/);
      helpers.logStep('Error report generated and downloaded');
    });
  });

  test.describe('Real-time User Activity Monitoring', () => {
    test('should monitor and display user activity in real-time', async ({ page }) => {
      helpers.logStep('Testing real-time user activity monitoring');

      await helpers.waitAndClick('[data-testid="real-time-nav-link"]');
      await helpers.expectElementVisible('[data-testid="real-time-dashboard"]');

      // Step 1: Navigate to user activity monitoring
      await helpers.waitAndClick('[data-testid="user-activity-tab"]');
      await helpers.expectElementVisible('[data-testid="user-activity-dashboard"]');

      // Step 2: Verify active users display
      await helpers.expectElementVisible('[data-testid="active-users-count"]');
      const activeUsersCount = await helpers.getTextContent('[data-testid="active-users-count"]');
      expect(parseInt(activeUsersCount)).toBeGreaterThanOrEqual(0);
      helpers.logStep(`Active users: ${activeUsersCount}`);

      // Step 3: Verify user activity feed
      await helpers.expectElementVisible('[data-testid="user-activity-feed"]');
      const activityItems = page.locator('[data-testid="activity-item"]');
      await expect(activityItems).toHaveCount.greaterThan(0);

      // Check activity item components
      const recentActivity = activityItems.first();
      await expect(recentActivity.locator('[data-testid="activity-user"]')).toBeVisible();
      await expect(recentActivity.locator('[data-testid="activity-action"]')).toBeVisible();
      await expect(recentActivity.locator('[data-testid="activity-timestamp"]')).toBeVisible();
      helpers.logStep('User activity feed displayed');

      // Step 4: Test user session tracking
      await helpers.expectElementVisible('[data-testid="user-sessions"]');
      const sessionItems = page.locator('[data-testid="session-item"]');
      await expect(sessionItems).toHaveCount.greaterThan(0);

      for (let i = 0; i < Math.min(await sessionItems.count(), 3); i++) {
        const session = sessionItems.nth(i);
        await expect(session.locator('[data-testid="session-user"]')).toBeVisible();
        await expect(session.locator('[data-testid="session-duration"]')).toBeVisible();
        await expect(session.locator('[data-testid="session-location"]')).toBeVisible();
      }
      helpers.logStep('User session tracking working');

      // Step 5: Test real-time activity updates
      const initialActivityCount = await activityItems.count();
      await page.waitForTimeout(3000);
      const updatedActivityCount = await activityItems.count();

      expect(updatedActivityCount).toBeGreaterThan(initialActivityCount);
      helpers.logStep('Real-time activity updates working');
    });

    test('should provide user behavior analytics', async ({ page }) => {
      helpers.logStep('Testing user behavior analytics');

      await helpers.waitAndClick('[data-testid="real-time-nav-link"]');
      await helpers.waitAndClick('[data-testid="user-behavior-tab"]');
      await helpers.expectElementVisible('[data-testid="user-behavior-analytics"]');

      // Step 1: Test popular features tracking
      await helpers.expectElementVisible('[data-testid="popular-features"]');
      const popularFeatures = page.locator('[data-testid="feature-item"]');
      await expect(popularFeatures).toHaveCount.greaterThan(0);

      for (let i = 0; i < await popularFeatures.count(); i++) {
        const feature = popularFeatures.nth(i);
        await expect(feature.locator('[data-testid="feature-name"]')).toBeVisible();
        await expect(feature.locator('[data-testid="feature-usage-count"]')).toBeVisible();
      }
      helpers.logStep('Popular features tracking working');

      // Step 2: Test user journey mapping
      await helpers.expectElementVisible('[data-testid="user-journey-map"]');
      const journeyMap = page.locator('[data-testid="journey-map"]');
      await expect(journeyMap.locator('svg')).toBeVisible();
      helpers.logStep('User journey mapping displayed');

      // Step 3: Test engagement metrics
      await helpers.expectElementVisible('[data-testid="engagement-metrics"]');
      const engagementMetrics = page.locator('[data-testid="engagement-metric"]');
      await expect(engagementMetrics).toHaveCount.greaterThan(0);

      const engagementValues = ['session_duration', 'page_views', 'bounce_rate', 'conversion_rate'];
      for (const metric of engagementValues) {
        const metricElement = page.locator(`[data-testid="${metric}"]`);
        if (await metricElement.count() > 0) {
          await expect(metricElement).toBeVisible();
          const value = await helpers.getTextContent(`[data-testid="${metric}"]`);
          expect(value).toBeTruthy();
        }
      }
      helpers.logStep('Engagement metrics displayed');

      // Step 4: Test user segmentation
      await helpers.waitAndClick('[data-testid="user-segmentation-tab"]');
      await helpers.expectElementVisible('[data-testid="user-segments"]');

      const userSegments = page.locator('[data-testid="user-segment"]');
      await expect(userSegments).toHaveCount.greaterThan(0);

      for (let i = 0; i < await userSegments.count(); i++) {
        const segment = userSegments.nth(i);
        await expect(segment.locator('[data-testid="segment-name"]')).toBeVisible();
        await expect(segment.locator('[data-testid="segment-size"]')).toBeVisible();
        await expect(segment.locator('[data-testid="segment-characteristics"]')).toBeVisible();
      }
      helpers.logStep('User segmentation completed');
    });
  });
});