import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object Model for the Multimodal Enterprise RAG Application
 *
 * Provides reusable page interaction methods and element locators
 */

export class BasePage {
  constructor(readonly page: Page) {}

  // Navigation elements
  readonly navigation = {
    dashboard: this.page.locator('[data-testid="nav-dashboard"]'),
    documents: this.page.locator('[data-testid="nav-documents"]'),
    search: this.page.locator('[data-testid="nav-search"]'),
    graph: this.page.locator('[data-testid="nav-graph"]'),
    analytics: this.page.locator('[data-testid="nav-analytics"]'),
    evaluation: this.page.locator('[data-testid="nav-evaluation"]'),
    settings: this.page.locator('[data-testid="nav-settings"]'),
  };

  // Common elements
  readonly userMenu = this.page.locator('[data-testid="user-menu"]');
  readonly logoutButton = this.page.locator('[data-testid="logout-button"]');
  readonly loadingSpinner = this.page.locator('[data-testid="loading-spinner"]');
  readonly errorMessage = this.page.locator('[data-testid="error-message"]');
  readonly successMessage = this.page.locator('[data-testid="success-message"]');

  // Helper methods
  async navigateTo(path: string) {
    await this.page.goto(path);
    await this.waitForPageLoad();
  }

  async waitForPageLoad() {
    await this.page.waitForLoadState('networkidle');
    await this.loadingSpinner.waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
  }

  async waitForElement(selector: string, timeout: number = 10000) {
    await this.page.waitForSelector(selector, { timeout });
  }

  async verifyTextVisible(text: string) {
    await expect(this.page.getByText(text)).toBeVisible();
  }

  async takeScreenshot(name: string) {
    await this.page.screenshot({ path: `test-results/screenshots/${name}-${Date.now()}.png` });
  }

  async logout() {
    await this.userMenu.click();
    await this.logoutButton.click();
    await this.page.waitForURL('/login');
  }
}

export class LoginPage extends BasePage {
  readonly emailInput = this.page.locator('[data-testid="email-input"]');
  readonly passwordInput = this.page.locator('[data-testid="password-input"]');
  readonly loginButton = this.page.locator('[data-testid="login-button"]');
  readonly registerLink = this.page.locator('[data-testid="register-link"]');
  readonly forgotPasswordLink = this.page.locator('[data-testid="forgot-password-link"]');

  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.loginButton.click();
    await this.page.waitForURL('/', { timeout: 10000 });
  }

  async verifyLoginSuccessful() {
    await this.page.waitForURL('/');
    await expect(this.page.locator('[data-testid="welcome-message"]')).toBeVisible();
  }

  async verifyLoginError() {
    await expect(this.page.locator('[data-testid="error-message"]')).toBeVisible();
  }
}

export class DocumentsPage extends BasePage {
  readonly uploadArea = this.page.locator('[data-testid="upload-area"]');
  readonly fileInput = this.page.locator('[data-testid="file-input"]');
  readonly uploadButton = this.page.locator('[data-testid="upload-button"]');
  readonly fileList = this.page.locator('[data-testid="file-list"]');
  readonly searchFiles = this.page.locator('[data-testid="search-files"]');
  readonly filterButton = this.page.locator('[data-testid="filter-button"]');
  readonly sortButton = this.page.locator('[data-testid="sort-button"]');

  // Dynamic file locators
  getFileItem(fileName: string) {
    return this.page.locator(`[data-testid="file-${fileName}"]`);
  }

  getFileStatus(fileName: string) {
    return this.page.locator(`[data-testid="file-${fileName}"] [data-testid="file-status"]`);
  }

  getFileActions(fileName: string) {
    return this.page.locator(`[data-testid="file-${fileName}"] [data-testid="file-actions"]`);
  }

  async uploadFile(filePath: string, fileName: string) {
    await this.fileInput.setInputFiles(filePath);

    // Wait for upload to appear in the list
    const fileItem = this.getFileItem(fileName);
    await fileItem.waitFor({ state: 'visible', timeout: 30000 });

    // Wait for upload to complete
    await this.page.waitForSelector(`[data-testid="file-${fileName}"][data-status="uploaded"]`, { timeout: 60000 });

    return fileItem;
  }

  async waitForFileProcessing(fileName: string, timeout: number = 120000) {
    await this.page.waitForSelector(`[data-testid="file-${fileName}"][data-status="processed"]`, { timeout });
  }

