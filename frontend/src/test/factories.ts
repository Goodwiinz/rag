/**
 * Centralized test data factories.
 * Usage: import { createMockDocument, createMockMessage } from '@/test/factories';
 */
import { v4 as uuidv4 } from 'uuid';

// ── Documents ──
export function createMockDocument(overrides: Record<string, unknown> = {}) {
  return {
    id: 'doc-1',
    name: 'Test Document.pdf',
    type: 'pdf',
    size: 1024000,
    status: 'processed',
    uploadDate: '2025-01-18T10:30:00Z',
    processedDate: '2025-01-18T10:35:00Z',
    metadata: {
      pageCount: 10,
      language: 'en',
      extractedText: 'Sample document content for testing',
      entities: ['Test', 'Document'],
      tags: ['test', 'document'],
    },
    ...overrides,
  };
}

// ── Search ──
export function createMockSearchResult(
  overrides: Record<string, unknown> = {}
) {
  return {
    id: 'result-1',
    content: 'Sample search result content',
    score: 0.95,
    source: 'document-1',
    sourceType: 'text',
    metadata: { page: 1, chunk: 1, confidence: 0.95 },
    ...overrides,
  };
}

// ── Users ──
export function createMockUser(overrides: Record<string, unknown> = {}) {
  return {
    id: 'user-1',
    username: 'testuser',
    email: 'test@example.com',
    role: 'user',
    permissions: ['read', 'write'],
    createdAt: '2025-01-01T00:00:00Z',
    lastLogin: '2025-01-18T10:30:00Z',
    ...overrides,
  };
}

// ── Chat Widget ──
export function createMockWidgetMessage(
  overrides: Record<string, unknown> = {}
) {
  return {
    id: `msg-${uuidv4()}`,
    role: 'user' as const,
    content: 'Test message',
    timestamp: new Date('2025-01-18T10:30:00Z'),
    ...overrides,
  };
}

export function createMockContextChip(overrides: Record<string, unknown> = {}) {
  return {
    kind: 'documents' as const,
    label: 'Documents',
    count: 3,
    active: true,
    icon: 'file-text' as const,
    ...overrides,
  };
}

// ── Graph ──
export function createMockGraphData(overrides: Record<string, unknown> = {}) {
  return {
    nodes: [
      {
        id: 'node-1',
        label: 'Test Node',
        type: 'entity',
        properties: { name: 'Test Node', type: 'Person' },
      },
    ],
    edges: [
      {
        id: 'edge-1',
        from: 'node-1',
        to: 'node-2',
        label: 'RELATED_TO',
        weight: 0.8,
      },
    ],
    ...overrides,
  };
}

// ── Evaluation ──
export function createMockEvaluationMetric(
  overrides: Record<string, unknown> = {}
) {
  return {
    name: 'answer_relevancy',
    value: 0.85,
    target: 0.7,
    unit: 'score',
    status: 'good' as const,
    trend: 'improving' as const,
    lastUpdated: '2025-01-18T10:30:00Z',
    history: [
      { timestamp: '2025-01-17T10:30:00Z', value: 0.82 },
      { timestamp: '2025-01-18T10:30:00Z', value: 0.85 },
    ],
    ...overrides,
  };
}

// ── API helpers ──
export function createMockApiResponse(data: unknown, status = 200) {
  return { data, status, statusText: 'OK', headers: {}, config: {} };
}

export function createMockFile(
  name = 'test.pdf',
  type = 'application/pdf',
  size = 1024
) {
  const content = new Array(size).fill('a').join('');
  const file = new File([content], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

// ── Project Chat ──
export function createMockStartChatResponse(
  overrides: Record<string, unknown> = {}
): {
  thread_id: string;
  conversation_id: string;
  project_thread_id: string;
  document_scope: string[];
  [key: string]: unknown;
} {
  return {
    thread_id: 'thread-1',
    conversation_id: 'conv-1',
    project_thread_id: 'pt-1',
    document_scope: ['doc-1', 'doc-2'],
    ...overrides,
  };
}
