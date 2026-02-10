const fs = require('fs');
const path = require('path');

let chromium;
try {
  chromium = require('playwright').chromium;
} catch (e) {
  try {
    chromium = require('@playwright/test').chromium;
  } catch (e2) {
    console.error('Could not find playwright or @playwright/test');
    process.exit(1);
  }
}

(async () => {
  const logFile = path.resolve('capture.log');
  const log = (msg) => {
    const text = `${new Date().toISOString()} - ${msg}\n`;
    fs.appendFileSync(logFile, text);
    console.log(msg);
  };

  log('Starting capture script...');
  
  const screenshotsDir = path.resolve('screenshots');
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir);
    log(`Created directory: ${screenshotsDir}`);
  }

  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  // Set viewport to a reasonable desktop size
  await page.setViewportSize({ width: 1280, height: 720 });

  const targets = [
    { name: 'dashboard', url: 'http://localhost:3000/dashboard' },
    { name: 'chat', url: 'http://localhost:3000/chat' },
    { name: 'documents', url: 'http://localhost:3000/documents' },
    { name: 'settings', url: 'http://localhost:3000/settings' }
  ];

  for (const t of targets) {
    try {
      log(`Navigating to ${t.url}`);
      await page.goto(t.url, { waitUntil: 'networkidle', timeout: 30000 });
      await page.waitForTimeout(1000); // Wait for animations
      
      const file = path.join(screenshotsDir, `${t.name}.png`);
      await page.screenshot({ path: file, fullPage: true });
      log(`Captured ${file}`);
    } catch (e) {
      log(`Error capturing ${t.name}: ${e.message}`);
    }
  }

  await browser.close();
  log('Done.');
})();
