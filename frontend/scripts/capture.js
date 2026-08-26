const fs = require('fs');
const path = require('path');
const { chromium } = require('@playwright/test');

const baseUrl = process.env.CAPTURE_BASE_URL || 'http://localhost:3000';
const email = process.env.CAPTURE_EMAIL;
const password = process.env.CAPTURE_PASSWORD;
const outputDir = path.resolve(
  process.env.CAPTURE_OUTPUT_DIR || path.join('..', 'brand', 'screenshots')
);

const targets = [
  ['01-dashboard', '/dashboard'],
  ['02-chat', '/chat'],
  ['03-search', '/search'],
  ['04-documents', '/documents'],
  ['05-upload', '/documents/upload'],
  ['06-entities', '/entities'],
  ['07-arxiv', '/arxiv'],
  ['08-research', '/research'],
  ['09-analytics', '/analytics'],
  ['10-diagnostics', '/diagnostics'],
  ['11-settings', '/settings'],
];

async function settle(page) {
  await page.waitForLoadState('domcontentloaded');
  await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {});
  await page.waitForTimeout(1_000);
}

async function login(page) {
  if (!email || !password) return;

  await page.goto(`${baseUrl}/login`);
  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL((url) => url.pathname !== '/login', { timeout: 30_000 });
  await settle(page);
}

(async () => {
  fs.mkdirSync(outputDir, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });
  await context.addInitScript(() => localStorage.setItem('theme', 'dark'));
  const page = await context.newPage();

  try {
    await login(page);

    for (const [name, route] of targets) {
      await page.goto(`${baseUrl}${route}`);
      await settle(page);

      const pathname = new URL(page.url()).pathname;
      if (pathname === '/login' || !pathname.startsWith(route)) {
        throw new Error(`${route} resolved to ${pathname}; refusing stale screenshot`);
      }

      await page.addStyleTag({
        content: '*,*::before,*::after{animation:none!important;transition:none!important}',
      });
      const file = path.join(outputDir, `${name}.png`);
      await page.screenshot({ path: file, fullPage: true });
      console.log(`${route} -> ${file}`);
    }
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
