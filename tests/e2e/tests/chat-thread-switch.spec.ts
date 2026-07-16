import { test, expect, type Route } from "@playwright/test";
import { createTestHelpers, TEST_DATA } from "../utils/test-helpers";

/**
 * Critical journey: rapid thread switching must not bleed a background
 * turn's content into whichever thread is currently displayed (the CX5
 * `isTurnDisplayed`/`streamingThreadId` gating and the local-overlay clear
 * on thread switch in useChatSession/useChatStreaming).
 *
 * The agent SSE endpoint is intercepted so the journey is deterministic and
 * fast: the first turn's response is deliberately delayed (simulating a
 * slow model response); the second turn's response is immediate. Timing is
 * driven entirely by real network events (`page.waitForResponse`) — no
 * fixed sleeps.
 *
 * @regression
 */

const STREAM_URL = "**/api/v1/agent/stream";
const RESUME_URL = "**/agent/stream/resume/**";
const ALPHA_DELAY_MS = 2500;

function sseFrame(event: string, data: Record<string, unknown>): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

test.describe("Chat thread switching @regression", () => {
  test("a delayed background turn never renders into a different thread", async ({
    page,
    context,
  }, testInfo) => {
    const helpers = createTestHelpers(page, context, testInfo);

    const alphaMarker = `alpha-${Date.now()}`;
    const bravoMarker = `bravo-${Date.now()}`;
    let streamCallCount = 0;

    // Resume attempts (mount-time reattach) are a no-op in this journey —
    // nothing was left running server-side.
    await page.route(RESUME_URL, (route: Route) =>
      route.fulfill({ status: 204, body: "" }),
    );

    await page.route(STREAM_URL, async (route: Route) => {
      streamCallCount += 1;
      if (streamCallCount === 1) {
        // Simulates a slow model response for the first (Alpha) turn.
        await new Promise((resolve) => setTimeout(resolve, ALPHA_DELAY_MS));
        await route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body:
            sseFrame("token", { content: `Reply: ${alphaMarker}` }) +
            sseFrame("done", { thread_id: null }),
        });
        return;
      }
      // Second (Bravo) turn resolves immediately.
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body:
          sseFrame("token", { content: `Reply: ${bravoMarker}` }) +
          sseFrame("done", { thread_id: null }),
      });
    });

    await helpers.login(TEST_DATA.USERS.ADMIN);

    await helpers.navigateTo("/chat?new=1");
    const composer = page.getByPlaceholder(
      "Ask anything, or paste a passage to discuss…",
    );
    await expect(composer).toBeVisible({ timeout: 15000 });

    // --- Turn A: send, then immediately abandon the thread while the
    // (delayed) response is still in flight. ---
    await composer.fill(`Alpha marker ${alphaMarker}`);
    const alphaResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/agent/stream") &&
        response.request().method() === "POST",
    );
    await page.getByRole("button", { name: /^Send/ }).click();

    await expect(
      page.locator('[data-role="user"]').filter({ hasText: alphaMarker }),
    ).toBeVisible();
    await page.waitForURL(/\/chat\?thread=/, { timeout: 15000 });

    await page.getByRole("button", { name: /New chat/ }).click();
    await page.waitForURL(/\/chat\?new=1/, { timeout: 15000 });

    // Rapid switch happened before Alpha's delayed reply arrived: the blank
    // composer must show nothing from thread A.
    await expect(page.locator("[data-runtime-id]")).toHaveCount(0);
    await expect(page.getByText(alphaMarker)).toHaveCount(0);

    // --- Turn B: a second thread, fast response. ---
    await composer.fill(`Bravo marker ${bravoMarker}`);
    await page.getByRole("button", { name: /^Send/ }).click();
    await expect(
      page.locator('[data-role="user"]').filter({ hasText: bravoMarker }),
    ).toBeVisible();
    await expect(
      page
        .locator('[data-role="assistant"]')
        .filter({ hasText: bravoMarker }),
    ).toBeVisible({ timeout: 15000 });

    // Wait for Alpha's delayed background response to actually land
    // (network-level synchronization, not a fixed sleep) …
    await alphaResponse;

    // … and confirm it still never rendered into the thread B view that's
    // currently displayed.
    await expect(page.getByText(alphaMarker)).toHaveCount(0);
    await expect(
      page
        .locator('[data-role="assistant"]')
        .filter({ hasText: bravoMarker }),
    ).toHaveCount(1);
  });
});
