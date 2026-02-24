import { test, expect } from '@playwright/test';
import { injectAxe, checkA11y } from 'axe-playwright';
import { createTestHelpers, TEST_DATA } from '../utils/test-helpers';

test.describe('Dashboard Accessibility Tests', () => {
  let helpers: ReturnType<typeof createTestHelpers>;

  test.beforeEach(async ({ page, context }, testInfo) => {
    helpers = createTestHelpers(page, context, testInfo);

    // Login and navigate to dashboard
    await helpers.login(TEST_DATA.USERS.ADMIN);

    // Inject axe after login/navigation so it remains available on the current document.
    await injectAxe(page);
  });

  test.describe('Main Dashboard Accessibility', () => {
    test('should meet WCAG 2.1 AA standards on analytics dashboard', async ({ page }) => {
      helpers.logStep('Testing analytics dashboard accessibility');

      // Navigate to analytics dashboard
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');
      await page.waitForLoadState('networkidle');
      await page.addStyleTag({
        content: '*,*::before,*::after{animation:none!important;transition:none!important;}',
      });
      await page.waitForTimeout(300);

      // Check accessibility with axe
      await checkA11y(page, null, {
        detailedReport: true,
        detailedReportOptions: { html: true },
        axeOptions: {
          runOnly: {
            type: 'tag',
            values: ['wcag2a', 'wcag2aa', 'wcag21aa'],
          },
        },
      });

      helpers.logStep('Analytics dashboard accessibility check completed');
    });

    test('should have proper semantic structure', async ({ page }) => {
      helpers.logStep('Testing semantic HTML structure');

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Check for proper heading hierarchy
      const headings = await page.locator('h1, h2, h3, h4, h5, h6').all();
      let lastLevel = 0;

      for (const heading of headings) {
        const level = parseInt(await heading.getAttribute('aria-level') ||
                             heading.textContent()?.match(/h(\d)/i)?.[1] || '1');

        // Headings should not skip levels (e.g., h1 to h3)
        expect(level).toBeLessThanOrEqual(lastLevel + 1);
        lastLevel = level;
      }

      // Check for main landmarks
      await expect(page.locator('main')).toHaveCount(1);
      await expect(page.locator('nav')).toHaveCount.greaterThan(0);
      await expect(page.locator('header')).toHaveCount(1);

      helpers.logStep('Semantic structure validation completed');
    });

    test('should have proper ARIA labels and roles', async ({ page }) => {
      helpers.logStep('Testing ARIA labels and roles');

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Check interactive elements have proper labels
      const buttons = page.locator('button:not([aria-label]):not([aria-labelledby])');
      await expect(buttons).toHaveCount(0); // All buttons should have accessible names

      // Check for proper ARIA roles on custom components
      const chartElements = page.locator('[data-testid*="chart"]');
      for (let i = 0; i < await chartElements.count(); i++) {
        const chart = chartElements.nth(i);
        const role = await chart.getAttribute('role');
        if (role) {
          // Verify custom roles are appropriate
          expect(['img', 'application', 'region']).toContain(role);
        }
      }

      // Check form elements have proper labels
      const inputs = page.locator('input:not([aria-label]):not([aria-labelledby])');
      const unlabeledInputs = await inputs.filter({ has: page.locator('label') }).count();
      expect(unlabeledInputs).toBe(0); // All inputs should have labels

      helpers.logStep('ARIA labels and roles validation completed');
    });

    test('should support keyboard navigation', async ({ page }) => {
      helpers.logStep('Testing keyboard navigation');

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Test tab navigation
      await page.keyboard.press('Tab');
      let focusedElement = await page.locator(':focus');
      expect(await focusedElement.count()).toBe(1);

      // Test that all interactive elements are reachable via keyboard
      const interactiveElements = page.locator('button, a, input, select, textarea, [tabindex]:not([tabindex="-1"])');

      for (let i = 0; i < Math.min(await interactiveElements.count(), 10); i++) {
        await page.keyboard.press('Tab');
        focusedElement = await page.locator(':focus');

        // Element should be visible and focusable
        await expect(focusedElement).toBeVisible();

        // Check for visible focus indicator
        const computedStyle = await focusedElement.evaluate(el => {
          return window.getComputedStyle(el);
        });

        // Element should have some focus styling
        expect(computedStyle.outline || computedStyle.boxShadow).toBeTruthy();
      }

      // Test Enter/Space activation
      const firstButton = page.locator('button').first();
      await firstButton.focus();
      await page.keyboard.press('Enter');

      // Button should activate (we can't easily test the result, but should not error)
      await page.waitForTimeout(500);

      helpers.logStep('Keyboard navigation validation completed');
    });

    test('should have sufficient color contrast', async ({ page }) => {
      helpers.logStep('Testing color contrast');

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Check specific elements for contrast
      const textElements = page.locator('p, h1, h2, h3, h4, h5, h6, span, div');

      for (let i = 0; i < Math.min(await textElements.count(), 20); i++) {
        const element = textElements.nth(i);
        const computedStyle = await element.evaluate(el => {
          return window.getComputedStyle(el);
        });

        const color = computedStyle.color;
        const backgroundColor = computedStyle.backgroundColor;

        // Skip transparent backgrounds
        if (backgroundColor === 'rgba(0, 0, 0, 0)' || backgroundColor === 'transparent') {
          continue;
        }

        // Element should have readable colors (this is a basic check)
        expect(color).toBeTruthy();
        expect(backgroundColor).toBeTruthy();
      }

      // Test specific high-contrast scenarios
      await page.emulateMedia({ forcedColors: 'active' });
      await page.waitForTimeout(1000);

      // Elements should still be readable in high contrast mode
      const highContrastElements = page.locator('button, a, input');
      await expect(highContrastElements).toHaveCount.greaterThan(0);

      helpers.logStep('Color contrast validation completed');
    });

    test('should have proper focus management', async ({ page }) => {
      helpers.logStep('Testing focus management');

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Test focus trap in modals
      const modalTrigger = page.locator('[data-testid*="modal-trigger"]').first();
      if (await modalTrigger.count() > 0) {
        await modalTrigger.click();
        await page.waitForTimeout(500);

        // Focus should be inside modal
        const modalFocus = await page.locator(':focus');
        const modal = page.locator('[data-testid*="modal"]');
        expect(await modal.count()).toBe(1);

        // Tab should stay within modal
        const modalElement = await modal.first();
        const modalBoundingBox = await modalElement.boundingBox();

        if (modalBoundingBox) {
          await page.keyboard.press('Tab');
          await page.keyboard.press('Tab');
          await page.keyboard.press('Tab');

          const focusedAfterTabs = await page.locator(':focus');
          const focusedBoundingBox = await focusedAfterTabs.boundingBox();

          if (focusedBoundingBox && modalBoundingBox) {
            // Focused element should be within modal bounds
            expect(focusedBoundingBox.x).toBeGreaterThanOrEqual(modalBoundingBox.x);
            expect(focusedBoundingBox.y).toBeGreaterThanOrEqual(modalBoundingBox.y);
          }
        }

        // Close modal
        await page.keyboard.press('Escape');
        await page.waitForTimeout(500);
      }

      // Test focus returns to triggering element
      const initialElement = await page.locator(':focus');
      expect(await initialElement.count()).toBe(1);

      helpers.logStep('Focus management validation completed');
    });

    test('should support screen readers', async ({ page }) => {
      helpers.logStep('Testing screen reader support');

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Test for alt text on images
      const images = page.locator('img');
      for (let i = 0; i < await images.count(); i++) {
        const img = images.nth(i);
        const alt = await img.getAttribute('alt');

        // Images should have alt text unless decorative
        if (alt === null || alt === '') {
          const role = await img.getAttribute('role');
          expect(role).toBe('presentation'); // Should be marked as decorative
        }
      }

      // Test for proper table headers
      const tables = page.locator('table');
      for (let i = 0; i < await tables.count(); i++) {
        const table = tables.nth(i);
        const headers = await table.locator('th').count();
        expect(headers).toBeGreaterThan(0); // Tables should have headers

        // Check scope attributes
        const thElements = await table.locator('th').all();
        for (const th of thElements) {
          const scope = await th.getAttribute('scope');
          if (scope) {
            expect(['col', 'row', 'colgroup', 'rowgroup']).toContain(scope);
          }
        }
      }

      // Test for descriptive link text
      const links = page.locator('a[href]');
      for (let i = 0; i < Math.min(await links.count(), 10); i++) {
        const link = links.nth(i);
        const text = await link.textContent();

        // Links should have descriptive text
        expect(text?.trim().length).toBeGreaterThan(0);
        expect(text?.toLowerCase()).not.toBe('click here');
        expect(text?.toLowerCase()).not.toBe('read more');
      }

      // Test for live regions
      const liveRegions = page.locator('[aria-live], [aria-atomic], [aria-relevant]');
      for (let i = 0; i < await liveRegions.count(); i++) {
        const region = liveRegions.nth(i);
        const live = await region.getAttribute('aria-live');

        if (live) {
          expect(['polite', 'assertive', 'off']).toContain(live);
        }
      }

      helpers.logStep('Screen reader support validation completed');
    });
  });

  test.describe('Form Accessibility', () => {
    test('should have accessible form controls', async ({ page }) => {
      helpers.logStep('Testing form accessibility');

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Look for filter forms
      const filterForms = page.locator('form');
      if (await filterForms.count() > 0) {
        const form = filterForms.first();

        // Test form labels
        const inputs = await form.locator('input, select, textarea').all();
        for (const input of inputs) {
          const id = await input.getAttribute('id');
          const label = page.locator(`label[for="${id}"]`);

          if (id) {
            expect(await label.count()).toBe(1);
          } else {
            const ariaLabel = await input.getAttribute('aria-label');
            const ariaLabelledBy = await input.getAttribute('aria-labelledby');

            expect(ariaLabel || ariaLabelledBy).toBeTruthy();
          }
        }

        // Test fieldset and legend for related controls
        const fieldsets = await form.locator('fieldset').all();
        for (const fieldset of fieldsets) {
          const legend = await fieldset.locator('legend').count();
          expect(legend).toBe(1);
        }

        // Test error messaging
        const errorMessages = page.locator('[data-testid*="error"], [role="alert"]');
        for (let i = 0; i < await errorMessages.count(); i++) {
          const error = errorMessages.nth(i);
          const ariaLive = await error.getAttribute('aria-live');

          // Errors should be announced to screen readers
          if (!ariaLive) {
            const role = await error.getAttribute('role');
            expect(role).toBe('alert');
          }
        }
      }

      helpers.logStep('Form accessibility validation completed');
    });

    test('should have accessible validation feedback', async ({ page }) => {
      helpers.logStep('Testing form validation accessibility');

      // Find and test form validation
      const submitButton = page.locator('button[type="submit"]').first();
      if (await submitButton.count() > 0) {
        await submitButton.click();
        await page.waitForTimeout(1000);

        // Check for validation errors
        const validationErrors = page.locator('[data-testid*="validation-error"]');

        for (let i = 0; i < await validationErrors.count(); i++) {
          const error = validationErrors.nth(i);

          // Errors should be programmatically associated with inputs
          const ariaDescribedBy = await error.getAttribute('id');
          if (ariaDescribedBy) {
            const associatedInput = page.locator(`[aria-describedby="${ariaDescribedBy}"]`);
            expect(await associatedInput.count()).toBeGreaterThan(0);
          }
        }
      }

      helpers.logStep('Form validation accessibility validation completed');
    });
  });

  test.describe('Dynamic Content Accessibility', () => {
    test('should announce dynamic content changes', async ({ page }) => {
      helpers.logStep('Testing dynamic content announcements');

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Test data updates
      const refreshButton = page.locator('[data-testid="refresh-button"]');
      if (await refreshButton.count() > 0) {
        await refreshButton.click();
        await page.waitForTimeout(2000);

        // Check for status updates
        const statusUpdates = page.locator('[aria-live="polite"], [aria-live="assertive"]');
        await expect(statusUpdates).toHaveCount.greaterThan(0);
      }

      // Test loading announcements
      await page.reload();
      const loadingAnnouncements = page.locator('[aria-live="polite"]');

      // Loading should be announced
      for (let i = 0; i < await loadingAnnouncements.count(); i++) {
        const announcement = loadingAnnouncements.nth(i);
        const text = await announcement.textContent();
        expect(text?.toLowerCase()).toMatch(/loading|loading/);
      }

      helpers.logStep('Dynamic content announcement validation completed');
    });

    test('should handle async operations accessibly', async ({ page }) => {
      helpers.logStep('Testing async operation accessibility');

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Test async loading states
      const asyncButton = page.locator('[data-testid*="async"]');
      if (await asyncButton.count() > 0) {
        await asyncButton.first().click();

        // Check for accessible loading indicators
        const loadingIndicators = page.locator('[aria-busy="true"], [data-testid*="loading"]');

        for (let i = 0; i < await loadingIndicators.count(); i++) {
          const indicator = loadingIndicators.nth(i);
          const ariaLabel = await indicator.getAttribute('aria-label');

          expect(ariaLabel).toBeTruthy();
          expect(ariaLabel?.toLowerCase()).toMatch(/loading|processing/);
        }
      }

      helpers.logStep('Async operation accessibility validation completed');
    });
  });

  test.describe('Navigation Accessibility', () => {
    test('should have accessible navigation structure', async ({ page }) => {
      helpers.logStep('Testing navigation accessibility');

      await helpers.expectElementVisible('[data-testid="dashboard-container"]');

      // Test main navigation
      const mainNav = page.locator('nav, [role="navigation"]');
      await expect(mainNav).toHaveCount.greaterThan(0);

      // Check for skip links
      const skipLinks = page.locator('a[href^="#"]');
      for (let i = 0; i < await skipLinks.count(); i++) {
        const skipLink = skipLinks.nth(i);
        const href = await skipLink.getAttribute('href');

        if (href && href.startsWith('#')) {
          const targetId = href.substring(1);
          const target = page.locator(`#${targetId}, [id="${targetId}"]`);

          if (await target.count() > 0) {
            // Target should exist and be focusable
            await expect(target.first()).toBeVisible();
          }
        }
      }

      // Test breadcrumb navigation
      const breadcrumbs = page.locator('[aria-label="breadcrumb"], nav[aria-label*="breadcrumb"]');
      if (await breadcrumbs.count() > 0) {
        const breadcrumbList = breadcrumbs.first().locator('ol, ul');
        await expect(breadcrumbList).toHaveCount(1);
      }

      helpers.logStep('Navigation accessibility validation completed');
    });

    test('should have accessible menu interactions', async ({ page }) => {
      helpers.logStep('Testing menu accessibility');

      await helpers.expectElementVisible('[data-testid="dashboard-container"]');

      // Test dropdown menus
      const dropdownTriggers = page.locator('[data-testid*="dropdown"], [aria-haspopup]');

      for (let i = 0; i < Math.min(await dropdownTriggers.count(), 5); i++) {
        const trigger = dropdownTriggers.nth(i);
        await trigger.click();
        await page.waitForTimeout(500);

        // Check for menu role
        const menu = page.locator('[role="menu"], [role="menu"]');
        if (await menu.count() > 0) {
          // Menu items should be focusable
          const menuItems = await menu.first().locator('[role="menuitem"]').all();

          for (const item of menuItems) {
            const tabIndex = await item.getAttribute('tabindex');
            expect(tabIndex === '-1' || tabIndex === '0').toBeTruthy();
          }

          // Test keyboard navigation in menu
          await page.keyboard.press('ArrowDown');
          await page.keyboard.press('ArrowUp');
          await page.keyboard.press('Escape');
        }

        await page.waitForTimeout(500);
      }

      helpers.logStep('Menu accessibility validation completed');
    });
  });

  test.describe('Mobile Accessibility', () => {
    test('should be accessible on mobile devices', async ({ page }) => {
      helpers.logStep('Testing mobile accessibility');

      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });
      await page.waitForTimeout(1000);

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');
      await page.addStyleTag({
        content: '*,*::before,*::after{animation:none!important;transition:none!important;}',
      });
      await page.waitForTimeout(300);

      // Run accessibility checks on mobile layout
      await checkA11y(page, null, {
        detailedReport: true,
        axeOptions: {
          runOnly: {
            type: 'tag',
            values: ['wcag2a', 'wcag2aa', 'wcag21aa'],
          },
        },
      });

      // Test mobile-specific elements
      const mobileMenu = page.locator('[data-testid="mobile-menu"]');
      if (await mobileMenu.count() > 0) {
        await mobileMenu.click();
        await page.waitForTimeout(500);

        // Mobile menu should be accessible
        const mobileMenuItems = page.locator('[data-testid="mobile-menu-item"]');
        await expect(mobileMenuItems).toHaveCount.greaterThan(0);

        // Test touch target sizes (44px minimum)
        for (let i = 0; i < Math.min(await mobileMenuItems.count(), 5); i++) {
          const item = mobileMenuItems.nth(i);
          const box = await item.boundingBox();

          if (box) {
            expect(box.height).toBeGreaterThanOrEqual(44);
            expect(box.width).toBeGreaterThanOrEqual(44);
          }
        }
      }

      helpers.logStep('Mobile accessibility validation completed');
    });
  });

  test.describe('Performance and Accessibility', () => {
    test('should maintain accessibility during loading', async ({ page }) => {
      helpers.logStep('Testing accessibility during loading states');

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');

      // Test accessibility while content is loading
      await page.reload();

      // Even during loading, basic accessibility should be maintained
      await checkA11y(page, null, {
        detailedReport: false, // Skip detailed report during loading
        axeOptions: {
          rules: {
            'html-has-lang': { enabled: true },
            'document-title': { enabled: true },
            'duplicate-id': { enabled: true },
          },
        },
      });

      // Wait for full load and re-check
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');
      await page.waitForLoadState('networkidle');

      helpers.logStep('Loading state accessibility validation completed');
    });

    test('should handle reduced motion preferences', async ({ page }) => {
      helpers.logStep('Testing reduced motion accessibility');

      // Set reduced motion preference
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.waitForTimeout(1000);

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Check that animations are disabled
      const animatedElements = page.locator('[style*="animation"], [style*="transition"]');

      for (let i = 0; i < await animatedElements.count(); i++) {
        const element = animatedElements.nth(i);
        const style = await element.getAttribute('style');

        // Animations should be disabled or very fast
        expect(style?.toLowerCase()).not.toContain('animation-duration: 0s');
      }

      helpers.logStep('Reduced motion accessibility validation completed');
    });
  });
});
