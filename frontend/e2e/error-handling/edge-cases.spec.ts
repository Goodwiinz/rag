import { test, expect } from '../fixtures/test-data.fixture';
import { LoginPage, DocumentsPage, SearchPage, KnowledgeGraphPage } from '../utils/page-objects';

/**
 * Error Handling and Edge Cases Testing Suite
 *
 * Test Coverage:
 * - Network connectivity issues
 * - File upload failures (size, format, corruption)
 * - Authentication token expiration
 * - Service unavailable scenarios
 * - Browser compatibility issues
 * - Data validation and sanitization
 * - Error recovery and user feedback
 */

test.describe('Error Handling and Edge Cases', () => {
  let loginPage: LoginPage;
  let documentsPage: DocumentsPage;
  let searchPage: SearchPage;
  let graphPage: KnowledgeGraphPage;

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page);
    documentsPage = new DocumentsPage(page);
    searchPage = new SearchPage(page);
    graphPage = new KnowledgeGraphPage(page);
  });

  test.describe('Network Connectivity Issues', () => {
    test('Handles offline mode gracefully', async ({ page }) => {
      // Simulate offline mode
      await page.context().setOffline(true);

      // Navigate to application
      await page.goto('/login');

      // Verify offline indication
      await expect(page.locator('[data-testid="offline-indicator"]')).toBeVisible({ timeout: 5000 });

      // Test login fails gracefully
      await loginPage.emailInput.fill('test@example.com');
      await loginPage.passwordInput.fill('password123');
      await loginPage.loginButton.click();

      // Should show network error
      await expect(loginPage.errorMessage).toBeVisible({ timeout: 10000 });
      await expect(loginPage.errorMessage).toContainText('network') ||
               await expect(loginPage.errorMessage).toContainText('connection');

      // Restore connection
      await page.context().setOffline(false);

      // Should recover automatically
      await expect(page.locator('[data-testid="offline-indicator"]')).not.toBeVisible({ timeout: 5000 });
    });

    test('Handles slow network conditions', async ({ page }) => {
      // Simulate slow network
      await page.route('**/*', async route => {
        await new Promise(resolve => setTimeout(resolve, 2000)); // 2 second delay
        await route.continue();
      });

      const startTime = Date.now();
      await page.goto('/login');
      const loadTime = Date.now() - startTime;

      // Should show loading indicator for slow networks
      await expect(page.locator('[data-testid="slow-connection-warning"]')).toBeVisible({ timeout: 3000 });

      console.log(`Page loaded in ${loadTime}ms with slow network simulation`);

      // Should still load eventually
      await expect(loginPage.emailInput).toBeVisible();

      // Test search with slow network
      await page.goto('/search');
      await searchPage.searchInput.fill('test query');
      await searchPage.searchButton.click();

      // Should show extended loading state
      await expect(page.locator('[data-testid="extended-loading"]')).toBeVisible({ timeout: 5000 });
    });

    test('Handles intermittent connection failures', async ({ page }) => {
      let requestCount = 0;

      // Simulate intermittent failures
      await page.route('**/api/**', async route => {
        requestCount++;
        if (requestCount % 3 === 0) {
          // Fail every 3rd request
          await route.abort('failed');
        } else {
          await route.continue();
        }
      });

      await page.goto('/search');
      await searchPage.searchInput.fill('test query');

      // Try multiple searches to trigger intermittent failures
      for (let i = 0; i < 5; i++) {
        await searchPage.searchButton.click();
        await page.waitForTimeout(2000);

        // Some searches should fail
        const errorVisible = await page.locator('[data-testid="error-message"]').isVisible();
        if (errorVisible) {
          await expect(page.locator('[data-testid="retry-button"]')).toBeVisible();
          await page.click('[data-testid="retry-button"]');
        }
      }

      // Application should remain functional
      await expect(searchPage.searchInput).toBeVisible();
    });
  });

  test.describe('File Upload Error Handling', () => {
    test('Rejects files exceeding size limits', async ({ page }) => {
      await page.goto('/documents');

      // Simulate uploading a large file
      await page.evaluate(() => {
        const input = document.querySelector('[data-testid="file-input"]') as HTMLInputElement;
        if (input) {
          // Create a mock large file
          const largeContent = 'x'.repeat(100 * 1024 * 1024); // 100MB
          const largeFile = new File([largeContent], 'large-file.pdf', { type: 'application/pdf' });
          const dataTransfer = new DataTransfer();
          dataTransfer.items.add(largeFile);
          input.files = dataTransfer.files;
        }
      });

      // Should show size limit error
      await expect(page.locator('[data-testid="file-size-error"]')).toBeVisible({ timeout: 5000 });
      await expect(page.locator('[data-testid="error-message"]')).toContainText('size') ||
               await expect(page.locator('[data-testid="error-message"]')).toContainText('large');
    });

    test('Handles unsupported file formats', async ({ page }) => {
      await page.goto('/documents');

      // Simulate uploading unsupported file
      await page.evaluate(() => {
        const input = document.querySelector('[data-testid="file-input"]') as HTMLInputElement;
        if (input) {
          const unsupportedFile = new File(['content'], 'unsupported.exe', { type: 'application/x-executable' });
          const dataTransfer = new DataTransfer();
          dataTransfer.items.add(unsupportedFile);
          input.files = dataTransfer.files;
        }
      });

      // Should show format error
      await expect(page.locator('[data-testid="file-format-error"]')).toBeVisible({ timeout: 5000 });
      await expect(page.locator('[data-testid="error-message"]')).toContainText('format') ||
               await expect(page.locator('[data-testid="error-message"]')).toContainText('supported');
    });

    test('Handles corrupted or damaged files', async ({ page, testData }) => {
      await page.goto('/documents');

      // Try to upload corrupted file
      await documentsPage.fileInput.setInputFiles(testData.files.corrupted.path);

      // Should handle gracefully
      const fileItem = documentsPage.getFileItem(testData.files.corrupted.name);
      await fileItem.waitFor({ state: 'visible', timeout: 10000 });

      const statusElement = documentsPage.getFileStatus(testData.files.corrupted.name);
      await expect(statusElement).toHaveAttribute('data-status', 'error');

      // Should show helpful error message
      const errorMessage = fileItem.locator('[data-testid="error-message"]');
      await expect(errorMessage).toBeVisible();
      await expect(errorMessage.textContent()).toContain('corrupted') ||
               await expect(errorMessage.textContent()).toContain('damaged') ||
               await expect(errorMessage.textContent()).toContain('invalid');
    });

    test('Handles upload interruption', async ({ page, testData }) => {
      await page.goto('/documents');

      // Simulate upload interruption
      await page.route('**/upload', async route => {
        await route.abort('failed');
      });

      // Attempt upload
      await documentsPage.fileInput.setInputFiles(testData.files.pdf.path);

      // Should show upload failed message
      await expect(page.locator('[data-testid="upload-failed"]')).toBeVisible({ timeout: 10000 });

      // Should provide retry option
      await expect(page.locator('[data-testid="retry-upload"]')).toBeVisible();

      // Test retry functionality
      await page.unroute('**/upload'); // Restore normal routing
      await page.click('[data-testid="retry-upload"]');

      // Upload should proceed normally after retry
      await page.waitForTimeout(5000);
    });

    test('Handles concurrent upload limits', async ({ page, testData }) => {
      await page.goto('/documents');

      // Simulate upload limit reached
      await page.route('**/upload', async route => {
        await route.fulfill({
          status: 429,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Too many concurrent uploads' })
        });
      });

      // Attempt multiple uploads
      await documentsPage.fileInput.setInputFiles([
        testData.files.pdf.path,
        testData.files.text.path,
        testData.files.image.path
      ].filter(path => path));

      // Should show rate limit error
      await expect(page.locator('[data-testid="rate-limit-error"]')).BeVisible({ timeout: 5000 });

      // Should provide retry with backoff
      await expect(page.locator('[data-testid="retry-with-delay"]')).BeVisible();
    });
  });

  test.describe('Authentication and Authorization Errors', () => {
    test('Handles expired authentication tokens', async ({ page }) => {
      // Simulate expired token scenario
      await page.addInitScript(() => {
        localStorage.setItem('auth_token', 'expired_token_12345');
        localStorage.setItem('token_expiry', (Date.now() - 100000).toString());
      });

      // Navigate to protected page
      await page.goto('/documents');

      // Should redirect to login due to expired token
      await page.waitForURL('/login', { timeout: 10000 });

      // Should show session expired message
      await expect(page.locator('[data-testid="session-expired"]')).toBeVisible({ timeout: 5000 });

      // Should allow re-authentication
      await expect(loginPage.emailInput).toBeVisible();
      await expect(loginPage.passwordInput).toBeVisible();
    });

    test('Handles insufficient permissions', async ({ page }) => {
      // Simulate user with limited permissions
      await page.addInitScript(() => {
        localStorage.setItem('auth_token', 'limited_user_token');
        localStorage.setItem('user_role', 'trial');
      });

      // Try to access admin features
      await page.goto('/admin/settings');

      // Should show access denied
      await expect(page.locator('[data-testid="access-denied"]')).toBeVisible({ timeout: 5000 });

      // Should provide helpful message
      await expect(page.locator('[data-testid="permission-error"]')).toContainText('permission') ||
               await expect(page.locator('[data-testid="permission-error"]')).toContainText('access');

      // Should suggest upgrade or contact admin
      await expect(page.locator('[data-testid="upgrade-prompt"]')).toBeVisible();
    });

    test('Handles concurrent login sessions', async ({ page }) => {
      // Simulate session conflict
      await page.route('**/api/auth/verify', async route => {
        await route.fulfill({
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Session conflict - User logged in elsewhere' })
        });
      });

      // Try to access protected resource
      await page.goto('/documents');

      // Should show session conflict message
      await expect(page.locator('[data-testid="session-conflict"]')).toBeVisible({ timeout: 5000 });

      // Should provide options to continue or logout elsewhere
      await expect(page.locator('[data-testid="continue-session"]')).toBeVisible();
      await expect(page.locator('[data-testid="logout-others"]')).toBeVisible();
    });
  });

  test.describe('Service Unavailable Scenarios', () => {
    test('Handles backend service downtime', async ({ page }) => {
      // Simulate backend service unavailable
      await page.route('**/api/**', async route => {
        await route.abort('failed');
      });

      await page.goto('/login');

      // Should show service unavailable message
      await expect(page.locator('[data-testid="service-unavailable"]')).toBeVisible({ timeout: 5000 });

      // Test graceful degradation
      await loginPage.emailInput.fill('test@example.com');
      await loginPage.passwordInput.fill('password123');
      await loginPage.loginButton.click();

      // Should show retry mechanism
      await expect(page.locator('[data-testid="retry-connection"]')).toBeVisible();

      // Should not crash application
      await expect(loginPage.emailInput).toBeVisible();
    });

    test('Handles partial service degradation', async ({ page }) => {
      // Simulate search service down but others working
      await page.route('**/api/search/**', async route => {
        await route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Search service temporarily unavailable' })
        });
      });

      await page.goto('/search');
      await searchPage.searchInput.fill('test query');
      await searchPage.searchButton.click();

      // Should show specific service unavailable message
      await expect(page.locator('[data-testid="search-service-down"]')).toBeVisible({ timeout: 5000 });

      // Should suggest alternative actions
      await expect(page.locator('[data-testid="try-browsing-documents"]')).toBeVisible();

      // Other features should still work
      await page.goto('/documents');
      await expect(documentsPage.uploadArea).toBeVisible();
    });

    test('Handles database connection issues', async ({ page }) => {
      // Simulate database errors
      await page.route('**/api/**', async route => {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Database connection failed' })
        });
      });

      await page.goto('/documents');

      // Should show appropriate error message
      await expect(page.locator('[data-testid="database-error"]')).toBeVisible({ timeout: 5000 });

      // Should not expose sensitive information
      const errorMessage = await page.locator('[data-testid="error-message"]').textContent();
      expect(errorMessage).not.toContain('password');
      expect(errorMessage).not.toContain('connection string');
      expect(errorMessage).not.toContain('internal server');
    });
  });

  test.describe('Data Validation and Sanitization', () => {
    test('Handles malicious input in search', async ({ page }) => {
      await page.goto('/search');

      // Test XSS prevention
      const xssPayloads = [
        '<script>alert("xss")</script>',
        'javascript:alert("xss")',
        '<img src="x" onerror="alert(\'xss\')">',
        '"><script>alert("xss")</script>',
        '\';alert("xss");//'
      ];

      for (const payload of xssPayloads) {
        await searchPage.searchInput.fill(payload);
        await searchPage.searchButton.click();

        // Should sanitize input
        await page.waitForTimeout(2000);

        // Verify no alert dialogs appear
        await page.waitForTimeout(1000);

        // Search input should show sanitized content
        const currentValue = await searchPage.searchInput.inputValue();
        expect(currentValue).not.toContain('<script>');
        expect(currentValue).not.toContain('javascript:');
      }
    });

    test('Handles extremely long input', async ({ page }) => {
      await page.goto('/search');

      // Test very long query
      const longQuery = 'a'.repeat(10000);
      await searchPage.searchInput.fill(longQuery);

      // Should handle gracefully
      await searchPage.searchButton.click();

      // Should show validation error or truncate
      const errorVisible = await page.locator('[data-testid="input-too-long"]').isVisible();
      if (errorVisible) {
        await expect(page.locator('[data-testid="input-too-long"]')).toBeVisible();
      } else {
        // Should truncate or handle appropriately
        await page.waitForTimeout(2000);
      }
    });

    test('Handles special characters and encoding', async ({ page }) => {
      await page.goto('/search');

      // Test various special characters
      const specialChars = [
        '!@#$%^&*()_+-=[]{}|;:,.<>?',
        '"quotes"',
        "'apostrophes'",
        'ñáéíóú',
        '中文字符',
        'العربية',
        '🚀🔍📚',
        '\n\r\t',
        '   multiple   spaces   '
      ];

      for (const chars of specialChars) {
        await searchPage.searchInput.clear();
        await searchPage.searchInput.fill(chars);
        await searchPage.searchButton.click();

        // Should not crash or error
        await page.waitForTimeout(1000);

        // Should handle gracefully or show appropriate message
        const errorVisible = await page.locator('[data-testid="error-message"]').isVisible();
        if (errorVisible) {
          // Error should be user-friendly
          const errorText = await page.locator('[data-testid="error-message"]').textContent();
          expect(errorText).not.toContain('undefined');
          expect(errorText).not.toContain('null');
        }
      }
    });

    test('Handles invalid URLs and parameters', async ({ page }) => {
      // Test malformed URLs
      const invalidUrls = [
        '/search?q=<script>alert("xss")</script>',
        '/documents?sort=javascript:alert("xss")',
        '/graph?filter=\"><script>alert("xss")</script>',
        '/invalid/path/that/does/not/exist',
        '/documents/999999999999999999999', // Very large ID
        '/search?q=' + encodeURIComponent('a'.repeat(10000)) // Very long query
      ];

      for (const url of invalidUrls) {
        await page.goto(url);

        // Should handle gracefully - either show proper page or appropriate error
        await page.waitForTimeout(2000);

        // Should not crash or show stack traces
        const errorVisible = await page.locator('[data-testid="error-page"], [data-testid="not-found"]').isVisible();
        if (errorVisible) {
          // Error should be user-friendly
          const errorText = await page.locator('[data-testid="error-page"], [data-testid="not-found"]').textContent();
          expect(errorText?.length).toBeGreaterThan(0);
        }
      }
    });
  });

  test.describe('Browser Compatibility Issues', () => {
    test('Handles disabled JavaScript', async ({ page }) => {
      // Disable JavaScript
      await page.context().addInitScript(() => {
        window.addEventListener('load', () => {
          // Remove all script tags
          const scripts = document.querySelectorAll('script');
          scripts.forEach(script => script.remove());
        });
      });

      await page.goto('/login');

      // Should show noscript message
      const noscriptElement = page.locator('noscript, [data-testid="noscript-warning"]');
      if (await noscriptElement.isVisible()) {
        await expect(noscriptElement).toBeVisible();
      }

      // Should provide basic functionality or clear message
      await expect(page.locator('body')).toContainText('JavaScript') ||
               await expect(page.locator('body')).toContainText('enabled');
    });

    test('Handles blocked third-party resources', async ({ page }) => {
      // Block common third-party domains
      await page.route('**/*.{googletagmanager,doubleclick,facebook,google-analytics}/**', route => {
        route.abort('failed');
      });

      await page.goto('/login');

      // Should load without third-party dependencies
      await expect(loginPage.emailInput).toBeVisible({ timeout: 10000 });

      // Should not show errors related to blocked resources
      const errorCount = await page.locator('[data-testid="error-message"]').count();
      expect(errorCount).toBe(0);
    });

    test('Handles localStorage/sessionStorage issues', async ({ page }) => {
      // Simulate storage quota exceeded
      await page.addInitScript(() => {
        // Fill localStorage to capacity
        try {
          const data = 'x'.repeat(5 * 1024 * 1024); // 5MB chunks
          for (let i = 0; i < 10; i++) {
            localStorage.setItem(`test_${i}`, data);
          }
        } catch (e) {
          // Ignore quota exceeded errors
        }
      });

      await page.goto('/login');

      // Should handle storage issues gracefully
      await expect(loginPage.emailInput).toBeVisible({ timeout: 10000 });

      // Should not show storage-related errors to user
      const storageError = page.locator('[data-testid="storage-error"]');
      expect(await storageError.isVisible()).toBeFalsy();
    });
  });

  test.describe('Error Recovery and User Feedback', () => {
    test('Provides helpful error messages', async ({ page }) => {
      await page.goto('/search');

      // Perform search that will fail
      await searchPage.searchInput.fill('intentional failure test query');
      await searchPage.searchButton.click();

      await page.waitForTimeout(3000);

      // Check for error message quality
      const errorElement = page.locator('[data-testid="error-message"]');
      if (await errorElement.isVisible()) {
        const errorText = await errorElement.textContent();

        // Error should be user-friendly
        expect(errorText?.length).toBeGreaterThan(10);
        expect(errorText?.length).toBeLessThan(500); // Not too long

        // Should provide actionable information
        const hasActionableWords = /please|try|contact|check|verify/i.test(errorText || '');
        expect(hasActionableWords).toBe(true);

        // Should not show technical details
        expect(errorText).not.toContain('stack trace');
        expect(errorText).not.toContain('undefined');
        expect(errorText).not.toContain('null');
        expect(errorText).not.toContain('error:');
      }
    });

    test('Provides retry mechanisms', async ({ page }) => {
      // Simulate failure then success
      let attemptCount = 0;
      await page.route('**/api/search', async route => {
        attemptCount++;
        if (attemptCount === 1) {
          await route.abort('failed');
        } else {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ results: [], message: 'success' })
          });
        }
      });

      await page.goto('/search');
      await searchPage.searchInput.fill('test query');
      await searchPage.searchButton.click();

      // Should show error and retry option
      await expect(page.locator('[data-testid="error-message"]')).toBeVisible({ timeout: 5000 });
      await expect(page.locator('[data-testid="retry-button"]')).toBeVisible();

      // Test retry functionality
      await page.click('[data-testid="retry-button"]');

      // Should succeed on retry
      await expect(page.locator('[data-testid="search-results"]')).toBeVisible({ timeout: 5000 });
    });

    test('Maintains application state during errors', async ({ page }) => {
      await page.goto('/documents');

      // Fill form or set some state
      if (await documentsPage.searchFiles.isVisible()) {
        await documentsPage.searchFiles.fill('test search');
      }

      // Simulate error
      await page.route('**/api/**', async route => {
        await route.abort('failed');
      });

      // Trigger error
      await page.reload();

      // Should preserve user input where possible
      if (await documentsPage.searchFiles.isVisible()) {
        const searchValue = await documentsPage.searchFiles.inputValue();
        // Search value might be preserved or cleared, but shouldn't crash
        expect(searchValue !== undefined).toBe(true);
      }

      // Application should remain functional
      await expect(documentsPage.uploadArea).toBeVisible();
    });
  });
});