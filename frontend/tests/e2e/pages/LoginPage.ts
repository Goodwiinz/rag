/**
 * LoginPage Page Object Model
 *
 * Encapsulates all interactions with the /login page.
 * Uses data-testid selectors from app/(auth)/login/page.tsx.
 */

import { type Page, type BrowserContext } from '@playwright/test';

export class LoginPage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  // Locators
  get emailInput() {
    return this.page.getByTestId('email-input');
  }

  get passwordInput() {
    return this.page.getByTestId('password-input');
  }

  get loginButton() {
    return this.page.getByTestId('login-button');
  }

  async goto() {
    await this.page.goto('/login');
    // Wait for the form to be interactive (past the SSR skeleton)
    await this.emailInput.waitFor({ state: 'visible', timeout: 15000 });
  }

  async login(email: string, password: string) {
    await this.goto();
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.loginButton.click();
    // Wait for redirect away from login
    await this.page.waitForURL((url) => !url.pathname.includes('/login'), {
      timeout: 15000,
    });
  }
}

/**
 * Perform login via direct API call and store the session cookie.
 * This is faster than going through the UI and avoids counting UI login
 * toward E2E test time for tests that don't care about the login flow.
 */
export async function loginViaAPI(
  context: BrowserContext,
  email: string,
  password: string,
  baseURL: string
) {
  const apiPage = await context.newPage();
  try {
    // Call the auth API endpoint
    const response = await apiPage.request.post(
      `${baseURL}/api/v1/auth/login`,
      {
        data: { email, password },
        headers: { 'Content-Type': 'application/json' },
      }
    );

    if (!response.ok()) {
      throw new Error(
        `Auth API returned ${response.status()}: ${await response.text()}`
      );
    }
  } finally {
    await apiPage.close();
  }
}
