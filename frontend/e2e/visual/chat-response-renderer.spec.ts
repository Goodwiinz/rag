import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

const FIXTURE = '[data-testid="response-renderer-fixture"]';

async function openFixture(page: Page, theme: 'light' | 'dark'): Promise<void> {
  await page.addInitScript(
    (selectedTheme) => localStorage.setItem('theme', selectedTheme),
    theme
  );
  await page.goto('/visual-test/response-renderer');
  await expect(page.locator(FIXTURE)).toBeVisible();
  await expect(page.locator('html')).toHaveClass(new RegExp(`\\b${theme}\\b`));
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
}

async function expectResponsiveLayout(page: Page): Promise<void> {
  const layout = await page.evaluate((selector) => {
    const fixture = document.querySelector<HTMLElement>(selector);
    const table = fixture?.querySelector('table');
    const tableScroller = table?.parentElement;
    const fixtureRect = fixture?.getBoundingClientRect();

    return {
      documentWidth: document.documentElement.scrollWidth,
      viewportWidth: document.documentElement.clientWidth,
      fixtureLeft: fixtureRect?.left ?? -1,
      fixtureRight: fixtureRect?.right ?? Number.POSITIVE_INFINITY,
      tableOverflow: tableScroller
        ? getComputedStyle(tableScroller).overflowX
        : null,
    };
  }, FIXTURE);

  expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewportWidth);
  expect(layout.fixtureLeft).toBeGreaterThanOrEqual(0);
  expect(layout.fixtureRight).toBeLessThanOrEqual(layout.viewportWidth);
  expect(layout.tableOverflow).toBe('auto');
}

async function expectAccessible(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page }).include(FIXTURE).analyze();
  expect(results.violations).toEqual([]);
}

test('response output remains polished and accessible in light mode', async ({
  page,
}) => {
  await openFixture(page, 'light');
  await expectResponsiveLayout(page);
  await expectAccessible(page);
  await expect(page.locator(FIXTURE)).toHaveScreenshot('response-light.png', {
    animations: 'disabled',
  });
});

test('response output remains polished and accessible in dark mode', async ({
  page,
}) => {
  await openFixture(page, 'dark');
  await expectResponsiveLayout(page);
  await expectAccessible(page);
  await expect(page.locator(FIXTURE)).toHaveScreenshot('response-dark.png', {
    animations: 'disabled',
  });
});
