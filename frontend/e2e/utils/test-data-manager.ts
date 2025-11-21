import { Page } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

/**
 * Test Data Manager for E2E Testing
 *
 * Provides comprehensive test data management:
 * - File creation and management
 * - User authentication data
 * - Test environment setup
 * - Test data cleanup
 * - Mock data generation
 */

export interface TestFile {
  name: string;
  path: string;
  type: string;
  size: number;
  content?: Buffer;
  expectedProcessingStages?: string[];
}

export interface TestUser {
  id: string;
  email: string;
  password: string;
  name: string;
  role: 'admin' | 'user' | 'lab-admin';
  permissions: string[];
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}

export class TestDataManager {
  private page: Page;
  private testDataPath: string;
  private tempFiles: string[] = [];
  private testUsers: Map<string, TestUser> = new Map();

  constructor(page: Page, testDataPath?: string) {
    this.page = page;
    this.testDataPath = testDataPath || path.join(process.cwd(), 'test-data', 'files');
    this.ensureTestDataDirectory();
    this.setupTestUsers();
  }

  /**
   * Ensure test data directory exists
   */
  private ensureTestDataDirectory(): void {
    if (!fs.existsSync(this.testDataPath)) {
      fs.mkdirSync(this.testDataPath, { recursive: true });
    }
  }

  /**
   * Setup test users
   */
  private setupTestUsers(): void {
    const testUsers: TestUser[] = [
      {
        id: 'test-user-1',
        email: 'test@example.com',
        password: 'testpassword123',
        name: 'Test User',
        role: 'user',
        permissions: ['read', 'write', 'upload']
      },
      {
        id: 'test-admin-1',
        email: 'admin@example.com',
        password: 'adminpassword123',
        name: 'Test Admin',
        role: 'admin',
        permissions: ['read', 'write', 'upload', 'delete', 'manage_users']
      },
      {
        id: 'test-lab-admin-1',
        email: 'lab-admin@example.com',
        password: 'labpassword123',
        name: 'Test Lab Admin',
        role: 'lab-admin',
        permissions: ['read', 'write', 'upload', 'delete', 'manage_experiments']
      }
    ];

    testUsers.forEach(user => {
      this.testUsers.set(user.id, user);
    });
  }

  /**
   * Authenticate a user and return tokens
   */
  async authenticateUser(page: Page, userRole: 'user' | 'admin' | 'lab-admin' = 'user'): Promise<AuthTokens> {
    const user = Array.from(this.testUsers.values()).find(u => u.role === userRole);
    if (!user) {
      throw new Error(`Test user with role ${userRole} not found`);
    }

    // Navigate to login page if not already there
    const currentUrl = page.url();
    if (!currentUrl.includes('/login')) {
      await page.goto('/login');
      await page.waitForLoadState('networkidle');
    }

    // Fill login form
    await page.fill('[data-testid="email-input"]', user.email);
    await page.fill('[data-testid="password-input"]', user.password);
    await page.click('[data-testid="login-button"]');

    // Wait for login to complete
    await page.waitForURL('**/dashboard');
    await page.waitForLoadState('networkidle');

    // Get authentication tokens from localStorage
    const tokens = await page.evaluate(() => {
      const accessToken = localStorage.getItem('auth_token');
      const refreshToken = localStorage.getItem('refresh_token');
      const expiresAt = parseInt(localStorage.getItem('token_expires_at') || '0');

      return { accessToken, refreshToken, expiresAt };
    });

    if (!tokens.accessToken) {
      throw new Error('Authentication failed - no access token received');
    }

    return {
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken || '',
      expiresAt: tokens.expiresAt
    };
  }

  /**
   * Get stored token from page
   */
  async getStoredToken(page: Page): Promise<string> {
    return await page.evaluate(() => {
      return localStorage.getItem('auth_token') || '';
    });
  }

  /**
   * Get stored user ID from page
   */
  async getStoredUserId(page: Page): Promise<string> {
    return await page.evaluate(() => {
      return localStorage.getItem('user_id') || '';
    });
  }

  /**
   * Get test file
   */
  async getTestFile(fileName: string, fileType?: string): Promise<TestFile> {
    const filePath = path.join(this.testDataPath, fileName);

    if (!fs.existsSync(filePath)) {
      // Create test file if it doesn't exist
      await this.createTestFile(fileName, fileType);
    }

    const stats = fs.statSync(filePath);
    const content = fs.readFileSync(filePath);
    const type = fileType || this.getFileTypeFromName(fileName);

    const testFile: TestFile = {
      name: fileName,
      path: filePath,
      type,
      size: stats.size,
      content,
      expectedProcessingStages: this.getExpectedProcessingStages(type)
    };

    return testFile;
  }

