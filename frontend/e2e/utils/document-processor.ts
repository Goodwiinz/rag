import { Page } from '@playwright/test';
import { WebSocketTestUtils } from './websocket-test-utils';

/**
 * Document Processing Utilities for E2E Testing
 *
 * Provides comprehensive document processing testing capabilities:
 * - Document upload automation
 * - Processing stage monitoring
 * - Real-time status validation
 * - Multi-modal file processing
 * - Error handling and recovery testing
 */

export interface ProcessingStage {
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  progress: number;
  startTime?: number;
  endTime?: number;
  error?: string;
  metadata?: Record<string, any>;
}

export interface DocumentProcessingState {
  documentId: string;
  fileName: string;
  fileType: string;
  fileSize: number;
  status: 'uploading' | 'queued' | 'processing' | 'ocr' | 'transcription' | 'embedding' | 'completed' | 'error';
  progress: number;
  stages: ProcessingStage[];
  error?: string;
  metadata?: Record<string, any>;
}

export interface TestFile {
  name: string;
  path: string;
  type: string;
  size: number;
  content?: Buffer;
  expectedProcessingStages?: string[];
}

export class DocumentProcessor {
  private page: Page;
  private wsUtils: WebSocketTestUtils;
  private activeDocuments: Map<string, DocumentProcessingState> = new Map();
  private processingCallbacks: Map<string, Function[]> = new Map();

  constructor(page: Page, wsUtils: WebSocketTestUtils) {
    this.page = page;
    this.wsUtils = wsUtils;
    this.setupProcessingMonitoring();
  }

  /**
   * Set up monitoring for document processing events
   */
  private setupProcessingMonitoring(): void {
    // Register WebSocket message handlers for document processing
    this.wsUtils.registerMessageHandler('document_status_update', (message: any) => {
      this.handleDocumentStatusUpdate(message);
    });

    this.wsUtils.registerMessageHandler('processing_stage_update', (message: any) => {
      this.handleProcessingStageUpdate(message);
    });

    this.wsUtils.registerMessageHandler('document_error', (message: any) => {
      this.handleDocumentError(message);
    });
  }

  /**
   * Handle document status updates from WebSocket
   */
  private handleDocumentStatusUpdate(message: any): void {
    const { documentId, status, progress, metadata } = message.payload;

    if (this.activeDocuments.has(documentId)) {
      const currentState = this.activeDocuments.get(documentId)!;
      currentState.status = status;
      currentState.progress = progress;
      if (metadata) {
        currentState.metadata = { ...currentState.metadata, ...metadata };
      }

      // Trigger callbacks
      const callbacks = this.processingCallbacks.get(documentId) || [];
      callbacks.forEach(callback => {
        try {
          callback(currentState);
        } catch (error) {
          console.error('Error in processing callback:', error);
        }
      });
    }
  }

  /**
   * Handle processing stage updates
   */
  private handleProcessingStageUpdate(message: any): void {
    const { documentId, stage, status, progress, error } = message.payload;

    if (this.activeDocuments.has(documentId)) {
      const currentState = this.activeDocuments.get(documentId)!;

      let stageInfo = currentState.stages.find(s => s.name === stage);
      if (!stageInfo) {
        stageInfo = {
          name: stage,
          status: 'pending',
          progress: 0
        };
        currentState.stages.push(stageInfo);
      }

      stageInfo.status = status;
      stageInfo.progress = progress;
      if (error) stageInfo.error = error;

      if (status === 'running' && !stageInfo.startTime) {
        stageInfo.startTime = Date.now();
      }
      if (status === 'completed' || status === 'error') {
        stageInfo.endTime = Date.now();
      }
    }
  }

  /**
   * Handle document processing errors
   */
  private handleDocumentError(message: any): void {
    const { documentId, error, stage } = message.payload;

    if (this.activeDocuments.has(documentId)) {
      const currentState = this.activeDocuments.get(documentId)!;
      currentState.status = 'error';
      currentState.error = error;

      if (stage) {
        const stageInfo = currentState.stages.find(s => s.name === stage);
        if (stageInfo) {
          stageInfo.status = 'error';
          stageInfo.error = error;
          stageInfo.endTime = Date.now();
        }
      }
    }
  }