  async deleteFile(fileName: string) {
    const fileItem = this.getFileItem(fileName);
    await fileItem.hover();
    await this.getFileActions(fileName).click();
    await this.page.click('[data-testid="delete-file"]');
    await this.page.click('[data-testid="confirm-delete"]');
    await fileItem.waitFor({ state: 'hidden', timeout: 10000 });
  }

  async verifyFileUploaded(fileName: string) {
    const fileItem = this.getFileItem(fileName);
    await expect(fileItem).toBeVisible();
  }

  async verifyFileProcessed(fileName: string) {
    const fileStatus = this.getFileStatus(fileName);
    await expect(fileStatus).toHaveAttribute('data-status', 'processed');
  }
}

export class SearchPage extends BasePage {
  readonly searchInput = this.page.locator('[data-testid="search-input"]');
  readonly searchButton = this.page.locator('[data-testid="search-button"]');
  readonly clearButton = this.page.locator('[data-testid="clear-search"]');
  readonly resultsContainer = this.page.locator('[data-testid="search-results"]');
  readonly resultsList = this.page.locator('[data-testid="results-list"]');
  readonly loadingResults = this.page.locator('[data-testid="loading-results"]');
  readonly noResults = this.page.locator('[data-testid="no-results"]');

  // Tab navigation
  readonly answersTab = this.page.locator('[data-testid="answers-tab"]');
  readonly sourcesTab = this.page.locator('[data-testid="sources-tab"]');
  readonly graphTab = this.page.locator('[data-testid="graph-tab"]');
  readonly evaluationTab = this.page.locator('[data-testid="evaluation-tab"]');

  // Filters and settings
  readonly filtersButton = this.page.locator('[data-testid="filters-button"]');
  readonly modalityFilter = this.page.locator('[data-testid="modality-filter"]');
  readonly dateFilter = this.page.locator('[data-testid="date-filter"]');
  readonly sourceFilter = this.page.locator('[data-testid="source-filter"]');

  async performSearch(query: string) {
    await this.searchInput.fill(query);
    await this.searchButton.click();
    await this.resultsContainer.waitFor({ state: 'visible', timeout: 15000 });
  }

  async waitForResults() {
    await this.loadingResults.waitFor({ state: 'hidden', timeout: 15000 });
  }

  async getResultsCount() {
    return await this.resultsList.locator('[data-testid="result-item"]').count();
  }

  async verifyResultsExist() {
    await expect(this.resultsList.locator('[data-testid="result-item"]')).toHaveCount({ min: 1 });
  }

  async verifyNoResults() {
    await expect(this.noResults).toBeVisible();
  }

  async openResult(index: number = 0) {
    const results = this.resultsList.locator('[data-testid="result-item"]');
    await results.nth(index).click();
  }

  async switchToTab(tabName: 'answers' | 'sources' | 'graph' | 'evaluation') {
    const tab = this[`${tabName}Tab` as keyof this] as Locator;
    await tab.click();
    await tab.waitFor({ state: 'visible' });
  }

  async setModalityFilter(modalities: string[]) {
    await this.filtersButton.click();
    for (const modality of modalities) {
      await this.page.locator(`[data-testid="modality-${modality}"]`).click();
    }
    await this.searchButton.click(); // Apply filters
  }
}

export class KnowledgeGraphPage extends BasePage {
  readonly graphCanvas = this.page.locator('[data-testid="graph-canvas"]');
  readonly graphControls = this.page.locator('[data-testid="graph-controls"]');
  readonly zoomInButton = this.page.locator('[data-testid="zoom-in"]');
  readonly zoomOutButton = this.page.locator('[data-testid="zoom-out"]');
  readonly fitButton = this.page.locator('[data-testid="fit-graph"]');
  readonly layoutSelector = this.page.locator('[data-testid="layout-selector"]');
  readonly searchEntities = this.page.locator('[data-testid="search-entities"]');
  readonly filterEntities = this.page.locator('[data-testid="filter-entities"]');
  readonly entityDetails = this.page.locator('[data-testid="entity-details"]');
  readonly relationshipInfo = this.page.locator('[data-testid="relationship-info"]');

  // Graph statistics
  readonly nodeCount = this.page.locator('[data-testid="node-count"]');
  readonly edgeCount = this.page.locator('[data-testid="edge-count"]');
  readonly selectedEntity = this.page.locator('[data-testid="selected-entity"]');

