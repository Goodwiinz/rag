import { test, expect } from '@playwright/test';
import path from 'path';

test('capture screenshots', async ({ page }) => {
  const failures: string[] = [];
  const pages = [
    { name: 'dashboard', url: '/dashboard' },
    { name: 'chat', url: '/chat' },
    { name: 'documents', url: '/documents' },
    { name: 'settings', url: '/settings' }
  ];

  for (const p of pages) {
    console.log(`Navigating to ${p.url}...`);
    try {
      await page.goto(p.url, { waitUntil: 'networkidle' });
      // Wait a bit for animations or dynamic content
      await page.waitForTimeout(2000); 
      
      const screenshotPath = path.join(process.cwd(), 'screenshots', `${p.name}.png`);
      console.log(`Capturing ${p.name} to ${screenshotPath}`);
      
      await page.screenshot({ path: screenshotPath, fullPage: true });
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      console.error(`Failed to capture ${p.name}:`, e);
      failures.push(`${p.name}: ${message}`);
    }
  }

  expect(failures, `Screenshot failures:\n${failures.join('\n')}`).toEqual([]);
});
