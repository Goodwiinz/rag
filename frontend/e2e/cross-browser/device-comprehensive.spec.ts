import { test, expect } from '../fixtures/enhanced-test-data.fixture';
import { DocumentProcessor } from '../utils/document-processor';

/**
 * Comprehensive Cross-Browser and Device Compatibility Tests
 *
 * Test Coverage:
 * - Desktop browser compatibility (Chrome, Firefox, Safari, Edge)
 * - Mobile device responsiveness (iOS, Android)
 * - Tablet device testing
 * - WebSocket functionality across browsers
 * - Real-time updates compatibility
 * - Performance variations across devices
 * - Touch interactions on mobile devices
 */

test.describe('Cross-Browser and Device Compatibility', () => {
  let documentProcessor: DocumentProcessor;

  test.beforeEach(async ({ page, webSocketUtils }) => {
    documentProcessor = new DocumentProcessor(page, webSocketUtils);
  });

  test.afterEach(async () => {
    await documentProcessor.cleanup();
  });

  test.describe('Desktop Browsers', () => {
    test('CB-1: Chrome desktop - Complete document processing workflow', async ({
      page,
      webSocketUtils,
      performanceMonitor,
      testDataManager
    }) => {
      test.slow();

      // Verify Chrome-specific features
      const browserInfo = await page.evaluate(() => ({
        userAgent: navigator.userAgent,
        vendor: navigator.vendor,
        platform: navigator.platform
      }));

      expect(browserInfo.userAgent).toContain('Chrome');
      expect(browserInfo.vendor).toContain('Google');

      // Test document processing workflow
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Verify WebSocket connection in Chrome
      await expect(page).toHaveWebSocketConnection('connected');

      // Test file upload with drag-and-drop
      const testFile = await testDataManager.getTestFile('chrome-test.pdf');
      const documentId = await documentProcessor.uploadDocument(testFile, {
        waitForProcessing: true
      });

      // Verify real-time updates work in Chrome
      await expect(page).toReceiveRealTimeUpdates(documentId, [
        'document_status_update',
        'processing_stage_update'
      ]);

      // Test Chrome-specific UI features
      await expect(page.locator('[data-testid="upload-area"]')).toBeVisible();
      await expect(page.locator('[data-testid="file-list"]')).toBeVisible();

      // Test keyboard shortcuts
      await page.keyboard.press('Control+a');
      await page.keyboard.press('Delete');
      await page.waitForTimeout(1000);

      // Test Chrome DevTools compatibility
      const performanceMetrics = await performanceMonitor.getMetric('firstContentfulPaint');
      expect(performanceMetrics).toBeLessThan(3000); // Should load quickly in Chrome

      // Take screenshot for Chrome comparison
      await page.screenshot({
        path: 'test-results/chrome-desktop-complete.png',
        fullPage: true
      });
    });

    test('CB-2: Firefox desktop - Complete document processing workflow', async ({
      page,
      webSocketUtils,
      testDataManager
    }) => {
      test.slow();

      // Verify Firefox-specific features
      const browserInfo = await page.evaluate(() => ({
        userAgent: navigator.userAgent,
        vendor: navigator.vendor,
        platform: navigator.platform
      }));

      expect(browserInfo.userAgent).toContain('Firefox');

      // Test document processing workflow
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Verify WebSocket connection in Firefox
      await expect(page).toHaveWebSocketConnection('connected');

      // Test file upload
      const testFile = await testDataManager.getTestFile('firefox-test.pdf');
      const documentId = await documentProcessor.uploadDocument(testFile, {
        waitForProcessing: true
      });

      // Verify real-time updates work in Firefox
      await expect(page).toReceiveRealTimeUpdates(documentId, [
        'document_status_update',
        'processing_stage_update'
      ]);

      // Test Firefox-specific UI features
      await expect(page.locator('[data-testid="upload-area"]')).toBeVisible();

      // Test Firefox-specific context menu behavior
      await page.click('[data-testid="file-item"]', { button: 'right' });
      await expect(page.locator('[data-testid="context-menu"]')).toBeVisible();
      await page.keyboard.press('Escape');

      // Take screenshot for Firefox comparison
      await page.screenshot({
        path: 'test-results/firefox-desktop-complete.png',
        fullPage: true
      });
    });

    test('CB-3: Safari desktop - Complete document processing workflow', async ({
      page,
      webSocketUtils,
      testDataManager
    }) => {
      test.slow();

      // Verify Safari-specific features
      const browserInfo = await page.evaluate(() => ({
        userAgent: navigator.userAgent,
        vendor: navigator.vendor,
        platform: navigator.platform
      }));

      expect(browserInfo.userAgent).toContain('Safari') || expect(browserInfo.userAgent).toContain('AppleWebKit');

      // Test document processing workflow
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Verify WebSocket connection in Safari
      await expect(page).toHaveWebSocketConnection('connected');

      // Test file upload (Safari has different file handling)
      const testFile = await testDataManager.getTestFile('safari-test.pdf');
      const documentId = await documentProcessor.uploadDocument(testFile, {
        waitForProcessing: true
      });

      // Verify real-time updates work in Safari
      await expect(page).toReceiveRealTimeUpdates(documentId, [
        'document_status_update',
        'processing_stage_update'
      ]);

      // Test Safari-specific touch events on desktop
      await page.locator('[data-testid="file-item"]').dispatchEvent('touchstart');
      await page.locator('[data-testid="file-item"]').dispatchEvent('touchend');

      // Take screenshot for Safari comparison
      await page.screenshot({
        path: 'test-results/safari-desktop-complete.png',
        fullPage: true
      });
    });

    test('CB-4: Edge desktop - Complete document processing workflow', async ({
      page,
      webSocketUtils,
      testDataManager
    }) => {
      test.slow();

      // Verify Edge-specific features
      const browserInfo = await page.evaluate(() => ({
        userAgent: navigator.userAgent,
        vendor: navigator.vendor,
        platform: navigator.platform
      }));

      expect(browserInfo.userAgent).toContain('Edg');

      // Test document processing workflow
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Verify WebSocket connection in Edge
      await expect(page).toHaveWebSocketConnection('connected');

      // Test file upload
      const testFile = await testDataManager.getTestFile('edge-test.pdf');
      const documentId = await documentProcessor.uploadDocument(testFile, {
        waitForProcessing: true
      });

      // Verify real-time updates work in Edge
      await expect(page).toReceiveRealTimeUpdates(documentId, [
        'document_status_update',
        'processing_stage_update'
      ]);

      // Test Edge-specific features (Windows integration)
      await page.keyboard.press('F11'); // Fullscreen
      await page.waitForTimeout(1000);
      await page.keyboard.press('F11'); // Exit fullscreen

      // Take screenshot for Edge comparison
      await page.screenshot({
        path: 'test-results/edge-desktop-complete.png',
        fullPage: true
      });
    });
  });

  test.describe('Mobile Devices', () => {
    test('MB-1: iPhone responsive document processing', async ({
      page,
      webSocketUtils,
      testDataManager
    }) => {
      test.slow();

      // Verify mobile viewport
      const viewportSize = page.viewportSize();
      expect(viewportSize?.width).toBeLessThanOrEqual(414); // iPhone max width

      // Test mobile navigation
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Verify mobile-specific UI elements
      await expect(page.locator('[data-testid="mobile-menu-button"]')).toBeVisible();
      await expect(page.locator('[data-testid="mobile-upload-button"]')).toBeVisible();

      // Test touch interactions for mobile
      await page.tap('[data-testid="mobile-menu-button"]');
      await expect(page.locator('[data-testid="mobile-menu"]')).toBeVisible();
      await page.tap('[data-testid="close-menu"]');

      // Test mobile file upload
      const testFile = await testDataManager.getTestFile('mobile-test.pdf');

      // Mobile upload via button tap
      await page.tap('[data-testid="mobile-upload-button"]');
      await page.setInputFiles('input[type="file"]', testFile.path);

      // Wait for upload to complete
      await page.waitForTimeout(5000);

      // Verify mobile progress indicators
      await expect(page.locator('[data-testid="mobile-progress-bar"]')).toBeVisible();

      // Test mobile pull-to-refresh functionality
      await page.touchscreen.tap(200, 100);
      await page.touchscreen.dragTo(200, 300);

      // Verify mobile-specific real-time updates
      const mobileUpdates = await webSocketUtils.getDocumentUpdates('mobile-upload');
      expect(mobileUpdates.length).toBeGreaterThan(0);

      // Test mobile device orientation change
      await page.evaluate(() => {
        // Simulate orientation change
        Object.defineProperty(window.screen, 'orientation', {
          value: { angle: 90, type: 'landscape-primary' },
          writable: true
        });
        window.dispatchEvent(new Event('orientationchange'));
      });

      // Take screenshot for mobile comparison
      await page.screenshot({
        path: 'test-results/iphone-mobile-complete.png',
        fullPage: true
      });
    });

    test('MB-2: Android responsive document processing', async ({
      page,
      webSocketUtils,
      testDataManager
    }) => {
      test.slow();

      // Verify Android viewport
      const viewportSize = page.viewportSize();
      expect(viewportSize?.width).toBeLessThanOrEqual(412); // Android max width

      // Test Android-specific features
      const deviceInfo = await page.evaluate(() => ({
        userAgent: navigator.userAgent,
        platform: navigator.platform
      }));

      expect(deviceInfo.userAgent).toContain('Android') || deviceInfo.userAgent.includes('Mobile');

      // Test Android file upload via share intent simulation
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Test Android back button behavior
      await page.goBack();
      await page.goForward();

      // Test Android material design elements
      await expect(page.locator('[data-testid="material-button"]')).toBeVisible();
      await expect(page.locator('[data-testid="material-card"]')).toBeVisible();

      // Test file upload with Android-specific interactions
      const testFile = await testDataManager.getTestFile('android-test.pdf');

      await page.tap('[data-testid="fab-button"]'); // Floating Action Button
      await page.setInputFiles('input[type="file"]', testFile.path);

      // Test Android notification handling
      await page.evaluate(() => {
        // Simulate Android notification permission
        Object.defineProperty(Notification, 'permission', {
          value: 'granted',
          writable: true
        });
      });

      // Verify WebSocket connection on mobile
      await expect(page).toHaveWebSocketConnection('connected');

      // Test mobile-specific error handling
      await page.evaluate(() => {
        // Simulate network loss
        Object.defineProperty(navigator, 'onLine', {
          value: false,
          writable: true
        });
        window.dispatchEvent(new Event('offline'));
      });

      await page.waitForTimeout(2000);

      await page.evaluate(() => {
        // Restore connection
        Object.defineProperty(navigator, 'onLine', {
          value: true,
          writable: true
        });
        window.dispatchEvent(new Event('online'));
      });

      // Verify reconnection on Android
      await expect(page).toHaveWebSocketConnection('connected');

      // Take screenshot for Android comparison
      await page.screenshot({
        path: 'test-results/android-mobile-complete.png',
        fullPage: true
      });
    });

    test('MB-3: Tablet responsive document processing', async ({
      page,
      webSocketUtils,
      testDataManager
    }) => {
      test.slow();

      // Verify tablet viewport
      const viewportSize = page.viewportSize();
      expect(viewportSize?.width).toBeGreaterThanOrEqual(768); // Tablet min width
      expect(viewportSize?.width).toBeLessThanOrEqual(1024); // Tablet max width

      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Test tablet-specific UI layout
      await expect(page.locator('[data-testid="tablet-layout"]')).toBeVisible();
      await expect(page.locator('[data-testid="sidebar"]')).toBeVisible();
      await expect(page.locator('[data-testid="main-content"]')).toBeVisible();

      // Test tablet split-screen functionality
      await page.setViewportSize({ width: 900, height: 600 });
      await page.waitForTimeout(1000);

      // Test tablet-specific touch interactions
      await page.locator('[data-testid="file-item"]').tap();
      await expect(page.locator('[data-testid="file-details"]')).toBeVisible();

      // Test tablet drag-and-drop
      const testFile = await testDataManager.getTestFile('tablet-test.pdf');
      const dataTransfer = await page.evaluateHandle(() => new DataTransfer());

      // Simulate tablet drag-and-drop
      await page.locator('[data-testid="upload-area"]').dispatchEvent('dragover', {
        dataTransfer: dataTransfer
      });

      await page.locator('[data-testid="upload-area"]').dispatchEvent('drop', {
        dataTransfer: dataTransfer
      });

      // Test tablet keyboard handling
      await page.tap('[data-testid="search-input"]');
      await page.keyboard.type('tablet search test');
      await page.keyboard.press('Enter');

      // Verify real-time updates on tablet
      await expect(page).toHaveWebSocketConnection('connected');

      // Take screenshot for tablet comparison
      await page.screenshot({
        path: 'test-results/tablet-complete.png',
        fullPage: true
      });
    });
  });

  test.describe('Cross-Device Performance Comparison', () => {
    test('CD-1: Performance comparison across devices', async ({
      page,
      performanceMonitor,
      testDataManager
    }) => {
      test.slow();

      const testFile = await testDataManager.getTestFile('performance-test.pdf');
      const deviceType = page.viewportSize()?.width! < 768 ? 'mobile' :
                        page.viewportSize()?.width! < 1024 ? 'tablet' : 'desktop';

      // Start performance monitoring
      const performanceId = await performanceMonitor.startMeasurement(`${deviceType}-performance`);

      // Measure load performance
      const loadStartTime = Date.now();
      await page.goto('/documents');
      const loadTime = Date.now() - loadStartTime;

      // Measure upload performance
      const uploadStartTime = Date.now();
      await page.setInputFiles('input[type="file"]', testFile.path);
      const uploadTime = Date.now() - uploadStartTime;

      // Wait for initial processing
      await page.waitForTimeout(3000);

      // Stop performance monitoring
      const performanceMetrics = await performanceMonitor.stopMeasurement(performanceId);

      // Get device-specific performance metrics
      const firstContentfulPaint = await performanceMonitor.getMetric('firstContentfulPaint');
      const largestContentfulPaint = await performanceMonitor.getMetric('largestContentfulPaint');
      const cumulativeLayoutShift = await performanceMonitor.getMetric('cumulativeLayoutShift');

      // Device-specific performance expectations
      if (deviceType === 'mobile') {
        expect(loadTime).toBeLessThan(5000); // Mobile: 5 seconds max
        expect(uploadTime).toBeLessThan(10000); // Mobile: 10 seconds max
        expect(firstContentfulPaint).toBeLessThan(2000); // Mobile: 2 seconds max
      } else if (deviceType === 'tablet') {
        expect(loadTime).toBeLessThan(3000); // Tablet: 3 seconds max
        expect(uploadTime).toBeLessThan(7000); // Tablet: 7 seconds max
        expect(firstContentfulPaint).toBeLessThan(1500); // Tablet: 1.5 seconds max
      } else {
        expect(loadTime).toBeLessThan(2000); // Desktop: 2 seconds max
        expect(uploadTime).toBeLessThan(5000); // Desktop: 5 seconds max
        expect(firstContentfulPaint).toBeLessThan(1000); // Desktop: 1 second max
      }

      // Log performance comparison
      console.log(`${deviceType.toUpperCase()} Performance Metrics:`);
      console.log(`  Load Time: ${loadTime}ms`);
      console.log(`  Upload Time: ${uploadTime}ms`);
      console.log(`  FCP: ${firstContentfulPaint}ms`);
      console.log(`  LCP: ${largestContentfulPaint}ms`);
      console.log(`  CLS: ${cumulativeLayoutShift}`);

      // Store performance data for comparison
      const performanceData = {
        deviceType,
        loadTime,
        uploadTime,
        firstContentfulPaint,
        largestContentfulPaint,
        cumulativeLayoutShift,
        totalDuration: performanceMetrics.duration
      };

      // Save performance data to file for analysis
      await page.evaluate((data) => {
        localStorage.setItem(`performance_${data.deviceType}`, JSON.stringify(data));
      }, performanceData);
    });

    test('CD-2: WebSocket performance across devices', async ({
      page,
      webSocketUtils,
      testDataManager
    }) => {
      test.slow();

      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Monitor WebSocket connection establishment time
      const connectionStartTime = Date.now();
      await expect(page).toHaveWebSocketConnection('connected');
      const connectionTime = Date.now() - connectionStartTime;

      // Test WebSocket message latency
      const testMessages = [
        { type: 'ping', payload: { timestamp: Date.now() } },
        { type: 'status_request', payload: { documentId: 'test' } },
        { type: 'health_check', payload: {} }
      ];

      const latencies = [];

      for (const message of testMessages) {
        const sendTime = Date.now();
        await webSocketUtils.mockWebSocketMessage({
          type: message.type,
          payload: message.payload,
          timestamp: sendTime
        });
        const receiveTime = Date.now();
        latencies.push(receiveTime - sendTime);
      }

      const averageLatency = latencies.reduce((sum, lat) => sum + lat, 0) / latencies.length;

      // Test WebSocket message handling under load
      const messageCount = 50;
      const loadTestStart = Date.now();

      for (let i = 0; i < messageCount; i++) {
        await webSocketUtils.mockWebSocketMessage({
          type: 'test_message',
          payload: { index: i, timestamp: Date.now() },
          timestamp: Date.now()
        });
      }

      const loadTestTime = Date.now() - loadTestStart;
      const messagesPerSecond = messageCount / (loadTestTime / 1000);

      // Device-specific WebSocket performance expectations
      const viewportWidth = page.viewportSize()?.width || 1200;
      const deviceType = viewportWidth < 768 ? 'mobile' :
                        viewportWidth < 1024 ? 'tablet' : 'desktop';

      if (deviceType === 'mobile') {
        expect(connectionTime).toBeLessThan(5000); // Mobile: 5 seconds max
        expect(averageLatency).toBeLessThan(500); // Mobile: 500ms max
        expect(messagesPerSecond).toBeGreaterThan(10); // Mobile: 10 messages/sec min
      } else if (deviceType === 'tablet') {
        expect(connectionTime).toBeLessThan(3000); // Tablet: 3 seconds max
        expect(averageLatency).toBeLessThan(300); // Tablet: 300ms max
        expect(messagesPerSecond).toBeGreaterThan(20); // Tablet: 20 messages/sec min
      } else {
        expect(connectionTime).toBeLessThan(2000); // Desktop: 2 seconds max
        expect(averageLatency).toBeLessThan(100); // Desktop: 100ms max
        expect(messagesPerSecond).toBeGreaterThan(50); // Desktop: 50 messages/sec min
      }

      // Get WebSocket performance metrics
      const wsMetrics = await webSocketUtils.getPerformanceMetrics();

      console.log(`${deviceType.toUpperCase()} WebSocket Performance:`);
      console.log(`  Connection Time: ${connectionTime}ms`);
      console.log(`  Average Latency: ${averageLatency}ms`);
      console.log(`  Messages/Second: ${messagesPerSecond}`);
      console.log(`  Total Messages: ${wsMetrics.messagesReceived}`);

      // Verify WebSocket connection stability
      expect(wsMetrics.messagesReceived).toBeGreaterThanOrEqual(messageCount);
      expect(wsMetrics.averageLatency).toBeLessThan(averageLatency * 1.5); // Within reasonable range
    });
  });

  test.describe('Browser-Specific Features', () => {
    test('BS-1: Chrome DevTools integration', async ({ page }) => {
      // Test Chrome DevTools protocol integration
      const client = await page.context().newCDPSession(page);

      // Enable performance domain
      await client.send('Performance.enable');

      // Navigate to page
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Get performance metrics via CDP
      const metrics = await client.send('Performance.getMetrics');

      // Verify key metrics are available
      const metricNames = metrics.metrics.map(m => m.name);
      expect(metricNames).toContain('DomContentLoaded');
      expect(metricNames).toContain('LoadEvent');

      // Test Chrome-specific features
      const consoleMessages = [];
      page.on('console', msg => consoleMessages.push(msg.text()));

      await page.evaluate(() => {
        // Chrome-specific console features
        console.log('%cChrome Feature Test', 'color: blue; font-size: 16px;');
        console.time('test-timer');
        setTimeout(() => console.timeEnd('test-timer'), 100);
      });

      await page.waitForTimeout(200);

      // Verify Chrome-specific console formatting
      const hasStyledMessage = consoleMessages.some(msg => msg.includes('Chrome Feature Test'));
      expect(hasStyledMessage).toBeTruthy();

      await client.detach();
    });

    test('BS-2: Firefox developer tools compatibility', async ({ page }) => {
      // Test Firefox-specific developer tools features
      const browserInfo = await page.evaluate(() => ({
        userAgent: navigator.userAgent,
        hasFirefoxConsole: typeof (window as any).console !== 'undefined'
      }));

      // Test Firefox-specific console features
      const consoleMessages = [];
      page.on('console', msg => consoleMessages.push(msg.text()));

      await page.evaluate(() => {
        // Firefox-specific console features
        console.log('Firefox Feature Test');

        // Test object inspection
        const testObj = { firefox: true, version: 'latest' };
        console.dir(testObj);

        // Test table display
        const data = [
          { name: 'Test 1', value: 100 },
          { name: 'Test 2', value: 200 }
        ];
        console.table(data);
      });

      await page.waitForTimeout(200);

      // Verify Firefox console features
      const hasLogMessage = consoleMessages.some(msg => msg.includes('Firefox Feature Test'));
      expect(hasLogMessage).toBeTruthy();
    });

    test('BS-3: Safari WebKit features', async ({ page }) => {
      // Test Safari/WebKit-specific features
      const webkitInfo = await page.evaluate(() => ({
        hasWebkit: 'webkitRequestAnimationFrame' in window,
        hasWebkitAudio: 'webkitAudioContext' in window,
        hasWebkitStorage: typeof Storage !== 'undefined',
        userAgent: navigator.userAgent
      }));

      expect(webkitInfo.hasWebkit).toBeTruthy();

      // Test Safari-specific gesture events
      await page.evaluate(() => {
        const element = document.body;

        // Simulate Safari gesture events
        const gestureStart = new Event('gesturestart', { bubbles: true });
        const gestureChange = new Event('gesturechange', { bubbles: true });
        const gestureEnd = new Event('gestureend', { bubbles: true });

        element.dispatchEvent(gestureStart);
        element.dispatchEvent(gestureChange);
        element.dispatchEvent(gestureEnd);
      });

      // Test Safari-specific storage features
      const storageInfo = await page.evaluate(() => {
        if ('storage' in navigator && 'estimate' in navigator.storage) {
          return navigator.storage.estimate();
        }
        return null;
      });

      // Safari should support storage estimation
      if (storageInfo) {
        expect(storageInfo.quota).toBeGreaterThan(0);
      }
    });
  });
});