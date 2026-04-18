/**
 * E2E Tests — Entities Page (/entities)
 *
 * Scenarios:
 *   1. Entity list loads — page title, entity rows, node counter, table columns
 *   2. Entity search works — typing a term filters the visible list
 *   3. Entity type filter works — selecting a type shows only that type
 *
 * Auth: admin@multimodal-rag.com / admin123
 * Backend: FastAPI on :8000, Frontend: Next.js on :3000
 */

import { test, expect, type Page } from '@playwright/test';
import { LoginPage } from '../pages/LoginPage';
import { EntitiesPage } from '../pages/EntitiesPage';

// ---------------------------------------------------------------------------
// Credentials (match the dev users documented in CLAUDE.md)
// ---------------------------------------------------------------------------
const ADMIN_EMAIL = 'admin@multimodal-rag.com';
const ADMIN_PASSWORD = 'admin123';

// ---------------------------------------------------------------------------
// Shared login helper — performs UI login and returns once redirected away
// ---------------------------------------------------------------------------
async function loginAsAdmin(page: Page): Promise<void> {
  const loginPage = new LoginPage(page);
  await loginPage.login(ADMIN_EMAIL, ADMIN_PASSWORD);
}

// ---------------------------------------------------------------------------
// Test Suite
// ---------------------------------------------------------------------------
test.describe('Entities Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  // -------------------------------------------------------------------------
  // Scenario 1: Entity list loads
  // -------------------------------------------------------------------------
  test('entity list loads with title, rows, node counter, and table columns', async ({
    page,
  }) => {
    const entitiesPage = new EntitiesPage(page);

    // Navigate to the entities page
    await entitiesPage.goto();

    // 1a. Page title is visible
    await expect(entitiesPage.pageTitle).toBeVisible({ timeout: 15000 });

    // 1b. Page subtitle is visible
    await expect(entitiesPage.pageSubtitle).toBeVisible();

    // 1c. Wait for skeleton loaders to clear and real data to appear
    await entitiesPage.waitForEntitiesLoaded(30000);

    // 1d. Entity rows are present — with ~2100 entities there should be rows
    const rowCount = await entitiesPage.entityRows.count();
    expect(rowCount).toBeGreaterThan(0);

    // 1e. Node counter shows a real non-zero number.
    // With default page size 100 and ~2128 total entities it shows "100 / 2128".
    // Without pagination it would show "N NODES". Either format is valid.
    await entitiesPage.waitForNodeCounterPopulated(30000);
    const counterText = await entitiesPage.nodeCounter.first().textContent();
    // Counter must match either "N NODES" or "N / M" format
    expect(counterText).toMatch(/\d+\s+NODES|\d+\s*\/\s*\d+/);
    // The first number must be > 0
    const firstNum = parseInt(counterText!.match(/(\d+)/)![1], 10);
    expect(firstNum).toBeGreaterThan(0);

    // 1f. Table has the expected column headers
    await expect(entitiesPage.columnNodeIdentity).toBeVisible();
    await expect(entitiesPage.columnClassification).toBeVisible();
    await expect(entitiesPage.columnConfidence).toBeVisible();

    // 1g. The tab bar has the documented view tabs
    await expect(entitiesPage.listTab).toBeVisible();
    await expect(entitiesPage.graphTab).toBeVisible();
    await expect(entitiesPage.pathFinderTab).toBeVisible();
    await expect(entitiesPage.searchTab).toBeVisible();

    // 1h. The tab bar has the documented action tabs
    await expect(entitiesPage.bulkOpsTab).toBeVisible();
    await expect(entitiesPage.extractTab).toBeVisible();
    await expect(entitiesPage.mergeTab).toBeVisible();
  });

  // -------------------------------------------------------------------------
  // Scenario 2: Entity search filters the list
  // -------------------------------------------------------------------------
  test('entity search filters results by matching name', async ({ page }) => {
    const entitiesPage = new EntitiesPage(page);

    await entitiesPage.goto();

    // Wait for data to be fully loaded before searching
    await entitiesPage.waitForEntitiesLoaded(30000);
    const totalRowsBefore = await entitiesPage.entityRows.count();
    expect(totalRowsBefore).toBeGreaterThan(0);

    // The search box must be visible with the correct placeholder
    await expect(entitiesPage.searchInput).toBeVisible();
    await expect(entitiesPage.searchInput).toHaveAttribute(
      'placeholder',
      'Search entities by name...'
    );

    // Type a search term that should match entities in a NLP/ML knowledge graph
    const searchTerm = 'transformer';
    await entitiesPage.search(searchTerm);

    // The active filter badge should appear: Search: "transformer"
    await expect(
      page.getByText(`Search: "${searchTerm}"`, { exact: false })
    ).toBeVisible({ timeout: 5000 });

    // If any matching rows exist, verify entity names contain the search term
    const filteredRowCount = await entitiesPage.entityRows.count();
    if (filteredRowCount > 0) {
      const names = await entitiesPage.getVisibleEntityNames();
      const allMatch = names.every((name) =>
        name.toLowerCase().includes(searchTerm.toLowerCase())
      );
      expect(allMatch).toBe(true);
    }

    // Clearing the search restores the original list
    await entitiesPage.clearSearch();
    await page.waitForTimeout(400);
    const restoredRowCount = await entitiesPage.entityRows.count();
    expect(restoredRowCount).toBe(totalRowsBefore);
  });

  // -------------------------------------------------------------------------
  // Scenario 3: Entity type filter shows only matching types
  // -------------------------------------------------------------------------
  test('entity type filter shows only PERSON entities', async ({ page }) => {
    const entitiesPage = new EntitiesPage(page);

    await entitiesPage.goto();

    // Wait for data load
    await entitiesPage.waitForEntitiesLoaded(30000);

    // The type filter trigger shows "All Types" by default (no selection)
    await expect(entitiesPage.typeFilterButtonAllTypes).toBeVisible();

    // Open the dropdown
    await entitiesPage.openTypeFilter();

    // Select the "PERSON" type checkbox item
    const personOption = page.getByRole('menuitemcheckbox', { name: 'PERSON' });
    await expect(personOption).toBeVisible({ timeout: 5000 });
    await personOption.click();

    // Close the dropdown by pressing Escape
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);

    // The button label should now show "1 Types" (since 1 type selected).
    // The trigger's text is dynamic so we match any button containing "Types".
    await expect(entitiesPage.typeFilterTrigger).toContainText('Types');
    // It should NOT still say "All Types"
    await expect(entitiesPage.typeFilterTrigger).not.toContainText('All Types');

    // An active filter badge for PERSON should appear in the filter bar.
    // The Badge component renders as a <div> with font-mono class containing the type name.
    await expect(
      page
        .locator('div.font-mono')
        .filter({ hasText: /^PERSON/ })
        .first()
    ).toBeVisible({ timeout: 5000 });

    // Wait for the filtered list to render
    await page.waitForTimeout(600);
    const filteredRowCount = await entitiesPage.entityRows.count();

    if (filteredRowCount > 0) {
      // All visible entity type badges should be "PERSON"
      const types = await entitiesPage.getVisibleEntityTypes();
      const allPerson = types.every(
        (type) => type.trim().toUpperCase() === 'PERSON'
      );
      expect(allPerson).toBe(true);
    }

    // The counter should reflect the filtered view
    const counterVisible = await page
      .getByText(/\d+.*NODES|\d+ \/ \d+/, { exact: false })
      .first()
      .isVisible();
    expect(counterVisible).toBe(true);
  });
});