  /**
   * Create test file
   */
  async createTestFile(fileName: string, fileType?: string): Promise<void> {
    const filePath = path.join(this.testDataPath, fileName);
    const type = fileType || this.getFileTypeFromName(fileName);

    let content: Buffer;

    switch (type) {
      case 'pdf':
        content = await this.createTestPdf(fileName);
        break;
      case 'text':
        content = await this.createTestTextFile(fileName);
        break;
      case 'image':
        content = await this.createTestImage(fileName);
        break;
      case 'audio':
        content = await this.createTestAudio(fileName);
        break;
      case 'video':
        content = await this.createTestVideo(fileName);
        break;
      default:
        content = Buffer.from('Test file content', 'utf8');
    }

    fs.writeFileSync(filePath, content);
    this.tempFiles.push(filePath);
  }

  /**
   * Create test PDF
   */
  private async createTestPdf(fileName: string): Promise<Buffer> {
    // Create a simple PDF with text content
    // For real implementation, you'd use a PDF library like pdfkit
    const pdfContent = `%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length ${new TextEncoder().encode('Test PDF Content for E2E Testing').length}
>>
stream
Test PDF Content for E2E Testing
endstream
endobj

xref
0 5
0000000000 65535 f
0000000010 00000 n
0000000079 00000 n
0000000173 00000 n
0000000301 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
398
%%EOF`;

    return Buffer.from(pdfContent, 'utf8');
  }

  /**
   * Create test text file
   */
  private async createTestTextFile(fileName: string): Promise<Buffer> {
    const content = `Test Document Content for E2E Testing

This is a sample text file created for end-to-end testing of the Multimodal Enterprise RAG System.

Document Name: ${fileName}
Created: ${new Date().toISOString()}
Content Type: Text/plain

The purpose of this document is to test various stages of document processing including:
1. Text extraction
2. Entity recognition
3. Content analysis
4. Vector embedding
5. Indexing

This document contains enough content to test the full processing pipeline and ensure that all components work correctly together in a real-time environment.

Additional test content includes various entities like:
- Email addresses: test@example.com, admin@multimodal-rag.com
- Phone numbers: +1-555-0123, (555) 123-4567
- Dates: 2024-01-15, January 15, 2024
- Locations: New York, NY; San Francisco, CA
- Organizations: Test Corp, Example Industries

End of test document.`;

    return Buffer.from(content, 'utf8');
  }

  /**
   * Create test image
   */
  private async createTestImage(fileName: string): Promise<Buffer> {
    // Create a simple PNG with text overlay
    // For real implementation, you'd use an image library like sharp or canvas
    const pngHeader = Buffer.from([
      0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, // PNG signature
      // Minimal PNG structure would follow
    ]);

    // For now, create a simple binary file that simulates an image
    const imageContent = Buffer.concat([
      pngHeader,
      Buffer.from('Test image content for E2E testing', 'utf8')
    ]);

    return imageContent;
  }

  /**
   * Create test audio file
   */
  private async createTestAudio(fileName: string): Promise<Buffer> {
    // Create a simple WAV file header and content
    const wavHeader = Buffer.alloc(44);
    wavHeader.write('RIFF', 0); // ChunkID
    wavHeader.writeUInt32LE(36, 4); // ChunkSize
    wavHeader.write('WAVE', 8); // Format
    wavHeader.write('fmt ', 12); // Subchunk1ID
    wavHeader.writeUInt32LE(16, 16); // Subchunk1Size
    wavHeader.writeUInt16LE(1, 20); // AudioFormat (PCM)
    wavHeader.writeUInt16LE(1, 22); // NumChannels (mono)
    wavHeader.writeUInt32LE(44100, 24); // SampleRate
    wavHeader.writeUInt32LE(88200, 28); // ByteRate
    wavHeader.writeUInt16LE(2, 32); // BlockAlign
    wavHeader.writeUInt16LE(16, 34); // BitsPerSample
    wavHeader.write('data', 36); // Subchunk2ID
    wavHeader.writeUInt32LE(1000, 40); // Subchunk2Size

    // Create some audio data (simple sine wave simulation)
    const audioData = Buffer.alloc(1000);
    for (let i = 0; i < audioData.length; i++) {
      audioData[i] = Math.sin(i * 0.1) * 127 + 128;
    }

    return Buffer.concat([wavHeader, audioData]);
  }

  /**
   * Create test video file
   */
  private async createTestVideo(fileName: string): Promise<Buffer> {
    // Create a simple MP4 header and content
    // For real implementation, you'd use a video library like ffmpeg
    const mp4Header = Buffer.from([
      // Minimal MP4 structure
      0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70, // ftyp box
      0x69, 0x73, 0x6F, 0x6D, 0x00, 0x00, 0x02, 0x00,
      0x69, 0x73, 0x6F, 0x6D, 0x69, 0x73, 0x6F, 0x32,
      0x6D, 0x70, 0x34, 0x31
    ]);

    // Create some video data
    const videoData = Buffer.alloc(5000); // Larger than audio
    for (let i = 0; i < videoData.length; i++) {
      videoData[i] = i % 256;
    }

    return Buffer.concat([mp4Header, videoData]);
  }

