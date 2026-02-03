import { test } from '@playwright/test';
import path from 'path';

test('capture screenshots', async ({ page }) => {
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
      console.error(`Failed to capture ${p.name}:`, e);
    }
  }
});
