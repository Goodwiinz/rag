import { chromium } from 'playwright';
import { mkdir, chmod } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { createInterface } from 'node:readline/promises';
import { stdin, stdout } from 'node:process';

// Run locally. Sign in yourself in the opened browser; this script never
// asks for your password in the terminal and records no login video/trace.
const origin = new URL(process.env.NOUS_BASE_URL ?? 'https://goodwiinz.tech').origin;
const statePath = resolve(process.env.NOUS_AUTH_STATE ?? '.auth/nous.json');
const browser = await chromium.launch({ headless: false });
const context = await browser.newContext();
const prompt = createInterface({ input: stdin, output: stdout });

try {
  const page = await context.newPage();
  await page.goto(`${origin}/login`);
  console.log('Sign in to NOUS in the opened browser. Do not paste credentials here.');
  await prompt.question('When the signed-in workspace is visible, press Enter here. ');
  if (new URL(page.url()).origin !== origin) {
    throw new Error('Return to the NOUS workspace before saving authentication.');
  }
  await page.getByRole('button', { name: 'Sign out', exact: true }).waitFor({
    state: 'visible', timeout: 30_000,
  });
  await mkdir(dirname(statePath), { recursive: true });
  await context.storageState({ path: statePath, indexedDB: true });
  await chmod(statePath, 0o600);
  console.log(`Authenticated state saved to ${statePath}. Keep this file private.`);
} finally {
  prompt.close();
  await context.close();
  await browser.close();
}
