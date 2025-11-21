import { test, expect } from '../fixtures/enhanced-test-data.fixture';
import { DocumentProcessor } from '../utils/document-processor';

/**
 * Comprehensive Real-Time Document Processing E2E Tests
 *
 * Test Coverage:
 * - Real-time WebSocket status updates during document processing
 * - Multi-stage processing visualization (OCR, transcription, embedding)
 * - WebSocket connection management and reconnection
 * - Error handling and recovery in real-time scenarios
 * - Concurrent document processing with real-time updates
 * - Performance metrics for real-time updates
 */

test.describe('Real-Time Document Processing', () => {
  let documentProcessor: DocumentProcessor;

  test.beforeEach(async ({ page, webSocketUtils }) => {
    // Initialize document processor
    documentProcessor = new DocumentProcessor(page, webSocketUtils);

    // Navigate to documents page
    await page.goto('/documents');
    await page.waitForLoadState('networkidle');

    // Verify WebSocket connection is established
    await expect(page).toHaveWebSocketConnection('connected');
  });

  test.afterEach(async () => {
    await documentProcessor.cleanup();
  });

  test('RT-1: Real-time status updates during PDF processing', async ({
    page,
    webSocketUtils,
    performanceMonitor,
    testDataManager
  }) => {
    test.slow();

    // Get a test PDF file
    const testPdfFile = await testDataManager.getTestFile('sample-document.pdf');

    // Start performance monitoring
    const performanceId = await performanceMonitor.startMeasurement('pdf-processing-realtime');

    // Upload document and start monitoring
    const documentId = await documentProcessor.uploadDocument(testPdfFile, {
      waitForProcessing: false
    });

    // Track real-time updates
    const statusUpdates: string[] = [];
    const stageUpdates: string[] = [];
    const progressValues: number[] = [];

    // Register callbacks for real-time updates
    documentProcessor.registerProcessingCallback(documentId, (state) => {
      statusUpdates.push(state.status);
      progressValues.push(state.progress);

      state.stages.forEach(stage => {
        if (stage.status === 'running' || stage.status === 'completed') {
          stageUpdates.push(`${stage.name}:${stage.status}`);
        }
      });
    });

    // Wait for processing completion with real-time monitoring
    const finalState = await documentProcessor.waitForProcessingCompletion(documentId, 120000);

    // Stop performance monitoring
    const performanceMetrics = await performanceMonitor.stopMeasurement(performanceId);

    // Verify real-time status progression
    expect(statusUpdates).toContain('uploading');
    expect(statusUpdates).toContain('queued');
    expect(statusUpdates).toContain('processing');
    expect(statusUpdates).toContain('completed');

    // Verify processing stages were executed
    const expectedStages = ['ocr', 'text_extraction', 'embedding'];
    for (const stage of expectedStages) {
      const stageCompleted = stageUpdates.some(update =>
        update.includes(`${stage}:completed`)
      );
      expect(stageCompleted).toBeTruthy();
    }

    // Verify progress tracking
    expect(progressValues.length).toBeGreaterThan(0);
    expect(Math.max(...progressValues)).toBe(100);

    // Verify WebSocket messages were received
    await expect(page).toReceiveRealTimeUpdates(documentId, [
      'document_status_update',
      'processing_stage_update'
    ]);

    // Verify performance metrics
    expect(performanceMetrics.duration).toBeLessThan(120000); // 2 minutes max
    expect(performanceMetrics.averageLatency).toBeLessThan(1000); // 1 second average latency

    // Take screenshot of final state
    await page.screenshot({
      path: `test-results/pdf-processing-completed-${documentId}.png`,
      fullPage: true
    });
  });

  test('RT-2: Real-time multi-modal file processing', async ({
    page,
    webSocketUtils,
    testDataManager
  }) => {
    test.slow();

    // Test different file types
    const testFiles = [
      await testDataManager.getTestFile('sample-document.pdf'),
      await testDataManager.getTestFile('sample-image.jpg'),
      await testDataManager.getTestFile('sample-audio.mp3'),
      await testDataManager.getTestFile('sample-video.mp4')
    ];

    const processingResults = [];

    for (const [index, testFile] of testFiles.entries()) {
      // Upload file and monitor real-time processing
      const documentId = await documentProcessor.uploadDocument(testFile, {
        waitForProcessing: false
      });

      // Track file-type specific processing stages
      const stageUpdates: string[] = [];

      documentProcessor.registerProcessingCallback(documentId, (state) => {
        state.stages.forEach(stage => {
          if (stage.status === 'completed') {
            stageUpdates.push(`${testFile.type}:${stage.name}`);
          }
        });
      });

      // Wait for processing completion
      const finalState = await documentProcessor.waitForProcessingCompletion(documentId, 180000);

      // Verify file-type specific processing stages
      if (testFile.type.includes('pdf') || testFile.type.includes('image')) {
        expect(stageUpdates.some(update => update.includes(':ocr'))).toBeTruthy();
      }

      if (testFile.type.includes('audio') || testFile.type.includes('video')) {
        expect(stageUpdates.some(update => update.includes(':transcription'))).toBeTruthy();
      }

      if (testFile.type.includes('video')) {
        expect(stageUpdates.some(update => update.includes(':frame_extraction'))).toBeTruthy();
      }

      // All files should have embedding stage
      expect(stageUpdates.some(update => update.includes(':embedding'))).toBeTruthy();

      processingResults.push({
        documentId,
        fileType: testFile.type,
        stages: stageUpdates,
        duration: finalState.stages.reduce((total, stage) => {
          if (stage.startTime && stage.endTime) {
            return total + (stage.endTime - stage.startTime);
          }
          return total;
        }, 0)
      });

      // Take screenshot for each file type
      await page.screenshot({
        path: `test-results/${testFile.type}-processing-complete-${documentId}.png`,
        fullPage: true
      });
    }

    // Verify all files processed successfully
    expect(processingResults).toHaveLength(testFiles.length);
    processingResults.forEach(result => {
      expect(result.stages.length).toBeGreaterThan(0);
    });

    // Log processing summary
    console.log('Multi-modal Processing Summary:');
    processingResults.forEach(result => {
      console.log(`  ${result.fileType}: ${result.stages.length} stages, ${result.duration}ms`);
    });
  });

  test('RT-3: WebSocket connection resilience during processing', async ({
    page,
    webSocketUtils,
    testDataManager
  }) => {
    test.slow();

    // Get a test file that will take time to process
    const testFile = await testDataManager.getTestFile('large-document.pdf');

    // Start document upload
    const documentId = await documentProcessor.uploadDocument(testFile, {
      waitForProcessing: false
    });

    // Wait for processing to start
    await documentProcessor.waitForStatusChange(documentId, 'queued', 'processing', 10000);

    // Simulate connection loss during processing
    console.log('Simulating WebSocket connection loss...');
    await webSocketUtils.simulateConnectionLoss(5000);

    // Verify connection is restored
    await expect(page).toHaveWebSocketConnection('connected');

    // Continue monitoring processing - should resume automatically
    const finalState = await documentProcessor.waitForProcessingCompletion(documentId, 180000);

    // Verify processing completed successfully despite connection loss
    expect(finalState.status).toBe('completed');

    // Verify WebSocket reconnection metrics
    const wsMetrics = await webSocketUtils.getPerformanceMetrics();
    expect(wsMetrics.messagesReceived).toBeGreaterThan(0);
    expect(wsMetrics.reconnectAttempts).toBeGreaterThanOrEqual(1);

    console.log('Connection resilience test passed - processing completed after reconnection');
  });

  test('RT-4: Concurrent document processing with real-time updates', async ({
    page,
    webSocketUtils,
    performanceMonitor,
    testDataManager
  }) => {
    test.slow();

    // Prepare multiple test files
    const testFiles = await Promise.all([
      testDataManager.getTestFile('document-1.pdf'),
      testDataManager.getTestFile('document-2.pdf'),
      testDataManager.getTestFile('document-3.pdf'),
      testDataManager.getTestFile('image-1.jpg'),
      testDataManager.getTestFile('image-2.png')
    ]);

    // Start performance monitoring for concurrent processing
    const performanceId = await performanceMonitor.startMeasurement('concurrent-processing');

    // Upload all files concurrently
    const documentIds = await Promise.all(
      testFiles.map(file =>
        documentProcessor.uploadDocument(file, { waitForProcessing: false })
      )
    );

    // Monitor real-time updates for all documents
    const allStatusUpdates = new Map<string, string[]>();

    documentIds.forEach(id => {
      allStatusUpdates.set(id, []);

      documentProcessor.registerProcessingCallback(id, (state) => {
        const updates = allStatusUpdates.get(id)!;
        updates.push(state.status);
      });
    });

    // Wait for all documents to complete processing
    const processingResults = await Promise.all(
      documentIds.map(id =>
        documentProcessor.waitForProcessingCompletion(id, 240000) // 4 minutes for concurrent
      )
    );

    // Stop performance monitoring
    const performanceMetrics = await performanceMonitor.stopMeasurement(performanceId);

    // Verify all documents processed successfully
    expect(processingResults).toHaveLength(testFiles.length);
    processingResults.forEach(result => {
      expect(result.status).toBe('completed');
      expect(result.progress).toBe(100);
    });

    // Verify real-time updates were received for all documents
    for (const documentId of documentIds) {
      const updates = allStatusUpdates.get(documentId)!;
      expect(updates.length).toBeGreaterThan(0);
      expect(updates).toContain('uploading');
      expect(updates).toContain('completed');
    }

    // Verify WebSocket performance under load
    const wsMetrics = await webSocketUtils.getPerformanceMetrics();
    expect(wsMetrics.messagesReceived).toBeGreaterThan(testFiles.length * 5); // At least 5 messages per document
    expect(wsMetrics.averageLatency).toBeLessThan(2000); // 2 seconds max average latency

    // Verify overall performance metrics
    expect(performanceMetrics.duration).toBeLessThan(300000); // 5 minutes max for concurrent processing

    console.log(`Concurrent processing completed: ${testFiles.length} files in ${performanceMetrics.duration}ms`);
    console.log(`WebSocket performance: ${wsMetrics.averageLatency}ms average latency`);
  });

  test('RT-5: Real-time error handling and recovery', async ({
    page,
    webSocketUtils,
    testDataManager
  }) => {
    test.slow();

    // Test with a corrupted file
    const corruptedFile = await testDataManager.createCorruptedFile('corrupted-document.pdf');

    try {
      // Upload corrupted file
      const documentId = await documentProcessor.uploadDocument(corruptedFile, {
        waitForProcessing: false
      });

      // Wait for error to be detected
      await page.waitForTimeout(5000);

      // Verify error status is received via WebSocket
      const errorState = documentProcessor.getProcessingState(documentId);
      expect(errorState?.status).toBe('error');
      expect(errorState?.error).toBeTruthy();

      // Verify error message is displayed in UI
      const errorMessage = page.locator(`[data-document-id="${documentId}"] [data-testid="error-message"]`);
      await expect(errorMessage).toBeVisible();
      await expect(errorMessage).toContainText('corrupted');

      // Verify retry functionality works
      const retryButton = page.locator(`[data-document-id="${documentId}"] [data-testid="retry-processing"]`);
      if (await retryButton.isVisible()) {
        await retryButton.click();

        // Should attempt processing again
        await page.waitForTimeout(2000);
        const retryState = documentProcessor.getProcessingState(documentId);
        expect(['uploading', 'queued', 'processing']).toContain(retryState?.status || '');
      }

    } catch (error) {
      // Expected to fail due to corrupted file
      expect(error.message).toContain('failed') || expect(error.message).toContain('corrupted');
    }

    // Test recovery by uploading a valid file after error
    const validFile = await testDataManager.getTestFile('valid-document.pdf');
    const validDocumentId = await documentProcessor.uploadDocument(validFile, {
      waitForProcessing: true
    });

    // Verify valid file processes successfully
    const validState = documentProcessor.getProcessingState(validDocumentId);
    expect(validState?.status).toBe('completed');
  });

  test('RT-6: Real-time progress accuracy and visualization', async ({
    page,
    webSocketUtils,
    testDataManager
  }) => {
    test.slow();

    // Get a test file for progress tracking
    const testFile = await testDataManager.getTestFile('multi-stage-document.pdf');

    // Upload file and track detailed progress
    const documentId = await documentProcessor.uploadDocument(testFile, {
      waitForProcessing: false
    });

    const progressHistory: Array<{ time: number; progress: number; stage?: string }> = [];
    const stageProgress = new Map<string, number[]>();

    // Register detailed progress tracking
    documentProcessor.registerProcessingCallback(documentId, (state) => {
      progressHistory.push({
        time: Date.now(),
        progress: state.progress,
        stage: state.stages.find(s => s.status === 'running')?.name
      });

      state.stages.forEach(stage => {
        if (!stageProgress.has(stage.name)) {
          stageProgress.set(stage.name, []);
        }
        stageProgress.get(stage.name)!.push(stage.progress);
      });
    });

    // Wait for processing completion
    const finalState = await documentProcessor.waitForProcessingCompletion(documentId, 120000);

    // Verify progress tracking accuracy
    expect(progressHistory.length).toBeGreaterThan(0);

    // Progress should be monotonically increasing (or staying the same)
    for (let i = 1; i < progressHistory.length; i++) {
      expect(progressHistory[i].progress).toBeGreaterThanOrEqual(progressHistory[i - 1].progress);
    }

    // Final progress should be 100%
    expect(finalState.progress).toBe(100);
    expect(progressHistory[progressHistory.length - 1].progress).toBe(100);

    // Verify stage-level progress tracking
    expect(stageProgress.size).toBeGreaterThan(0);

    // Each stage should reach 100% completion
    for (const [stageName, stageProgressValues] of stageProgress) {
      const maxProgress = Math.max(...stageProgressValues);
      if (stageName !== 'error') { // Don't expect error stages to complete
        expect(maxProgress).toBe(100);
      }
    }

    // Verify UI progress indicators
    const progressBar = page.locator(`[data-document-id="${documentId}"] [data-testid="processing-progress"]`);
    await expect(progressBar).toBeVisible();

    const progressText = page.locator(`[data-document-id="${documentId}"] [data-testid="progress-text"]`);
    await expect(progressText).toBeVisible();

    // Final progress text should show 100%
    await expect(progressText).toContainText('100%');

    // Take screenshot showing progress visualization
    await page.screenshot({
      path: `test-results/progress-visualization-${documentId}.png`,
      fullPage: true
    });
  });

  test('RT-7: WebSocket message ordering and reliability', async ({
    page,
    webSocketUtils,
    testDataManager
  }) => {
    test.slow();

    // Clear any existing message log
    webSocketUtils.clearMessageLog();

    // Get test file
    const testFile = await testDataManager.getTestFile('ordering-test-document.pdf');

    // Upload and monitor message ordering
    const documentId = await documentProcessor.uploadDocument(testFile, {
      waitForProcessing: true
    });

    // Get all WebSocket messages for this document
    const messageLog = webSocketUtils.getMessageLog();
    const documentMessages = messageLog.filter(msg => msg.documentId === documentId);

    // Verify messages are in chronological order
    for (let i = 1; i < documentMessages.length; i++) {
      expect(documentMessages[i].timestamp).toBeGreaterThanOrEqual(documentMessages[i - 1].timestamp);
    }

    // Verify expected message types are present
    const messageTypes = documentMessages.map(msg => msg.type);
    expect(messageTypes).toContain('document_status_update');
    expect(messageTypes).toContain('processing_stage_update');

    // Verify status progression in messages
    const statusUpdates = documentMessages
      .filter(msg => msg.type === 'document_status_update')
      .map(msg => msg.payload?.status);

    expect(statusUpdates).toContain('uploading');
    expect(statusUpdates).toContain('processing');
    expect(statusUpdates).toContain('completed');

    // Verify no duplicate timestamps (within reasonable tolerance)
    const timestamps = documentMessages.map(msg => msg.timestamp);
    const uniqueTimestamps = [...new Set(timestamps)];
    expect(uniqueTimestamps.length).toBeGreaterThan(timestamps.length * 0.8); // At least 80% unique

    console.log(`Message reliability test passed: ${documentMessages.length} messages received in correct order`);
  });

  test('RT-8: Performance under high-frequency updates', async ({
    page,
    webSocketUtils,
    performanceMonitor,
    testDataManager
  }) => {
    test.slow();

    // Create a scenario with many rapid status updates
    const rapidUpdateFiles = await Promise.all([
      testDataManager.getTestFile('rapid-1.pdf'),
      testDataManager.getTestFile('rapid-2.pdf'),
      testDataManager.getTestFile('rapid-3.pdf')
    ]);

    // Start performance monitoring
    const performanceId = await performanceMonitor.startMeasurement('high-frequency-updates');

    // Upload files rapidly
    const documentIds = await Promise.all(
      rapidUpdateFiles.map(file =>
        documentProcessor.uploadDocument(file, { waitForProcessing: false })
      )
    );

    // Monitor message frequency and performance
    const messageFrequency = [];
    const startMonitoring = Date.now();

    const checkFrequency = setInterval(() => {
      const messages = webSocketUtils.getMessageLog();
      const recentMessages = messages.filter(msg =>
        msg.timestamp > startMonitoring &&
        documentIds.includes(msg.documentId!)
      );

      messageFrequency.push({
        timestamp: Date.now(),
        messageCount: recentMessages.length
      });
    }, 1000);

    // Wait for all processing to complete
    await Promise.all(
      documentIds.map(id =>
        documentProcessor.waitForProcessingCompletion(id, 120000)
      )
    );

    clearInterval(checkFrequency);

    // Stop performance monitoring
    const performanceMetrics = await performanceMonitor.stopMeasurement(performanceId);

    // Verify performance under high-frequency updates
    const wsMetrics = await webSocketUtils.getPerformanceMetrics();
    expect(wsMetrics.averageLatency).toBeLessThan(1500); // Should handle high frequency
    expect(performanceMetrics.duration).toBeLessThan(180000); // 3 minutes max

    // Verify message frequency was reasonable
    const maxMessagesPerSecond = Math.max(...messageFrequency.map(f => f.messageCount));
    expect(maxMessagesPerSecond).toBeLessThan(100); // Should not exceed 100 messages/second

    console.log(`High-frequency update test passed:`);
    console.log(`  Total messages: ${wsMetrics.messagesReceived}`);
    console.log(`  Average latency: ${wsMetrics.averageLatency}ms`);
    console.log(`  Peak frequency: ${maxMessagesPerSecond} messages/second`);
  });
});