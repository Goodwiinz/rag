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
    const userIdentity = page.locator('[data-runtime-id]').filter({
      has: page.locator('[data-role="user"]'),
      hasText: marker,
    });
    await expect(userIdentity).toHaveCount(1);
    await expect(userIdentity).toBeVisible();

    await expect
      .poll(() => assistantRows.count(), { timeout: 150_000 })
      .toBeGreaterThan(assistantCountBefore);
    const completedAnswer = page.locator('[data-runtime-id]').filter({
      has: page.locator('[data-role="assistant"]'),
      hasText: marker,
    });
    await expect(completedAnswer).toHaveCount(1, { timeout: 150_000 });
    await expect(completedAnswer).toContainText(marker);
    await expect(page.getByRole('button', { name: /^Send/ })).toBeEnabled({
      timeout: 30_000,
    });
    const userRuntimeId = await userIdentity.getAttribute('data-runtime-id');
    const assistantRuntimeId =
      await completedAnswer.getAttribute('data-runtime-id');
    const userPersistedId =
      await userIdentity.getAttribute('data-persisted-id');
    const assistantPersistedId =
      await completedAnswer.getAttribute('data-persisted-id');
    expect(userRuntimeId).toBeTruthy();
    expect(assistantRuntimeId).toBeTruthy();
    expect(userPersistedId).toBeTruthy();
    expect(assistantPersistedId).toBeTruthy();

    // The original defect removed the optimistic answer after terminal state
    // reconciliation. It only reappeared after reload. Hold through the swap.
    await page.waitForTimeout(1_000);
    await expect(completedAnswer).toContainText(marker);

    // Client-side selection reset and return: no page reload is allowed to
    // recover the rows, and both identity layers must remain unchanged.
    await page.getByRole('button', { name: /New chat/ }).click();
    await page.waitForURL(/\/chat\?new=1/, { timeout: 30_000 });
    await page.goBack();
    await page.waitForURL(new RegExp(`thread=${threadId}`), {
      timeout: 30_000,
    });
    await expect(
      page.locator(`[data-runtime-id="${userRuntimeId}"]`)
    ).toHaveAttribute('data-persisted-id', userPersistedId!);
    await expect(
      page.locator(`[data-runtime-id="${assistantRuntimeId}"]`)
    ).toHaveAttribute('data-persisted-id', assistantPersistedId!);

    await page.reload();
    await expect(composer).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator(`[data-runtime-id="${userRuntimeId}"]`)
    ).toHaveAttribute('data-persisted-id', userPersistedId!, {
      timeout: 30_000,
    });
    await expect(
      page.locator(`[data-runtime-id="${assistantRuntimeId}"]`)
    ).toHaveAttribute('data-persisted-id', assistantPersistedId!, {
      timeout: 30_000,
    });

    // Complete a second turn while no transcript is selected. Returning to
    // the owning thread must hydrate it without writing into the blank chat.
    const backgroundMarker = `background-${Date.now()}`;
    await composer.fill(
      `Reply with this exact marker and no other text: ${backgroundMarker}`
    );
    await page.getByRole('button', { name: /^Send/ }).click();
    await expect(
      page.locator('[data-role="user"]').filter({ hasText: backgroundMarker })
    ).toBeVisible();
    await page.getByRole('button', { name: /New chat/ }).click();
    await page.waitForURL(/\/chat\?new=1/, { timeout: 30_000 });
    await expect(page.getByRole('button', { name: /^Send/ })).toBeEnabled({
      timeout: 150_000,
    });
    await page.goBack();
    await page.waitForURL(new RegExp(`thread=${threadId}`), {
      timeout: 30_000,
    });
    await expect(
      page.locator('[data-role="assistant"]').filter({
        hasText: backgroundMarker,
      })
    ).toBeVisible({ timeout: 30_000 });
  });
});
