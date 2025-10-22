import { test, expect, devices } from '@playwright/test';
import { createTestHelpers, TEST_DATA } from '../utils/test-helpers';

test.describe('Responsive Design Tests', () => {
  let helpers: ReturnType<typeof createTestHelpers>;

  // Define viewports for testing
  const VIEWPORTS = {
    desktop: { width: 1920, height: 1080, name: 'Desktop' },
    laptop: { width: 1366, height: 768, name: 'Laptop' },
    tablet: { width: 768, height: 1024, name: 'Tablet' },
    mobileLarge: { width: 414, height: 896, name: 'Mobile Large' },
    mobile: { width: 375, height: 667, name: 'Mobile' },
    mobileSmall: { width: 320, height: 568, name: 'Mobile Small' },
  };

  test.describe('Dashboard Responsive Behavior', () => {
    test.beforeEach(async ({ page, context }, testInfo) => {
      helpers = createTestHelpers(page, context, testInfo);
      await helpers.login(TEST_DATA.USERS.ADMIN);
    });

    Object.entries(VIEWPORTS).forEach(([key, viewport]) => {
      test(`should display correctly on ${viewport.name} (${viewport.width}x${viewport.height})`, async ({ page }) => {
        helpers.logStep(`Testing responsive design on ${viewport.name}`);

        // Set viewport
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        await page.waitForTimeout(1000);

        // Navigate to dashboard
        await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
        await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');
        await page.waitForLoadState('networkidle');

        // Test header responsiveness
        await testHeaderResponsiveness(page, viewport);

        // Test navigation responsiveness
        await testNavigationResponsiveness(page, viewport);

        // Test content layout responsiveness
        await testContentLayoutResponsiveness(page, viewport);

        // Test widget responsiveness
        await testWidgetResponsiveness(page, viewport);

        // Take screenshot for visual verification
        await page.screenshot({
          path: `test-results/responsive-${key}-${viewport.width}x${viewport.height}.png`,
          fullPage: true,
        });

        helpers.logStep(`${viewport.name} responsive design test completed`);
      });
    });

    async function testHeaderResponsiveness(page: any, viewport: any) {
      const header = page.locator('[data-testid="dashboard-header"]');
      await expect(header).toBeVisible();

      if (viewport.width < 768) {
        // Mobile: hamburger menu should be visible
        await expect(page.locator('[data-testid="mobile-menu-button"]')).toBeVisible();
        await expect(page.locator('[data-testid="desktop-nav"]')).toBeHidden();
      } else {
        // Desktop/Tablet: full navigation should be visible
        if (viewport.width >= 1024) {
          await expect(page.locator('[data-testid="desktop-nav"]')).toBeVisible();
          await expect(page.locator('[data-testid="mobile-menu-button"]')).toBeHidden();
        } else {
          // Tablet: might have hybrid navigation
          await expect(page.locator('[data-testid="mobile-menu-button"]')).toBeVisible();
        }
      }

      // Test user menu responsiveness
      const userMenu = page.locator('[data-testid="user-menu"]');
      await expect(userMenu).toBeVisible();

      // Test logo sizing
      const logo = page.locator('[data-testid="app-logo"]');
      if (await logo.count() > 0) {
        const logoBox = await logo.boundingBox();
        if (logoBox) {
          expect(logoBox.width).toBeLessThanOrEqual(viewport.width * 0.3);
        }
      }
    }

    async function testNavigationResponsiveness(page: any, viewport: any) {
      if (viewport.width < 768) {
        // Mobile navigation
        await page.locator('[data-testid="mobile-menu-button"]').click();
        await page.waitForTimeout(500);

        // Mobile menu should be full-screen or large overlay
        const mobileMenu = page.locator('[data-testid="mobile-nav-menu"]');
        await expect(mobileMenu).toBeVisible();

        const menuBox = await mobileMenu.boundingBox();
        if (menuBox) {
          expect(menuBox.width).toBeGreaterThanOrEqual(viewport.width * 0.8);
        }

        // Menu items should be large touch targets
        const menuItems = page.locator('[data-testid="mobile-nav-item"]');
        for (let i = 0; i < Math.min(await menuItems.count(), 5); i++) {
          const item = menuItems.nth(i);
          const itemBox = await item.boundingBox();
          if (itemBox) {
            expect(itemBox.height).toBeGreaterThanOrEqual(44); // Minimum touch target
          }
        }

        // Close mobile menu
        await page.keyboard.press('Escape');
      } else {
        // Desktop/Tablet navigation
        const navItems = page.locator('[data-testid="desktop-nav-item"]');
        if (await navItems.count() > 0) {
          await expect(navItems.first()).toBeVisible();

          // Test hover states
          await navItems.first().hover();
          await page.waitForTimeout(300);

          // Dropdown should appear on desktop
          if (viewport.width >= 1024) {
            const dropdown = page.locator('[data-testid="nav-dropdown"]');
            if (await dropdown.count() > 0) {
              await expect(dropdown.first()).toBeVisible();
            }
          }
        }
      }
    }

    async function testContentLayoutResponsiveness(page: any, viewport: any) {
      const mainContent = page.locator('[data-testid="dashboard-main-content"]');
      await expect(mainContent).toBeVisible();

      const contentBox = await mainContent.boundingBox();
      if (contentBox) {
        // Content should use available width efficiently
        expect(contentBox.width).toBeGreaterThan(viewport.width * 0.7);
      }

      // Test sidebar responsiveness
      const sidebar = page.locator('[data-testid="dashboard-sidebar"]');
      if (await sidebar.count() > 0) {
        if (viewport.width < 1024) {
          // Sidebar might be hidden or overlay on smaller screens
          await expect(sidebar).toBeHidden();
        } else {
          // Sidebar should be visible on larger screens
          await expect(sidebar).toBeVisible();
        }
      }
    }

    async function testWidgetResponsiveness(page: any, viewport: any) {
      // Test metric cards
      const metricCards = page.locator('[data-testid="metric-card"]');
      if (await metricCards.count() > 0) {
        await expect(metricCards.first()).toBeVisible();

        // Cards should stack appropriately
        const firstCard = metricCards.first();
        const cardBox = await firstCard.boundingBox();
        if (cardBox) {
          if (viewport.width < 768) {
            // Mobile: cards should be full width or mostly full width
            expect(cardBox.width).toBeGreaterThan(viewport.width * 0.9);
          } else if (viewport.width < 1200) {
            // Tablet: cards should be half width or flexible
            expect(cardBox.width).toBeGreaterThan(viewport.width * 0.4);
          } else {
            // Desktop: cards can be smaller
            expect(cardBox.width).toBeGreaterThan(viewport.width * 0.2);
          }
        }
      }

      // Test charts
      const charts = page.locator('[data-testid="chart"]');
      if (await charts.count() > 0) {
        await expect(charts.first()).toBeVisible();

        // Charts should be responsive
        const chart = charts.first();
        const chartBox = await chart.boundingBox();
        if (chartBox) {
          expect(chartBox.width).toBeGreaterThan(viewport.width * 0.3);
          expect(chartBox.height).toBeGreaterThan(200); // Minimum chart height
        }
      }

      // Test data tables
      const tables = page.locator('[data-testid="data-table"]');
      if (await tables.count() > 0) {
        const table = tables.first();

        if (viewport.width < 768) {
          // Mobile: tables should scroll horizontally
          const tableContainer = table.locator('..');
          const containerBox = await tableContainer.boundingBox();
          const tableBox = await table.boundingBox();

          if (containerBox && tableBox) {
            expect(tableBox.width).toBeGreaterThan(containerBox.width);
          }
        } else {
          // Desktop: tables should fit within container
          const tableBox = await table.boundingBox();
          if (tableBox) {
            expect(tableBox.width).toBeLessThanOrEqual(viewport.width * 0.9);
          }
        }
      }
    }
  });

  test.describe('Mobile-Specific Features', () => {
    test('should support touch gestures on mobile', async ({ page }) => {
      helpers.logStep('Testing touch gestures on mobile');

      // Set mobile viewport
      await page.setViewportSize(VIEWPORTS.mobile);
      await helpers.login(TEST_DATA.USERS.ADMIN);
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');

      // Test swipe gestures for carousel/slider
      const carousel = page.locator('[data-testid="widget-carousel"]');
      if (await carousel.count() > 0) {
        const carouselBox = await carousel.boundingBox();
        if (carouselBox) {
          // Swipe left
          await page.touch.start(carouselBox.x + carouselBox.width / 2, carouselBox.y + carouselBox.height / 2);
          await page.touch.move(carouselBox.x + 100, carouselBox.y + carouselBox.height / 2);
          await page.touch.end();

          await page.waitForTimeout(500);

          // Swipe right
          await page.touch.start(carouselBox.x + 100, carouselBox.y + carouselBox.height / 2);
          await page.touch.move(carouselBox.x + carouselBox.width / 2, carouselBox.y + carouselBox.height / 2);
          await page.touch.end();
        }
      }

      // Test pull-to-refresh
      const pullToRefreshArea = page.locator('[data-testid="pull-to-refresh"]');
      if (await pullToRefreshArea.count() > 0) {
        const refreshBox = await pullToRefreshArea.boundingBox();
        if (refreshBox) {
          await page.touch.start(refreshBox.x + refreshBox.width / 2, refreshBox.y + 50);
          await page.touch.move(refreshBox.x + refreshBox.width / 2, refreshBox.y + 200);
          await page.touch.end();

          await page.waitForTimeout(1000);
          await expect(page.locator('[data-testid="refresh-indicator"]')).toBeVisible();
        }
      }

      helpers.logStep('Touch gestures test completed');
    });

    test('should handle virtual keyboard properly', async ({ page }) => {
      helpers.logStep('Testing virtual keyboard handling');

      await page.setViewportSize(VIEWPORTS.mobile);
      await helpers.login(TEST_DATA.USERS.ADMIN);
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');

      // Find an input field
      const searchInput = page.locator('[data-testid="search-input"], input[type="text"]').first();
      if (await searchInput.count() > 0) {
        // Focus input to trigger virtual keyboard
        await searchInput.focus();

        // Mock virtual keyboard appearance
        await page.evaluate(() => {
          window.visualViewport.height = window.innerHeight * 0.6; // Simulate keyboard
          window.dispatchEvent(new Event('resize'));
        });

        await page.waitForTimeout(500);

        // View should adjust for virtual keyboard
        const focusedElement = page.locator(':focus');
        await expect(focusedElement).toBeVisible();

        // The focused element should be visible above the keyboard
        const elementBox = await focusedElement.boundingBox();
        if (elementBox) {
          expect(elementBox.y).toBeLessThan(VIEWPORTS.mobile.height * 0.5);
        }

        // Test dismissal of virtual keyboard
        await page.evaluate(() => {
          window.visualViewport.height = window.innerHeight;
          window.dispatchEvent(new Event('resize'));
        });

        await page.keyboard.press('Escape');
        await page.waitForTimeout(500);
      }

      helpers.logStep('Virtual keyboard handling test completed');
    });

    test('should support device-specific features', async ({ page }) => {
      helpers.logStep('Testing device-specific features');

      await page.setViewportSize(VIEWPORTS.mobile);
      await helpers.login(TEST_DATA.USERS.ADMIN);
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');

      // Test geolocation if available
      await page.context().grantPermissions(['geolocation']);

      const geolocationButton = page.locator('[data-testid="geolocation-button"]');
      if (await geolocationButton.count() > 0) {
        // Mock geolocation
        await page.setGeolocation({ latitude: 40.7128, longitude: -74.0060 });
        await geolocationButton.click();
        await page.waitForTimeout(1000);

        // Check if location-based content updates
        const locationInfo = page.locator('[data-testid="location-info"]');
        if (await locationInfo.count() > 0) {
          await expect(locationInfo).toBeVisible();
        }
      }

      // Test camera/image capture if available
      await page.context().grantPermissions(['camera']);
      const cameraButton = page.locator('[data-testid="camera-button"]');
      if (await cameraButton.count() > 0) {
        await cameraButton.click();
        await page.waitForTimeout(500);

        // Should show camera interface or file picker
        const cameraInterface = page.locator('[data-testid="camera-interface"]');
        if (await cameraInterface.count() > 0) {
          await expect(cameraInterface).toBeVisible();
        }
      }

      // Test vibration if available
      await page.context().grantPermissions(['vibration']);
      await page.evaluate(() => {
        if ('vibrate' in navigator) {
          navigator.vibrate(100);
        }
      });

      helpers.logStep('Device-specific features test completed');
    });
  });

  test.describe('Performance on Different Devices', () => {
    test('should perform well on low-end mobile devices', async ({ page }) => {
      helpers.logStep('Testing performance on low-end mobile');

      // Simulate low-end device
      await page.emulateCPUThrottling(4); // 4x slowdown
      await page.setViewportSize(VIEWPORTS.mobileSmall);

      await helpers.login(TEST_DATA.USERS.ADMIN);

      const startTime = Date.now();
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');
      const loadTime = Date.now() - startTime;

      // Should still load reasonably fast even on slow devices
      expect(loadTime).toBeLessThan(8000); // 8 seconds max

      // Test interactions are still responsive
      const interactionStart = Date.now();
      await helpers.waitAndClick('[data-testid="metric-card"]');
      await page.waitForTimeout(500);
      const interactionTime = Date.now() - interactionStart;

      expect(interactionTime).toBeLessThan(2000); // 2 seconds max

      // Reset throttling
      await page.emulateCPUThrottling(1);

      helpers.logStep('Low-end mobile performance test completed');
    });

    test('should handle slow network conditions', async ({ page }) => {
      helpers.logStep('Testing slow network conditions');

      await page.setViewportSize(VIEWPORTS.mobile);

      // Simulate slow 3G network
      await page.route('**/*', async route => {
        await new Promise(resolve => setTimeout(resolve, 1000)); // 1 second delay
        await route.continue();
      });

      await helpers.login(TEST_DATA.USERS.ADMIN);

      // Should show loading indicators
      await helpers.expectElementVisible('[data-testid="loading-indicator"]');

      const startTime = Date.now();
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');
      const loadTime = Date.now() - startTime;

      expect(loadTime).toBeLessThan(15000); // 15 seconds max on slow network

      // Remove network throttling
      await page.unroute('**/*');

      helpers.logStep('Slow network performance test completed');
    });
  });

  test.describe('Accessibility Across Devices', () => {
    Object.entries(VIEWPORTS).forEach(([key, viewport]) => {
      test(`should maintain accessibility on ${viewport.name}`, async ({ page }) => {
        helpers.logStep(`Testing accessibility on ${viewport.name}`);

        await page.setViewportSize({ width: viewport.width, height: viewport.height });

        if (viewport.width < 768) {
          // Enable mobile accessibility features
          await page.emulateMedia({ reducedMotion: 'reduce' });
        }

        await helpers.login(TEST_DATA.USERS.ADMIN);
        await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
        await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

        // Test touch target sizes on mobile
        if (viewport.width < 768) {
          const interactiveElements = page.locator('button, a, input, [role="button"]');

          for (let i = 0; i < Math.min(await interactiveElements.count(), 10); i++) {
            const element = interactiveElements.nth(i);
            const box = await element.boundingBox();

            if (box) {
              // Minimum touch target size is 44x44 points
              expect(box.width).toBeGreaterThanOrEqual(44);
              expect(box.height).toBeGreaterThanOrEqual(44);
            }
          }
        }

        // Test keyboard navigation works on all devices
        await page.keyboard.press('Tab');
        const focusedElement = page.locator(':focus');
        await expect(focusedElement).toHaveCount(1);

        helpers.logStep(`${viewport.name} accessibility test completed`);
      });
    });
  });
});

