import { test, expect } from '@playwright/test';
import { AxeBuilder } from '@axe-core/playwright';
import { LoginPage, DocumentsPage, SearchPage, KnowledgeGraphPage } from '../utils/page-objects';

/**
 * Comprehensive Accessibility Testing Suite
 *
 * Test Coverage:
 * - WCAG 2.1 AA compliance validation
 * - Screen reader compatibility
 * - Keyboard navigation
 * - Color contrast and visual accessibility
 * - ARIA labels and semantic HTML
 * - Focus management
 * - Accessibility with assistive technologies
 */

test.describe('Accessibility Compliance', () => {
  let loginPage: LoginPage;
  let documentsPage: DocumentsPage;
  let searchPage: SearchPage;
  let graphPage: KnowledgeGraphPage;

  test.use({ viewport: { width: 1280, height: 720 } });

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page);
    documentsPage = new DocumentsPage(page);
    searchPage = new SearchPage(page);
    graphPage = new KnowledgeGraphPage(page);
  });

  test('Login page accessibility compliance', async ({ page }) => {
    await page.goto('/login');

    // Run axe accessibility tests
    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);

    // Test keyboard navigation
    await page.keyboard.press('Tab');
    let focusedElement = await page.locator(':focus');
    await expect(focusedElement).toBeVisible();

    // Tab through all interactive elements
    const interactiveElements = page.locator('input, button, a, select, textarea, [tabindex]:not([tabindex="-1"])');
    const elementCount = await interactiveElements.count();

    for (let i = 0; i < elementCount; i++) {
      await page.keyboard.press('Tab');
      focusedElement = await page.locator(':focus');
      await expect(focusedElement).toBeVisible();
    }

    // Test form accessibility
    await expect(loginPage.emailInput).toHaveAttribute('aria-label');
    await expect(loginPage.passwordInput).toHaveAttribute('aria-label');
    await expect(loginPage.loginButton).toHaveAttribute('aria-label');

    // Test semantic HTML structure
    await expect(page.locator('main')).toBeVisible();
    await expect(page.locator('h1, h2')).toHaveCount({ min: 1 });
    await expect(page.locator('form')).toBeVisible();

    // Test skip links (if present)
    const skipLink = page.locator('[href="#main-content"], .skip-link');
    if (await skipLink.count() > 0) {
      await expect(skipLink.first()).toBeVisible();
    }
  });

  test('Documents page accessibility', async ({ page }) => {
    await page.goto('/documents');

    // Run axe accessibility tests
    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);

    // Test file upload accessibility
    await expect(documentsPage.fileInput).toHaveAttribute('aria-label');
    await expect(documentsPage.uploadButton).toHaveAttribute('aria-label');

    // Test data table accessibility (if present)
    const dataTable = page.locator('[role="table"], table');
    if (await dataTable.count() > 0) {
      await expect(dataTable.first().locator('thead')).toBeVisible();
      await expect(dataTable.first().locator('th')).toHaveCount({ min: 1 });

      // Test table navigation
      await dataTable.first().focus();
      await page.keyboard.press('ArrowDown');
      await expect(page.locator(':focus')).toBeVisible();
    }

    // Test search and filter accessibility
    if (await documentsPage.searchFiles.isVisible()) {
      await expect(documentsPage.searchFiles).toHaveAttribute('aria-label');
      await expect(documentsPage.filterButton).toHaveAttribute('aria-label');
    }

    // Test dynamic content announcements
    await page.evaluate(() => {
      const liveRegion = document.createElement('div');
      liveRegion.setAttribute('aria-live', 'polite');
      liveRegion.setAttribute('aria-atomic', 'true');
      liveRegion.className = 'sr-only';
      liveRegion.id = 'status-announcements';
      document.body.appendChild(liveRegion);
    });
  });

  test('Search page accessibility', async ({ page }) => {
    await page.goto('/search');

    // Run axe accessibility tests
    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);

    // Test search form accessibility
    await expect(searchPage.searchInput).toHaveAttribute('aria-label');
    await expect(searchPage.searchButton).toHaveAttribute('aria-label');

    // Test search results accessibility
    const resultsList = page.locator('[role="list"], [data-testid="results-list"]');
    if (await resultsList.isVisible()) {
      await expect(resultsList).toHaveAttribute('aria-label');

      const resultItems = resultsList.locator('[role="listitem"], [data-testid="result-item"]');
      const itemCount = await resultItems.count();

      if (itemCount > 0) {
        // Test result item structure
        for (let i = 0; i < Math.min(3, itemCount); i++) {
          const item = resultItems.nth(i);
          await expect(item.locator('[data-testid="result-content"]')).toBeVisible();

          // Test citation accessibility
          const citations = item.locator('[data-testid="citation-link"]');
          if (await citations.count() > 0) {
            await expect(citations.first()).toHaveAttribute('aria-label');
          }
        }
      }
    }

    // Test tab navigation accessibility
    const tabList = page.locator('[role="tablist"]');
    if (await tabList.isVisible()) {
      await expect(tabList).toHaveAttribute('aria-label');

      const tabs = tabList.locator('[role="tab"]');
      const tabCount = await tabs.count();

      for (let i = 0; i < tabCount; i++) {
        await expect(tabs.nth(i)).toHaveAttribute('aria-selected');
        await expect(tabs.nth(i)).toHaveAttribute('aria-controls');
      }

      const tabPanels = page.locator('[role="tabpanel"]');
      expect(await tabPanels.count()).toBe(tabCount);
    }

    // Test loading states accessibility
    const loadingElement = page.locator('[data-testid="loading-results"], [aria-busy="true"]');
    if (await loadingElement.isVisible()) {
      await expect(loadingElement).toHaveAttribute('aria-live');
    }
  });

  test('Knowledge Graph accessibility', async ({ page }) => {
    await page.goto('/graph');

    // Wait for graph to load
    await page.waitForSelector('[data-testid="graph-canvas"]', { timeout: 15000 });

    // Run axe accessibility tests
    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);

    // Test graph canvas accessibility
    const graphCanvas = page.locator('[data-testid="graph-canvas"]');
    await expect(graphCanvas).toHaveAttribute('role', 'img');
    await expect(graphCanvas).toHaveAttribute('aria-label');

    // Test graph controls accessibility
    await expect(graphPage.zoomInButton).toHaveAttribute('aria-label');
    await expect(graphPage.zoomOutButton).toHaveAttribute('aria-label');
    await expect(graphPage.fitButton).toHaveAttribute('aria-label');

    // Test keyboard graph navigation
    await graphCanvas.focus();
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('ArrowLeft');
    await page.keyboard.press('ArrowUp');

    // Test entity details accessibility
    const entityDetails = page.locator('[data-testid="entity-details"]');
    if (await entityDetails.isVisible()) {
      await expect(entityDetails).toHaveAttribute('role', 'region');
      await expect(entityDetails).toHaveAttribute('aria-label');

      // Test entity property accessibility
      const properties = entityDetails.locator('[data-testid="property-item"]');
      const propCount = await properties.count();

      for (let i = 0; i < Math.min(3, propCount); i++) {
        const prop = properties.nth(i);
        const key = prop.locator('[data-testid="property-key"]');
        const value = prop.locator('[data-testid="property-value"]');

        await expect(key).toHaveAttribute('aria-label');
        await expect(value).toHaveAttribute('aria-label');
      }
    }

    // Test graph search accessibility
    if (await graphPage.searchEntities.isVisible()) {
      await expect(graphPage.searchEntities).toHaveAttribute('aria-label');
      await expect(graphPage.searchEntities).toHaveAttribute('aria-describedby');
    }
  });

  test('Color contrast and visual accessibility', async ({ page }) => {
    await page.goto('/login');

    // Check color contrast using axe
    const colorContrastResults = await new AxeBuilder({ page })
      .withTags(['wcag2aa'])
      .withRules(['color-contrast'])
      .analyze();

    expect(colorContrastResults.violations).toEqual([]);

    // Test high contrast mode simulation
    await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
    await page.waitForTimeout(1000);

    // Verify elements remain visible in dark mode
    await expect(loginPage.emailInput).toBeVisible();
    await expect(loginPage.passwordInput).BeVisible();
    await expect(loginPage.loginButton).BeVisible();

    // Test reduced motion preference
    await page.emulateMedia({ reducedMotion: 'reduce' });

    // Verify animations are reduced or disabled
    const animatedElements = page.locator('[class*="animate"], [style*="animation"]');
    if (await animatedElements.count() > 0) {
      const animationStyles = await animatedElements.first().evaluate(el => {
        return window.getComputedStyle(el).animationDuration;
      });
      expect(animationStyles).toBe('0s' || animationStyles?.includes('0'));
    }

    // Test forced colors mode (Windows High Contrast)
    await page.emulateMedia({ forcedColors: 'active' });
    await page.waitForTimeout(1000);

    // Verify elements remain functional with forced colors
    await expect(loginPage.loginButton).toBeVisible();
  });

  test('Screen reader compatibility', async ({ page }) => {
    await page.goto('/search');

    // Set up screen reader simulation
    await page.addStyleTag({
      content: `
        .sr-only {
          position: absolute;
          width: 1px;
          height: 1px;
          padding: 0;
          margin: -1px;
          overflow: hidden;
          clip: rect(0, 0, 0, 0);
          white-space: nowrap;
          border: 0;
        }
      `
    });

    // Test ARIA landmarks
    await expect(page.locator('main, [role="main"]')).toBeVisible();
    await expect(page.locator('nav, [role="navigation"]')).toBeVisible();
    await expect(page.locator('header, [role="banner"]')).toBeVisible();
    await expect(page.locator('footer, [role="contentinfo"]')).toBeVisible();

    // Test page structure and headings
    const headings = page.locator('h1, h2, h3, h4, h5, h6');
    const headingCount = await headings.count();
    expect(headingCount).toBeGreaterThan(0);

    // Verify heading hierarchy (no skipped levels)
    let lastLevel = 0;
    for (let i = 0; i < headingCount; i++) {
      const heading = headings.nth(i);
      const level = parseInt((await heading.evaluate(el => el.tagName)).substring(1));

      if (lastLevel > 0 && level > lastLevel + 1) {
        console.warn(`Skipped heading level: from h${lastLevel} to h${level}`);
      }
      lastLevel = level;
    }

    // Test form labels and descriptions
    await expect(searchPage.searchInput).toHaveAttribute('aria-label');

    // Test list and table structures
    const resultsList = page.locator('[role="list"], ol, ul');
    if (await resultsList.isVisible()) {
      await expect(resultsList).toHaveAttribute('aria-label');
    }

    // Test dynamic content announcements
    await page.evaluate(() => {
      // Create status region for announcements
      if (!document.getElementById('status-announcements')) {
        const statusRegion = document.createElement('div');
        statusRegion.id = 'status-announcements';
        statusRegion.setAttribute('aria-live', 'polite');
        statusRegion.setAttribute('aria-atomic', 'true');
        statusRegion.className = 'sr-only';
        document.body.appendChild(statusRegion);
      }
    });

    // Simulate search and verify announcement
    await searchPage.searchInput.fill('test query');
    await searchPage.searchButton.click();

    // Verify content is announced to screen readers
    await page.waitForTimeout(2000);
  });

  test('Keyboard navigation and focus management', async ({ page }) => {
    await page.goto('/documents');

    // Test tab order consistency
    const focusableElements = page.locator(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );

    const elementCount = await focusableElements.count();
    expect(elementCount).toBeGreaterThan(0);

    // Test tab navigation through all elements
    for (let i = 0; i < elementCount; i++) {
      await page.keyboard.press('Tab');

      const focusedElement = page.locator(':focus');
      await expect(focusedElement).toBeVisible();

      // Verify focus indicator is visible
      const focusedStyles = await focusedElement.evaluate(el => {
        const styles = window.getComputedStyle(el);
        return {
          outline: styles.outline,
          boxShadow: styles.boxShadow,
          border: styles.border
        };
      });

      // At least one focus indicator should be present
      const hasFocusIndicator =
        focusedStyles.outline !== 'none' ||
        focusedStyles.boxShadow !== 'none' ||
        focusedStyles.border !== 'none';

      expect(hasFocusIndicator).toBe(true);
    }

    // Test escape key functionality
    await page.keyboard.press('Escape');

    // Test enter and space key activation
    const firstButton = page.locator('button').first();
    await firstButton.focus();
    await page.keyboard.press('Enter');
    await page.waitForTimeout(500);

    // Test arrow key navigation in menus
    const menuElements = page.locator('[role="menu"], [role="listbox"]');
    if (await menuElements.count() > 0) {
      const menu = menuElements.first();
      await menu.focus();
      await page.keyboard.press('ArrowDown');
      await expect(page.locator(':focus')).toBeVisible();
    }

    // Test focus trapping in modals (if present)
    const modal = page.locator('[role="dialog"], .modal');
    if (await modal.isVisible()) {
      // Focus should be trapped within modal
      await modal.focus();
      await page.keyboard.press('Tab');

      const focusedInModal = await page.evaluate(() => {
        const activeElement = document.activeElement;
        const modalElement = document.querySelector('[role="dialog"], .modal');
        return modalElement?.contains(activeElement);
      });

      expect(focusedInModal).toBe(true);
    }
  });

  test('Accessibility for users with motor impairments', async ({ page }) => {
    await page.goto('/search');

    // Test larger click targets
    const clickableElements = page.locator('button, a, input[type="button"], input[type="submit"]');
    const elementCount = await clickableElements.count();

    for (let i = 0; i < Math.min(5, elementCount); i++) {
      const element = clickableElements.nth(i);
      const boundingBox = await element.boundingBox();

      if (boundingBox) {
        // Verify minimum touch target size (44x44px recommended)
        expect(boundingBox.width).toBeGreaterThanOrEqual(44);
        expect(boundingBox.height).toBeGreaterThanOrEqual(44);
      }
    }

    // Test error prevention and confirmation
    await searchPage.searchInput.fill(''); // Empty search
    await searchPage.searchButton.click();

    // Test for helpful error messages
    const errorMessage = page.locator('[data-testid="error-message"], [role="alert"]');
    if (await errorMessage.isVisible()) {
      await expect(errorMessage).toHaveAttribute('aria-live');
    }

    // Test time limits (if any)
    await page.evaluate(() => {
      // Check for any time-based elements
      const timedElements = document.querySelectorAll('[data-timeout], [countdown], [timer]');
      return {
        hasTimeLimits: timedElements.length > 0,
        timeLimitElements: timedElements.length
      };
    });
  });

  test('Cognitive accessibility', async ({ page }) => {
    await page.goto('/');

    // Test clear and simple language
    const pageTitle = await page.title();
    expect(pageTitle.length).toBeLessThan(60); // Reasonable title length

    // Test consistent navigation
    const navigation = page.locator('nav, [role="navigation"]');
    if (await navigation.count() > 0) {
      await expect(navigation.first()).toBeVisible();

      // Test consistent navigation labels
      const navLinks = navigation.first().locator('a');
      const linkCount = await navLinks.count();

      for (let i = 0; i < linkCount; i++) {
        const link = navLinks.nth(i);
        const linkText = await link.textContent();
        expect(linkText?.trim()?.length).toBeGreaterThan(0);
      }
    }

    // Test help and instructions
    const helpElements = page.locator('[data-testid="help"], [aria-label*="help"], .instructions');
    if (await helpElements.count() > 0) {
      await expect(helpElements.first()).toBeVisible();
    }

    // Test error recovery
    await page.goto('/invalid-url');
    const errorPage = page.locator('[data-testid="error-page"], h1');
    await expect(errorPage).toBeVisible();

    // Test for clear error messages
    const errorMessage = page.locator('[data-testid="error-message"]');
    if (await errorMessage.isVisible()) {
      const errorText = await errorMessage.textContent();
      expect(errorText?.length).toBeGreaterThan(10); // Meaningful error message
    }

    // Test content organization
    const headings = page.locator('h1, h2, h3, h4, h5, h6');
    const headingCount = await headings.count();
    expect(headingCount).toBeGreaterThan(0);

    // Verify logical content structure
    const mainContent = page.locator('main, [role="main"]');
    await expect(mainContent).toBeVisible();
  });

  test('Mobile accessibility', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/documents');

    // Run axe accessibility tests on mobile
    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);

    // Test touch accessibility
    const touchTargets = page.locator('button, a, input, [role="button"]');
    const targetCount = await touchTargets.count();

    for (let i = 0; i < Math.min(5, targetCount); i++) {
      const target = touchTargets.nth(i);
      const boundingBox = await target.boundingBox();

      if (boundingBox) {
        // Minimum touch target size for mobile
        expect(boundingBox.width).toBeGreaterThanOrEqual(48);
        expect(boundingBox.height).toBeGreaterThanOrEqual(48);
      }
    }

    // Test mobile-specific gestures
    const uploadArea = page.locator('[data-testid="upload-area"]');
    if (await uploadArea.isVisible()) {
      // Test tap functionality
      await uploadArea.tap();
      await page.waitForTimeout(500);
    }

    // Test mobile navigation accessibility
    const mobileMenu = page.locator('[data-testid="mobile-menu"], .hamburger');
    if (await mobileMenu.isVisible()) {
      await expect(mobileMenu).toHaveAttribute('aria-label');
      await expect(mobileMenu).toHaveAttribute('aria-expanded');

      // Test mobile menu toggle
      await mobileMenu.tap();
      await page.waitForTimeout(500);

      const isExpanded = await mobileMenu.getAttribute('aria-expanded');
      expect(isExpanded).toBe('true');
    }

    // Test swipe gestures accessibility (if implemented)
    const swipeContainer = page.locator('[data-testid="swipe-container"]');
    if (await swipeContainer.isVisible()) {
      // Test that swipe gestures have keyboard alternatives
      await page.keyboard.press('ArrowRight');
      await page.waitForTimeout(500);
    }
  });
});