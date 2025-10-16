/**
 * End-to-End Tests for Document Upload Journey
 * Tests complete user workflows from upload to processing completion
 * Using Playwright for browser automation and cross-platform testing
 */

import { test, expect, type Page, type BrowserContext } from '@playwright/test';
import path from 'path';
import fs from 'fs';

// Test data and utilities
import {
  generateTestFile,
  createTestUser,
  loginAsUser,
  waitForDocumentProcessing,
  cleanupTestFiles,
  takeScreenshot,
  generateLargeTestFile
} from '../utils/test-helpers';
import { API_URL, FRONTEND_URL } from '../config/test-config';

// Test configurations
const TEST_FILES = {
  PDF_SMALL: { name: 'test-small.pdf', size: 1024 * 1024, type: 'application/pdf' },
  PDF_LARGE: { name: 'test-large.pdf', size: 10 * 1024 * 1024, type: 'application/pdf' },
  IMAGE: { name: 'test-image.jpg', size: 2 * 1024 * 1024, type: 'image/jpeg' },
  AUDIO: { name: 'test-audio.mp3', size: 5 * 1024 * 1024, type: 'audio/mpeg' },
  VIDEO: { name: 'test-video.mp4', size: 20 * 1024 * 1024, type: 'video/mp4' },
  CORRUPTED: { name: 'corrupted.pdf', size: 1024 * 1024, type: 'application/pdf' }
};

const USERS = {
  REGULAR: { email: 'user@test.com', password: 'test123', role: 'user' },
  ADMIN: { email: 'admin@test.com', password: 'REDACTED', role: 'admin' },
  VIEWER: { email: 'viewer@test.com', password: 'viewer123', role: 'viewer' }
};