test.describe('Device-Specific Tests', () => {
  test.describe('iPhone Tests', () => {
    test('should work correctly on iPhone', async ({ page }) => {
      await useDevice(devices['iPhone 12'], page);
    });
  });

  test.describe('Android Tests', () => {
    test('should work correctly on Android', async ({ page }) => {
      await useDevice(devices['Pixel 5'], page);
    });
  });

  test.describe('Tablet Tests', () => {
    test('should work correctly on iPad', async ({ page }) => {
      await useDevice(devices['iPad Pro'], page);
    });
  });

  async function useDevice(device: any, page: any) {
    const helpers = createTestHelpers(page, page.context(), {} as any);
    helpers.logStep(`Testing on ${device.defaultBrowserType} - ${device.userAgent}`);

    // Apply device settings
    await page.setViewportSize(device.viewport);
    await page.setUserAgent(device.userAgent);
    await page.emulateMedia({ colorScheme: 'light' });

    // Test basic functionality
    await helpers.login(TEST_DATA.USERS.ADMIN);
    await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
    await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

    // Test device-specific interactions
    if (device.defaultBrowserType === 'webkit') {
      // Test Safari-specific features
      await testSafariFeatures(page);
    } else {
      // Test Chrome/Android features
      await testChromeFeatures(page);
    }

    // Take device-specific screenshot
    await page.screenshot({
      path: `test-results/device-${device.defaultBrowserType}-${device.viewport.width}x${device.viewport.height}.png`,
      fullPage: true,
    });

    helpers.logStep(`Device test completed for ${device.defaultBrowserType}`);
  }

  async function testSafariFeatures(page: any) {
    // Test Safari-specific features like 3D touch, Apple Pay, etc.
    const safariButton = page.locator('[data-testid="safari-feature"]');
    if (await safariButton.count() > 0) {
      await safariButton.click();
      await page.waitForTimeout(500);
    }
  }

  async function testChromeFeatures(page: any) {
    // Test Chrome-specific features like PWA, install prompts, etc.
    const chromeButton = page.locator('[data-testid="chrome-feature"]');
    if (await chromeButton.count() > 0) {
      await chromeButton.click();
      await page.waitForTimeout(500);
    }
  }
});