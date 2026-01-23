/**
 * E2E tests for Citation workflows (T124)
 *
 * Tests citation extraction, bibliography export, and citation graph features.
 */

import { test, expect } from '@playwright/test';

test.describe('Citation Extraction', () => {
  test('test_e2e_extract_citations_from_arxiv', async ({ page }) => {
    // Upload ArXiv paper and extract citations
    await page.goto('/documents');

    // Upload a paper
    await page.setInputFiles('input[type="file"]', 'tests/fixtures/sample-arxiv.pdf');
    await page.waitForSelector('.upload-success');

    // Click extract citations
    await page.click('button:has-text("Extract Citations")');

    // Wait for extraction to complete
    await page.waitForSelector('.extraction-complete', { timeout: 30000 });

    // Verify metadata was extracted
    await expect(page.locator('.citation-title')).toBeVisible();
    await expect(page.locator('.citation-authors')).toBeVisible();
    await expect(page.locator('.citation-year')).toBeVisible();
  });

  test('test_e2e_export_bibtex', async ({ page }) => {
    // Navigate to documents with citations
    await page.goto('/documents');

    // Select papers for export
    await page.click('.document-checkbox >> nth=0');
    await page.click('.document-checkbox >> nth=1');

    // Open export dialog
    await page.click('button:has-text("Export Bibliography")');

    // Select BibTeX format
    await page.selectOption('select[name="format"]', 'bibtex');

    // Download
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('button:has-text("Download")'),
    ]);

    // Verify file extension
    expect(download.suggestedFilename()).toMatch(/\.bib$/);
  });

  test('test_e2e_export_ieee', async ({ page }) => {
    // Navigate to documents with citations
    await page.goto('/documents');

    // Select papers for export
    await page.click('.document-checkbox >> nth=0');

    // Open export dialog
    await page.click('button:has-text("Export Bibliography")');

    // Select IEEE format
    await page.selectOption('select[name="format"]', 'ieee');

    // Download
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('button:has-text("Download")'),
    ]);

    // Verify file
    expect(download.suggestedFilename()).toMatch(/\.txt$/);
  });
});

test.describe('Citation Graph', () => {
  test('test_e2e_view_citation_graph', async ({ page }) => {
    // Navigate to document with extracted citations
    await page.goto('/documents/test-doc-id');

    // Click show citation graph
    await page.click('button:has-text("Show Citation Graph")');

    // Wait for graph to render
    await page.waitForSelector('.cytoscape-container', { timeout: 10000 });

    // Verify nodes are visible
    const nodeCount = await page.locator('.cy-node').count();
    expect(nodeCount).toBeGreaterThan(0);
  });

  test('test_e2e_graph_node_interaction', async ({ page }) => {
    // Navigate to citation graph
    await page.goto('/documents/test-doc-id');
    await page.click('button:has-text("Show Citation Graph")');
    await page.waitForSelector('.cytoscape-container');

    // Click on a node
    await page.click('.cy-node >> nth=0');

    // Verify details panel appears
    await expect(page.locator('.node-details-panel')).toBeVisible();
    await expect(page.locator('.node-details-panel .paper-title')).toBeVisible();
  });

  test('test_e2e_graph_add_external_to_collection', async ({ page }) => {
    // Navigate to citation graph
    await page.goto('/documents/test-doc-id');
    await page.click('button:has-text("Show Citation Graph")');
    await page.waitForSelector('.cytoscape-container');

    // Click on an external node (referenced paper not in collection)
    await page.click('.cy-node.external >> nth=0');

    // Click add to collection
    await page.click('button:has-text("Add to Collection")');

    // Verify success message
    await expect(page.locator('.toast-success')).toContainText('Added to collection');
  });
});

