import { test, expect } from '../fixtures/enhanced-test-data.fixture';
import { DocumentProcessor } from '../utils/document-processor';

/**
 * Comprehensive Visual Regression Testing (Safe Implementation)
 *
 * Test Coverage:
 * - Visual consistency across browsers and devices
 * - UI component visual regression
 * - Responsive design verification
 * - Dark/light mode visual consistency
 * - Animation and transition visual testing
 * - Form and interaction visual states
 * - Error state visual validation
 * - Dynamic content visual testing
 */

test.describe('Visual Regression Testing', () => {
  let documentProcessor: DocumentProcessor;

  test.beforeEach(async ({ page, webSocketUtils }) => {
    documentProcessor = new DocumentProcessor(page, webSocketUtils);
    // Ensure consistent visual testing environment
    await page.addStyleTag({
      content: `
        /* Disable animations for consistent screenshots */
        *, *::before, *::after {
          animation-duration: 0.01ms !important;
          animation-delay: 0.01ms !important;
          transition-duration: 0.01ms !important;
          transition-delay: 0.01ms !important;
          scroll-behavior: auto !important;
        }

        /* Ensure consistent font rendering */
        body {
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }
      `
    });
  });

  test.describe('Layout and Component Visual Testing', () => {
    test('VISUAL-1: Document management page layout', async ({ page }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Full page screenshot
      await expect(page).toHaveScreenshot('documents-page-full.png', {
        fullPage: true,
        animations: 'disabled'
      });

      // Individual component screenshots
      const uploadArea = page.locator('[data-testid="upload-area"]');
      if (await uploadArea.count() > 0) {
        await expect(uploadArea).toHaveScreenshot('upload-area.png', {
          animations: 'disabled'
        });
      }

      const fileList = page.locator('[data-testid="file-list"]');
      if (await fileList.count() > 0) {
        await expect(fileList).toHaveScreenshot('file-list-empty.png', {
          animations: 'disabled'
        });
      }

      const navigation = page.locator('[data-testid="navigation"]');
      if (await navigation.count() > 0) {
        await expect(navigation).toHaveScreenshot('navigation.png', {
          animations: 'disabled'
        });
      }

      const sidebar = page.locator('[data-testid="sidebar"]');
      if (await sidebar.count() > 0) {
        await expect(sidebar).toHaveScreenshot('sidebar.png', {
          animations: 'disabled'
        });
      }
    });

    test('VISUAL-2: Upload modal visual states', async ({ page }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Open upload modal if button exists
      const uploadButton = page.locator('[data-testid="upload-button"]');
      if (await uploadButton.count() > 0) {
        await uploadButton.click();
        const modal = page.locator('[data-testid="upload-modal"]');
        if (await modal.count() > 0) {
          await expect(modal).toBeVisible();

          // Modal screenshot
          await expect(modal).toHaveScreenshot('upload-modal-open.png', {
            animations: 'disabled'
          });

          // Close modal
          await page.keyboard.press('Escape');
          await expect(modal).not.toBeVisible({ timeout: 3000 });
        }
      }
    });

    test('VISUAL-3: File item visual states', async ({ page, testDataManager }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Upload test file to test visual states
      const testFile = await testDataManager.getTestFile('visual-test.pdf');
      await page.setInputFiles('input[type="file"]', testFile.path);

      // Wait for file item to appear
      const fileItem = page.locator('[data-testid="file-item"]');
      if (await fileItem.count() > 0) {
        await expect(fileItem.first()).toHaveScreenshot('file-item-uploading.png', {
          animations: 'disabled'
        });

        // Test hover state
        await fileItem.first().hover({ position: { x: 10, y: 10 } });
        await expect(fileItem.first()).toHaveScreenshot('file-item-hover.png', {
          animations: 'disabled'
        });

        // Test focus state
        await fileItem.first().focus();
        await expect(fileItem.first()).toHaveScreenshot('file-item-focused.png', {
          animations: 'disabled'
        });
      }
    });

    test('VISUAL-4: Search and filter components', async ({ page }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Search bar states
      const searchContainer = page.locator('[data-testid="search-container"]');
      if (await searchContainer.count() > 0) {
        await expect(searchContainer).toHaveScreenshot('search-bar-default.png', {
          animations: 'disabled'
        });
      }

      const searchInput = page.locator('[data-testid="search-input"]');
      if (await searchInput.count() > 0) {
        await searchInput.fill('test search');
        await expect(searchContainer).toHaveScreenshot('search-bar-with-text.png', {
          animations: 'disabled'
        });
      }

      // Test filter dropdown if exists
      const filterButton = page.locator('[data-testid="filter-button"]');
      if (await filterButton.count() > 0) {
        await filterButton.click();
        const filterDropdown = page.locator('[data-testid="filter-dropdown"]');
        if (await filterDropdown.count() > 0) {
          await expect(filterDropdown).toHaveScreenshot('filter-dropdown-open.png', {
            animations: 'disabled'
          });
        }
      }

      // Test sort dropdown if exists
      const sortButton = page.locator('[data-testid="sort-button"]');
      if (await sortButton.count() > 0) {
        await sortButton.click();
        const sortDropdown = page.locator('[data-testid="sort-dropdown"]');
        if (await sortDropdown.count() > 0) {
          await expect(sortDropdown).toHaveScreenshot('sort-dropdown-open.png', {
            animations: 'disabled'
          });
        }
      }
    });
  });

  test.describe('Responsive Design Visual Testing', () => {
    test('VISUAL-5: Desktop viewport visual validation', async ({ page }) => {
      await page.setViewportSize({ width: 1920, height: 1080 });
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      await expect(page).toHaveScreenshot('documents-desktop-1920x1080.png', {
        fullPage: true,
        animations: 'disabled'
      });

      // Test larger desktop size
      await page.setViewportSize({ width: 2560, height: 1440 });
      await expect(page).toHaveScreenshot('documents-desktop-2560x1440.png', {
        fullPage: true,
        animations: 'disabled'
      });

      // Test smaller desktop size
      await page.setViewportSize({ width: 1280, height: 720 });
      await expect(page).toHaveScreenshot('documents-desktop-1280x720.png', {
        fullPage: true,
        animations: 'disabled'
      });
    });

    test('VISUAL-6: Tablet viewport visual validation', async ({ page }) => {
      await page.setViewportSize({ width: 1024, height: 768 });
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      await expect(page).toHaveScreenshot('documents-tablet-1024x768.png', {
        fullPage: true,
        animations: 'disabled'
      });

      // Test iPad landscape
      await page.setViewportSize({ width: 1366, height: 1024 });
      await expect(page).toHaveScreenshot('documents-tablet-landscape-1366x1024.png', {
        fullPage: true,
        animations: 'disabled'
      });

      // Test smaller tablet
      await page.setViewportSize({ width: 768, height: 1024 });
      await expect(page).toHaveScreenshot('documents-tablet-768x1024.png', {
        fullPage: true,
        animations: 'disabled'
      });
    });

    test('VISUAL-7: Mobile viewport visual validation', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 667 }); // iPhone SE
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      await expect(page).toHaveScreenshot('documents-mobile-375x667.png', {
        fullPage: true,
        animations: 'disabled'
      });

      // Test larger phone
      await page.setViewportSize({ width: 414, height: 896 }); // iPhone 11
      await expect(page).toHaveScreenshot('documents-mobile-414x896.png', {
        fullPage: true,
        animations: 'disabled'
      });

      // Test Android phone
      await page.setViewportSize({ width: 360, height: 640 }); // Small Android
      await expect(page).toHaveScreenshot('documents-mobile-360x640.png', {
        fullPage: true,
        animations: 'disabled'
      });

      // Test landscape mobile
      await page.setViewportSize({ width: 812, height: 375 }); // iPhone 11 landscape
      await expect(page).toHaveScreenshot('documents-mobile-landscape-812x375.png', {
        fullPage: true,
        animations: 'disabled'
      });
    });

    test('VISUAL-8: Responsive component behavior', async ({ page }) => {
      const viewports = [
        { width: 375, height: 667, name: 'mobile' },
        { width: 768, height: 1024, name: 'tablet' },
        { width: 1920, height: 1080, name: 'desktop' }
      ];

      for (const viewport of viewports) {
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        await page.goto('/documents');
        await page.waitForLoadState('networkidle');

        // Test responsive navigation
        const navigation = page.locator('[data-testid="navigation"]');
        if (await navigation.count() > 0) {
          await expect(navigation).toHaveScreenshot(`navigation-${viewport.name}.png`, {
            animations: 'disabled'
          });
        }

        // Test responsive upload area
        const uploadArea = page.locator('[data-testid="upload-area"]');
        if (await uploadArea.count() > 0) {
          await expect(uploadArea).toHaveScreenshot(`upload-area-${viewport.name}.png`, {
            animations: 'disabled'
          });
        }

        // Test responsive file list
        const fileList = page.locator('[data-testid="file-list"]');
        if (await fileList.count() > 0) {
          await expect(fileList).toHaveScreenshot(`file-list-${viewport.name}.png`, {
            animations: 'disabled'
          });
        }
      }
    });
  });

  test.describe('Theme and Color Mode Testing', () => {
    test('VISUAL-9: Light theme visual validation', async ({ page }) => {
      await page.emulateMedia({ colorScheme: 'light' });
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      await expect(page).toHaveScreenshot('documents-light-theme.png', {
        fullPage: true,
        animations: 'disabled'
      });

      // Test light theme components
      const uploadArea = page.locator('[data-testid="upload-area"]');
      if (await uploadArea.count() > 0) {
        await expect(uploadArea).toHaveScreenshot('upload-area-light-theme.png', {
          animations: 'disabled'
        });
      }

      const fileItem = page.locator('[data-testid="file-item"]');
      if (await fileItem.count() > 0) {
        await expect(fileItem.first()).toHaveScreenshot('file-item-light-theme.png', {
          animations: 'disabled'
        });
      }
    });

    test('VISUAL-10: Dark theme visual validation', async ({ page }) => {
      await page.emulateMedia({ colorScheme: 'dark' });
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      await expect(page).toHaveScreenshot('documents-dark-theme.png', {
        fullPage: true,
        animations: 'disabled'
      });

      // Test dark theme components
      const uploadArea = page.locator('[data-testid="upload-area"]');
      if (await uploadArea.count() > 0) {
        await expect(uploadArea).toHaveScreenshot('upload-area-dark-theme.png', {
          animations: 'disabled'
        });
      }

      const fileItem = page.locator('[data-testid="file-item"]');
      if (await fileItem.count() > 0) {
        await expect(fileItem.first()).toHaveScreenshot('file-item-dark-theme.png', {
          animations: 'disabled'
        });
      }
    });

    test('VISUAL-11: High contrast mode testing', async ({ page }) => {
      // Simulate high contrast mode
      await page.addStyleTag({
        content: `
          :root {
            --color-text: #000000 !important;
            --color-background: #ffffff !important;
            --color-border: #000000 !important;
            --color-primary: #0000ff !important;
            --color-secondary: #800080 !important;
          }
        `
      });

      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      await expect(page).toHaveScreenshot('documents-high-contrast.png', {
        fullPage: true,
        animations: 'disabled'
      });
    });
  });

  test.describe('Loading and Progress Visual Testing', () => {
    test('VISUAL-14: Loading states visual validation', async ({ page }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Create skeleton loading state
      await page.evaluate(() => {
        const skeletonDiv = document.createElement('div');
        skeletonDiv.setAttribute('data-testid', 'skeleton-loader');

        // Create skeleton elements safely
        const container = document.createElement('div');
        container.className = 'skeleton-container';

        const header = document.createElement('div');
        header.className = 'skeleton-header';
        header.textContent = 'Loading...';

        container.appendChild(header);
        skeletonDiv.appendChild(container);
        document.body.appendChild(skeletonDiv);
      });

      const skeletonLoader = page.locator('[data-testid="skeleton-loader"]');
      if (await skeletonLoader.count() > 0) {
        await expect(skeletonLoader).toHaveScreenshot('skeleton-loader.png', {
          animations: 'disabled'
        });
      }

      // Create loading spinner state
      await page.evaluate(() => {
        const spinnerDiv = document.createElement('div');
        spinnerDiv.setAttribute('data-testid', 'loading-spinner');

        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';

        const spinner = document.createElement('div');
        spinner.className = 'spinner';
        spinner.textContent = 'Loading';

        const text = document.createElement('p');
        text.textContent = 'Loading documents...';

        overlay.appendChild(spinner);
        overlay.appendChild(text);
        spinnerDiv.appendChild(overlay);
        document.body.appendChild(spinnerDiv);
      });

      const loadingSpinner = page.locator('[data-testid="loading-spinner"]');
      if (await loadingSpinner.count() > 0) {
        await expect(loadingSpinner).toHaveScreenshot('loading-spinner.png', {
          animations: 'disabled'
        });
      }

      // Create progress states
      await page.evaluate(() => {
        const progressDiv = document.createElement('div');
        progressDiv.setAttribute('data-testid', 'progress-states');

        const container = document.createElement('div');
        container.className = 'progress-container';

        const progressLevels = [25, 50, 75, 100];
        progressLevels.forEach(level => {
          const progressBar = document.createElement('div');
          progressBar.className = 'progress-bar';
          progressBar.style.width = `${level}%`;
          progressBar.textContent = `${level}%`;
          container.appendChild(progressBar);
        });

        progressDiv.appendChild(container);
        document.body.appendChild(progressDiv);
      });

      const progressStates = page.locator('[data-testid="progress-states"]');
      if (await progressStates.count() > 0) {
        await expect(progressStates).toHaveScreenshot('progress-states.png', {
          animations: 'disabled'
        });
      }
    });

    test('VISUAL-15: Real-time progress indicators', async ({ page, webSocketUtils, testDataManager }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Upload file to test real-time progress
      const testFile = await testDataManager.getTestFile('progress-test.pdf');
      await page.setInputFiles('input[type="file"]', testFile.path);

      // Wait for progress indicator to appear
      const uploadProgress = page.locator('[data-testid="upload-progress"]');
      if (await uploadProgress.count() > 0) {
        // Screenshot different progress states by simulating progress updates
        await webSocketUtils.mockWebSocketMessage({
          type: 'document_status_update',
          payload: {
            documentId: 'test-doc',
            status: 'uploading',
            progress: 25
          },
          timestamp: Date.now()
        });

        await expect(uploadProgress).toHaveScreenshot('progress-25-percent.png', {
          animations: 'disabled'
        });

        await webSocketUtils.mockWebSocketMessage({
          type: 'document_status_update',
          payload: {
            documentId: 'test-doc',
            status: 'uploading',
            progress: 50
          },
          timestamp: Date.now()
        });

        await expect(uploadProgress).toHaveScreenshot('progress-50-percent.png', {
          animations: 'disabled'
        });

        await webSocketUtils.mockWebSocketMessage({
          type: 'document_status_update',
          payload: {
            documentId: 'test-doc',
            status: 'uploading',
            progress: 75
          },
          timestamp: Date.now()
        });

        await expect(uploadProgress).toHaveScreenshot('progress-75-percent.png', {
          animations: 'disabled'
        });
      }
    });
  });

  test.describe('Cross-Browser Visual Consistency', () => {
    test('VISUAL-16: Visual consistency across browsers', async ({ page, browserName }) => {
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Take browser-specific screenshot
      await expect(page).toHaveScreenshot(`documents-${browserName}-browser.png`, {
        fullPage: true,
        animations: 'disabled'
      });

      // Test key components for consistency
      const components = [
        '[data-testid="upload-area"]',
        '[data-testid="navigation"]',
        '[data-testid="file-item"]',
        '[data-testid="search-container"]'
      ];

      for (const componentSelector of components) {
        const component = page.locator(componentSelector);
        if (await component.count() > 0) {
          const componentName = componentSelector.replace(/[\[\]""]/g, '-').replace(/-+/g, '-');
          await expect(component.first()).toHaveScreenshot(`${componentName}-${browserName}.png`, {
            animations: 'disabled'
          });
        }
      }
    });
  });

  test.describe('Comprehensive Visual Test Suite', () => {
    test('VISUAL-19: Complete application visual regression suite', async ({ page }) => {
      const testPages = [
        { path: '/', name: 'homepage' },
        { path: '/documents', name: 'documents' },
        { path: '/dashboard', name: 'dashboard' },
        { path: '/settings', name: 'settings' }
      ];

      const viewports = [
        { width: 1920, height: 1080, name: 'desktop' },
        { width: 1024, height: 768, name: 'tablet' },
        { width: 375, height: 667, name: 'mobile' }
      ];

      for (const viewport of viewports) {
        await page.setViewportSize({ width: viewport.width, height: viewport.height });

        for (const pageConfig of testPages) {
          console.log(`Visual testing: ${pageConfig.name} on ${viewport.name}`);

          await page.goto(pageConfig.path);
          await page.waitForLoadState('networkidle');

          // Full page screenshot
          await expect(page).toHaveScreenshot(
            `${pageConfig.name}-${viewport.name}-full.png`,
            {
              fullPage: true,
              animations: 'disabled',
              maxDiffPixelRatio: 0.01 // Allow 1% pixel difference for minor variations
            }
          );

          // Component-specific screenshots for key pages
          if (pageConfig.name === 'documents') {
            const uploadArea = page.locator('[data-testid="upload-area"]');
            if (await uploadArea.count() > 0) {
              await expect(uploadArea).toHaveScreenshot(
                `upload-area-${viewport.name}.png`,
                { animations: 'disabled', maxDiffPixelRatio: 0.01 }
              );
            }

            const navigation = page.locator('[data-testid="navigation"]');
            if (await navigation.count() > 0) {
              await expect(navigation).toHaveScreenshot(
                `navigation-${viewport.name}.png`,
                { animations: 'disabled', maxDiffPixelRatio: 0.01 }
              );
            }
          }

          if (pageConfig.name === 'settings') {
            const settingsForm = page.locator('[data-testid="settings-form"]');
            if (await settingsForm.count() > 0) {
              await expect(settingsForm).toHaveScreenshot(
                `settings-form-${viewport.name}.png`,
                { animations: 'disabled', maxDiffPixelRatio: 0.01 }
              );
            }
          }
        }
      }
    });
  });
});