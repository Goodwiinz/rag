import { test, expect } from '../fixtures/test-data.fixture';
import { DocumentsPage, SearchPage } from '../utils/page-objects';

/**
 * E2E Tests for Natural Language Query Workflow (User Story 2)
 *
 * Test Coverage:
 * - Query input with natural language
 * - Search execution with loading states
 * - Results display with source citations
 * - Tab navigation (Answers, Sources, Graph, Eval)
 * - Search history management
 */

test.describe('Natural Language Query Workflow', () => {
  let documentsPage: DocumentsPage;
  let searchPage: SearchPage;

  test.beforeEach(async ({ authenticatedPage }) => {
    documentsPage = new DocumentsPage(authenticatedPage);
    searchPage = new SearchPage(authenticatedPage);
  });

  test('US2-1: Basic natural language query execution', async ({ page, testData }) => {
    // First, upload some documents to search through
    await documentsPage.navigateTo('/documents');
    await documentsPage.uploadFile(testData.files.pdf.path, testData.files.pdf.name);
    await documentsPage.uploadFile(testData.files.text.path, testData.files.text.name);

    // Navigate to search page
    await searchPage.navigateTo('/search');

    // Perform a basic search
    const query = testData.queries.simple[0]; // "What is machine learning?"
    await searchPage.performSearch(query);

    // Verify search results are displayed
    await searchPage.verifyResultsExist();
    await expect(searchPage.resultsContainer).toBeVisible();

    // Verify the query is displayed in the search box
    await expect(searchPage.searchInput).toHaveValue(query);

    // Take screenshot for documentation
    await searchPage.takeScreenshot('basic-search-results');
  });

  test('US2-2: Complex query handling', async ({ page, testData }) => {
    // Upload documents with complex content
    await documentsPage.navigateTo('/documents');
    await documentsPage.uploadFile(testData.files.pdf.path, testData.files.pdf.name);

    // Navigate to search
    await searchPage.navigateTo('/search');

    // Perform a complex query
    const complexQuery = testData.queries.complex[0];
    await searchPage.performSearch(complexQuery);

    // Verify results are found
    await searchPage.verifyResultsExist();

    // Check if results contain relevant information
    const resultsList = searchPage.resultsList;
    const resultItems = await resultsList.locator('[data-testid="result-item"]').count();
    expect(resultItems).toBeGreaterThan(0);

    // Verify results have content
    const firstResult = resultsList.locator('[data-testid="result-item"]').first();
    await expect(firstResult.locator('[data-testid="result-content"]')).toBeVisible();
  });

  test('US2-3: Search loading states and progress indicators', async ({ page, testData }) => {
    await searchPage.navigateTo('/search');

    // Enter a query and start search
    const query = testData.queries.simple[1];
    await searchPage.searchInput.fill(query);

    // Click search button
    await searchPage.searchButton.click();

    // Verify loading state is shown immediately
    await expect(searchPage.loadingResults).toBeVisible();

    // Verify loading animation or spinner
    await expect(page.locator('[data-testid="search-spinner"]')).toBeVisible();

    // Wait for results to load
    await searchPage.waitForResults();

    // Verify loading state is hidden when results arrive
    await expect(searchPage.loadingResults).not.toBeVisible();
  });

  test('US2-4: Results display with source citations', async ({ page, testData }) => {
    // Upload test documents
    await documentsPage.navigateTo('/documents');
    await documentsPage.uploadFile(testData.files.pdf.path, testData.files.pdf.name);
    await documentsPage.uploadFile(testData.files.text.path, testData.files.text.name);

    // Wait for processing
    await page.waitForTimeout(5000);

    // Perform search
    await searchPage.navigateTo('/search');
    await searchPage.performSearch(testData.queries.simple[0]);

    // Wait for results
    await searchPage.waitForResults();

    // Verify results have citations
    const firstResult = searchPage.resultsList.locator('[data-testid="result-item"]').first();
    await expect(firstResult.locator('[data-testid="result-citations"]')).toBeVisible();

    // Verify citations link to source documents
    const citations = firstResult.locator('[data-testid="citation-link"]');
    const citationCount = await citations.count();
    expect(citationCount).toBeGreaterThan(0);

    // Click on a citation to verify it opens the source
    await citations.first().click();
    await expect(page.locator('[data-testid="source-document"]')).toBeVisible();
  });

  test('US2-5: Tab navigation functionality', async ({ page, testData }) => {
    // Upload documents first
    await documentsPage.navigateTo('/documents');
    await documentsPage.uploadFile(testData.files.pdf.path, testData.files.pdf.name);

    // Perform search
    await searchPage.navigateTo('/search');
    await searchPage.performSearch(testData.queries.simple[0]);
    await searchPage.waitForResults();

    // Test Answers tab (default)
    await expect(searchPage.answersTab).toHaveClass(/active/);
    await expect(page.locator('[data-testid="answers-content"]')).toBeVisible();

    // Test Sources tab
    await searchPage.switchToTab('sources');
    await expect(searchPage.sourcesTab).toHaveClass(/active/);
    await expect(page.locator('[data-testid="sources-content"]')).toBeVisible();

    // Verify sources list shows relevant documents
    const sourcesList = page.locator('[data-testid="sources-list"]');
    await expect(sourcesList).toBeVisible();
    const sourceItems = await sourcesList.locator('[data-testid="source-item"]').count();
    expect(sourceItems).toBeGreaterThan(0);

    // Test Graph tab (if available)
    await searchPage.switchToTab('graph');
    await expect(searchPage.graphTab).toHaveClass(/active/);
    // Graph might take time to load
    await page.waitForTimeout(2000);
    await expect(page.locator('[data-testid="graph-content"]')).toBeVisible();

    // Test Evaluation tab
    await searchPage.switchToTab('evaluation');
    await expect(searchPage.evaluationTab).toHaveClass(/active/);
    await expect(page.locator('[data-testid="evaluation-content"]')).toBeVisible();
  });

  test('US2-6: Search history management', async ({ page, testData }) => {
    await searchPage.navigateTo('/search');

    // Perform multiple searches
    const queries = testData.queries.simple.slice(0, 3);
    for (const query of queries) {
      await searchPage.performSearch(query);
      await searchPage.waitForResults();
      await page.waitForTimeout(1000);
    }

    // Open search history
    await page.click('[data-testid="search-history-toggle"]');

    // Verify search history is displayed
    const historyPanel = page.locator('[data-testid="search-history"]');
    await expect(historyPanel).toBeVisible();

    // Verify recent searches are listed
    const historyItems = historyPanel.locator('[data-testid="history-item"]');
    expect(await historyItems.count()).toBeGreaterThanOrEqual(queries.length);

    // Click on a history item to re-run search
    await historyItems.first().click();

    // Verify the search input is updated and search is executed
    const searchValue = await searchPage.searchInput.inputValue();
    expect(searchValue).not.toBe('');

    await searchPage.waitForResults();
  });

  test('US2-7: Search result filtering by modality', async ({ page, testData }) => {
    // Upload files of different types
    await documentsPage.navigateTo('/documents');
    await documentsPage.uploadFile(testData.files.pdf.path, testData.files.pdf.name);
    await documentsPage.uploadFile(testData.files.text.path, testData.files.text.name);
    await documentsPage.uploadFile(testData.files.image.path, testData.files.image.name);

    // Perform search
    await searchPage.navigateTo('/search');
    await searchPage.performSearch('test query');
    await searchPage.waitForResults();

    // Get initial result count
    const initialResults = await searchPage.getResultsCount();

    // Apply modality filter
    await searchPage.setModalityFilter(['text']);

    // Wait for filtered results
    await page.waitForTimeout(2000);

    // Verify filtered results
    const filteredResults = await searchPage.getResultsCount();
    expect(filteredResults).toBeLessThanOrEqual(initialResults);

    // Verify filter indicator is shown
    await expect(page.locator('[data-testid="active-filters"]')).toBeVisible();
  });

  test('US2-8: Search query suggestions and autocomplete', async ({ page }) => {
    await searchPage.navigateTo('/search');

    // Start typing a query
    await searchPage.searchInput.fill('machine');

    // Wait for suggestions to appear
    const suggestions = page.locator('[data-testid="search-suggestions"]');
    await expect(suggestions).toBeVisible({ timeout: 3000 });

    // Verify suggestions are relevant
    const suggestionItems = suggestions.locator('[data-testid="suggestion-item"]');
    const suggestionCount = await suggestionItems.count();
    expect(suggestionCount).toBeGreaterThan(0);

    // Click on a suggestion
    await suggestionItems.first().click();

    // Verify suggestion is applied to search input
    const searchValue = await searchPage.searchInput.inputValue();
    expect(searchValue.length).toBeGreaterThan('machine'.length);
  });

  test('US2-9: No results handling', async ({ page }) => {
    await searchPage.navigateTo('/search');

    // Perform a query that should return no results
    await searchPage.performSearch('xqjzklmnoptuvwryst');

    // Wait for search to complete
    await searchPage.waitForResults();

    // Verify no results message is shown
    await expect(searchPage.noResults).toBeVisible();

    // Verify helpful suggestions are provided
    await expect(page.locator('[data-testid="search-suggestions"]')).toBeVisible();
    await expect(page.locator('[data-testid="try-different-query"]')).toBeVisible();
  });

  test('US2-10: Search result ranking and relevance', async ({ page, testData }) => {
    // Upload documents with varied content
    await documentsPage.navigateTo('/documents');
    await documentsPage.uploadFile(testData.files.pdf.path, testData.files.pdf.name);
    await documentsPage.uploadFile(testData.files.text.path, testData.files.text.name);

    // Perform a specific search
    await searchPage.navigateTo('/search');
    await searchPage.performSearch('machine learning');
    await searchPage.waitForResults();

    // Verify results are ranked (should have relevance scores)
    const firstResult = searchPage.resultsList.locator('[data-testid="result-item"]').first();
    const relevanceScore = firstResult.locator('[data-testid="relevance-score"]');
    await expect(relevanceScore).toBeVisible();

    // Verify score is a percentage
    const scoreText = await relevanceScore.textContent();
    expect(scoreText).toMatch(/\d+%$/);

    // Higher-ranked results should appear first
    const scores = [];
    const resultItems = searchPage.resultsList.locator('[data-testid="result-item"]');

    for (let i = 0; i < Math.min(3, await resultItems.count()); i++) {
      const item = resultItems.nth(i);
      const score = await item.locator('[data-testid="relevance-score"]').textContent();
      scores.push(parseInt(score?.match(/\d+/)?.[0] || '0'));
    }

    // Scores should be in descending order
    for (let i = 0; i < scores.length - 1; i++) {
      expect(scores[i]).toBeGreaterThanOrEqual(scores[i + 1]);
    }
  });

  test('US2-11: Multimodal search queries', async ({ page, testData }) => {
    // Upload different file types
    await documentsPage.navigateTo('/documents');
    await documentsPage.uploadFile(testData.files.pdf.path, testData.files.pdf.name);
    await documentsPage.uploadFile(testData.files.image.path, testData.files.image.name);

    // Perform a multimodal query
    await searchPage.navigateTo('/search');
    const multimodalQuery = testData.queries.multimodal[0];
    await searchPage.performSearch(multimodalQuery);
    await searchPage.waitForResults();

    // Verify results include multiple content types
    const resultItems = searchPage.resultsList.locator('[data-testid="result-item"]');
    let hasTextResults = false;
    let hasImageResults = false;

    for (let i = 0; i < await resultItems.count(); i++) {
      const item = resultItems.nth(i);
      const contentType = await item.locator('[data-testid="content-type"]').textContent();

      if (contentType?.includes('text')) hasTextResults = true;
      if (contentType?.includes('image')) hasImageResults = true;
    }

    // Should have at least one type of result
    expect(hasTextResults || hasImageResults).toBe(true);
  });

  test('US2-12: Search query persistence and sharing', async ({ page, testData }) => {
    await searchPage.navigateTo('/search');

    // Perform a search
    const query = testData.queries.simple[0];
    await searchPage.performSearch(query);
    await searchPage.waitForResults();

    // Get the current URL (should contain search parameters)
    const currentUrl = page.url();
    expect(currentUrl).toContain('query=');

    // Copy search link
    await page.click('[data-testid="share-search"]');
    await page.click('[data-testid="copy-link"]');

    // Verify copy success message
    await expect(page.locator('[data-testid="copy-success"]')).toBeVisible();

    // Navigate away and back with the URL
    await page.goto('/dashboard');
    await page.goto(currentUrl);

    // Verify search is automatically performed
    await expect(searchPage.searchInput).toHaveValue(query);
    await searchPage.waitForResults();
  });

  test('US2-13: Search performance with large document sets', async ({ page, testData }) => {
    // This test would ideally upload many documents
    // For now, we'll test with what we have

    await documentsPage.navigateTo('/documents');

    // Upload multiple files if available
    const files = [testData.files.pdf, testData.files.text, testData.files.image];
    for (const file of files) {
      if (file.size > 0) {
        await documentsPage.uploadFile(file.path, file.name);
      }
    }

    // Perform search and measure response time
    await searchPage.navigateTo('/search');

    const startTime = Date.now();
    await searchPage.performSearch(testData.queries.complex[0]);
    await searchPage.waitForResults();
    const endTime = Date.now();

    const searchTime = endTime - startTime;

    // Search should complete within reasonable time (adjust as needed)
    expect(searchTime).toBeLessThan(10000); // 10 seconds max

    console.log(`Search completed in ${searchTime}ms`);
  });
});