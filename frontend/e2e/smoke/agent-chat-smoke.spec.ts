/**
 * Post-deploy agent-chat smoke test.
 *
 * Closes the delivery-layer blind spot in the agent benchmark
 * (evals/agent-full-benchmark-v1.json): the benchmark certifies the LangGraph
 * core in-process, but nothing exercised login → SSE stream → frontend render
 * → persistence reload → thread switch → HITL confirm round trip against a
 * deployed environment. This spec does exactly that, and nothing more.
 *
 * Env-gated: skips entirely unless SMOKE_BASE_URL (or BASE_URL),
 * SMOKE_USER_EMAIL, and SMOKE_USER_PASSWORD are all set.
 *
 *   SMOKE_BASE_URL=https://goodwiinz.tech \
 *   SMOKE_USER_EMAIL=... SMOKE_USER_PASSWORD=... \
 *   npx playwright test --config=playwright.smoke.config.ts
 */
import { test, expect, type Page } from '@playwright/test';

const BASE_URL =
  process.env.SMOKE_BASE_URL?.trim() || process.env.BASE_URL?.trim() || '';
const EMAIL = process.env.SMOKE_USER_EMAIL ?? '';
const PASSWORD = process.env.SMOKE_USER_PASSWORD ?? '';

const CONFIGURED = Boolean(BASE_URL && EMAIL && PASSWORD);

// Model latency dominates; every agent-turn wait shares this budget.
const AGENT_TURN_TIMEOUT = 180_000;

test.skip(
  !CONFIGURED,
  'smoke test requires SMOKE_BASE_URL, SMOKE_USER_EMAIL, SMOKE_USER_PASSWORD'
);

async function login(page: Page) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector('[data-testid="email-input"]', { timeout: 20_000 });
  await page.fill('[data-testid="email-input"]', EMAIL);
  await page.fill('[data-testid="password-input"]', PASSWORD);
  await page.click('[data-testid="login-button"]');
  await page.waitForURL(/\/(dashboard|chat)/, { timeout: 30_000 });
}

/** Fill the chat composer and submit with Enter. */
async function sendMessage(page: Page, text: string) {
  const composer = page.getByPlaceholder(/Ask anything/);
  await expect(composer).toBeEnabled({ timeout: 30_000 });
  await composer.fill(text);
  await composer.press('Enter');
}

/** The whole page must not have crashed into an error boundary. */
async function expectNoCrash(page: Page) {
  await expect(page.getByText(/Application error|Something went wrong/)).toHaveCount(
    0
  );
}

test.describe('agent chat smoke (deployed env)', () => {
  test('send → stream renders → reload persists → thread switch survives', async ({
    page,
  }) => {
    await login(page);
    await page.goto(`${BASE_URL}/chat`);

    // 1. Send a turn and require the streamed answer to actually RENDER.
    //    A green backend run with a broken SSE contract or store reducer
    //    fails right here.
    await sendMessage(
      page,
      'Reply with exactly the word SMOKE_OK and nothing else.'
    );
    await expect(page.getByText('SMOKE_OK').first()).toBeVisible({
      timeout: AGENT_TURN_TIMEOUT,
    });

    // The thread URL is the durable handle for the switch-back below.
    await page.waitForURL(/thread=/, { timeout: 30_000 });
    const firstThreadUrl = page.url();

    // 2. Reload — the transcript the UI shows now comes from the persistence
    //    read path, not the live stream. Checkpointer/app-DB divergence
    //    surfaces here.
    await page.reload();
    await expect(page.getByText('SMOKE_OK').first()).toBeVisible({
      timeout: 60_000,
    });
    await expectNoCrash(page);

    // 3. New thread, second turn.
    await page.getByRole('button', { name: /New chat/ }).click();
    await sendMessage(
      page,
      'Reply with exactly the word SECOND_OK and nothing else.'
    );
    await expect(page.getByText('SECOND_OK').first()).toBeVisible({
      timeout: AGENT_TURN_TIMEOUT,
    });

    // 4. Switch back to the first thread — the historical crash mode
    //    ("Rendered more hooks", stranded loading flags) lives on this
    //    transition.
    await page.goto(firstThreadUrl);
    await expect(page.getByText('SMOKE_OK').first()).toBeVisible({
      timeout: 60_000,
    });
    await expectNoCrash(page);
  });

  test('HITL approval gate appears and Deny resolves the turn', async ({
    page,
  }) => {
    await login(page);
    await page.goto(`${BASE_URL}/chat`);

    // create_note is a destructive tool → must trigger interrupt().
    await sendMessage(
      page,
      'Use the create_note tool to create a note titled smoke-hitl-check ' +
        'with content "smoke". Do not ask clarifying questions.'
    );

    // The approval gate must reach the browser…
    const gate = page.getByRole('alertdialog', { name: 'Approval needed' });
    await expect(gate).toBeVisible({ timeout: AGENT_TURN_TIMEOUT });

    // …and Deny must complete the confirm round trip (frontend → /confirm →
    // resumed stream → terminal state). Deny, not Approve: exercises the same
    // wiring without writing data into the environment. A dead confirm gate
    // leaves the composer disabled forever and fails the re-enable check.
    await gate.getByRole('button', { name: 'Deny' }).click();
    await expect(gate).toBeHidden({ timeout: 60_000 });
    await expect(page.getByPlaceholder(/Ask anything/)).toBeEnabled({
      timeout: AGENT_TURN_TIMEOUT,
    });
    await expectNoCrash(page);
  });
});