  async waitForGraphLoad() {
    await this.graphCanvas.waitFor({ state: 'visible', timeout: 15000 });
    // Wait for nodes to appear
    await this.page.waitForSelector('[data-testid="graph-node"]', { timeout: 10000 });
  }

  async zoomIn() {
    await this.zoomInButton.click();
  }

  async zoomOut() {
    await this.zoomOutButton.click();
  }

  async fitToScreen() {
    await this.fitButton.click();
  }

  async changeLayout(layout: string) {
    await this.layoutSelector.click();
    await this.page.locator(`[data-testid="layout-${layout}"]`).click();
  }

  async selectEntity(entityName: string) {
    await this.page.locator(`[data-testid="entity-${entityName}"]`).click();
    await this.entityDetails.waitFor({ state: 'visible' });
  }

  async searchForEntity(searchTerm: string) {
    await this.searchEntities.fill(searchTerm);
    await this.page.keyboard.press('Enter');
    await this.page.locator(`[data-testid="entity-${searchTerm}"]`).waitFor({ state: 'visible' });
  }

  async verifyGraphLoaded() {
    await expect(this.graphCanvas).toBeVisible();
    await expect(this.page.locator('[data-testid="graph-node"]')).toHaveCount({ min: 1 });
  }

  async getNodeCount(): Promise<number> {
    const text = await this.nodeCount.textContent();
    return parseInt(text?.match(/\d+/)?.[0] || '0');
  }

  async getEdgeCount(): Promise<number> {
    const text = await this.edgeCount.textContent();
    return parseInt(text?.match(/\d+/)?.[0] || '0');
  }
}

export class EvaluationPage extends BasePage {
  readonly createEvaluationButton = this.page.locator('[data-testid="create-evaluation"]');
  readonly evaluationList = this.page.locator('[data-testid="evaluation-list"]');
  readonly evaluationDetails = this.page.locator('[data-testid="evaluation-details"]');
  readonly metricsOverview = this.page.locator('[data-testid="metrics-overview"]');
  readonly ragTriadMetrics = this.page.locator('[data-testid="rag-triad-metrics"]');

  // RAG Triad specific metrics
  readonly answerRelevancy = this.page.locator('[data-testid="answer-relevancy"]');
  readonly faithfulness = this.page.locator('[data-testid="faithfulness"]');
  readonly contextualRelevancy = this.page.locator('[data-testid="contextual-relevancy"]');

  // Performance metrics
  readonly latencyMetric = this.page.locator('[data-testid="latency"]');
  readonly throughputMetric = this.page.locator('[data-testid="throughput"]');
  readonly errorRateMetric = this.page.locator('[data-testid="error-rate"]');

  // Actions
  readonly runEvaluationButton = this.page.locator('[data-testid="run-evaluation"]');
  readonly exportButton = this.page.locator('[data-testid="export-results"]');
  readonly compareButton = this.page.locator('[data-testid="compare-evaluations"]');

  async createEvaluation(name: string, description: string) {
    await this.createEvaluationButton.click();
    await this.page.fill('[data-testid="evaluation-name"]', name);
    await this.page.fill('[data-testid="evaluation-description"]', description);
    await this.page.click('[data-testid="save-evaluation"]');
  }

  async runEvaluation() {
    await this.runEvaluationButton.click();
    await this.page.waitForSelector('[data-testid="evaluation-running"]', { state: 'hidden', timeout: 120000 });
  }

  async verifyRAGTriadMetrics() {
    await expect(this.answerRelevancy).toBeVisible();
    await expect(this.faithfulness).toBeVisible();
    await expect(this.contextualRelevancy).toBeVisible();
  }

  async getMetricScore(metricType: 'answer-relevancy' | 'faithfulness' | 'contextual-relevancy'): Promise<number> {
    const metric = this.page.locator(`[data-testid="${metricType}-score"]`);
    const text = await metric.textContent();
    return parseFloat(text?.match(/[\d.]+/)?.[0] || '0');
  }

  async verifyPerformanceThresholds() {
    const relevancy = await this.getMetricScore('answer-relevancy');
    const faithfulness = await this.getMetricScore('faithfulness');
    const contextual = await this.getMetricScore('contextual-relevancy');

    expect(relevancy).toBeGreaterThan(70); // >70% threshold
    expect(faithfulness).toBeGreaterThan(90); // >90% threshold
    expect(contextual).toBeGreaterThan(70); // >70% threshold
  }
}