  /**
   * Upload a document and start monitoring its processing
   */
  async uploadDocument(testFile: TestFile, options: {
    waitForProcessing?: boolean;
    timeout?: number;
  } = {}): Promise<string> {
    const { waitForProcessing = true, timeout = 120000 } = options;

    // Navigate to documents page if not already there
    const currentUrl = this.page.url();
    if (!currentUrl.includes('/documents')) {
      await this.page.goto('/documents');
      await this.page.waitForLoadState('networkidle');
    }

    // Create file input and upload
    const fileInput = this.page.locator('input[type="file"]');
    await fileInput.setInputFiles(testFile.path);

    // Wait for file to appear in the list and get document ID
    await this.page.waitForSelector(`[data-testid*="file-"]`, { timeout: 10000 });

    const documentId = await this.getDocumentIdFromFileName(testFile.name);

    // Initialize document state tracking
    const initialState: DocumentProcessingState = {
      documentId,
      fileName: testFile.name,
      fileType: testFile.type,
      fileSize: testFile.size,
      status: 'uploading',
      progress: 0,
      stages: []
    };

    this.activeDocuments.set(documentId, initialState);

    // Wait for initial processing status
    await this.waitForStatusChange(documentId, 'uploading', 'queued', 10000);

    if (waitForProcessing) {
      await this.waitForProcessingCompletion(documentId, timeout);
    }

    return documentId;
  }

  /**
   * Get document ID from file name in the UI
   */
  private async getDocumentIdFromFileName(fileName: string): Promise<string> {
    const fileItem = this.page.locator(`[data-testid*="file-"]`).filter({
      has: this.page.locator(`text=${fileName}`)
    }).first();

    const documentId = await fileItem.getAttribute('data-document-id');
    if (!documentId) {
      throw new Error(`Could not find document ID for file: ${fileName}`);
    }

    return documentId;
  }

