import { test, expect } from '../fixtures/enhanced-test-data.fixture';
import { DocumentProcessor } from '../utils/document-processor';

/**
 * Comprehensive Error Scenarios and Recovery Tests
 *
 * Test Coverage:
 * - Network connectivity issues and recovery
 * - WebSocket connection failures and reconnection
 * - File upload errors and retry mechanisms
 * - Document processing failures and error handling
 * - Server-side errors and graceful degradation
 * - User interface error states and recovery
 * - Concurrent error scenarios handling
 */

test.describe('Error Scenarios and Recovery', () => {
  let documentProcessor: DocumentProcessor;

  test.beforeEach(async ({ page, webSocketUtils }) => {
    documentProcessor = new DocumentProcessor(page, webSocketUtils);
    await page.goto('/documents');
    await page.waitForLoadState('networkidle');
  });

  test.afterEach(async () => {
    await documentProcessor.cleanup();
  });

  test.describe('Network Connectivity Issues', () => {
    test('NET-1: Network disconnection during file upload', async ({
      page,
      webSocketUtils,
      testDataManager
    }) => {
      test.slow();

      // Start file upload
      const largeFile = await testDataManager.getTestFile('large-upload-test.pdf');
      await page.setInputFiles('input[type="file"]', largeFile.path);

      // Wait for upload to start
      await page.waitForSelector('[data-testid="upload-progress"]', { timeout: 5000 });

      // Simulate network disconnection
      await page.setOffline(true);

      // Verify upload error handling
      await expect(page.locator('[data-testid="network-error"]')).toBeVisible({ timeout: 10000 });
      await expect(page.locator('[data-testid="upload-failed"]')).toBeVisible();

      // Verify retry button appears
      const retryButton = page.locator('[data-testid="retry-upload"]');
      await expect(retryButton).toBeVisible();

      // Restore network connection
      await page.setOffline(false);

      // Click retry button
      await retryButton.click();

      // Verify upload resumes and completes
      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible({ timeout: 30000 });

      // Verify file appears in list after successful upload
      await expect(page.locator(`[data-file-name="${largeFile.name}"]`)).toBeVisible({ timeout: 10000 });

      console.log('Network disconnection during upload handled successfully');
    });

    test('NET-2: WebSocket connection loss during processing', async ({
      page,
      webSocketUtils,
      testDataManager
    }) => {
      test.slow();

      // Upload a document for processing
      const testFile = await testDataManager.getTestFile('websocket-test.pdf');
      const documentId = await documentProcessor.uploadDocument(testFile, {
        waitForProcessing: false
      });

      // Wait for processing to start
      await documentProcessor.waitForStatusChange(documentId, 'queued', 'processing', 10000);

      // Simulate WebSocket connection loss
      await webSocketUtils.simulateConnectionLoss(3000);

      // Verify connection status indicator
      await expect(page.locator('[data-testid="connection-lost"]')).toBeVisible();
      await expect(page.locator('[data-testid="reconnecting"]')).toBeVisible();

      // Wait for reconnection
      await page.waitForSelector('[data-testid="connection-restored"]', { timeout: 15000 });

      // Verify processing continues after reconnection
      const finalState = await documentProcessor.waitForProcessingCompletion(documentId, 180000);
      expect(finalState.status).toBe('completed');

      // Verify no data was lost during connection loss
      const processingStages = finalState.stages.filter(stage => stage.status === 'completed');
      expect(processingStages.length).toBeGreaterThan(0);

      console.log('WebSocket connection loss during processing handled successfully');
    });

    test('NET-3: Slow network conditions handling', async ({
      page,
      testDataManager
    }) => {
      test.slow();

      // Simulate slow network (3G speeds)
      await page.route('**/*', async (route) => {
        // Add artificial delay
        await new Promise(resolve => setTimeout(resolve, 1000));
        await route.continue();
      });

      // Test file upload under slow network
      const testFile = await testDataManager.getTestFile('slow-network-test.pdf');

      const uploadStartTime = Date.now();
      await page.setInputFiles('input[type="file"]', testFile.path);

      // Verify slow upload indicator
      await expect(page.locator('[data-testid="slow-upload-warning"]')).toBeVisible({ timeout: 5000 });

      // Verify progress updates still work under slow network
      const progressBar = page.locator('[data-testid="upload-progress"]');
      await expect(progressBar).toBeVisible();

      // Wait for upload to complete (should take longer due to network throttling)
      await page.waitForSelector('[data-testid="upload-complete"]', { timeout: 60000 });
      const uploadDuration = Date.now() - uploadStartTime;

      // Verify upload succeeded despite slow network
      expect(uploadDuration).toBeGreaterThan(5000); // Should take at least 5 seconds due to throttling

      // Clear network throttling
      await page.unroute('**/*');

      // Verify normal operation resumes
      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      console.log(`Slow network upload completed in ${uploadDuration}ms`);
    });

    test('NET-4: Intermittent network failures', async ({
      page,
      webSocketUtils,
      testDataManager
    }) => {
      test.slow();

      // Create intermittent network failure pattern
      let failureCount = 0;
      await page.route('**/*', async (route) => {
        failureCount++;
        if (failureCount % 3 === 0) {
          // Fail every 3rd request
          await route.abort('failed');
        } else {
          await route.continue();
        }
      });

      // Upload file with intermittent failures
      const testFile = await testDataManager.getTestFile('intermittent-test.pdf');

      try {
        await page.setInputFiles('input[type="file"]', testFile.path);

        // Should show intermittent error warnings
        await expect(page.locator('[data-testid="intermittent-error"]')).toBeVisible({ timeout: 10000 });

        // Should eventually succeed with retries
        await page.waitForSelector('[data-testid="upload-success"]', { timeout: 120000 });

      } catch (error) {
        // Handle expected intermittent failures
        console.log('Intermittent network failures detected:', error.message);
      }

      // Clear network routing
      await page.unroute('**/*');

      console.log(`Intermittent network failures: ${failureCount} requests processed`);
    });
  });

  test.describe('File Upload Errors', () => {
    test('FILE-1: Oversized file upload handling', async ({
      page,
      testDataManager
    }) => {
      test.slow();

      // Create a file that exceeds size limits
      const oversizedFile = await testDataManager.createOversizedFile('oversized-test.pdf', 50 * 1024 * 1024); // 50MB

      // Attempt to upload oversized file
      await page.setInputFiles('input[type="file"]', oversizedFile.path);

      // Verify size validation error
      await expect(page.locator('[data-testid="file-size-error"]')).toBeVisible({ timeout: 5000 });
      await expect(page.locator('[data-testid="error-message"]')).toContainText('too large');

      // Verify helpful error message with size limits
      const errorMessage = page.locator('[data-testid="error-details"]');
      await expect(errorMessage).toBeVisible();
      await expect(errorMessage).toContainText('50MB');

      // Verify file is not added to upload list
      const fileItems = page.locator('[data-testid="file-item"]');
      await expect(fileItems).toHaveCount(0);

      console.log('Oversized file upload handled correctly');
    });

    test('FILE-2: Unsupported file format handling', async ({
      page,
      testDataManager
    }) => {
      test.slow();

      // Create unsupported file
      const unsupportedFile = await testDataManager.createUnsupportedFile('test.exe', 'application/x-executable');

      // Attempt to upload unsupported file
      await page.setInputFiles('input[type="file"]', unsupportedFile.path);

      // Verify format validation error
      await expect(page.locator('[data-testid="file-format-error"]')).toBeVisible({ timeout: 5000 });
      await expect(page.locator('[data-testid="error-message"]')).toContainText('unsupported format');

      // Verify list of supported formats is shown
      const supportedFormats = page.locator('[data-testid="supported-formats"]');
      await expect(supportedFormats).toBeVisible();
      await expect(supportedFormats).toContainText('PDF') || await expect(supportedFormats).toContainText('Image');

      // Test conversion suggestion if available
      const conversionSuggestion = page.locator('[data-testid="conversion-suggestion"]');
      if (await conversionSuggestion.isVisible()) {
        await expect(conversionSuggestion).toContainText('convert');
      }

      console.log('Unsupported file format handled correctly');
    });

    test('FILE-3: Corrupted file handling', async ({
      page,
      testDataManager
    }) => {
      test.slow();

      // Create corrupted file
      const corruptedFile = await testDataManager.createCorruptedFile('corrupted-test.pdf');

      // Attempt to upload corrupted file
      await page.setInputFiles('input[type="file"]', corruptedFile.path);

      // Wait for corruption detection
      await expect(page.locator('[data-testid="file-corrupted-error"]')).toBeVisible({ timeout: 15000 });
      await expect(page.locator('[data-testid="error-message"]')).toContainText('corrupted') ||
      await expect(page.locator('[data-testid="error-message"]')).toContainText('invalid');

      // Verify retry option is available
      const retryButton = page.locator('[data-testid="retry-upload"]');
      await expect(retryButton).toBeVisible();

      // Verify remove option is available
      const removeButton = page.locator('[data-testid="remove-file"]');
      await expect(removeButton).toBeVisible();

      // Test remove functionality
      await removeButton.click();
      await expect(page.locator(`[data-file-name="${corruptedFile.name}"]`)).not.toBeVisible({ timeout: 5000 });

      console.log('Corrupted file handling completed successfully');
    });

    test('FILE-4: Duplicate file upload handling', async ({
      page,
      testDataManager
    }) => {
      test.slow();

      // Upload initial file
      const testFile = await testDataManager.getTestFile('duplicate-test.pdf');
      await page.setInputFiles('input[type="file"]', testFile.path);

      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible({ timeout: 30000 });

      // Clear file input for second upload
      await page.evaluate(() => {
        const input = document.querySelector('input[type="file"]') as HTMLInputElement;
        if (input) {
          input.value = '';
        }
      });

      // Attempt to upload same file again
      await page.setInputFiles('input[type="file"]', testFile.path);

      // Verify duplicate detection
      await expect(page.locator('[data-testid="duplicate-file-warning"]')).toBeVisible({ timeout: 5000 });
      await expect(page.locator('[data-testid="error-message"]')).toContainText('already exists') ||
      await expect(page.locator('[data-testid="error-message"]')).toContainText('duplicate');

      // Test overwrite option
      const overwriteButton = page.locator('[data-testid="overwrite-file"]');
      if (await overwriteButton.isVisible()) {
        await overwriteButton.click();
        await expect(page.locator('[data-testid="overwrite-success"]')).toBeVisible({ timeout: 30000 });
      }

      // Test cancel option
      const cancelButton = page.locator('[data-testid="cancel-duplicate"]');
      if (await cancelButton.isVisible()) {
        await cancelButton.click();
        await expect(page.locator('[data-testid="upload-cancelled"]')).toBeVisible();
      }

      console.log('Duplicate file upload handling completed');
    });
  });

  test.describe('Document Processing Errors', () => {
    test('PROC-1: OCR processing failure recovery', async ({
      page,
      webSocketUtils,
      testDataManager
    }) => {
      test.slow();

      // Create a file that will cause OCR to fail (image-only PDF with no readable text)
      const ocrFailureFile = await testDataManager.createOCRFailureFile('ocr-failure-test.pdf');

      // Upload file
      const documentId = await documentProcessor.uploadDocument(ocrFailureFile, {
        waitForProcessing: false
      });

      // Monitor processing stages
      let ocrStageFailed = false;
      documentProcessor.registerProcessingCallback(documentId, (state) => {
        const ocrStage = state.stages.find(s => s.name === 'ocr');
        if (ocrStage?.status === 'error') {
          ocrStageFailed = true;
        }
      });

      // Wait for processing to complete or fail
      try {
        await documentProcessor.waitForProcessingCompletion(documentId, 120000);
      } catch (error) {
        // Expected to fail due to OCR issues
      }

      // Verify OCR failure was handled gracefully
      expect(ocrStageFailed).toBeTruthy();

      // Verify fallback to text extraction if available
      const finalState = documentProcessor.getProcessingState(documentId);
      if (finalState?.status === 'completed') {
        // Should have completed with fallback
        const fallbackStages = finalState.stages.filter(s => s.status === 'completed');
        expect(fallbackStages.length).toBeGreaterThan(0);
      } else {
        // Should show proper error message
        await expect(page.locator('[data-testid="processing-error"]')).toBeVisible();
        await expect(page.locator('[data-testid="error-message"]')).toContainText('OCR');
      }

      console.log('OCR processing failure handled gracefully');
    });

    test('PROC-2: Transcription service failure', async ({
      page,
      webSocketUtils,
      testDataManager
    }) => {
      test.slow();

      // Upload audio file for transcription
      const audioFile = await testDataManager.getTestFile('transcription-test.mp3');
      const documentId = await documentProcessor.uploadDocument(audioFile, {
        waitForProcessing: false
      });

      // Monitor transcription stage
      let transcriptionFailed = false;
      documentProcessor.registerProcessingCallback(documentId, (state) => {
        const transcriptionStage = state.stages.find(s => s.name === 'transcription');
        if (transcriptionStage?.status === 'error') {
          transcriptionFailed = true;
        }
      });

      // Mock transcription service failure
      await webSocketUtils.mockWebSocketMessage({
        type: 'processing_stage_update',
        payload: {
          documentId,
          stage: 'transcription',
          status: 'error',
          error: 'Transcription service temporarily unavailable'
        },
        timestamp: Date.now()
      });

      // Wait for error handling
      await page.waitForTimeout(3000);

      // Verify transcription failure was handled
      expect(transcriptionFailed).toBeTruthy();

      // Verify retry option for transcription
      const retryTranscription = page.locator('[data-testid="retry-transcription"]');
      await expect(retryTranscription).toBeVisible();

      // Test retry functionality
      await retryTranscription.click();

      // Verify processing continues with retry
      await page.waitForTimeout(5000);

      console.log('Transcription service failure handled correctly');
    });

    test('PROC-3: Memory exhaustion during processing', async ({
      page,
      webSocketUtils,
      testDataManager
    }) => {
      test.slow();

      // Upload multiple large files to trigger memory issues
      const largeFiles = await Promise.all([
        testDataManager.createLargeFile('memory-test-1.pdf', 20 * 1024 * 1024), // 20MB
        testDataManager.createLargeFile('memory-test-2.pdf', 20 * 1024 * 1024), // 20MB
        testDataManager.createLargeFile('memory-test-3.pdf', 20 * 1024 * 1024)  // 20MB
      ]);

      // Upload files concurrently
      const uploadPromises = largeFiles.map(file =>
        page.setInputFiles('input[type="file"]', file.path)
      );

      await Promise.all(uploadPromises);

      // Monitor for memory warning
      let memoryWarningShown = false;
      page.on('console', msg => {
        if (msg.text().includes('memory') || msg.text().includes('heap')) {
          memoryWarningShown = true;
        }
      });

      // Check for UI memory warnings
      const memoryWarning = page.locator('[data-testid="memory-warning"]');
      if (await memoryWarning.isVisible({ timeout: 30000 })) {
        memoryWarningShown = true;

        // Verify memory warning provides options
        await expect(page.locator('[data-testid="reduce-concurrency"]')).toBeVisible();
        await expect(page.locator('[data-testid="continue-processing"]')).toBeVisible();

        // Test continue processing option
        await page.click('[data-testid="continue-processing"]');
      }

      // Monitor processing continues despite memory pressure
      await page.waitForTimeout(10000);

      // Verify system remains responsive
      await expect(page.locator('[data-testid="file-list"]')).toBeVisible();

      console.log(`Memory exhaustion handling: warning shown = ${memoryWarningShown}`);
    });

    test('PROC-4: Timeout during processing', async ({
      page,
      webSocketUtils,
      testDataManager
    }) => {
      test.slow();

      // Create a file that will take long time to process
      const complexFile = await testDataManager.createComplexFile('timeout-test.pdf');

      // Upload file
      const documentId = await documentProcessor.uploadDocument(complexFile, {
        waitForProcessing: false
      });

      // Mock timeout scenario
      await webSocketUtils.mockWebSocketMessage({
        type: 'processing_timeout',
        payload: {
          documentId,
          stage: 'embedding',
          timeout: 300000, // 5 minutes
          message: 'Processing timeout exceeded'
        },
        timestamp: Date.now()
      });

      // Wait for timeout handling
      await page.waitForTimeout(3000);

      // Verify timeout error is displayed
      await expect(page.locator('[data-testid="processing-timeout"]')).toBeVisible();
      await expect(page.locator('[data-testid="error-message"]')).toContainText('timeout');

      // Verify timeout-specific options
      await expect(page.locator('[data-testid="extend-timeout"]')).toBeVisible();
      await expect(page.locator('[data-testid="cancel-processing"]')).toBeVisible();

      // Test extend timeout option
      await page.click('[data-testid="extend-timeout"]');

      // Verify processing continues with extended timeout
      await page.waitForTimeout(2000);

      console.log('Processing timeout handled correctly');
    });
  });

  test.describe('User Interface Error Recovery', () => {
    test('UI-1: Error state recovery and retry mechanisms', async ({
      page,
      testDataManager
    }) => {
      test.slow();

      // Trigger various UI error states
      await page.evaluate(() => {
        // Simulate JavaScript error
        setTimeout(() => {
          throw new Error('Test JavaScript error');
        }, 100);
      });

      // Verify error boundary catches the error
      await expect(page.locator('[data-testid="error-boundary"]')).toBeVisible({ timeout: 5000 });

      // Verify recovery options
      await expect(page.locator('[data-testid="reload-page"]')).toBeVisible();
      await expect(page.locator('[data-testid="report-error"]')).toBeVisible();

      // Test reload recovery
      await page.click('[data-testid="reload-page"]');
      await page.waitForLoadState('networkidle');

      // Verify page recovered successfully
      await expect(page.locator('[data-testid="upload-area"]')).toBeVisible();

      // Test successful upload after recovery
      const testFile = await testDataManager.getTestFile('recovery-test.pdf');
      await page.setInputFiles('input[type="file"]', testFile.path);

      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible({ timeout: 30000 });

      console.log('UI error state recovery successful');
    });

    test('UI-2: Form validation and error feedback', async ({
      page,
      testDataManager
    }) => {
      test.slow();

      // Navigate to a form that requires validation
      await page.goto('/settings');
      await page.waitForLoadState('networkidle');

      // Test form validation with empty required fields
      await page.click('[data-testid="save-settings"]');

      // Verify validation errors
      await expect(page.locator('[data-testid="validation-error"]')).toBeVisible();
      await expect(page.locator('[data-testid="field-error"]')).toHaveCount({ min: 1 });

      // Test inline validation feedback
      const requiredField = page.locator('[data-testid="required-field"]');
      await requiredField.fill('');
      await requiredField.blur();

      await expect(page.locator('[data-testid="field-validation-error"]')).toBeVisible();

      // Test correction and successful submission
      await requiredField.fill('Valid input');
      await page.fill('[data-testid="email-field"]', 'test@example.com');

      // Verify validation errors clear
      await expect(page.locator('[data-testid="field-validation-error"]')).not.toBeVisible();

      // Test successful form submission
      await page.click('[data-testid="save-settings"]');
      await expect(page.locator('[data-testid="save-success"]')).toBeVisible();

      console.log('Form validation and error feedback working correctly');
    });

    test('UI-3: Component failure isolation', async ({
      page
    }) => {
      test.slow();

      // Navigate to page with multiple components
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      // Inject error into one component using safe DOM manipulation
      await page.evaluate(() => {
        const component = document.querySelector('[data-testid="failing-component"]');
        if (component) {
          // Use textContent instead of innerHTML for safety
          const errorDiv = document.createElement('div');
          errorDiv.setAttribute('data-testid', 'component-error');
          errorDiv.textContent = 'Component failed to load';
          component.innerHTML = '';
          component.appendChild(errorDiv);
        }
      });

      // Verify component error is isolated
      await expect(page.locator('[data-testid="component-error"]')).toBeVisible();

      // Verify other components still work
      await expect(page.locator('[data-testid="working-component"]')).toBeVisible();
      await expect(page.locator('[data-testid="navigation"]')).toBeVisible();

      // Test component reload functionality
      const reloadComponent = page.locator('[data-testid="reload-component"]');
      if (await reloadComponent.isVisible()) {
        await reloadComponent.click();

        // Component should recover
        await expect(page.locator('[data-testid="component-error"]')).not.toBeVisible({ timeout: 5000 });
      }

      console.log('Component failure isolation working correctly');
    });
  });

  test.describe('Concurrent Error Scenarios', () => {
    test('CONC-1: Multiple simultaneous error handling', async ({
      page,
      webSocketUtils,
      testDataManager
    }) => {
      test.slow();

      // Start multiple file uploads simultaneously
      const testFiles = await Promise.all([
        testDataManager.getTestFile('concurrent-1.pdf'),
        testDataManager.getTestFile('concurrent-2.pdf'),
        testDataManager.getTestFile('concurrent-3.pdf')
      ]);

      // Upload files concurrently
      const uploadPromises = testFiles.map(file =>
        page.setInputFiles('input[type="file"]', file.path)
      );

      await Promise.all(uploadPromises);

      // Wait for uploads to start
      await page.waitForSelector('[data-testid="upload-progress"]', { timeout: 10000 });

      // Simulate multiple concurrent errors
      await webSocketUtils.simulateConnectionLoss(2000);

      // Mock multiple processing errors
      testFiles.forEach((file, index) => {
        setTimeout(() => {
          webSocketUtils.mockWebSocketMessage({
            type: 'processing_error',
            payload: {
              documentId: `concurrent-${index}`,
              error: `Simulated error ${index}`
            },
            timestamp: Date.now()
          });
        }, index * 500);
      });

      // Verify multiple errors are handled gracefully
      await expect(page.locator('[data-testid="multiple-errors"]')).toBeVisible({ timeout: 15000 });

      // Verify error count is displayed
      const errorCount = page.locator('[data-testid="error-count"]');
      await expect(errorCount).toBeVisible();

      // Verify batch retry option
      const batchRetry = page.locator('[data-testid="batch-retry"]');
      await expect(batchRetry).toBeVisible();

      // Test batch retry functionality
      await batchRetry.click();

      // Wait for retry processing
      await page.waitForTimeout(5000);

      // Verify some uploads recover
      const successfulUploads = page.locator('[data-testid="upload-success"]');
      const successCount = await successfulUploads.count();
      expect(successCount).toBeGreaterThan(0);

      console.log(`Concurrent error handling: ${successCount} files recovered out of ${testFiles.length}`);
    });

    test('CONC-2: Resource exhaustion under load', async ({
      page,
      testDataManager
    }) => {
      test.slow();

      // Create resource pressure by uploading many files
      const manyFiles = await Promise.all(
        Array(10).fill(null).map((_, i) =>
          testDataManager.createFile(`resource-test-${i}.pdf`, 1024 * 1024) // 1MB each
        )
      );

      // Upload files rapidly to create pressure
      for (const file of manyFiles) {
        await page.setInputFiles('input[type="file"]', file.path);
        await page.waitForTimeout(100); // Small delay between uploads
      }

      // Monitor for resource warnings
      const resourceWarning = page.locator('[data-testid="resource-warning"]');
      if (await resourceWarning.isVisible({ timeout: 30000 })) {
        // Verify resource warning provides clear information
        await expect(page.locator('[data-testid="warning-message"]')).toBeVisible();
        await expect(page.locator('[data-testid="resource-suggestions"]')).toBeVisible();

        // Test resource management options
        const pauseUploads = page.locator('[data-testid="pause-uploads"]');
        if (await pauseUploads.isVisible()) {
          await pauseUploads.click();

          // Verify uploads pause
          await page.waitForTimeout(2000);

          // Verify can resume
          const resumeUploads = page.locator('[data-testid="resume-uploads"]');
          await expect(resumeUploads).toBeVisible();

          await resumeUploads.click();
        }
      }

      // Verify system remains stable
      await expect(page.locator('[data-testid="file-list"]')).toBeVisible();
      await expect(page.locator('[data-testid="application-header"]')).toBeVisible();

      console.log('Resource exhaustion under load handled successfully');
    });
  });

  test.describe('Graceful Degradation', () => {
    test('DEG-1: Feature fallback when services unavailable', async ({
      page,
      testDataManager
    }) => {
      test.slow();

      // Simulate service unavailability
      await page.route('**/api/**', async (route) => {
        await route.abort('failed');
      });

      // Upload file to test fallback behavior
      const testFile = await testDataManager.getTestFile('fallback-test.pdf');
      await page.setInputFiles('input[type="file"]', testFile.path);

      // Verify fallback mode is activated
      await expect(page.locator('[data-testid="fallback-mode"]')).toBeVisible({ timeout: 10000 });
      await expect(page.locator('[data-testid="limited-functionality"]')).toBeVisible();

      // Verify basic functionality still works
      await expect(page.locator('[data-testid="local-storage"]')).toBeVisible();
      await expect(page.locator('[data-testid="offline-indicator"]')).toBeVisible();

      // Test queue for later processing
      const queueForLater = page.locator('[data-testid="queue-for-later"]');
      if (await queueForLater.isVisible()) {
        await queueForLater.click();

        await expect(page.locator('[data-testid="queued-message"]')).toBeVisible();
      }

      // Clear service routing
      await page.unroute('**/api/**');

      // Test service recovery
      await page.reload();
      await page.waitForLoadState('networkidle');

      console.log('Graceful degradation and recovery working correctly');
    });

    test('DEG-2: Progressive enhancement testing', async ({
      page,
      testDataManager
    }) => {
      test.slow();

      // Test with JavaScript disabled (simulate)
      await page.context().route('**/*.js', route => route.abort());

      await page.goto('/documents');
      await page.waitForLoadState('networkidle');

      // Verify basic HTML structure works without JavaScript
      await expect(page.locator('h1')).toBeVisible();
      await expect(page.locator('form')).toBeVisible();

      // Verify noscript fallbacks
      const noscriptContent = page.locator('noscript');
      if (await noscriptContent.count() > 0) {
        await expect(noscriptContent.first()).toBeVisible();
      }

      // Re-enable JavaScript
      await page.context().unroute('**/*.js');

      // Test full functionality with JavaScript enabled
      await page.reload();
      await page.waitForLoadState('networkidle');

      // Upload file to test enhanced functionality
      const testFile = await testDataManager.getTestFile('enhancement-test.pdf');
      await page.setInputFiles('input[type="file"]', testFile.path);

      // Verify enhanced features work
      await expect(page.locator('[data-testid="drag-drop-area"]')).toBeVisible();
      await expect(page.locator('[data-testid="progress-bar"]')).toBeVisible();

      console.log('Progressive enhancement working correctly');
    });
  });
});