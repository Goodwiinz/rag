import { expect, test, type Page } from '@playwright/test';

const email = process.env.E2E_EMAIL;
const password = process.env.E2E_PASSWORD;
const threadId =
  process.env.CHAT_RECONCILIATION_THREAD_ID ??
  'f30644d3-2f5f-420d-b4e3-95220b49e3e2';

async function login(page: Page) {
  await page.goto('/login');
  await page.getByTestId('email-input').fill(email!);
  await page.getByTestId('password-input').fill(password!);
  await page.getByTestId('login-button').click();
  await page.waitForURL(/\/dashboard|\/chat/, { timeout: 30_000 });
}

test.describe('chat terminal reconciliation', () => {
  test.skip(
    !email || !password,
    'Set E2E_EMAIL and E2E_PASSWORD to run authenticated chat persistence.'
  );

  test('keeps the completed arXiv turn visible and restores it after reload', async ({
    page,
  }) => {
    test.setTimeout(180_000);
    await login(page);
    await page.goto(`/chat?thread=${threadId}`);

    const composer = page.getByPlaceholder(
      'Ask anything, or paste a passage to discuss…'
    );
    await expect(composer).toBeVisible({ timeout: 30_000 });

    const marker = `reconciliation-${Date.now()}`;
    const prompt =
      `Find recent arXiv papers on retrieval-augmented generation. ` +
      `Include this marker in the answer: ${marker}`;
    const assistantRows = page.locator('[data-role="assistant"]');
    const assistantCountBefore = await assistantRows.count();

    await composer.fill(prompt);
    await page.getByRole('button', { name: /^Send/ }).click();
    await expect(
      page.locator('[data-role="user"]').filter({ hasText: marker }).last()
    ).toBeVisible();

    await expect
      .poll(() => assistantRows.count(), { timeout: 150_000 })
      .toBeGreaterThan(assistantCountBefore);
    const completedAnswer = assistantRows.last();
    await expect(completedAnswer).toContainText(marker, { timeout: 150_000 });
    await expect(page.getByRole('button', { name: /^Send/ })).toBeEnabled({
      timeout: 30_000,
    });

    // The original defect removed the optimistic answer after terminal state
    // reconciliation. It only reappeared after reload. Hold through the swap.
    await page.waitForTimeout(1_000);
    await expect(completedAnswer).toContainText(marker);

    await page.reload();
    await expect(composer).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator('[data-role="user"]').filter({ hasText: marker }).last()
    ).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator('[data-role="assistant"]').filter({ hasText: marker }).last()
    ).toBeVisible({ timeout: 30_000 });
  });
});