test.describe('Document Upload Journey', () => {
  let page: Page;
  let context: BrowserContext;
  let testFiles: Map<string, string> = new Map();

  test.beforeAll(async ({ browser }) => {
    // Setup browser context
    context = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
      ignoreHTTPSErrors: true,
      permissions: ['clipboard-read', 'clipboard-write']
    });

    // Generate test files
    for (const [key, config] of Object.entries(TEST_FILES)) {
      const filePath = await generateTestFile(config.name, config.size, config.type);
      testFiles.set(key, filePath);
    }
  });

  test.afterAll(async () => {
    // Cleanup test files
    for (const filePath of testFiles.values()) {
      await cleanupTestFiles(filePath);
    }
    await context.close();
  });

  test.beforeEach(async () => {
    page = await context.newPage();
    await page.goto(FRONTEND_URL);
  });

  test.afterEach(async () => {
    await page.close();
  });

  test.describe('Authentication and Access Control', () => {
    test('should redirect unauthenticated users to login', async () => {
      // Try to access documents page without authentication
      await page.goto(`${FRONTEND_URL}/documents`);

      // Should be redirected to login
      await expect(page).toHaveURL(/.*\/login/);
      await expect(page.locator('h1')).toContainText('Sign In');
    });

    test('should allow authenticated users to access upload functionality', async () => {
      await loginAsUser(page, USERS.REGULAR);

      // Navigate to documents page
      await page.goto(`${FRONTEND_URL}/documents`);

      // Verify upload button is present
      await expect(page.locator('[data-testid="upload-button"]')).toBeVisible();
    });

    test('should restrict access based on user roles', async () => {
      // Test viewer role (should not be able to upload)
      await loginAsUser(page, USERS.VIEWER);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Upload button should not be present or disabled
      const uploadButton = page.locator('[data-testid="upload-button"]');
      await expect(uploadButton).toBeHidden();
    });
  });

  test.describe('Single Document Upload', () => {
    test('should successfully upload a PDF document', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Click upload button
      await page.click('[data-testid="upload-button"]');

      // Verify upload modal is open
      await expect(page.locator('[data-testid="upload-modal"]')).toBeVisible();

      // Upload file via drag and drop
      const fileInput = page.locator('input[type="file"]');
      const testFile = testFiles.get('PDF_SMALL')!;

      await fileInput.setInputFiles(testFile);

      // Fill in document details
      await page.fill('[data-testid="document-title"]', 'Test PDF Document');
      await page.fill('[data-testid="document-description"]', 'This is a test PDF document for upload testing');
      await page.fill('[data-testid="document-tags"]', 'test,pdf,upload');

      // Set processing priority
      await page.selectOption('[data-testid="processing-priority"]', 'normal');

      // Enable quality check
      await page.check('[data-testid="enable-quality-check"]');

      // Click upload button
      await page.click('[data-testid="confirm-upload"]');

      // Verify upload progress
      await expect(page.locator('[data-testid="upload-progress"]')).toBeVisible();
      await expect(page.locator('[data-testid="progress-bar"]')).toBeVisible();

      // Wait for upload completion
      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible({ timeout: 30000 });

      // Verify success message
      await expect(page.locator('[data-testid="success-message"]')).toContainText('Document uploaded successfully');

      // Navigate to documents page
      await page.goto(`${FRONTEND_URL}/documents`);

      // Verify document appears in library
      await expect(page.locator('text=Test PDF Document')).toBeVisible({ timeout: 10000 });

      await takeScreenshot(page, 'pdf-upload-success');
    });

    test('should handle upload with custom metadata', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Start upload process
      await page.click('[data-testid="upload-button"]');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(testFiles.get('IMAGE')!);

      // Fill in document details with custom metadata
      await page.fill('[data-testid="document-title"]', 'Test Image with Metadata');
      await page.fill('[data-testid="document-description"]', 'Test image with custom metadata');

      // Add custom metadata
      await page.click('[data-testid="show-advanced-options"]');
      await page.fill('[data-testid="custom-author"]', 'Test Author');
      await page.fill('[data-testid="custom-category"]', 'Test Category');
      await page.fill('[data-testid="custom-keywords"]', 'test,image,metadata');

      // Set document as public
      await page.check('[data-testid="make-public"]');

      // Upload document
      await page.click('[data-testid="confirm-upload"]');

      // Wait for completion
      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible({ timeout: 30000 });

      // Verify metadata was saved
      await page.goto(`${FRONTEND_URL}/documents`);
      await page.click('text=Test Image with Metadata');

      await expect(page.locator('[data-testid="document-author"]')).toContainText('Test Author');
      await expect(page.locator('[data-testid="document-category"]')).toContainText('Test Category');
    });

    test('should validate file types and reject unsupported formats', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Create unsupported file
      const unsupportedFile = await generateTestFile('malicious.exe', 1024, 'application/x-executable');

      // Try to upload unsupported file
      await page.click('[data-testid="upload-button"]');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(unsupportedFile);

      // Verify error message
      await expect(page.locator('[data-testid="file-type-error"]')).toBeVisible();
      await expect(page.locator('[data-testid="error-message"]')).toContainText('Unsupported file type');

      await cleanupTestFiles(unsupportedFile);
    });

    test('should handle file size limits appropriately', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Try to upload oversized file
      await page.click('[data-testid="upload-button"]');
      const fileInput = page.locator('input[type="file"]');

      // Create temporary oversized file (assuming 100MB limit)
      const oversizedFile = await generateLargeTestFile('oversized.pdf', 150 * 1024 * 1024);
      await fileInput.setInputFiles(oversizedFile);

      // Verify size limit error
      await expect(page.locator('[data-testid="file-size-error"]')).toBeVisible();
      await expect(page.locator('[data-testid="error-message"]')).toContainText('File size exceeds limit');

      await cleanupTestFiles(oversizedFile);
    });

    test('should provide real-time upload progress updates', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Start upload
      await page.click('[data-testid="upload-button"]');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(testFiles.get('PDF_LARGE')!);

      await page.fill('[data-testid="document-title"]', 'Large File Upload Test');
      await page.click('[data-testid="confirm-upload"]');

      // Monitor progress updates
      const progressBar = page.locator('[data-testid="progress-bar"]');
      const progressText = page.locator('[data-testid="progress-text"]');

      // Should show initial progress
      await expect(progressBar).toBeVisible();
      await expect(progressText).toBeVisible();

      // Progress should increase over time
      let lastProgress = 0;
      for (let i = 0; i < 10; i++) {
        const currentProgress = await progressText.textContent();
        const progressValue = parseInt(currentProgress?.match(/(\d+)%/)?.[1] || '0');

        expect(progressValue).toBeGreaterThanOrEqual(lastProgress);
        lastProgress = progressValue;

        if (progressValue >= 100) break;

        await page.waitForTimeout(1000);
      }

      // Wait for completion
      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible({ timeout: 60000 });
    });
  });

  test.describe('Batch Document Upload', () => {
    test('should handle multiple file uploads simultaneously', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Enable batch upload mode
      await page.click('[data-testid="upload-button"]');
      await page.click('[data-testid="batch-upload-mode"]');

      // Select multiple files
      const fileInput = page.locator('input[type="file"][multiple]');
      const filesToUpload = [
        testFiles.get('PDF_SMALL')!,
        testFiles.get('IMAGE')!,
        testFiles.get('AUDIO')!
      ];

      await fileInput.setInputFiles(filesToUpload);

      // Verify all files are listed
      await expect(page.locator('[data-testid="file-list-item"]')).toHaveCount(3);

      // Fill in batch details
      await page.fill('[data-testid="batch-title-prefix"]', 'Batch Test');
      await page.selectOption('[data-testid="batch-processing-mode"]', 'parallel');

      // Start batch upload
      await page.click('[data-testid="start-batch-upload"]');

      // Monitor batch progress
      await expect(page.locator('[data-testid="batch-progress"]')).toBeVisible();

      // Wait for all uploads to complete
      await expect(page.locator('[data-testid="batch-complete"]')).toBeVisible({ timeout: 120000 });

      // Verify all documents appear in library
      await page.goto(`${FRONTEND_URL}/documents`);
      await expect(page.locator('[data-testid="document-card"]')).toHaveCount.atLeast(3);

      await takeScreenshot(page, 'batch-upload-success');
    });

    test('should handle batch upload with mixed file types', async () => {
      await loginAsUser(page, USERS.ADMIN);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Upload mixed file types
      await page.click('[data-testid="upload-button"]');
      await page.click('[data-testid="batch-upload-mode"]');

      const fileInput = page.locator('input[type="file"][multiple]');
      const mixedFiles = [
        testFiles.get('PDF_SMALL')!,
        testFiles.get('IMAGE')!,
        testFiles.get('AUDIO')!,
        testFiles.get('VIDEO')!
      ];

      await fileInput.setInputFiles(mixedFiles);

      // Verify file type detection
      await expect(page.locator('[data-testid="file-type-pdf"]')).toHaveCount(1);
      await expect(page.locator('[data-testid="file-type-image"]')).toHaveCount(1);
      await expect(page.locator('[data-testid="file-type-audio"]')).toHaveCount(1);
      await expect(page.locator('[data-testid="file-type-video"]')).toHaveCount(1);

      // Start upload
      await page.click('[data-testid="start-batch-upload"]');

      // Wait for completion
      await expect(page.locator('[data-testid="batch-complete"]')).toBeVisible({ timeout: 180000 });
    });

    test('should allow cancellation of batch uploads', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Start large batch upload
      await page.click('[data-testid="upload-button"]');
      await page.click('[data-testid="batch-upload-mode"]');

      const fileInput = page.locator('input[type="file"][multiple]');
      const largeFiles = Array(5).fill(null).map((_, i) =>
        testFiles.get('PDF_LARGE')!
      );

      await fileInput.setInputFiles(largeFiles);
      await page.click('[data-testid="start-batch-upload"]');

      // Wait for upload to start
      await expect(page.locator('[data-testid="batch-progress"]')).toBeVisible();

      // Cancel upload
      await page.click('[data-testid="cancel-batch-upload"]');

      // Confirm cancellation
      await page.click('[data-testid="confirm-cancel"]');

      // Verify cancellation message
      await expect(page.locator('[data-testid="upload-cancelled"]')).toBeVisible();
    });
  });

  test.describe('Document Processing and Status Updates', () => {
    test('should track document processing status in real-time', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Upload a document
      await page.click('[data-testid="upload-button"]');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(testFiles.get('PDF_SMALL')!);

      await page.fill('[data-testid="document-title"]', 'Processing Status Test');
      await page.click('[data-testid="confirm-upload"]');

      // Wait for upload completion
      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible();

      // Navigate to documents and monitor processing
      await page.goto(`${FRONTEND_URL}/documents`);
      await page.click('text=Processing Status Test');

      // Monitor processing stages
      const processingStages = [
        'queued',
        'processing',
        'analyzing',
        'indexing',
        'completed'
      ];

      for (const stage of processingStages) {
        try {
          await expect(page.locator(`[data-testid="status-${stage}"]`)).toBeVisible({
            timeout: 30000
          });
        } catch (error) {
          // Some stages might be too fast to capture
          console.log(`Stage ${stage} may have been skipped or too fast`);
        }
      }

      // Wait for final completion
      await expect(page.locator('[data-testid="status-completed"]')).toBeVisible({
        timeout: 120000
      });

      await takeScreenshot(page, 'processing-complete');
    });

    test('should display processing errors and allow retry', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Upload a file that will fail processing (corrupted file)
      await page.click('[data-testid="upload-button"]');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(testFiles.get('CORRUPTED')!);

      await page.fill('[data-testid="document-title"]', 'Error Test Document');
      await page.click('[data-testid="confirm-upload"]');

      // Wait for upload completion
      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible();

      // Monitor for processing failure
      await page.goto(`${FRONTEND_URL}/documents`);

      // Wait for error status
      await expect(page.locator('[data-testid="status-failed"]')).toBeVisible({
        timeout: 60000
      });

      // Verify error message is displayed
      await expect(page.locator('[data-testid="error-message"]')).toBeVisible();

      // Test retry functionality
      await page.click('[data-testid="retry-processing"]');

      // Verify retry was initiated
      await expect(page.locator('[data-testid="retry-initiated"]')).toBeVisible();

      await takeScreenshot(page, 'processing-error-retry');
    });

    test('should show quality assessment results', async () => {
      await loginAsUser(page, USERS.ADMIN);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Upload document with quality assessment enabled
      await page.click('[data-testid="upload-button"]');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(testFiles.get('PDF_SMALL')!);

      await page.fill('[data-testid="document-title"]', 'Quality Assessment Test');
      await page.check('[data-testid="enable-quality-check"]');
      await page.click('[data-testid="confirm-upload"]');

      // Wait for processing completion
      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible();

      // Check quality assessment results
      await page.goto(`${FRONTEND_URL}/documents`);
      await page.click('text=Quality Assessment Test');

      // Should show quality metrics
      await expect(page.locator('[data-testid="quality-score"]')).toBeVisible({
        timeout: 120000
      });

      // Verify quality breakdown
      await expect(page.locator('[data-testid="readability-score"]')).toBeVisible();
      await expect(page.locator('[data-testid="content-quality-score"]')).toBeVisible();
      await expect(page.locator('[data-testid="technical-quality-score"]')).toBeVisible();

      // Check for recommendations if quality is not perfect
      const recommendations = page.locator('[data-testid="quality-recommendations"]');
      if (await recommendations.isVisible()) {
        await expect(recommendations).toBeVisible();
      }

      await takeScreenshot(page, 'quality-assessment');
    });
  });

  test.describe('Document Management After Upload', () => {
    test('should allow document preview and download', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Upload and process a document
      await page.click('[data-testid="upload-button"]');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(testFiles.get('PDF_SMALL')!);

      await page.fill('[data-testid="document-title"]', 'Preview Download Test');
      await page.click('[data-testid="confirm-upload"]');

      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible();

      // Navigate to documents and find the uploaded document
      await page.goto(`${FRONTEND_URL}/documents`);
      await page.click('text=Preview Download Test');

      // Test preview functionality
      await page.click('[data-testid="preview-button"]');
      await expect(page.locator('[data-testid="document-preview"]')).toBeVisible();

      // Test download functionality
      const downloadPromise = page.waitForEvent('download');
      await page.click('[data-testid="download-button"]');
      const download = await downloadPromise;

      // Verify download filename
      expect(download.suggestedFilename()).toBe('test-small.pdf');

      await takeScreenshot(page, 'document-preview-download');
    });

    test('should allow document editing and metadata updates', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Upload a document
      await page.click('[data-testid="upload-button"]');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(testFiles.get('PDF_SMALL')!);

      await page.fill('[data-testid="document-title"]', 'Edit Test Document');
      await page.click('[data-testid="confirm-upload"]');

      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible();

      // Edit document metadata
      await page.goto(`${FRONTEND_URL}/documents`);
      await page.click('text=Edit Test Document');
      await page.click('[data-testid="edit-metadata"]');

      // Update metadata
      await page.fill('[data-testid="document-title"]', 'Updated Document Title');
      await page.fill('[data-testid="document-description"]', 'Updated description');
      await page.fill('[data-testid="document-tags"]', 'updated,edited,test');

      // Save changes
      await page.click('[data-testid="save-metadata"]');

      // Verify changes were saved
      await expect(page.locator('[data-testid="save-success"]')).toBeVisible();
      await expect(page.locator('text=Updated Document Title')).toBeVisible();

      await takeScreenshot(page, 'document-edit-success');
    });

    test('should handle document deletion properly', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Upload a document
      await page.click('[data-testid="upload-button"]');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(testFiles.get('PDF_SMALL')!);

      await page.fill('[data-testid="document-title"]', 'Delete Test Document');
      await page.click('[data-testid="confirm-upload"]');

      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible();

      // Delete the document
      await page.goto(`${FRONTEND_URL}/documents`);
      await page.click('text=Delete Test Document');
      await page.click('[data-testid="document-actions"]');
      await page.click('[data-testid="delete-document"]');

      // Confirm deletion
      await expect(page.locator('[data-testid="delete-confirmation"]')).toBeVisible();
      await page.click('[data-testid="confirm-delete"]');

      // Verify deletion success
      await expect(page.locator('[data-testid="delete-success"]')).toBeVisible();

      // Verify document is no longer in library
      await expect(page.locator('text=Delete Test Document')).toBeHidden();

      await takeScreenshot(page, 'document-delete-success');
    });
  });

  test.describe('Error Handling and Edge Cases', () => {
    test('should handle network interruptions during upload', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Start upload
      await page.click('[data-testid="upload-button"]');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(testFiles.get('PDF_LARGE')!);

      await page.fill('[data-testid="document-title"]', 'Network Interrupt Test');
      await page.click('[data-testid="confirm-upload"]');

      // Simulate network interruption
      await page.route('**/api/v2/documents/upload/single', route => route.abort());

      // Should show network error
      await expect(page.locator('[data-testid="network-error"]')).toBeVisible({
        timeout: 30000
      });

      // Test retry functionality
      await page.unroute('**/api/v2/documents/upload/single');
      await page.click('[data-testid="retry-upload"]');

      // Should resume upload after network restore
      await expect(page.locator('[data-testid="upload-progress"]')).toBeVisible();
    });

    test('should handle concurrent upload conflicts', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents");

      // Open two upload sessions
      await page.click('[data-testid="upload-button"]');

      // Start first upload
      const fileInput1 = page.locator('input[type="file"]');
      await fileInput1.setInputFiles(testFiles.get('PDF_SMALL')!);
      await page.fill('[data-testid="document-title"]', 'Concurrent Upload 1');
      await page.click('[data-testid="confirm-upload"]');

      // Try to start second upload (should handle gracefully)
      await page.goBack();
      await page.click('[data-testid="upload-button"]');
      const fileInput2 = page.locator('input[type="file"]');
      await fileInput2.setInputFiles(testFiles.get('IMAGE')!);
      await page.fill('[data-testid="document-title"]', 'Concurrent Upload 2');
      await page.click('[data-testid="confirm-upload"]');

      // Both uploads should succeed or queue appropriately
      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible({
        timeout: 60000
      });
    });

    test('should handle browser tab closing during upload', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Start upload
      await page.click('[data-testid="upload-button"]');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(testFiles.get('PDF_LARGE')!);

      await page.fill('[data-testid="document-title"]', 'Tab Close Test');
      await page.click('[data-testid="confirm-upload"]');

      // Wait for upload to start
      await expect(page.locator('[data-testid="upload-progress"]')).toBeVisible();

      // Simulate tab close and reopen
      await page.close();
      page = await context.newPage();
      await page.goto(FRONTEND_URL);
      await loginAsUser(page, USERS.REGULAR);

      // Should show upload status recovery
      await page.goto(`${FRONTEND_URL}/documents`);

      // Check if upload continued in background or can be resumed
      const uploadStatus = page.locator('[data-testid="upload-status"]');
      if (await uploadStatus.isVisible()) {
        await expect(uploadStatus).toContainText('completed');
      }
    });
  });

  test.describe('Performance and Scalability', () => {
    test('should handle large file uploads efficiently', async () => {
      await loginAsUser(page, USERS.ADMIN);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Monitor performance during large file upload
      const startTime = Date.now();

      await page.click('[data-testid="upload-button"]');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(testFiles.get('VIDEO')!); // 20MB file

      await page.fill('[data-testid="document-title"]', 'Large File Performance Test');
      await page.click('[data-testid="confirm-upload"]');

      // Monitor memory usage
      const memoryMonitor = async () => {
        const metrics = await page.evaluate(() => ({
          usedJSHeapSize: performance.memory?.usedJSHeapSize || 0,
          totalJSHeapSize: performance.memory?.totalJSHeapSize || 0
        }));
        return metrics;
      };

      const initialMemory = await memoryMonitor();

      // Wait for completion
      await expect(page.locator('[data-testid="upload-success"]')).toBeVisible({
        timeout: 180000
      });

      const endTime = Date.now();
      const uploadTime = endTime - startTime;
      const finalMemory = await memoryMonitor();

      // Performance assertions
      expect(uploadTime).toBeLessThan(120000); // Should complete within 2 minutes
      expect(finalMemory.usedJSHeapSize - initialMemory.usedJSHeapSize).toBeLessThan(50 * 1024 * 1024); // Memory increase < 50MB

      console.log(`Upload completed in ${uploadTime}ms`);
      console.log(`Memory increase: ${(finalMemory.usedJSHeapSize - initialMemory.usedJSHeapSize) / 1024 / 1024}MB`);
    });

    test('should maintain responsiveness during batch uploads', async () => {
      await loginAsUser(page, USERS.ADMIN);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Start large batch upload
      await page.click('[data-testid="upload-button"]');
      await page.click('[data-testid="batch-upload-mode"]');

      const fileInput = page.locator('input[type="file"][multiple]');
      const manyFiles = Array(10).fill(null).map((_, i) =>
        testFiles.get('PDF_SMALL')!
      );

      await fileInput.setInputFiles(manyFiles);
      await page.click('[data-testid="start-batch-upload"]');

      // Test UI responsiveness during upload
      await expect(page.locator('[data-testid="batch-progress"]')).toBeVisible();

      // Should be able to navigate to other pages
      await page.click('[data-testid="nav-dashboard"]');
      await expect(page).toHaveURL(/.*\/dashboard/);

      // Should be able to navigate back
      await page.click('[data-testid="nav-documents"]');
      await expect(page).toHaveURL(/.*\/documents/);

      // Upload should still be running
      await expect(page.locator('[data-testid="batch-progress"]')).toBeVisible();

      // Wait for completion
      await expect(page.locator('[data-testid="batch-complete"]')).toBeVisible({
        timeout: 300000
      });
    });
  });

  test.describe('Accessibility Testing', () => {
    test('should be accessible for keyboard navigation', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Test keyboard navigation through upload flow
      await page.keyboard.press('Tab');
      await expect(page.locator(':focus')).toBeVisible();

      // Navigate to upload button
      let focused = false;
      for (let i = 0; i < 10; i++) {
        await page.keyboard.press('Tab');
        const element = page.locator(':focus');
        if (await element.getAttribute('data-testid') === 'upload-button') {
          focused = true;
          break;
        }
      }
      expect(focused).toBe(true);

      // Activate upload with keyboard
      await page.keyboard.press('Enter');
      await expect(page.locator('[data-testid="upload-modal"]')).toBeVisible();

      // Test keyboard file input navigation
      await page.keyboard.press('Tab');
      await page.keyboard.press('Enter'); // Should open file dialog

      // Test form navigation
      await page.keyboard.press('Tab');
      await page.keyboard.type('Keyboard Test Document');

      // Test submit with keyboard
      await page.keyboard.press('Tab');
      await page.keyboard.press('Enter');

      // Should start upload
      await expect(page.locator('[data-testid="upload-progress"]')).toBeVisible();
    });

    test('should support screen reader accessibility', async () => {
      await loginAsUser(page, USERS.REGULAR);
      await page.goto(`${FRONTEND_URL}/documents`);

      // Check for proper ARIA labels
      await expect(page.locator('[aria-label*="upload"]')).toBeVisible();
      await expect(page.locator('[role="button"]')).toHaveCount.atLeast(1);
      await expect(page.locator('[role="main"]')).toBeVisible();

      // Test semantic HTML structure
      await expect(page.locator('h1')).toBeVisible();
      await expect(page.locator('nav')).toBeVisible();
      await expect(page.locator('main')).toBeVisible();

      // Check for proper heading hierarchy
      const headings = await page.locator('h1, h2, h3, h4, h5, h6').all();
      expect(headings.length).toBeGreaterThan(0);

      // Test form accessibility
      await page.click('[data-testid="upload-button"]');
      await expect(page.locator('label')).toHaveCount.atLeast(1);
      await expect(page.locator('[for]')).toHaveCount.atLeast(1);
    });
  });
});