  /**
   * Wait for document processing to complete
   */
  async waitForProcessingCompletion(documentId: string, timeout: number = 120000): Promise<DocumentProcessingState> {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();

      const checkCompletion = () => {
        const state = this.activeDocuments.get(documentId);

        if (!state) {
          reject(new Error(`Document ${documentId} not found in active documents`));
          return;
        }

        if (state.status === 'completed') {
          resolve(state);
          return;
        }

        if (state.status === 'error') {
          reject(new Error(`Document processing failed: ${state.error}`));
          return;
        }

        if (Date.now() - startTime > timeout) {
          reject(new Error(`Document processing did not complete within ${timeout}ms`));
          return;
        }

        // Check again in 1000ms
        setTimeout(checkCompletion, 1000);
      };

      // Register callback for status updates
      const callback = (newState: DocumentProcessingState) => {
        if (newState.status === 'completed' || newState.status === 'error') {
          resolve(newState);
        }
      };

      this.registerProcessingCallback(documentId, callback);

      // Start checking
      checkCompletion();
    });
  }

  /**
   * Wait for specific status change
   */
  async waitForStatusChange(
    documentId: string,
    fromStatus: string,
    toStatus: string,
    timeout: number = 30000
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();

      const checkStatus = () => {
        const state = this.activeDocuments.get(documentId);

        if (state?.status === toStatus) {
          resolve();
          return;
        }

        if (Date.now() - startTime > timeout) {
          reject(new Error(`Status did not change from ${fromStatus} to ${toStatus} within ${timeout}ms`));
          return;
        }

        // Check again in 500ms
        setTimeout(checkStatus, 500);
      };

      // Register callback for status updates
      const callback = (newState: DocumentProcessingState) => {
        if (newState.status === toStatus) {
          resolve();
        }
      };

      this.registerProcessingCallback(documentId, callback);
      checkStatus();
    });
  }

  /**
   * Wait for specific processing stage
   */
  async waitForProcessingStage(
    documentId: string,
    stageName: string,
    timeout: number = 60000
  ): Promise<ProcessingStage> {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();

      const checkStage = () => {
        const state = this.activeDocuments.get(documentId);

        if (!state) {
          reject(new Error(`Document ${documentId} not found`));
          return;
        }

        const stage = state.stages.find(s => s.name === stageName);

        if (stage && (stage.status === 'completed' || stage.status === 'error')) {
          resolve(stage);
          return;
        }

        if (Date.now() - startTime > timeout) {
          reject(new Error(`Processing stage ${stageName} did not complete within ${timeout}ms`));
          return;
        }

        // Check again in 1000ms
        setTimeout(checkStage, 1000);
      };

      checkStage();
    });
  }

  /**
   * Get current processing status for a document
   */
  getProcessingStatus(documentId: string): string | null {
    const state = this.activeDocuments.get(documentId);
    return state?.status || null;
  }

  /**
   * Get current processing state for a document
   */
  getProcessingState(documentId: string): DocumentProcessingState | null {
    return this.activeDocuments.get(documentId) || null;
  }

  /**
   * Get processing progress for a document
   */
  getProcessingProgress(documentId: string): number {
    const state = this.activeDocuments.get(documentId);
    return state?.progress || 0;
  }

  /**
   * Verify expected processing stages for file type
   */
  async verifyProcessingStages(documentId: string, expectedStages: string[]): Promise<boolean> {
    const state = this.activeDocuments.get(documentId);
    if (!state) return false;

    const completedStages = state.stages
      .filter(stage => stage.status === 'completed')
      .map(stage => stage.name);

    return expectedStages.every(stage => completedStages.includes(stage));
  }

  /**
   * Test document processing under various conditions
   */
  async testProcessingRobustness(testFile: TestFile, scenarios: string[]): Promise<void> {
    for (const scenario of scenarios) {
      switch (scenario) {
        case 'connection_loss':
          await this.testConnectionLossDuringProcessing(testFile);
          break;
        case 'large_file':
          await this.testLargeFileProcessing(testFile);
          break;
        case 'corrupted_file':
          await this.testCorruptedFileProcessing(testFile);
          break;
        case 'concurrent_uploads':
          await this.testConcurrentProcessing(testFile);
          break;
        default:
          console.warn(`Unknown processing scenario: ${scenario}`);
      }
    }
  }

  /**
   * Test processing resilience during connection loss
   */
  private async testConnectionLossDuringProcessing(testFile: TestFile): Promise<void> {
    // Start document upload
    const documentId = await this.uploadDocument(testFile, { waitForProcessing: false });

    // Wait for processing to start
    await this.waitForStatusChange(documentId, 'queued', 'processing', 10000);

    // Simulate connection loss
    await this.wsUtils.simulateConnectionLoss(5000);

    // Verify processing resumes
    await this.waitForProcessingCompletion(documentId, 180000); // Extended timeout
  }

  /**
   * Test large file processing
   */
  private async testLargeFileProcessing(testFile: TestFile): Promise<void> {
    const largeFile = { ...testFile, name: `large_${testFile.name}` };

    const documentId = await this.uploadDocument(largeFile, { timeout: 300000 });

    // Verify processing stages are handled correctly
    const state = this.getProcessingState(documentId);
    expect(state).toBeTruthy();
    expect(state?.status).toBe('completed');
  }

  /**
   * Test corrupted file handling
   */
  private async testCorruptedFileProcessing(testFile: TestFile): Promise<void> {
    // Create a corrupted version of the file
    const corruptedFile = { ...testFile, name: `corrupted_${testFile.name}` };

    try {
      const documentId = await this.uploadDocument(corruptedFile, { waitForProcessing: false });

      // Wait for error status
      await this.page.waitForTimeout(10000); // Give time for error processing

      const state = this.getProcessingState(documentId);
      expect(state?.status).toBe('error');
      expect(state?.error).toBeTruthy();
    } catch (error) {
      // Expected to fail due to corrupted file
      expect(error.message).toContain('failed');
    }
  }

  /**
   * Test concurrent document processing
   */
  private async testConcurrentProcessing(testFile: TestFile): Promise<void> {
    const concurrentFiles = Array(3).fill(null).map((_, i) => ({
      ...testFile,
      name: `concurrent_${i}_${testFile.name}`
    }));

    const documentIds = await Promise.all(
      concurrentFiles.map(file => this.uploadDocument(file, { waitForProcessing: false }))
    );

    // Wait for all to complete
    await Promise.all(
      documentIds.map(id => this.waitForProcessingCompletion(id, 180000))
    );

    // Verify all completed successfully
    documentIds.forEach(id => {
      const state = this.getProcessingState(id);
      expect(state?.status).toBe('completed');
    });
  }

  /**
   * Register processing callback
   */
  registerProcessingCallback(documentId: string, callback: Function): void {
    const callbacks = this.processingCallbacks.get(documentId) || [];
    callbacks.push(callback);
    this.processingCallbacks.set(documentId, callbacks);
  }

  /**
   * Remove processing callbacks
   */
  removeProcessingCallbacks(documentId: string): void {
    this.processingCallbacks.delete(documentId);
  }

  /**
   * Cleanup resources
   */
  async cleanup(): Promise<void> {
    this.activeDocuments.clear();
    this.processingCallbacks.clear();
  }
}