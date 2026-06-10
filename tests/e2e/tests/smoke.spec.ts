import { test, expect } from '@playwright/test';
import { createTestHelpers, TEST_DATA } from '../utils/test-helpers';

/**
 * Smoke Test Suite
 * Fast, reliable tests that verify core functionality.
 * Run on every PR to catch critical regressions.
 * @smoke
 */

test.describe('Smoke Tests @smoke', () => {
  test('should load login page', async ({ page }) => {
    await page.goto('http://localhost:3000/login');
    await expect(page).toHaveTitle(/Sign in|NOUS|Login/i);
    await expect(page.locator('[data-testid="email-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="password-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="login-button"]')).toBeVisible();
  });

  test('should login and access dashboard', async ({ page }) => {
    // Navigate to login
    await page.goto('http://localhost:3000/login');
    
    // Fill in credentials
    await page.fill('[data-testid="email-input"]', TEST_DATA.USERS.ADMIN.email);
    await page.fill('[data-testid="password-input"]', TEST_DATA.USERS.ADMIN.password);
    
    // Click login
    await page.click('[data-testid="login-button"]');
    
    // Wait for dashboard navigation
    await page.waitForURL(/.*dashboard/, { timeout: 15000 });
    
    // Verify dashboard loaded
    await expect(page).toHaveURL(/.*dashboard/);
    
    // Verify we're not on login page
    await expect(page.locator('[data-testid="email-input"]')).not.toBeVisible();
  });

  test('should reject invalid credentials', async ({ page }) => {
    await page.goto('http://localhost:3000/login');
    
    await page.fill('[data-testid="email-input"]', 'invalid@example.com');
    await page.fill('[data-testid="password-input"]', 'wrongpassword');
    await page.click('[data-testid="login-button"]');
    
    // Should stay on login page
    await expect(page).toHaveURL(/.*login/);
    
    // Should show error
    await expect(page.locator('text=/Invalid|Error|Failed/i').first()).toBeVisible({ timeout: 5000 });
  });

  test('should redirect unauthenticated users to login', async ({ page }) => {
    await page.goto('http://localhost:3000/dashboard');
    
    // Should redirect to login
    await page.waitForURL(/.*login/, { timeout: 10000 });
    await expect(page).toHaveURL(/.*login/);
  });

  test('should load frontend without errors', async ({ page }) => {
    await page.goto('http://localhost:3000');
    
    // Page should load without console errors
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });
    
    // Wait for page to settle
    await page.waitForLoadState('networkidle');
    
    // Filter out non-critical errors (e.g., analytics, third-party)
    const criticalErrors = errors.filter(e => 
      !e.includes('analytics') && 
      !e.includes('statsig') && 
      !e.includes('sentry') &&
      !e.includes('googletagmanager')
    );
    
    expect(criticalErrors).toHaveLength(0);
  });

  test('backend health endpoint should respond', async ({ request }) => {
    const response = await request.get('http://localhost:8000/health');
    expect(response.ok()).toBeTruthy();
  });
});
