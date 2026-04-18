/**
 * EntitiesPage Page Object Model
 *
 * Encapsulates all interactions with the /entities page.
 * Reflects the component structure from:
 *   - app/(dashboard)/entities/page.tsx
 *   - src/components/entities/EntityFilters.tsx
 *   - src/components/entities/EntityList.tsx
 */

import { type Page, type Locator, expect } from '@playwright/test';

export class EntitiesPage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  // ---- Navigation ----

  async goto() {
    await this.page.goto('/entities');
  }

  // ---- Header Locators ----

  get pageTitle(): Locator {
    // The h1 renders: NEURAL_ENTITY_REGISTRY
    return this.page.getByRole('heading', { name: 'NEURAL_ENTITY_REGISTRY' });
  }

  get pageSubtitle(): Locator {
    return this.page.getByText('Knowledge Graph Nodes Management', {
      exact: false,
    });
  }

  // ---- Filter Bar Locators ----

  get searchInput(): Locator {
    return this.page.getByPlaceholder('Search entities by name...');
  }

  /**
   * The type filter dropdown trigger button.
   * When no types are selected it reads "All Types".
   * When types are selected it reads "N Types".
   * Use a broad filter that matches either state.
   */
  get typeFilterTrigger(): Locator {
    // Matches a button whose accessible name contains "Types" (both "All Types" and "1 Types")
    return this.page.locator('button:has-text("Types")').first();
  }

  /**
   * The type filter trigger when it shows "All Types" (no selection).
   */
  get typeFilterButtonAllTypes(): Locator {
    return this.page.getByRole('button', { name: /All Types/i });
  }

  /**
   * Locates the node counter text element in the filter bar.
   *
   * The component renders:
   *   - "${filteredCount} NODES" when filteredCount === totalCount (no pagination / no filter)
   *   - "${filteredCount} / ${totalCount}" when pagination or filters reduce count
   *
   * With default page size 100 and 2128 total entities, the counter typically
   * shows "100 / 2128". We match both patterns.
   */
  get nodeCounter(): Locator {
    // Match "N NODES" or "N / M" patterns. Using getByText with a broad regex.
    return this.page.getByText(/\d+\s+NODES|\d+\s*\/\s*\d+/, { exact: false });
  }

  // ---- Loading State Locators ----

  get skeletonRows(): Locator {
    // Skeleton rows have animate-pulse class and appear during loading
    return this.page.locator('.animate-pulse');
  }

  // ---- Table Locators ----

  get tableHeader(): Locator {
    return this.page.locator('thead');
  }

  get tableBody(): Locator {
    return this.page.locator('tbody');
  }

  get entityRows(): Locator {
    return this.page.locator('tbody tr');
  }

  // Specific column headers from EntityList.tsx
  get columnNodeIdentity(): Locator {
    return this.page.getByText('Node_Identity', { exact: true });
  }

  get columnClassification(): Locator {
    return this.page.getByText('Classification', { exact: true });
  }

  get columnConfidence(): Locator {
    return this.page.getByText('Confidence', { exact: true });
  }

  // ---- Tab Locators ----

  get listTab(): Locator {
    return this.page.getByRole('tab', { name: /^List$/i });
  }

  get graphTab(): Locator {
    return this.page.getByRole('tab', { name: /^Graph$/i });
  }

  get pathFinderTab(): Locator {
    return this.page.getByRole('tab', { name: /Path Finder/i });
  }

  get searchTab(): Locator {
    return this.page.getByRole('tab', { name: /^Search$/i });
  }

  get bulkOpsTab(): Locator {
    return this.page.getByRole('tab', { name: /Bulk Ops/i });
  }

  get extractTab(): Locator {
    return this.page.getByRole('tab', { name: /^Extract$/i });
  }

  get mergeTab(): Locator {
    return this.page.getByRole('tab', { name: /^Merge$/i });
  }

  // ---- Type Filter Dropdown ----

  /** Open the type filter dropdown */
  async openTypeFilter(): Promise<void> {
    await this.typeFilterTrigger.click();
    // Wait for dropdown to open — the "Entity Types" label is in the dropdown header
    await this.page
      .getByText('Entity Types', { exact: true })
      .waitFor({ state: 'visible', timeout: 5000 });
  }

  /** Click a specific entity type option in the open dropdown */
  async selectTypeFilter(typeName: string): Promise<void> {
    const item = this.page.getByRole('menuitemcheckbox', { name: typeName });
    await item.click();
  }

  // ---- Wait Helpers ----

  /**
   * Wait for skeleton loaders to disappear, indicating data has loaded.
   * Returns when the list tab content is visible with real rows or empty state.
   */
  async waitForEntitiesLoaded(timeout = 30000): Promise<void> {
    // Wait for either real entity rows OR the empty-state text to appear.
    const tableRows = this.page.locator('tbody tr');
    const emptyState = this.page.getByText('NO_ENTITIES_FOUND', {
      exact: true,
    });
    await tableRows
      .or(emptyState)
      .first()
      .waitFor({ state: 'visible', timeout });
  }

  /**
   * Wait for the node counter to show a non-zero number.
   *
   * The counter shows either "N NODES" (no pagination/filter) or "N / M"
   * (paginated or filtered). We wait for either a non-zero "N NODES" pattern
   * or a non-zero "N / M" pattern indicating data has been fetched.
   */
  async waitForNodeCounterPopulated(timeout = 30000): Promise<void> {
    // Keep polling until counter text reflects loaded data (non-zero)
    await expect(async () => {
      // The counter element contains the count text
      const counterEl = this.page.getByText(/\d+\s+NODES|\d+\s*\/\s*\d+/, {
        exact: false,
      });
      const text = await counterEl.first().textContent({ timeout: 2000 });
      if (!text) throw new Error('Counter not found');

      // Extract the first number in the counter text
      const firstNum = parseInt(text.match(/(\d+)/)?.[1] ?? '0', 10);
      if (firstNum === 0)
        throw new Error(
          `Counter still shows 0 — data not yet loaded. Got: "${text}"`
        );
    }).toPass({ timeout });
  }

  /**
   * Type a search query. Filtering is client-side so we only need to wait
   * briefly for React to re-render.
   */
  async search(query: string): Promise<void> {
    await this.searchInput.fill(query);
    await this.page.waitForTimeout(400);
  }

  /**
   * Clear the search box using the X button or by clearing the field.
   */
  async clearSearch(): Promise<void> {
    const clearButton = this.page.getByRole('button', { name: 'Clear search' });
    if (await clearButton.isVisible()) {
      await clearButton.click();
    } else {
      await this.searchInput.clear();
    }
    await this.page.waitForTimeout(300);
  }

  /**
   * Get all visible entity names from the table.
   * Uses the bold font-mono span inside the second column.
   */
  async getVisibleEntityNames(): Promise<string[]> {
    const nameLocator = this.page.locator(
      'tbody tr td:nth-child(2) span.font-mono.font-bold'
    );
    return nameLocator.allTextContents();
  }

  /**
   * Get all visible classification badges (entity type labels).
   */
  async getVisibleEntityTypes(): Promise<string[]> {
    const badgeLocator = this.page.locator(
      'tbody tr td:nth-child(3) .font-mono'
    );
    return badgeLocator.allTextContents();
  }
}