  /**
   * Create corrupted file for error testing
   */
  async createCorruptedFile(fileName: string): Promise<TestFile> {
    const filePath = path.join(this.testDataPath, `corrupted_${fileName}`);

    // Create file with invalid structure
    const corruptedContent = Buffer.from([
      0x00, 0x01, 0x02, 0x03, 0x04, 0x05, // Invalid header
      ...Array(1000).fill(0).map((_, i) => i % 256) // Random data
    ]);

    fs.writeFileSync(filePath, corruptedContent);
    this.tempFiles.push(filePath);

    const type = this.getFileTypeFromName(fileName);

    return {
      name: `corrupted_${fileName}`,
      path: filePath,
      type,
      size: corruptedContent.length,
      content: corruptedContent
    };
  }

  /**
   * Get file type from file name
   */
  private getFileTypeFromName(fileName: string): string {
    const ext = path.extname(fileName).toLowerCase();
    const typeMap: Record<string, string> = {
      '.pdf': 'application/pdf',
      '.txt': 'text/plain',
      '.jpg': 'image/jpeg',
      '.jpeg': 'image/jpeg',
      '.png': 'image/png',
      '.mp3': 'audio/mpeg',
      '.wav': 'audio/wav',
      '.mp4': 'video/mp4',
      '.avi': 'video/avi',
      '.mov': 'video/quicktime'
    };

    return typeMap[ext] || 'application/octet-stream';
  }

  /**
   * Get expected processing stages for file type
   */
  private getExpectedProcessingStages(fileType: string): string[] {
    const stages = ['upload', 'validation', 'embedding', 'indexing'];

    if (fileType.includes('pdf') || fileType.includes('image')) {
      stages.splice(2, 0, 'ocr', 'text_extraction');
    }

    if (fileType.includes('audio')) {
      stages.splice(2, 0, 'transcription', 'text_extraction');
    }

    if (fileType.includes('video')) {
      stages.splice(2, 0, 'frame_extraction', 'transcription', 'text_extraction');
    }

    if (fileType.includes('text')) {
      stages.splice(2, 0, 'text_extraction');
    }

    return stages;
  }

  /**
   * Get batch of test files for comprehensive testing
   */
  async getTestFileBatch(): Promise<TestFile[]> {
    const fileNames = [
      'sample-document.pdf',
      'sample-text.txt',
      'sample-image.jpg',
      'sample-audio.mp3',
      'sample-video.mp4'
    ];

    const files = await Promise.all(
      fileNames.map(name => this.getTestFile(name))
    );

    return files.filter(file => file.size > 0);
  }

  /**
   * Generate random test data
   */
  generateRandomText(length: number = 1000): string {
    const words = [
      'Lorem', 'ipsum', 'dolor', 'sit', 'amet', 'consectetur', 'adipiscing', 'elit',
      'sed', 'do', 'eiusmod', 'tempor', 'incididunt', 'ut', 'labore', 'et', 'dolore',
      'magna', 'aliqua', 'enim', 'ad', 'minim', 'veniam', 'quis', 'nostrud',
      'exercitation', 'ullamco', 'laboris', 'nisi', 'aliquip', 'ex', 'ea', 'commodo'
    ];

    const result = [];
    for (let i = 0; i < length; i++) {
      result.push(words[Math.floor(Math.random() * words.length)]);
    }

    return result.join(' ');
  }

  /**
   * Setup test environment
   */
  async setupTestEnvironment(): Promise<void> {
    // Clear any existing test data
    await this.cleanup();

    // Create necessary test files
    await this.ensureTestFilesExist();

    // Setup test user authentication
    await this.setupTestAuthentication();
  }

  /**
   * Ensure test files exist
   */
  private async ensureTestFilesExist(): Promise<void> {
    const requiredFiles = [
      'sample-document.pdf',
      'sample-text.txt',
      'sample-image.jpg',
      'large-document.pdf'
    ];

    for (const fileName of requiredFiles) {
      const filePath = path.join(this.testDataPath, fileName);
      if (!fs.existsSync(filePath)) {
        await this.createTestFile(fileName);
      }
    }
  }

  /**
   * Setup test authentication
   */
  private async setupTestAuthentication(): Promise<void> {
    // This would typically involve setting up test users in the backend
    // For now, we'll just ensure the test user data is available
    console.log('Test authentication setup completed');
  }

  /**
   * Cleanup test data
   */
  async cleanup(): Promise<void> {
    // Remove temporary files
    for (const filePath of this.tempFiles) {
      try {
        if (fs.existsSync(filePath)) {
          fs.unlinkSync(filePath);
        }
      } catch (error) {
        console.warn(`Could not remove temp file ${filePath}:`, error);
      }
    }

    this.tempFiles = [];

    // Clear any test authentication tokens
    await this.page.evaluate(() => {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user_id');
      localStorage.removeItem('token_expires_at');
    });
  }

  /**
   * Get test user by role
   */
  getTestUser(role: 'user' | 'admin' | 'lab-admin'): TestUser | undefined {
    return Array.from(this.testUsers.values()).find(user => user.role === role);
  }

  /**
   * Get all test users
   */
  getAllTestUsers(): TestUser[] {
    return Array.from(this.testUsers.values());
  }
}