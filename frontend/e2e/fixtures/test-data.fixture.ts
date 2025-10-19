import { test as base, Page } from '@playwright/test';
import path from 'path';
import fs from 'fs';

/**
 * Test data fixtures for E2E testing
 *
 * Provides reusable test data, user accounts, and file fixtures
 */

// Test user types
export type UserType = 'valid' | 'admin' | 'premium' | 'trial';

// Test file types
export type FileType = 'pdf' | 'text' | 'image' | 'audio' | 'video' | 'corrupted';

interface TestData {
  users: Record<UserType, {
    email: string;
    password: string;
    name: string;
    role?: string;
  }>;
  files: Record<FileType, {
    path: string;
    name: string;
    type: string;
    size: number;
  }>;
  queries: {
    simple: string[];
    complex: string[];
    multimodal: string[];
    edgeCase: string[];
  };
}

// Extend test with fixtures
type TestFixtures = {
  testData: TestData;
  authenticatedPage: Page;
  tempDir: string;
};

export const test = base.extend<TestFixtures>({
  // Test data fixture
  testData: async ({}, use) => {
    const testData: TestData = {
      users: {
        valid: {
          email: process.env.TEST_USER_EMAIL || 'test@example.com',
          password: process.env.TEST_USER_PASSWORD || 'testpassword123',
          name: 'Test User',
          role: 'user'
        },
        admin: {
          email: process.env.TEST_ADMIN_EMAIL || 'admin@example.com',
          password: process.env.TEST_ADMIN_PASSWORD || 'adminpassword123',
          name: 'Admin User',
          role: 'admin'
        },
        premium: {
          email: 'premium@example.com',
          password: 'premiumuser123',
          name: 'Premium User',
          role: 'premium'
        },
        trial: {
          email: 'trial@example.com',
          password: 'trialuser123',
          name: 'Trial User',
          role: 'trial'
        }
      },
      files: {
        pdf: {
          path: path.join(process.cwd(), 'test-data', 'files', 'sample.pdf'),
          name: 'sample.pdf',
          type: 'application/pdf',
          size: 102400
        },
        text: {
          path: path.join(process.cwd(), 'test-data', 'files', 'sample.txt'),
          name: 'sample.txt',
          type: 'text/plain',
          size: 2048
        },
        image: {
          path: path.join(process.cwd(), 'test-data', 'files', 'sample.jpg'),
          name: 'sample.jpg',
          type: 'image/jpeg',
          size: 51200
        },
        audio: {
          path: path.join(process.cwd(), 'test-data', 'files', 'sample.mp3'),
          name: 'sample.mp3',
          type: 'audio/mpeg',
          size: 204800
        },
        video: {
          path: path.join(process.cwd(), 'test-data', 'files', 'sample.mp4'),
          name: 'sample.mp4',
          type: 'video/mp4',
          size: 1024000
        },
        corrupted: {
          path: path.join(process.cwd(), 'test-data', 'files', 'corrupted.pdf'),
          name: 'corrupted.pdf',
          type: 'application/pdf',
          size: 0
        }
      },
      queries: {
        simple: [
          'What is machine learning?',
          'How does RAG work?',
          'What are the benefits of AI?',
          'Explain neural networks'
        ],
        complex: [
          'Compare and contrast different approaches to information retrieval',
          'What are the ethical implications of large language models?',
          'How do knowledge graphs enhance search capabilities?',
          'Explain the architecture of multimodal AI systems'
        ],
        multimodal: [
          'Find information about the diagrams in the documents',
          'What visual elements are present in the uploaded files?',
          'Analyze the relationship between text and images in the documents',
          'Search for content related to the audio transcripts'
        ],
        edgeCase: [
          '', // Empty query
          ' '.repeat(1000), // Very long query
          '!@#$%^&*()', // Special characters only
          'search for "quoted text" with [brackets] and {braces}', // Complex syntax
          'a'.repeat(500), // Repeated character
          '🚀🔍📚', // Emojis only
        ]
      }
    };

    // Ensure test files exist
    await ensureTestFiles(testData.files);

    await use(testData);
  },

  // Authenticated page fixture
  authenticatedPage: async ({ page, testData }, use) => {
    await loginAsUser(page, testData.users.valid);
    await use(page);
  },

  // Temporary directory fixture
  tempDir: async ({}, use) => {
    const tempDir = path.join(process.cwd(), 'test-data', 'temp', `test-${Date.now()}`);
    fs.mkdirSync(tempDir, { recursive: true });

    await use(tempDir);

    // Cleanup
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

/**
 * Ensure test files exist, create them if necessary
 */
async function ensureTestFiles(files: TestData['files']) {
  const filesDir = path.join(process.cwd(), 'test-data', 'files');

  // Create files directory if it doesn't exist
  if (!fs.existsSync(filesDir)) {
    fs.mkdirSync(filesDir, { recursive: true });
  }

  // Create sample files if they don't exist
  for (const [fileType, fileInfo] of Object.entries(files)) {
    const filePath = fileInfo.path;

    if (!fs.existsSync(filePath)) {
      console.log(`📄 Creating sample ${fileType} file: ${filePath}`);

      switch (fileType) {
        case 'text':
          fs.writeFileSync(filePath, 'This is a sample text file for E2E testing.\nIt contains multiple lines of text.\nThis content will be used for testing document ingestion and search functionality.');
          break;

        case 'pdf':
          // Create a simple PDF placeholder (in real implementation, you'd use a PDF library)
          fs.writeFileSync(filePath, Buffer.from('%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n72 720 Td\n(Sample PDF Content) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000123 00000 n\n0000000201 00000 n\ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n299\n%%EOF'));
          break;

        case 'image':
          // Create a simple image placeholder (in real implementation, you'd use an image library)
          fs.writeFileSync(filePath, Buffer.from('data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k='));
          break;

        case 'audio':
        case 'video':
        case 'corrupted':
          // Create empty placeholder files for media and corrupted files
          fs.writeFileSync(filePath, '');
          break;
      }
    }
  }
}

/**
 * Login as a specific user
 */
async function loginAsUser(page: Page, user: TestData['users'][UserType]) {
  try {
    // Navigate to login page
    await page.goto('/login');

    // Fill login form
    await page.fill('[data-testid="email-input"]', user.email);
    await page.fill('[data-testid="password-input"]', user.password);

    // Submit form
    await page.click('[data-testid="login-button"]');

    // Wait for successful login - check for redirect to dashboard or home
    await page.waitForURL('/', { timeout: 10000 });

    // Verify login was successful
    const welcomeText = await page.locator('[data-testid="welcome-message"]').first().textContent();
    if (welcomeText && !welcomeText.toLowerCase().includes(user.name.toLowerCase())) {
      throw new Error(`Login failed for user ${user.email}`);
    }

    console.log(`✅ Logged in as ${user.name} (${user.email})`);

  } catch (error) {
    // Check if we're already logged in
    const currentUrl = page.url();
    if (currentUrl.includes('/dashboard') || currentUrl === '/') {
      console.log(`ℹ️ Already logged in as ${user.email}`);
      return;
    }
    throw new Error(`Failed to login as ${user.email}: ${error.message}`);
  }
}

/**
 * Logout current user
 */
export async function logout(page: Page) {
  try {
    await page.click('[data-testid="user-menu"]');
    await page.click('[data-testid="logout-button"]');
    await page.waitForURL('/login');
    console.log('✅ Logged out successfully');
  } catch (error) {
    console.warn('⚠️ Could not logout:', error.message);
  }
}

/**
 * Upload a file and wait for processing
 */
export async function uploadFile(page: Page, filePath: string, fileName: string) {
  // Navigate to documents page
  await page.goto('/documents');

  // Handle file upload
  const fileInput = page.locator('[data-testid="file-input"]');
  await fileInput.setInputFiles(filePath);

  // Wait for upload to complete
  await page.waitForSelector(`[data-testid="file-${fileName}"]`, { timeout: 30000 });

  // Wait for processing to complete (or timeout after reasonable time)
  try {
    await page.waitForSelector(`[data-testid="file-${fileName}"][data-status="processed"]`, { timeout: 60000 });
  } catch (error) {
    console.warn(`⚠️ File ${fileName} may still be processing`);
  }

  return page.locator(`[data-testid="file-${fileName}"]`);
}

/**
 * Perform a search and wait for results
 */
export async function performSearch(page: Page, query: string) {
  // Navigate to search page
  await page.goto('/search');

  // Enter search query
  await page.fill('[data-testid="search-input"]', query);

  // Submit search
  await page.click('[data-testid="search-button"]');

  // Wait for results to load
  await page.waitForSelector('[data-testid="search-results"]', { timeout: 15000 });

  return page.locator('[data-testid="search-results"]');
}

export { expect } from '@playwright/test';