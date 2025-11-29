import { test, expect } from '../fixtures/enhanced-test-data.fixture';
import { DocumentProcessor } from '../utils/document-processor';

/**
 * Comprehensive Multi-Modal File Processing E2E Tests
 *
 * Test Coverage:
 * - PDF processing with OCR and text extraction
 * - Image processing with object detection and captioning
 * - Audio processing with transcription and speaker identification
 * - Video processing with frame extraction and audio analysis
 * - Cross-modal content correlation and metadata extraction
 * - Performance validation for different media types
 */

test.describe('Multi-Modal File Processing', () => {
  let documentProcessor: DocumentProcessor;

  test.beforeEach(async ({ page, webSocketUtils }) => {
    documentProcessor = new DocumentProcessor(page, webSocketUtils);
    await page.goto('/documents');
    await page.waitForLoadState('networkidle');
  });

  test.afterEach(async () => {
    await documentProcessor.cleanup();
  });

  test('MM-1: PDF document processing with OCR and metadata extraction', async ({
    page,
    webSocketUtils,
    performanceMonitor,
    testDataManager
  }) => {
    test.slow();

    // Get test PDF file with different content types
    const testPdf = await testDataManager.getTestFile('complex-document.pdf');

    // Start performance monitoring
    const performanceId = await performanceMonitor.startMeasurement('pdf-ocr-processing');

    // Upload PDF and monitor processing stages
    const documentId = await documentProcessor.uploadDocument(testPdf, {
      waitForProcessing: false
    });

    // Track PDF-specific processing stages
    const pdfStages: string[] = [];
    const extractedText: string[] = [];
    const detectedEntities: any[] = [];

    documentProcessor.registerProcessingCallback(documentId, (state) => {
      state.stages.forEach(stage => {
        if (stage.status === 'completed') {
          pdfStages.push(stage.name);
          extractedText.push(stage.metadata?.extractedText || '');
          if (stage.metadata?.entities) {
            detectedEntities.push(...stage.metadata.entities);
          }
        }
      });
    });

    // Wait for specific PDF processing stages
    await documentProcessor.waitForProcessingStage(documentId, 'ocr', 60000);
    await documentProcessor.waitForProcessingStage(documentId, 'text_extraction', 60000);
    await documentProcessor.waitForProcessingStage(documentId, 'entity_extraction', 60000);

    // Wait for complete processing
    const finalState = await documentProcessor.waitForProcessingCompletion(documentId, 120000);

    // Stop performance monitoring
    const performanceMetrics = await performanceMonitor.stopMeasurement(performanceId);

    // Verify PDF-specific stages completed
    expect(pdfStages).toContain('ocr');
    expect(pdfStages).toContain('text_extraction');
    expect(pdfStages).toContain('embedding');

    // Verify text extraction
    const totalExtractedText = extractedText.join(' ');
    expect(totalExtractedText.length).toBeGreaterThan(100);

    // Verify entity detection
    expect(detectedEntities.length).toBeGreaterThan(0);
    const entityTypes = new Set(detectedEntities.map(e => e.type));
    expect(entityTypes.size).toBeGreaterThan(1); // Multiple entity types detected

    // Verify performance metrics
    expect(performanceMetrics.duration).toBeLessThan(120000); // 2 minutes max
    expect(finalState.metadata?.pageCount).toBeGreaterThan(0);

    // Verify document metadata is available in UI
    await page.click(`[data-document-id="${documentId}"] [data-testid="view-metadata"]`);
    await expect(page.locator('[data-testid="metadata-panel"]')).toBeVisible();
    await expect(page.locator('[data-testid="extracted-text"]')).toBeVisible();
    await expect(page.locator('[data-testid="detected-entities"]')).toBeVisible();

    // Take screenshot of PDF processing results
    await page.screenshot({
      path: `test-results/pdf-ocr-processing-${documentId}.png`,
      fullPage: true
    });

    console.log(`PDF processing completed in ${performanceMetrics.duration}ms`);
    console.log(`Extracted ${totalExtractedText.length} characters and ${detectedEntities.length} entities`);
  });

  test('MM-2: Image processing with object detection and captioning', async ({
    page,
    webSocketUtils,
    performanceMonitor,
    testDataManager
  }) => {
    test.slow();

    // Get test image files with different content
    const testImages = await Promise.all([
      testDataManager.getTestFile('test-image-1.jpg'),
      testDataManager.getTestFile('test-image-2.png'),
      testDataManager.getTestFile('diagram-image.png')
    ]);

    const imageProcessingResults = [];

    for (const [index, testImage] of testImages.entries()) {
      // Start performance monitoring for this image
      const performanceId = await performanceMonitor.startMeasurement(`image-processing-${index}`);

      // Upload image and monitor processing
      const documentId = await documentProcessor.uploadDocument(testImage, {
        waitForProcessing: false
      });

      // Track image-specific processing stages
      const imageStages: string[] = [];
      let detectedObjects: any[] = [];
      let generatedCaption = '';
      let extractedText = '';

      documentProcessor.registerProcessingCallback(documentId, (state) => {
        state.stages.forEach(stage => {
          if (stage.status === 'completed') {
            imageStages.push(stage.name);

            if (stage.metadata?.objects) {
              detectedObjects = stage.metadata.objects;
            }
            if (stage.metadata?.caption) {
              generatedCaption = stage.metadata.caption;
            }
            if (stage.metadata?.text) {
              extractedText = stage.metadata.text;
            }
          }
        });
      });

      // Wait for image-specific processing stages
      await documentProcessor.waitForProcessingStage(documentId, 'image_analysis', 60000);
      await documentProcessor.waitForProcessingStage(documentId, 'object_detection', 60000);

      // Wait for complete processing
      const finalState = await documentProcessor.waitForProcessingCompletion(documentId, 90000);

      // Stop performance monitoring
      const performanceMetrics = await performanceMonitor.stopMeasurement(performanceId);

      // Verify image-specific stages completed
      expect(imageStages).toContain('image_analysis');
      expect(imageStages).toContain('object_detection');
      expect(imageStages).toContain('embedding');

      // Verify object detection results
      expect(detectedObjects.length).toBeGreaterThan(0);
      const objectCategories = new Set(detectedObjects.map(obj => obj.category));
      expect(objectCategories.size).toBeGreaterThan(0);

      // Verify caption generation
      expect(generatedCaption.length).toBeGreaterThan(10);

      // Verify text extraction if applicable
      if (testImage.name.includes('diagram') || testImage.name.includes('text')) {
        expect(extractedText.length).toBeGreaterThan(0);
      }

      imageProcessingResults.push({
        documentId,
        fileName: testImage.name,
        stages: imageStages,
        objectsDetected: detectedObjects.length,
        caption: generatedCaption,
        textExtracted: extractedText.length,
        duration: performanceMetrics.duration
      });

      // Take screenshot for each image processing result
      await page.screenshot({
        path: `test-results/image-processing-${index}-${documentId}.png`,
        fullPage: true
      });
    }

    // Verify all images processed successfully
    expect(imageProcessingResults).toHaveLength(testImages.length);
    imageProcessingResults.forEach(result => {
      expect(result.objectsDetected).toBeGreaterThan(0);
      expect(result.caption.length).toBeGreaterThan(10);
      expect(result.duration).toBeLessThan(90000);
    });

    // Log image processing summary
    console.log('Image Processing Summary:');
    imageProcessingResults.forEach(result => {
      console.log(`  ${result.fileName}: ${result.objectsDetected} objects, ${result.caption.length} chars caption`);
    });
  });

  test('MM-3: Audio processing with transcription and speaker identification', async ({
    page,
    webSocketUtils,
    performanceMonitor,
    testDataManager
  }) => {
    test.slow();

    // Get test audio files
    const testAudioFiles = await Promise.all([
      testDataManager.getTestFile('speech-audio.mp3'),
      testDataManager.getTestFile('meeting-audio.wav')
    ]);

    const audioProcessingResults = [];

    for (const [index, testAudio] of testAudioFiles.entries()) {
      // Start performance monitoring
      const performanceId = await performanceMonitor.startMeasurement(`audio-processing-${index}`);

      // Upload audio and monitor processing
      const documentId = await documentProcessor.uploadDocument(testAudio, {
        waitForProcessing: false
      });

      // Track audio-specific processing stages
      const audioStages: string[] = [];
      let transcriptionText = '';
      let speakerSegments: any[] = [];
      let audioMetadata: any = {};

      documentProcessor.registerProcessingCallback(documentId, (state) => {
        state.stages.forEach(stage => {
          if (stage.status === 'completed') {
            audioStages.push(stage.name);

            if (stage.metadata?.transcription) {
              transcriptionText = stage.metadata.transcription;
            }
            if (stage.metadata?.speakerSegments) {
              speakerSegments = stage.metadata.speakerSegments;
            }
            if (stage.metadata?.audioInfo) {
              audioMetadata = stage.metadata.audioInfo;
            }
          }
        });
      });

      // Wait for audio-specific processing stages
      await documentProcessor.waitForProcessingStage(documentId, 'audio_analysis', 60000);
      await documentProcessor.waitForProcessingStage(documentId, 'transcription', 120000);
      await documentProcessor.waitForProcessingStage(documentId, 'speaker_diarization', 120000);

      // Wait for complete processing
      const finalState = await documentProcessor.waitForProcessingCompletion(documentId, 180000);

      // Stop performance monitoring
      const performanceMetrics = await performanceMonitor.stopMeasurement(performanceId);

      // Verify audio-specific stages completed
      expect(audioStages).toContain('audio_analysis');
      expect(audioStages).toContain('transcription');
      expect(audioStages).toContain('embedding');

      // Verify transcription quality
      expect(transcriptionText.length).toBeGreaterThan(50);
      expect(transcriptionText).toMatch(/[a-zA-Z]/); // Contains actual text

      // Verify speaker identification
      expect(speakerSegments.length).toBeGreaterThan(0);
      const uniqueSpeakers = new Set(speakerSegments.map(seg => seg.speaker));
      expect(uniqueSpeakers.size).toBeGreaterThanOrEqual(1);

      // Verify audio metadata
      expect(audioMetadata.duration).toBeGreaterThan(0);
      expect(audioMetadata.sampleRate).toBeGreaterThan(0);

      audioProcessingResults.push({
        documentId,
        fileName: testAudio.name,
        stages: audioStages,
        transcriptionLength: transcriptionText.length,
        speakerCount: uniqueSpeakers.size,
        audioDuration: audioMetadata.duration,
        duration: performanceMetrics.duration
      });

      // Take screenshot of audio processing results
      await page.screenshot({
        path: `test-results/audio-processing-${index}-${documentId}.png`,
        fullPage: true
      });
    }

    // Verify all audio files processed successfully
    expect(audioProcessingResults).toHaveLength(testAudioFiles.length);
    audioProcessingResults.forEach(result => {
      expect(result.transcriptionLength).toBeGreaterThan(50);
      expect(result.speakerCount).toBeGreaterThanOrEqual(1);
      expect(result.duration).toBeLessThan(180000);
    });

    // Log audio processing summary
    console.log('Audio Processing Summary:');
    audioProcessingResults.forEach(result => {
      console.log(`  ${result.fileName}: ${result.transcriptionLength} chars, ${result.speakerCount} speakers, ${result.audioDuration}s duration`);
    });
  });

  test('MM-4: Video processing with frame extraction and audio analysis', async ({
    page,
    webSocketUtils,
    performanceMonitor,
    testDataManager
  }) => {
    test.slow();

    // Get test video files
    const testVideoFiles = await Promise.all([
      testDataManager.getTestFile('presentation-video.mp4'),
      testDataManager.getTestFile('demo-video.mp4')
    ]);

    const videoProcessingResults = [];

    for (const [index, testVideo] of testVideoFiles.entries()) {
      // Start performance monitoring
      const performanceId = await performanceMonitor.startMeasurement(`video-processing-${index}`);

      // Upload video and monitor processing
      const documentId = await documentProcessor.uploadDocument(testVideo, {
        waitForProcessing: false
      });

      // Track video-specific processing stages
      const videoStages: string[] = [];
      let extractedFrames: any[] = [];
      let audioTranscription = '';
      let videoMetadata: any = {};
      let sceneSegments: any[] = [];

      documentProcessor.registerProcessingCallback(documentId, (state) => {
        state.stages.forEach(stage => {
          if (stage.status === 'completed') {
            videoStages.push(stage.name);

            if (stage.metadata?.frames) {
              extractedFrames = stage.metadata.frames;
            }
            if (stage.metadata?.audioTranscription) {
              audioTranscription = stage.metadata.audioTranscription;
            }
            if (stage.metadata?.videoInfo) {
              videoMetadata = stage.metadata.videoInfo;
            }
            if (stage.metadata?.scenes) {
              sceneSegments = stage.metadata.scenes;
            }
          }
        });
      });

      // Wait for video-specific processing stages
      await documentProcessor.waitForProcessingStage(documentId, 'video_analysis', 60000);
      await documentProcessor.waitForProcessingStage(documentId, 'frame_extraction', 120000);
      await documentProcessor.waitForProcessingStage(documentId, 'audio_extraction', 90000);
      await documentProcessor.waitForProcessingStage(documentId, 'transcription', 120000);

      // Wait for complete processing
      const finalState = await documentProcessor.waitForProcessingCompletion(documentId, 300000); // 5 minutes for video

      // Stop performance monitoring
      const performanceMetrics = await performanceMonitor.stopMeasurement(performanceId);

      // Verify video-specific stages completed
      expect(videoStages).toContain('video_analysis');
      expect(videoStages).toContain('frame_extraction');
      expect(videoStages).toContain('embedding');

      // Verify frame extraction
      expect(extractedFrames.length).toBeGreaterThan(0);
      expect(extractedFrames[0]).toHaveProperty('timestamp');
      expect(extractedFrames[0]).toHaveProperty('imageUrl');

      // Verify audio transcription
      expect(audioTranscription.length).toBeGreaterThan(10);

      // Verify video metadata
      expect(videoMetadata.duration).toBeGreaterThan(0);
      expect(videoMetadata.resolution).toBeTruthy();
      expect(videoMetadata.frameRate).toBeGreaterThan(0);

      // Verify scene segmentation if applicable
      if (videoMetadata.duration > 30) { // Only for longer videos
        expect(sceneSegments.length).toBeGreaterThan(0);
      }

      videoProcessingResults.push({
        documentId,
        fileName: testVideo.name,
        stages: videoStages,
        framesExtracted: extractedFrames.length,
        transcriptionLength: audioTranscription.length,
        videoDuration: videoMetadata.duration,
        sceneCount: sceneSegments.length,
        duration: performanceMetrics.duration
      });

      // Take screenshot of video processing results
      await page.screenshot({
        path: `test-results/video-processing-${index}-${documentId}.png`,
        fullPage: true
      });
    }

    // Verify all video files processed successfully
    expect(videoProcessingResults).toHaveLength(testVideoFiles.length);
    videoProcessingResults.forEach(result => {
      expect(result.framesExtracted).toBeGreaterThan(0);
      expect(result.transcriptionLength).toBeGreaterThan(10);
      expect(result.duration).toBeLessThan(300000);
    });

    // Log video processing summary
    console.log('Video Processing Summary:');
    videoProcessingResults.forEach(result => {
      console.log(`  ${result.fileName}: ${result.framesExtracted} frames, ${result.transcriptionLength} chars audio, ${result.videoDuration}s duration`);
    });
  });

  test('MM-5: Cross-modal content correlation and metadata extraction', async ({
    page,
    webSocketUtils,
    performanceMonitor,
    testDataManager
  }) => {
    test.slow();

    // Create a comprehensive multi-modal document set
    const relatedFiles = await Promise.all([
      testDataManager.getTestFile('research-paper.pdf'), // Main document
      testDataManager.getTestFile('research-chart.png'), // Related image
      testDataManager.getTestFile('research-audio.mp3'), // Related audio
      testDataManager.getTestFile('research-video.mp4')  // Related video
    ]);

    // Upload all files
    const documentIds = [];
    const uploadPromises = [];

    for (const file of relatedFiles) {
      uploadPromises.push(
        documentProcessor.uploadDocument(file, { waitForProcessing: false })
          .then(id => {
            documentIds.push(id);
            return id;
          })
      );
    }

    await Promise.all(uploadPromises);

    // Wait for all documents to complete processing
    const processingResults = await Promise.all(
      documentIds.map(id =>
        documentProcessor.waitForProcessingCompletion(id, 300000)
      )
    );

    // Verify cross-modal correlation
    for (let i = 0; i < documentIds.length; i++) {
      const documentId = documentIds[i];
      const finalState = processingResults[i];

      // Check for cross-modal metadata
      expect(finalState.metadata).toBeTruthy();
      expect(finalState.metadata?.crossModalReferences).toBeTruthy();

      // Verify that related content was detected
      if (finalState.metadata?.crossModalReferences) {
        const references = finalState.metadata.crossModalReferences;
        expect(references.length).toBeGreaterThan(0);

        // Verify references point to other documents in the set
        const relatedDocumentIds = documentIds.filter(id => id !== documentId);
        const hasRelatedReferences = references.some((ref: any) =>
          relatedDocumentIds.includes(ref.documentId)
        );
        expect(hasRelatedReferences).toBeTruthy();
      }
    }

    // Test cross-modal search functionality
    await page.fill('[data-testid="search-input"]', 'research methodology');
    await page.click('[data-testid="search-button"]');

    // Wait for search results
    await page.waitForSelector('[data-testid="search-results"]', { timeout: 30000 });

    // Verify search finds related content across different media types
    const searchResults = page.locator('[data-testid="search-result-item"]');
    const resultCount = await searchResults.count();

    expect(resultCount).toBeGreaterThan(0);

    // Verify results include different media types
    const mediaTypes = new Set();
    for (let i = 0; i < Math.min(resultCount, 10); i++) {
      const mediaType = await searchResults.nth(i).getAttribute('data-media-type');
      if (mediaType) {
        mediaTypes.add(mediaType);
      }
    }

    expect(mediaTypes.size).toBeGreaterThan(1); // Multiple media types in results

    // Take screenshot of cross-modal search results
    await page.screenshot({
      path: 'test-results/cross-modal-search-results.png',
      fullPage: true
    });

    console.log(`Cross-modal correlation test completed with ${resultCount} search results across ${mediaTypes.size} media types`);
  });

  test('MM-6: Performance optimization for different media types', async ({
    page,
    webSocketUtils,
    performanceMonitor,
    testDataManager
  }) => {
    test.slow();

    // Test files of different sizes and types for performance analysis
    const performanceTestFiles = await Promise.all([
      testDataManager.getTestFile('small-text.txt'),
      testDataManager.getTestFile('medium-document.pdf'),
      testDataManager.getTestFile('large-image.jpg'),
      testDataManager.getTestFile('long-audio.mp3')
    ]);

    const performanceResults = [];

    for (const [index, testFile] of performanceTestFiles.entries()) {
      // Start detailed performance monitoring
      const performanceId = await performanceMonitor.startMeasurement(`media-performance-${index}`);

      // Monitor memory usage before upload
      const initialMemory = await performanceMonitor.getMemoryUsage();

      // Upload and process file
      const startTime = Date.now();
      const documentId = await documentProcessor.uploadDocument(testFile, {
        waitForProcessing: true
      });
      const uploadDuration = Date.now() - startTime;

      // Monitor memory usage after processing
      const finalMemory = await performanceMonitor.getMemoryUsage();

      // Stop performance monitoring
      const performanceMetrics = await performanceMonitor.stopMeasurement(performanceId);

      // Calculate performance metrics
      const memoryIncrease = finalMemory && initialMemory
        ? finalMemory.usedJSHeapSize - initialMemory.usedJSHeapSize
        : 0;

      const processingSpeed = testFile.size / (performanceMetrics.duration / 1000); // bytes per second

      performanceResults.push({
        fileName: testFile.name,
        fileSize: testFile.size,
        fileType: testFile.type,
        uploadDuration,
        processingDuration: performanceMetrics.duration,
        memoryIncrease,
        processingSpeed,
        networkMetrics: performanceMetrics.networkMetrics
      });

      console.log(`Processed ${testFile.name}: ${processingSpeed.toFixed(0)} bytes/sec, ${memoryIncrease} bytes memory increase`);
    }

    // Analyze performance across different media types
    const pdfResults = performanceResults.filter(r => r.fileType.includes('pdf'));
    const imageResults = performanceResults.filter(r => r.fileType.includes('image'));
    const audioResults = performanceResults.filter(r => r.fileType.includes('audio'));

    // Verify performance expectations
    if (pdfResults.length > 0) {
      const avgPdfSpeed = pdfResults.reduce((sum, r) => sum + r.processingSpeed, 0) / pdfResults.length;
      expect(avgPdfSpeed).toBeGreaterThan(1000); // At least 1KB/s for PDFs
    }

    if (imageResults.length > 0) {
      const avgImageSpeed = imageResults.reduce((sum, r) => sum + r.processingSpeed, 0) / imageResults.length;
      expect(avgImageSpeed).toBeGreaterThan(5000); // At least 5KB/s for images
    }

    if (audioResults.length > 0) {
      const avgAudioSpeed = audioResults.reduce((sum, r) => sum + r.processingSpeed, 0) / audioResults.length;
      expect(avgAudioSpeed).toBeGreaterThan(500); // At least 500B/s for audio
    }

    // Verify memory usage is reasonable
    performanceResults.forEach(result => {
      expect(result.memoryIncrease).toBeLessThan(result.fileSize * 2); // Memory increase should be less than 2x file size
    });

    // Log performance analysis
    console.log('Multi-Modal Performance Analysis:');
    console.log(`  Average PDF processing speed: ${pdfResults.length > 0 ? (pdfResults.reduce((sum, r) => sum + r.processingSpeed, 0) / pdfResults.length).toFixed(0) : 0} bytes/sec`);
    console.log(`  Average Image processing speed: ${imageResults.length > 0 ? (imageResults.reduce((sum, r) => sum + r.processingSpeed, 0) / imageResults.length).toFixed(0) : 0} bytes/sec`);
    console.log(`  Average Audio processing speed: ${audioResults.length > 0 ? (audioResults.reduce((sum, r) => sum + r.processingSpeed, 0) / audioResults.length).toFixed(0) : 0} bytes/sec`);
  });

  test('MM-7: Error handling and recovery for unsupported media types', async ({
    page,
    webSocketUtils,
    testDataManager
  }) => {
    test.slow();

    // Test with unsupported file types
    const unsupportedFiles = [
      { name: 'test.exe', type: 'application/x-executable' },
      { name: 'test.zip', type: 'application/zip' },
      { name: 'test.dll', type: 'application/x-msdownload' }
    ];

    for (const [index, unsupportedFile] of unsupportedFiles.entries()) {
      try {
        // Create unsupported test file
        const testFile = await testDataManager.createUnsupportedFile(unsupportedFile.name, unsupportedFile.type);

        // Attempt to upload unsupported file
        const documentId = await documentProcessor.uploadDocument(testFile, {
          waitForProcessing: false
        });

        // Wait for error to be detected
        await page.waitForTimeout(5000);

        // Verify error status
        const errorState = documentProcessor.getProcessingState(documentId);
        expect(errorState?.status).toBe('error');
        expect(errorState?.error).toContain('unsupported') || expect(errorState?.error).toContain('format');

        // Verify error message is displayed
        const errorMessage = page.locator(`[data-document-id="${documentId}"] [data-testid="error-message"]`);
        await expect(errorMessage).toBeVisible();

      } catch (error) {
        // Expected to fail due to unsupported file type
        expect(error.message).toContain('unsupported') || expect(error.message).toContain('format');
      }
    }

    // Verify recovery by uploading a supported file after unsupported file attempts
    const recoveryFile = await testDataManager.getTestFile('recovery-test.pdf');
    const recoveryDocumentId = await documentProcessor.uploadDocument(recoveryFile, {
      waitForProcessing: true
    });

    const recoveryState = documentProcessor.getProcessingState(recoveryDocumentId);
    expect(recoveryState?.status).toBe('completed');

    console.log('Unsupported file handling and recovery test completed successfully');
  });
});