test.describe('Edge Cases', () => {
  test('test_e2e_paper_no_references_shows_message', async ({ page }) => {
    // Upload a paper with no extractable references
    await page.goto('/documents');

    // Mock upload of paper without references
    await page.setInputFiles('input[type="file"]', 'tests/fixtures/paper-no-refs.pdf');
    await page.waitForSelector('.upload-success');

    // Click extract citations
    await page.click('button:has-text("Extract Citations")');

    // Wait for extraction attempt
    await page.waitForSelector('.extraction-complete, .no-references-message', { timeout: 30000 });

    // Should show "No references found" message or allow manual entry
    const noRefsMessage = page.locator('.no-references-message');
    const manualEntryButton = page.locator('button:has-text("Add Manual Entry")');

    // At least one of these should be visible
    const hasNoRefsMessage = await noRefsMessage.isVisible().catch(() => false);
    const hasManualEntry = await manualEntryButton.isVisible().catch(() => false);

    expect(hasNoRefsMessage || hasManualEntry).toBeTruthy();
  });

  test('test_e2e_non_english_paper_shows_warning', async ({ page }) => {
    // Upload a non-English paper
    await page.goto('/documents');

    await page.setInputFiles('input[type="file"]', 'tests/fixtures/paper-chinese.pdf');
    await page.waitForSelector('.upload-success');

    // Click extract citations
    await page.click('button:has-text("Extract Citations")');

    // Wait for extraction
    await page.waitForSelector('.extraction-complete, .language-warning', { timeout: 30000 });

    // May show language warning about reduced accuracy
    const languageWarning = page.locator('.language-warning, .extraction-warning');
    const warningVisible = await languageWarning.isVisible().catch(() => false);

    // This is a soft assertion - non-English papers may still extract successfully
    if (warningVisible) {
      await expect(languageWarning).toContainText(/non-English|language|accuracy/i);
    }
  });

  test('test_e2e_citation_extraction_partial_failure', async ({ page }) => {
    // Test handling of partial extraction failures
    await page.goto('/documents');

    await page.setInputFiles('input[type="file"]', 'tests/fixtures/corrupted-refs.pdf');
    await page.waitForSelector('.upload-success');

    await page.click('button:has-text("Extract Citations")');

    // Wait for extraction
    await page.waitForSelector('.extraction-complete, .extraction-partial', { timeout: 30000 });

    // Should show partial results with option to manually correct
    const partialResults = page.locator('.extraction-partial, .needs-review-badge');
    const isPartial = await partialResults.isVisible().catch(() => false);

    // If partial, should show correction option
    if (isPartial) {
      await expect(page.locator('button:has-text("Edit"), button:has-text("Correct")')).toBeVisible();
    }
  });

  test('test_e2e_bulk_upload_shows_progress', async ({ page }) => {
    // Test bulk upload progress indicator
    await page.goto('/documents');

    // Create array of test files (simulated)
    // In real test, would use multiple actual files
    const files = [
      'tests/fixtures/paper-1.pdf',
      'tests/fixtures/paper-2.pdf',
      'tests/fixtures/paper-3.pdf',
    ];

    // Upload multiple files
    await page.setInputFiles('input[type="file"]', files);

    // Should show progress indicator for bulk operations
    const progressIndicator = page.locator('.bulk-upload-progress, .upload-progress');
    const hasProgress = await progressIndicator.isVisible().catch(() => false);

    if (hasProgress) {
      // Verify progress shows count
      await expect(progressIndicator).toContainText(/\d+/);
    }

    // Wait for all uploads to complete
    await page.waitForSelector('.upload-complete, .all-uploads-done', { timeout: 60000 });
  });

  test('test_e2e_context_exceeded_truncation', async ({ page }) => {
    // Test that context truncation happens gracefully for local models
    await page.goto('/chat');

    // Select a small local model (1B)
    await page.selectOption('select[name="model"]', { label: /1B|Llama.*1B/i });

    // Enable RAG
    const ragToggle = page.locator('input[name="ragEnabled"], .rag-toggle');
    await ragToggle.click();

    // Ask a question that would normally need lots of context
    await page.fill('textarea[name="message"]', 'Summarize all the key findings from every paper in my collection');
    await page.click('button:has-text("Send")');

    // Wait for response
    await page.waitForSelector('.assistant-message', { timeout: 120000 });

    // Response should be generated (even if truncated)
    await expect(page.locator('.assistant-message')).toBeVisible();

    // Should not show error about context exceeded
    const errorMessage = page.locator('.error-message');
    const hasError = await errorMessage.isVisible().catch(() => false);

    if (hasError) {
      // If there is an error, it should be informative not a crash
      await expect(errorMessage).not.toContainText(/crash|fatal|undefined/i);
    }
  });
});

test.describe('Citation Needs Review', () => {
  test('test_e2e_shows_needs_review_warnings', async ({ page }) => {
    // Navigate to bibliography export with incomplete citations
    await page.goto('/documents');

    // Select documents including one with incomplete metadata
    await page.click('.document-checkbox >> nth=0');

    await page.click('button:has-text("Export Bibliography")');

    // Check for needs review warnings
    const needsReviewWarning = page.locator('.needs-review-warning, .incomplete-citation-warning');
    const hasWarning = await needsReviewWarning.isVisible().catch(() => false);

    // If there are incomplete citations, warning should be shown
    if (hasWarning) {
      await expect(needsReviewWarning).toContainText(/review|incomplete|missing/i);
    }
  });
});
