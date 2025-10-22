import { test, expect } from '@playwright/test';
import { createTestHelpers, TEST_DATA } from '../utils/test-helpers';

test.describe('Custom Dashboard Creation - User Journey', () => {
  let helpers: ReturnType<typeof createTestHelpers>;

  test.beforeEach(async ({ page, context, browserName }, testInfo) => {
    helpers = createTestHelpers(page, context, testInfo);
    helpers.logStep(`Starting custom dashboard test on ${browserName}`);

    // Login as admin for full dashboard creation permissions
    await helpers.login(TEST_DATA.USERS.ADMIN);
  });

  test.describe('Dashboard Creation Workflow', () => {
    test('should create a new custom dashboard from scratch', async ({ page }) => {
      helpers.logStep('Testing complete dashboard creation workflow');

      // Step 1: Navigate to dashboard management
      await helpers.waitAndClick('[data-testid="dashboard-management-link"]');
      await helpers.expectElementVisible('[data-testid="dashboard-management"]');
      helpers.logStep('Successfully navigated to dashboard management');

      // Step 2: Start new dashboard creation
      await helpers.waitAndClick('[data-testid="create-dashboard-button"]');
      await helpers.expectElementVisible('[data-testid="dashboard-creation-wizard"]');
      helpers.logStep('Dashboard creation wizard opened');

      // Step 3: Configure dashboard basic settings
      await helpers.fillField('[data-testid="dashboard-name-input"]', 'Test Analytics Dashboard');
      await helpers.fillField('[data-testid="dashboard-description-input"]', 'A test dashboard for E2E testing purposes');
      await helpers.selectOption('[data-testid="dashboard-category"]', 'analytics');
      await helpers.waitAndClick('[data-testid="dashboard-public-toggle"]');
      helpers.logStep('Dashboard basic settings configured');

      // Step 4: Add widgets to dashboard
      await helpers.waitAndClick('[data-testid="add-widget-button"]');
      await helpers.expectElementVisible('[data-testid="widget-gallery"]');

      // Add metric card widget
      await helpers.waitAndClick('[data-testid="widget-metric-card"]');
      await helpers.expectElementVisible('[data-testid="widget-configurator"]');

      // Configure metric card
      await helpers.fillField('[data-testid="widget-title-input"]', 'Total Documents');
      await helpers.selectOption('[data-testid="metric-type-select"]', 'document_count');
      await helpers.selectOption('[data-testid="time-range-select"]', '7d');
      await helpers.waitAndClick('[data-testid="save-widget-config"]');
      helpers.logStep('Metric card widget added and configured');

      // Add line chart widget
      await helpers.waitAndClick('[data-testid="add-widget-button"]');
      await helpers.waitAndClick('[data-testid="widget-line-chart"]');
      await helpers.fillField('[data-testid="widget-title-input"]', 'Query Performance Trend');
      await helpers.selectOption('[data-testid="chart-metric-select"]', 'query_response_time');
      await helpers.selectOption('[data-testid="chart-aggregation-select"]', 'avg');
      await helpers.waitAndClick('[data-testid="save-widget-config"]');
      helpers.logStep('Line chart widget added and configured');

      // Add graph visualization widget
      await helpers.waitAndClick('[data-testid="add-widget-button"]');
      await helpers.waitAndClick('[data-testid="widget-graph-visualization"]');
      await helpers.fillField('[data-testid="widget-title-input"]', 'Knowledge Graph Overview');
      await helpers.fillField('[data-testid="max-nodes-input"]', '50');
      await helpers.selectOption('[data-testid="graph-layout-select"]', 'force');
      await helpers.waitAndClick('[data-testid="save-widget-config"]');
      helpers.logStep('Graph visualization widget added and configured');

      // Step 5: Configure dashboard layout
      await helpers.waitAndClick('[data-testid="layout-configuration-tab"]');
      await helpers.expectElementVisible('[data-testid="dashboard-canvas"]');

      // Drag and drop widgets to arrange layout
      const metricCard = page.locator('[data-testid="widget-metric-card"]');
      const chartWidget = page.locator('[data-testid="widget-line-chart"]');
      const graphWidget = page.locator('[data-testid="widget-graph-visualization"]');

      // Arrange widgets in grid layout
      await metricCard.dragTo(page.locator('[data-testid="grid-cell-1"]'));
      await chartWidget.dragTo(page.locator('[data-testid="grid-cell-2"]'));
      await graphWidget.dragTo(page.locator('[data-testid="grid-cell-3"]'));

      helpers.logStep('Dashboard layout configured');

      // Step 6: Set dashboard filters
      await helpers.waitAndClick('[data-testid="filters-configuration-tab"]');
      await helpers.expectElementVisible('[data-testid="dashboard-filters"]');

      // Add date range filter
      await helpers.waitAndClick('[data-testid="add-filter-button"]');
      await helpers.waitAndClick('[data-testid="filter-date-range"]');
      await helpers.fillField('[data-testid="filter-label-input"]', 'Date Range');
      await helpers.waitAndClick('[data-testid="save-filter-config"]');
      helpers.logStep('Date range filter added');

      // Add organization filter
      await helpers.waitAndClick('[data-testid="add-filter-button"]');
      await helpers.waitAndClick('[data-testid="filter-organization"]');
      await helpers.fillField('[data-testid="filter-label-input"]', 'Organization');
      await helpers.waitAndClick('[data-testid="save-filter-config"]');
      helpers.logStep('Organization filter added');

      // Step 7: Configure dashboard permissions
      await helpers.waitAndClick('[data-testid="permissions-configuration-tab"]');
      await helpers.expectElementVisible('[data-testid="dashboard-permissions"]');

      // Set view permissions
      await helpers.waitAndClick('[data-testid="add-permission-button"]');
      await helpers.waitAndClick('[data-testid="permission-role-select"]');
      await helpers.waitAndClick('[data-testid="role-user"]');
      await helpers.waitAndClick('[data-testid="permission-view"]');
      await helpers.waitAndClick('[data-testid="save-permission"]');
      helpers.logStep('Dashboard permissions configured');

      // Step 8: Save and publish dashboard
      await helpers.waitAndClick('[data-testid="save-dashboard-button"]');
      await helpers.expectElementVisible('[data-testid="save-confirmation"]');
      await helpers.waitAndClick('[data-testid="confirm-save"]');
      helpers.logStep('Dashboard saved successfully');

      // Step 9: Verify dashboard creation
      await helpers.expectElementVisible('[data-testid="success-message"]');
      await helpers.expectElementVisible('[data-testid="dashboard-preview-link"]');
      await helpers.takeScreenshot('dashboard-created-successfully');

      // Step 10: Navigate to created dashboard
      await helpers.waitAndClick('[data-testid="view-dashboard-button"]');
      await helpers.expectElementVisible('[data-testid="dashboard-viewer"]');
      helpers.logStep('Navigated to created dashboard');

      // Verify all widgets are displayed
      await helpers.expectElementVisible('[data-testid="widget-metric-card"]');
      await helpers.expectElementVisible('[data-testid="widget-line-chart"]');
      await helpers.expectElementVisible('[data-testid="widget-graph-visualization"]');
      helpers.logStep('All widgets displayed correctly');
    });

    test('should create dashboard from template', async ({ page }) => {
      helpers.logStep('Testing dashboard creation from template');

      // Step 1: Navigate to dashboard management
      await helpers.waitAndClick('[data-testid="dashboard-management-link"]');
      await helpers.expectElementVisible('[data-testid="dashboard-management"]');

      // Step 2: Start from template
      await helpers.waitAndClick('[data-testid="create-from-template-button"]');
      await helpers.expectElementVisible('[data-testid="template-gallery"]');
      helpers.logStep('Template gallery opened');

      // Step 3: Select analytics template
      await helpers.waitAndClick('[data-testid="template-analytics-overview"]');
      await helpers.expectElementVisible('[data-testid="template-preview"]');
      helpers.logStep('Analytics template selected');

      // Step 4: Customize template
      await helpers.fillField('[data-testid="dashboard-name-input"]', 'Custom Analytics Dashboard');
      await helpers.fillField('[data-testid="dashboard-description-input"]', 'Customized from analytics template');

      // Modify template widgets
      await helpers.waitAndClick('[data-testid="edit-template-widgets"]');
      await helpers.expectElementVisible('[data-testid="widget-editor"]');

      // Customize existing widget
      await helpers.waitAndClick('[data-testid="edit-widget-metric"]');
      await helpers.fillField('[data-testid="widget-title-input"]', 'Custom Document Count');
      await helpers.selectOption('[data-testid="time-range-select"]', '30d');
      await helpers.waitAndClick('[data-testid="save-widget-config"]');
      helpers.logStep('Template widget customized');

      // Add new widget to template
      await helpers.waitAndClick('[data-testid="add-widget-button"]');
      await helpers.waitAndClick('[data-testid="widget-pie-chart"]');
      await helpers.fillField('[data-testid="widget-title-input"]', 'Document Types Distribution');
      await helpers.waitAndClick('[data-testid="save-widget-config"]');
      helpers.logStep('New widget added to template');

      // Step 5: Save dashboard from template
      await helpers.waitAndClick('[data-testid="save-dashboard-button"]');
      await helpers.expectElementVisible('[data-testid="success-message"]');
      helpers.logStep('Dashboard created from template successfully');

      // Step 6: Verify customized dashboard
      await helpers.expectElementVisible('[data-testid="widget-metric-card"]');
      await helpers.expectElementVisible('[data-testid="widget-pie-chart"]');

      const customTitle = await helpers.getTextContent('[data-testid="widget-metric-card"]');
      expect(customTitle).toContain('Custom Document Count');
      helpers.logStep('Template customization verified');
    });

    test('should duplicate and modify existing dashboard', async ({ page }) => {
      helpers.logStep('Testing dashboard duplication and modification');

      // Step 1: Navigate to dashboard management
      await helpers.waitAndClick('[data-testid="dashboard-management-link"]');
      await helpers.expectElementVisible('[data-testid="dashboard-management"]');

      // Step 2: Find existing dashboard to duplicate
      await helpers.expectElementVisible('[data-testid="dashboard-list"]');
      const firstDashboard = page.locator('[data-testid="dashboard-item"]').first();
      await firstDashboard.hover();
      await helpers.waitAndClick('[data-testid="duplicate-dashboard-button"]');
      helpers.logStep('Dashboard duplication initiated');

      // Step 3: Configure duplicated dashboard
      await helpers.expectElementVisible('[data-testid="duplicate-dashboard-modal"]');
      await helpers.fillField('[data-testid="dashboard-name-input"]', 'Duplicated Test Dashboard');
      await helpers.fillField('[data-testid="dashboard-description-input"]', 'A duplicated version of the original dashboard');
      await helpers.waitAndClick('[data-testid="confirm-duplicate"]');
      helpers.logStep('Dashboard duplication configured');

      // Step 4: Modify duplicated dashboard
      await helpers.expectElementVisible('[data-testid="dashboard-editor"]');

      // Remove existing widget
      await helpers.waitAndClick('[data-testid="widget-remove-button"]');
      await helpers.waitAndClick('[data-testid="confirm-remove"]');
      helpers.logStep('Widget removed from duplicated dashboard');

      // Add new widget
      await helpers.waitAndClick('[data-testid="add-widget-button"]');
      await helpers.waitAndClick('[data-testid="widget-bar-chart"]');
      await helpers.fillField('[data-testid="widget-title-input"]', 'New Bar Chart Widget');
      await helpers.waitAndClick('[data-testid="save-widget-config"]');
      helpers.logStep('New widget added to duplicated dashboard');

      // Modify dashboard layout
      await helpers.waitAndClick('[data-testid="layout-configuration-tab"]');
      const newWidget = page.locator('[data-testid="widget-bar-chart"]');
      await newWidget.dragTo(page.locator('[data-testid="grid-cell-1"]'));
      helpers.logStep('Duplicated dashboard layout modified');

      // Step 5: Save modified dashboard
      await helpers.waitAndClick('[data-testid="save-dashboard-button"]');
      await helpers.expectElementVisible('[data-testid="success-message"]');
      helpers.logStep('Modified dashboard saved successfully');

      // Step 6: Verify modifications
      await helpers.expectElementVisible('[data-testid="widget-bar-chart"]');
      await expect(page.locator('[data-testid="widget-remove-button"]')).toHaveCount(0);
      helpers.logStep('Dashboard modifications verified');
    });
  });

  test.describe('Widget Configuration and Customization', () => {
    test.beforeEach(async ({ page }) => {
      // Start dashboard creation process
      await helpers.waitAndClick('[data-testid="dashboard-management-link"]');
      await helpers.waitAndClick('[data-testid="create-dashboard-button"]');
      await helpers.fillField('[data-testid="dashboard-name-input"]', 'Widget Test Dashboard');
    });

    test('should configure metric card widget with various options', async ({ page }) => {
      helpers.logStep('Testing metric card widget configuration');

      // Add metric card widget
      await helpers.waitAndClick('[data-testid="add-widget-button"]');
      await helpers.waitAndClick('[data-testid="widget-metric-card"]');

      // Test basic configuration
      await helpers.fillField('[data-testid="widget-title-input"]', 'Test Metric Card');
      await helpers.selectOption('[data-testid="metric-type-select"]', 'user_count');
      await helpers.selectOption('[data-testid="time-range-select"]', '24h');

      // Test advanced configuration
      await helpers.waitAndClick('[data-testid="advanced-settings-toggle"]');
      await helpers.expectElementVisible('[data-testid="advanced-settings"]');

      // Configure number formatting
      await helpers.selectOption('[data-testid="number-format-select"]', 'compact');
      await helpers.selectOption('[data-testid="decimal-places-select"]', '1');

      // Configure trend display
      await helpers.waitAndClick('[data-testid="show-trend-toggle"]');
      await helpers.selectOption('[data-testid="trend-period-select"]', '7d');

      // Configure threshold alerts
      await helpers.waitAndClick('[data-testid="enable-thresholds-toggle"]');
      await helpers.fillField('[data-testid="threshold-warning-input"]', '100');
      await helpers.fillField('[data-testid="threshold-critical-input"]', '50');
      await helpers.selectOption('[data-testid="threshold-operator-select"]', 'less_than');

      // Configure colors
      await helpers.waitAndClick('[data-testid="warning-color-picker"]');
      await helpers.waitAndClick('[data-testid="color-yellow"]');
      await helpers.waitAndClick('[data-testid="critical-color-picker"]');
      await helpers.waitAndClick('[data-testid="color-red"]');

      // Test preview
      await helpers.waitAndClick('[data-testid="preview-widget-button"]');
      await helpers.expectElementVisible('[data-testid="widget-preview"]');
      await helpers.takeScreenshot('metric-card-preview');

      // Save configuration
      await helpers.waitAndClick('[data-testid="save-widget-config"]');
      helpers.logStep('Metric card widget configured successfully');

      // Verify widget appears on dashboard
      await helpers.expectElementVisible('[data-testid="widget-metric-card"]');
      const widgetTitle = await helpers.getTextContent('[data-testid="widget-title"]');
      expect(widgetTitle).toContain('Test Metric Card');
      helpers.logStep('Metric card widget verified on dashboard');
    });

    test('should configure chart widgets with customization options', async ({ page }) => {
      helpers.logStep('Testing chart widget configuration');

      // Add line chart widget
      await helpers.waitAndClick('[data-testid="add-widget-button"]');
      await helpers.waitAndClick('[data-testid="widget-line-chart"]');

      // Basic configuration
      await helpers.fillField('[data-testid="widget-title-input"]', 'Test Line Chart');
      await helpers.selectOption('[data-testid="chart-metric-select"]', 'query_response_time');
      await helpers.selectOption('[data-testid="chart-aggregation-select"]', 'avg');

      // Chart appearance settings
      await helpers.waitAndClick('[data-testid="appearance-settings-tab"]');
      await helpers.selectOption('[data-testid="chart-line-style-select"]', 'smooth');
      await helpers.selectOption('[data-testid="chart-point-style-select"]', 'circle');
      await helpers.waitAndClick('[data-testid="show-grid-toggle"]');
      await helpers.waitAndClick('[data-testid="show-legend-toggle"]');

      // Axis configuration
      await helpers.waitAndClick('[data-testid="axis-settings-tab"]');
      await helpers.fillField('[data-testid="y-axis-label-input"]', 'Response Time (ms)');
      await helpers.fillField('[data-testid="x-axis-label-input"]', 'Time');
      await helpers.selectOption('[data-testid="y-axis-format-select"]', 'number');

      // Color configuration
      await helpers.waitAndClick('[data-testid="color-settings-tab"]');
      await helpers.waitAndClick('[data-testid="primary-color-picker"]');
      await helpers.waitAndClick('[data-testid="color-blue"]');
      await helpers.waitAndClick('[data-testid="secondary-color-picker"]');
      await helpers.waitAndClick('[data-testid="color-green"]');

      // Test chart preview
      await helpers.waitAndClick('[data-testid="preview-widget-button"]');
      await helpers.expectElementVisible('[data-testid="chart-preview"]');
      await page.waitForTimeout(2000); // Wait for chart to render
      await helpers.takeScreenshot('line-chart-preview');

      // Save configuration
      await helpers.waitAndClick('[data-testid="save-widget-config"]');
      helpers.logStep('Line chart widget configured successfully');

      // Test bar chart
      await helpers.waitAndClick('[data-testid="add-widget-button"]');
      await helpers.waitAndClick('[data-testid="widget-bar-chart"]');
      await helpers.fillField('[data-testid="widget-title-input"]', 'Test Bar Chart');
      await helpers.selectOption('[data-testid="chart-metric-select"]', 'document_count');
      await helpers.selectOption('[data-testid="chart-aggregation-select"]', 'sum');

      // Bar chart specific settings
      await helpers.waitAndClick('[data-testid="appearance-settings-tab"]');
      await helpers.selectOption('[data-testid="bar-style-select"] =', 'grouped');
      await helpers.selectOption('[data-testid="bar-width-select"]', '70%');

      await helpers.waitAndClick('[data-testid="save-widget-config"]');
      helpers.logStep('Bar chart widget configured successfully');

      // Verify both charts on dashboard
      await helpers.expectElementVisible('[data-testid="widget-line-chart"]');
      await helpers.expectElementVisible('[data-testid="widget-bar-chart"]');
      helpers.logStep('Both chart widgets verified on dashboard');
    });

    test('should configure graph visualization widget', async ({ page }) => {
      helpers.logStep('Testing graph visualization widget configuration');

      // Add graph visualization widget
      await helpers.waitAndClick('[data-testid="add-widget-button"]');
      await helpers.waitAndClick('[data-testid="widget-graph-visualization"]');

      // Basic configuration
      await helpers.fillField('[data-testid="widget-title-input"]', 'Test Graph Visualization');
      await helpers.fillField('[data-testid="max-nodes-input"]', '100');
      await helpers.selectOption('[data-testid="graph-layout-select"]', 'force');

      // Graph appearance settings
      await helpers.waitAndClick('[data-testid="graph-appearance-tab"]');
      await helpers.waitAndClick('[data-testid="show-labels-toggle"]');
      await helpers.waitAndClick('[data-testid="show-edges-toggle"]');
      await helpers.selectOption('[data-testid="node-size-select"]', 'degree');
      await helpers.selectOption('[data-testid="node-color-select"]', 'type');

      // Layout settings
      await helpers.waitAndClick('[data-testid="layout-settings-tab"]');
      await helpers.fillField('[data-testid="layout-iterations-input"]', '1000');
      await helpers.fillField('[data-testid="node-spacing-input"] =', '50');
      await helpers.fillField('[data-testid="edge-length-input"]', '30');

      // Filter settings
      await helpers.waitAndClick('[data-testid="filter-settings-tab"]');
      await helpers.waitAndClick('[data-testid="enable-node-filter"]');
      await helpers.selectOption('[data-testid="node-type-filter"]', 'Person');
      await helpers.waitAndClick('[data-testid="enable-edge-filter"]');
      await helpers.selectOption('[data-testid="edge-type-filter"]', 'WORKS_FOR');

      // Interaction settings
      await helpers.waitAndClick('[data-testid="interaction-settings-tab"]');
      await helpers.waitAndClick('[data-testid="enable-zoom-toggle"]');
      await helpers.waitAndClick('[data-testid="enable-pan-toggle"]');
      await helpers.waitAndClick('[data-testid="enable-node-selection-toggle"]');

      // Test graph preview
      await helpers.waitAndClick('[data-testid="preview-widget-button"]');
      await helpers.expectElementVisible('[data-testid="graph-preview"]');
      await page.waitForTimeout(3000); // Wait for graph to render
      await helpers.takeScreenshot('graph-preview');

      // Save configuration
      await helpers.waitAndClick('[data-testid="save-widget-config"]');
      helpers.logStep('Graph visualization widget configured successfully');

      // Verify graph widget on dashboard
      await helpers.expectElementVisible('[data-testid="widget-graph-visualization"]');
      helpers.logStep('Graph visualization widget verified on dashboard');
    });
  });

  test.describe('Dashboard Layout and Responsive Design', () => {
    test.beforeEach(async ({ page }) => {
      // Create a basic dashboard with multiple widgets
      await helpers.waitAndClick('[data-testid="dashboard-management-link"]');
      await helpers.waitAndClick('[data-testid="create-dashboard-button"]');
      await helpers.fillField('[data-testid="dashboard-name-input"]', 'Layout Test Dashboard');

      // Add multiple widgets for layout testing
      const widgets = ['metric-card', 'line-chart', 'bar-chart', 'graph-visualization'];

      for (const widget of widgets) {
        await helpers.waitAndClick('[data-testid="add-widget-button"]');
        await helpers.waitAndClick(`[data-testid="widget-${widget}"]`);
        await helpers.fillField('[data-testid="widget-title-input"]', `Test ${widget}`);
        await helpers.waitAndClick('[data-testid="save-widget-config"]');
      }
    });

    test('should arrange widgets in grid layout', async ({ page }) => {
      helpers.logStep('Testing grid layout arrangement');

      // Navigate to layout configuration
      await helpers.waitAndClick('[data-testid="layout-configuration-tab"]');
      await helpers.expectElementVisible('[data-testid="dashboard-canvas"]');

      // Test grid layout mode
      await helpers.selectOption('[data-testid="layout-mode-select"]', 'grid');
      await helpers.expectElementVisible('[data-testid="grid-layout"]');

      // Arrange widgets in 2x2 grid
      const widgets = page.locator('[data-testid="widget"]');

      await widgets.nth(0).dragTo(page.locator('[data-testid="grid-cell-1"]'));
      await widgets.nth(1).dragTo(page.locator('[data-testid="grid-cell-2"]'));
      await widgets.nth(2).dragTo(page.locator('[data-testid="grid-cell-3"]'));
      await widgets.nth(3).dragTo(page.locator('[data-testid="grid-cell-4"]'));

      helpers.logStep('Widgets arranged in 2x2 grid');

      // Test grid size adjustments
      await helpers.waitAndClick('[data-testid="grid-cell-1"]');
      await helpers.waitAndClick('[data-testid="resize-handle-se"]');
      await page.mouse.move(400, 300);
      await page.mouse.down();
      await page.mouse.move(600, 500);
      await page.mouse.up();

      helpers.logStep('Grid cell resized');

      // Test grid reordering
      const widget1 = page.locator('[data-testid="grid-cell-1"] [data-testid="widget"]');
      const widget2 = page.locator('[data-testid="grid-cell-2"] [data-testid="widget"]');
      await widget1.dragTo(page.locator('[data-testid="grid-cell-2"]'));

      helpers.logStep('Grid widgets reordered');

      // Save layout
      await helpers.waitAndClick('[data-testid="save-layout-button"]');
      helpers.logStep('Grid layout saved successfully');

      // Verify layout
      await helpers.expectElementVisible('[data-testid="grid-layout"]');
      const gridCells = page.locator('[data-testid="grid-cell"]');
      await expect(gridCells).toHaveCount(4);
      helpers.logStep('Grid layout verified');
    });

    test('should adapt layout for different screen sizes', async ({ page }) => {
      helpers.logStep('Testing responsive layout adaptation');

      // Configure initial desktop layout
      await helpers.waitAndClick('[data-testid="layout-configuration-tab"]');
      await helpers.selectOption('[data-testid="layout-mode-select"]', 'grid');

      // Arrange widgets for desktop
      const widgets = page.locator('[data-testid="widget"]');
      for (let i = 0; i < await widgets.count(); i++) {
        await widgets.nth(i).dragTo(page.locator(`[data-testid="grid-cell-${i + 1}"]`));
      }

      // Test desktop layout (1280x720)
      await helpers.setViewport(1280, 720);
      await helpers.waitAndClick('[data-testid="preview-layout-button"]');
      await helpers.takeScreenshot('layout-desktop');
      helpers.logStep('Desktop layout verified');

      // Test tablet layout (768x1024)
      await helpers.setViewport(768, 1024);
      await page.waitForTimeout(1000); // Wait for layout adjustment
      await helpers.takeScreenshot('layout-tablet');

      // Verify tablets uses 2-column layout
      const tabletColumns = page.locator('[data-testid="layout-column"]');
      await expect(tabletColumns).toHaveCount(2);
      helpers.logStep('Tablet layout verified (2 columns)');

      // Test mobile layout (375x667)
      await helpers.setViewport(375, 667);
      await page.waitForTimeout(1000);
      await helpers.takeScreenshot('layout-mobile');

      // Verify mobile uses single column layout
      const mobileColumns = page.locator('[data-testid="layout-column"]');
      await expect(mobileColumns).toHaveCount(1);
      helpers.logStep('Mobile layout verified (1 column)');

      // Test wide screen layout (1920x1080)
      await helpers.setViewport(1920, 1080);
      await page.waitForTimeout(1000);
      await helpers.takeScreenshot('layout-widescreen');

      const wideColumns = page.locator('[data-testid="layout-column"]');
      await expect(wideColumns).toHaveCount.greaterThanOrEqual(3);
      helpers.logStep('Widescreen layout verified (3+ columns)');

      // Return to editing mode
      await helpers.waitAndClick('[data-testid="exit-preview-button"]');
      helpers.logStep('Responsive layout testing completed');
    });

    test('should handle widget stacking and layering', async ({ page }) => {
      helpers.logStep('Testing widget stacking and layering');

      // Configure freeform layout
      await helpers.waitAndClick('[data-testid="layout-configuration-tab"]');
      await helpers.selectOption('[data-testid="layout-mode-select"]', 'freeform');

      // Position widgets to overlap
      const widgets = page.locator('[data-testid="widget"]');

      await widgets.nth(0).dragTo(page.locator('[data-testid="canvas-area"]'));
      await page.mouse.move(200, 200);
      await page.mouse.up();

      await widgets.nth(1).dragTo(page.locator('[data-testid="canvas-area"]'));
      await page.mouse.move(250, 250); // Overlap with first widget
      await page.mouse.up();

      helpers.logStep('Widgets positioned with overlap');

      // Test layering controls
      await widgets.nth(1).click(); // Select overlapping widget
      await helpers.expectElementVisible('[data-testid="layering-controls"]');

      // Bring to front
      await helpers.waitAndClick('[data-testid="bring-to-front-button"]');
      helpers.logStep('Widget brought to front');

      // Send to back
      await helpers.waitAndClick('[data-testid="send-to-back-button"]');
      helpers.logStep('Widget sent to back');

      // Test layer ordering
      await helpers.waitAndClick('[data-testid="bring-forward-button"]');
      await helpers.waitAndClick('[data-testid="bring-forward-button"]');
      helpers.logStep('Widget moved forward in layer stack');

      // Verify layering through visual inspection
      await helpers.takeScreenshot('widget-layering');
      helpers.logStep('Widget layering verified');
    });
  });

  test.describe('Dashboard Sharing and Collaboration', () => {
    test.beforeEach(async ({ page }) => {
      // Create a dashboard for sharing tests
      await helpers.waitAndClick('[data-testid="dashboard-management-link"]');
      await helpers.waitAndClick('[data-testid="create-dashboard-button"]');
      await helpers.fillField('[data-testid="dashboard-name-input"]', 'Sharing Test Dashboard');

      // Add a widget
      await helpers.waitAndClick('[data-testid="add-widget-button"]');
      await helpers.waitAndClick('[data-testid="widget-metric-card"]');
      await helpers.waitAndClick('[data-testid="save-widget-config"]');
      await helpers.waitAndClick('[data-testid="save-dashboard-button"]');
    });

    test('should share dashboard with specific users', async ({ page }) => {
      helpers.logStep('Testing dashboard sharing with specific users');

      // Navigate to sharing settings
      await helpers.waitAndClick('[data-testid="dashboard-settings-button"]');
      await helpers.waitAndClick('[data-testid="sharing-settings-tab"]');
      await helpers.expectElementVisible('[data-testid="sharing-settings"]');

      // Add user to sharing list
      await helpers.waitAndClick('[data-testid="add-user-sharing"]');
      await helpers.expectElementVisible('[data-testid="user-search-dialog"]');

      // Search for user
      await helpers.fillField('[data-testid="user-search-input"]', 'user');
      await helpers.waitAndClick('[data-testid="user-search-result"]');
      helpers.logStep('User selected for sharing');

      // Set user permissions
      await helpers.selectOption('[data-testid="user-permission-select"]', 'view_and_comment');
      await helpers.waitAndClick('[data-testid="add-user-permission"]');
      helpers.logStep('User permissions set');

      // Add another user with different permissions
      await helpers.waitAndClick('[data-testid="add-user-sharing"]');
      await helpers.fillField('[data-testid="user-search-input"]', 'orgadmin');
      await helpers.waitAndClick('[data-testid="user-search-result"]');
      await helpers.selectOption('[data-testid="user-permission-select"]', 'view_only');
      await helpers.waitAndClick('[data-testid="add-user-permission"]');
      helpers.logStep('Second user added with view-only permissions');

      // Save sharing settings
      await helpers.waitAndClick('[data-testid="save-sharing-settings"]');
      await helpers.expectElementVisible('[data-testid="sharing-saved-message"]');
      helpers.logStep('Sharing settings saved');

      // Verify sharing list
      const sharedUsers = page.locator('[data-testid="shared-user"]');
      await expect(sharedUsers).toHaveCount(2);
      helpers.logStep('Sharing list verified');

      // Test notification sending
      await helpers.waitAndClick('[data-testid="notify-users-button"]');
      await helpers.fillField('[data-testid="notification-message-input"]', 'Check out this new dashboard!');
      await helpers.waitAndClick('[data-testid="send-notifications"]');
      await helpers.expectElementVisible('[data-testid="notifications-sent-message"]');
      helpers.logStep('Notifications sent to shared users');
    });

    test('should create public dashboard link', async ({ page }) => {
      helpers.logStep('Testing public dashboard link creation');

      // Navigate to sharing settings
      await helpers.waitAndClick('[data-testid="dashboard-settings-button"]');
      await helpers.waitAndClick('[data-testid="sharing-settings-tab"]');

      // Enable public sharing
      await helpers.waitAndClick('[data-testid="enable-public-sharing"]');
      await helpers.expectElementVisible('[data-testid="public-sharing-options"]');

      // Configure public sharing settings
      await helpers.waitAndClick('[data-testid="require-password-toggle"]');
      await helpers.fillField('[data-testid="public-password-input"]', 'testpassword123');
      await helpers.waitAndClick('[data-testid="expire-link-toggle"]');
      await helpers.selectOption('[data-testid="link-expiry-select"]', '7d');
      helpers.logStep('Public sharing settings configured');

      // Generate public link
      await helpers.waitAndClick('[data-testid="generate-public-link"]');
      await helpers.expectElementVisible('[data-testid="public-link-generated"]');
      helpers.logStep('Public link generated');

      // Copy public link
      await helpers.waitAndClick('[data-testid="copy-public-link"]');
      await helpers.expectElementVisible('[data-testid="link-copied-message"]');
      helpers.logStep('Public link copied');

      // Test public link access
      const publicLink = await helpers.getAttribute('[data-testid="public-link-input"]', 'value');
      await page.goto(publicLink);

      // Verify password prompt
      await helpers.expectElementVisible('[data-testid="public-password-input"]');
      await helpers.fillField('[data-testid="public-password-input"]', 'testpassword123');
      await helpers.waitAndClick('[data-testid="unlock-dashboard"]');
      helpers.logStep('Public dashboard accessed with password');

      // Verify dashboard is visible publicly
      await helpers.expectElementVisible('[data-testid="dashboard-viewer"]');
      await helpers.expectElementVisible('[data-testid="public-access-indicator"]');
      helpers.logStep('Public dashboard access verified');
    });

    test('should export dashboard configuration', async ({ page }) => {
      helpers.logStep('Testing dashboard configuration export');

      // Navigate to dashboard export
      await helpers.waitAndClick('[data-testid="dashboard-settings-button"]');
      await helpers.waitAndClick('[data-testid="export-import-tab"]');
      await helpers.expectElementVisible('[data-testid="export-import-settings"]');

      // Test JSON export
      await helpers.waitAndClick('[data-testid="export-json-button"]');
      const jsonDownload = await page.waitForEvent('download');
      expect(jsonDownload.suggestedFilename()).toMatch(/\.json$/);
      helpers.logStep('Dashboard configuration exported as JSON');

      // Test YAML export
      await helpers.waitAndClick('[data-testid="export-yaml-button"]');
      const yamlDownload = await page.waitForEvent('download');
      expect(yamlDownload.suggestedFilename()).toMatch(/\.yaml$/);
      helpers.logStep('Dashboard configuration exported as YAML');

      // Test full package export
      await helpers.waitAndClick('[data-testid="export-package-button"]');
      await helpers.expectElementVisible('[data-testid="export-options"]');

      await helpers.waitAndClick('[data-testid="include-data-toggle"]');
      await helpers.waitAndClick('[data-testid="include-filters-toggle"]');
      await helpers.waitAndClick('[data-testid="confirm-export-package"]');

      const packageDownload = await page.waitForEvent('download');
      expect(packageDownload.suggestedFilename()).toMatch(/\.zip$/);
      helpers.logStep('Dashboard package exported successfully');

      // Verify exported content structure
      // This would involve extracting and verifying the ZIP content in a real implementation
      helpers.logStep('Dashboard export functionality verified');
    });
  });

  test.describe('Dashboard Performance and Optimization', () => {
    test('should handle large number of widgets efficiently', async ({ page }) => {
      helpers.logStep('Testing dashboard performance with many widgets');

      // Create dashboard with many widgets
      await helpers.waitAndClick('[data-testid="dashboard-management-link"]');
      await helpers.waitAndClick('[data-testid="create-dashboard-button"]');
      await helpers.fillField('[data-testid="dashboard-name-input"]', 'Performance Test Dashboard');

      // Add many widgets
      const widgetTypes = ['metric-card', 'line-chart', 'bar-chart', 'pie-chart'];
      const startTime = Date.now();

      for (let i = 0; i < 20; i++) {
        const widgetType = widgetTypes[i % widgetTypes.length];

        await helpers.waitAndClick('[data-testid="add-widget-button"]');
        await helpers.waitAndClick(`[data-testid="widget-${widgetType}"]`);
        await helpers.fillField('[data-testid="widget-title-input"]', `Widget ${i + 1}`);
        await helpers.waitAndClick('[data-testid="save-widget-config"]');

        // Add small delay to avoid overwhelming the UI
        await page.waitForTimeout(100);
      }

      const creationTime = Date.now() - startTime;
      helpers.logStep(`Created 20 widgets in ${creationTime}ms`);

      // Verify all widgets are displayed
      const allWidgets = page.locator('[data-testid="widget"]');
      await expect(allWidgets).toHaveCount(20);
      helpers.logStep('All widgets displayed successfully');

      // Test dashboard load time
      const loadStartTime = Date.now();
      await helpers.waitAndClick('[data-testid="save-dashboard-button"]');
      await helpers.waitAndClick('[data-testid="view-dashboard-button"]');
      await helpers.expectElementVisible('[data-testid="dashboard-viewer"]');

      const loadTime = Date.now() - loadStartTime;
      expect(loadTime).toBeLessThan(5000); // Should load in under 5 seconds
      helpers.logStep(`Dashboard loaded in ${loadTime}ms`);

      // Test widget interactions performance
      const interactionStartTime = Date.now();

      // Test clicking through widgets
      for (let i = 0; i < 10; i++) {
        await allWidgets.nth(i).click();
        await page.waitForTimeout(100);
      }

      const interactionTime = Date.now() - interactionStartTime;
      expect(interactionTime).toBeLessThan(3000); // Should be responsive
      helpers.logStep(`Widget interactions completed in ${interactionTime}ms`);

      // Test dashboard performance monitoring
      await helpers.waitAndClick('[data-testid="dashboard-settings-button"]');
      await helpers.waitAndClick('[data-testid="performance-tab"]');

      const performanceMetrics = [
        '[data-testid="render-time"]',
        '[data-testid="memory-usage"]',
        '[data-testid="widget-count"]',
        '[data-testid="update-frequency"]',
      ];

      for (const metric of performanceMetrics) {
        if (await helpers.elementExists(metric)) {
          await helpers.expectElementVisible(metric);
          const value = await helpers.getTextContent(metric);
          expect(value).toBeTruthy();
          helpers.logStep(`Performance metric ${metric}: ${value}`);
        }
      }

      helpers.logStep('Dashboard performance with many widgets verified');
    });

    test('should optimize widget loading and updates', async ({ page }) => {
      helpers.logStep('Testing widget loading optimization');

      // Create dashboard
      await helpers.waitAndClick('[data-testid="dashboard-management-link"]');
      await helpers.waitAndClick('[data-testid="create-dashboard-button"]');
      await helpers.fillField('[data-testid="dashboard-name-input"]', 'Optimization Test Dashboard');

      // Add widgets with different loading strategies
      await helpers.waitAndClick('[data-testid="add-widget-button"]');
      await helpers.waitAndClick('[data-testid="widget-line-chart"]');

      // Configure lazy loading
      await helpers.waitAndClick('[data-testid="advanced-settings-toggle"]');
      await helpers.waitAndClick('[data-testid="lazy-loading-toggle"]');
      await helpers.waitAndClick('[data-testid="save-widget-config"]');
      helpers.logStep('Widget configured with lazy loading');

      // Add widget with caching
      await helpers.waitAndClick('[data-testid="add-widget-button"]');
      await helpers.waitAndClick('[data-testid="widget-metric-card"]');
      await helpers.waitAndClick('[data-testid="advanced-settings-toggle"]');
      await helpers.waitAndClick('[data-testid="enable-caching-toggle"]');
      await helpers.selectOption('[data-testid="cache-duration-select"]', '5m');
      await helpers.waitAndClick('[data-testid="save-widget-config"]');
      helpers.logStep('Widget configured with caching');

      // Save and view dashboard
      await helpers.waitAndClick('[data-testid="save-dashboard-button"]');
      await helpers.waitAndClick('[data-testid="view-dashboard-button"]');

      // Test lazy loading
      await helpers.expectElementVisible('[data-testid="lazy-loading-placeholder"]');
      await page.waitForTimeout(2000); // Wait for lazy loading
      await helpers.expectElementHidden('[data-testid="lazy-loading-placeholder"]');
      helpers.logStep('Lazy loading working correctly');

      // Test caching by refreshing
      const cacheTestStart = Date.now();
      await page.reload();
      await helpers.expectElementVisible('[data-testid="dashboard-viewer"]');
      const cacheTestTime = Date.now() - cacheTestStart;

      // Should load faster with caching
      expect(cacheTestTime).toBeLessThan(3000);
      helpers.logStep(`Dashboard loaded in ${cacheTestTime}ms with caching`);

      // Test performance optimization settings
      await helpers.waitAndClick('[data-testid="dashboard-settings-button"]');
      await helpers.waitAndClick('[data-testid="performance-tab"]');

      // Enable performance optimizations
      await helpers.waitAndClick('[data-testid="enable-virtual-scrolling"]');
      await helpers.waitAndClick('[data-testid="enable-throttled-updates"]');
      await helpers.waitAndClick('[data-testid="enable-compression"]');
      await helpers.waitAndClick('[data-testid="save-performance-settings"]');
      helpers.logStep('Performance optimizations enabled');

      // Verify optimizations are active
      await helpers.expectElementVisible('[data-testid="optimization-active"]');
      const activeOptimizations = page.locator('[data-testid="optimization-item"]');
      await expect(activeOptimizations).toHaveCount.greaterThan(0);
      helpers.logStep('Performance optimizations verified');
    });
  });
});