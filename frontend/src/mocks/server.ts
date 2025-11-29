/**
 * Mock server for API testing using MSW (Mock Service Worker) v2
 */

import { setupServer } from 'msw/node';
import { http, HttpResponse, delay } from 'msw';

// Mock data generators
const createMockDocument = (id: string) => ({
  id,
  name: `Document ${id}.pdf`,
  type: 'pdf',
  size: 1024000,
  status: 'processed',
  uploadDate: '2025-01-18T10:30:00Z',
  processedDate: '2025-01-18T10:35:00Z',
  metadata: {
    pageCount: 10,
    language: 'en',
    extractedText: `Sample content for document ${id}`,
    entities: ['Test', 'Document', 'Sample'],
    tags: ['test', 'document'],
  }
});

const createMockSearchResult = (id: string) => ({
  id: `result-${id}`,
  content: `Sample search result content ${id}`,
  score: 0.85 + Math.random() * 0.1,
  source: `document-${id}`,
  sourceType: 'text',
  metadata: {
    page: 1,
    chunk: 1,
    confidence: 0.9,
    timestamp: '2025-01-18T10:30:00Z',
  }
});

const createMockEvaluationMetric = (name: string) => ({
  name,
  value: 0.7 + Math.random() * 0.3,
  target: 0.8,
  unit: 'score',
  status: 'good' as const,
  trend: 'improving' as const,
  lastUpdated: '2025-01-18T10:30:00Z',
  history: Array.from({ length: 7 }, (_, i) => ({
    timestamp: new Date(Date.now() - (6 - i) * 24 * 60 * 60 * 1000).toISOString(),
    value: 0.7 + Math.random() * 0.3,
  })),
});

export const handlers = [
  // Document upload endpoints
  http.post('/api/documents/upload', async ({ request }) => {
    const body = await request.json() as { files: any[] };
    const { files } = body;

    // Simulate processing delay
    await delay(1000);

    return HttpResponse.json({
      success: true,
      documents: files.map((file: any, index: number) => ({
        id: `doc-${Date.now()}-${index}`,
        name: file.name,
        status: 'processing',
        uploadDate: new Date().toISOString(),
      }))
    });
  }),

  http.post('/api/documents/validate', async ({ request }) => {
    const body = await request.json() as { file: { name: string; size: number } };
    const { file } = body;

    // Simulate validation logic
    const isValidFile =
      file.name.endsWith('.pdf') ||
      file.name.endsWith('.txt') ||
      file.name.endsWith('.docx') ||
      file.name.endsWith('.jpg') ||
      file.name.endsWith('.png') ||
      file.name.endsWith('.mp3') ||
      file.name.endsWith('.mp4');

    if (!isValidFile) {
      return HttpResponse.json(
        {
          valid: false,
          message: 'Invalid file type',
        },
        { status: 400 }
      );
    }

    if (file.size > 50 * 1024 * 1024) { // 50MB limit
      return HttpResponse.json(
        {
          valid: false,
          message: 'File too large',
        },
        { status: 400 }
      );
    }

    await delay(500);
    return HttpResponse.json({
      valid: true,
      message: 'File is valid',
    });
  }),

  http.get('/api/documents/:id/status', async ({ params }) => {
    const { id } = params;

    // Simulate different statuses based on ID
    const statusMap: Record<string, string> = {
      'processing': 'processing',
      'completed': 'processed',
      'failed': 'failed',
    };

    const idString = Array.isArray(id) ? id[0] : id;
    const idParts = idString?.split('-') || [];
    const status = statusMap[idParts[1]] || 'processing';

    if (status === 'failed') {
      return HttpResponse.json(
        {
          status: 'failed',
          error: 'Processing failed',
        },
        { status: 500 }
      );
    }

    await delay(2000);
    return HttpResponse.json({
      status,
      progress: status === 'completed' ? 100 : Math.floor(Math.random() * 100),
      stage: status === 'processing' ? 'ocr' : null,
    });
  }),

  http.get('/api/documents', ({ request }) => {
    const url = new URL(request.url);
    const page = Number(url.searchParams.get('page')) || 1;
    const limit = Number(url.searchParams.get('limit')) || 10;
    const search = url.searchParams.get('search');
    const type = url.searchParams.get('type');

    // Generate mock documents
    const documents = Array.from({ length: 20 }, (_, i) => createMockDocument(`doc-${i + 1}`));

    // Apply filters
    let filteredDocuments = documents;

    if (search) {
      filteredDocuments = filteredDocuments.filter(doc =>
        doc.name.toLowerCase().includes((search as string).toLowerCase())
      );
    }

    if (type) {
      filteredDocuments = filteredDocuments.filter(doc => doc.type === type);
    }

    // Apply pagination
    const startIndex = (Number(page) - 1) * Number(limit);
    const paginatedDocuments = filteredDocuments.slice(startIndex, startIndex + Number(limit));

    return HttpResponse.json({
      documents: paginatedDocuments,
      total: filteredDocuments.length,
      page: Number(page),
      limit: Number(limit),
      totalPages: Math.ceil(filteredDocuments.length / Number(limit)),
    });
  }),

  http.get('/api/documents/:id', ({ params }) => {
    const { id } = params;
    const idString = Array.isArray(id) ? id[0] : id || '';
    return HttpResponse.json(createMockDocument(idString));
  }),

  http.delete('/api/documents/:id', ({ params }) => {
    const { id } = params;
    const idString = Array.isArray(id) ? id[0] : id || '';
    return HttpResponse.json({
      success: true,
      message: `Document ${idString} deleted successfully`,
    });
  }),

  // Search endpoints
  http.post('/api/search', async ({ request }) => {
    const body = await request.json() as { query: string; filters?: any; limit?: number; offset?: number };
    const { query, filters = {}, limit = 10, offset = 0 } = body;

    if (!query || query.trim().length === 0) {
      return HttpResponse.json(
        {
          error: 'Query is required',
        },
        { status: 400 }
      );
    }

    // Generate mock search results
    const results = Array.from({ length: 5 }, (_, i) => createMockSearchResult(String(i + 1)));

    // Apply filters
    let filteredResults = results;

    if (filters.fileType) {
      filteredResults = filteredResults.filter(result =>
        result.sourceType === filters.fileType
      );
    }

    if (filters.dateRange) {
      // Mock date filtering logic
      filteredResults = filteredResults.slice(0, 3);
    }

    await delay(800);
    return HttpResponse.json({
      results: filteredResults.slice(Number(offset), Number(offset) + Number(limit)),
      total: filteredResults.length,
      query,
      filters,
      processingTime: Math.random() * 1000 + 500,
    });
  }),

  http.get('/api/search/suggestions', ({ request }) => {
    const url = new URL(request.url);
    const q = url.searchParams.get('q');

    if (!q) {
      return HttpResponse.json([]);
    }

    const suggestions = [
      `${q} related terms`,
      `${q} examples`,
      `${q} best practices`,
      `${q} tutorial`,
    ];

    return HttpResponse.json(suggestions);
  }),

  http.get('/api/search/history', () => {
    const history = [
      { id: 'hist-1', query: 'previous search 1', timestamp: '2025-01-17T10:30:00Z', results: 15 },
      { id: 'hist-2', query: 'previous search 2', timestamp: '2025-01-16T15:45:00Z', results: 8 },
      { id: 'hist-3', query: 'previous search 3', timestamp: '2025-01-15T09:20:00Z', results: 12 },
    ];

    return HttpResponse.json(history);
  }),

  // Knowledge Graph endpoints
  http.get('/api/graph/nodes', ({ request }) => {
    const url = new URL(request.url);
    const search = url.searchParams.get('search');
    const type = url.searchParams.get('type');
    const limit = Number(url.searchParams.get('limit')) || 50;

    const nodes = Array.from({ length: 20 }, (_, i) => ({
      id: `node-${i + 1}`,
      label: `Entity ${i + 1}`,
      type: type || ['Person', 'Organization', 'Location', 'Event'][i % 4],
      properties: {
        importance: Math.random(),
        frequency: Math.floor(Math.random() * 100),
        lastSeen: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
      },
    }));

    let filteredNodes = nodes;

    if (search) {
      filteredNodes = filteredNodes.filter(node =>
        node.label.toLowerCase().includes((search as string).toLowerCase())
      );
    }

    return HttpResponse.json({
      nodes: filteredNodes.slice(0, Number(limit)),
      total: filteredNodes.length,
    });
  }),

  http.get('/api/graph/relationships', ({ request }) => {
    const url = new URL(request.url);
    const nodeId = url.searchParams.get('nodeId');

    const relationships = Array.from({ length: 5 }, (_, i) => ({
      id: `rel-${i + 1}`,
      from: nodeId || `node-${i + 1}`,
      to: `node-${i + 2}`,
      type: ['RELATED_TO', 'WORKS_AT', 'LOCATED_IN', 'PARTICIPATED_IN'][i % 4],
      weight: Math.random(),
      properties: {
        confidence: Math.random(),
        source: 'automatic',
        timestamp: new Date().toISOString(),
      },
    }));

    return HttpResponse.json({ relationships });
  }),

  http.get('/api/graph/metrics', () => {
    return HttpResponse.json({
      totalNodes: 1250,
      totalRelationships: 3400,
      nodeTypes: {
        Person: 450,
        Organization: 200,
        Location: 300,
        Event: 200,
        Other: 100,
      },
      relationshipTypes: {
        RELATED_TO: 1200,
        WORKS_AT: 800,
        LOCATED_IN: 600,
        PARTICIPATED_IN: 800,
      },
      avgNodeDegree: 5.4,
      graphDensity: 0.0043,
    });
  }),

  // Evaluation endpoints
  http.get('/api/evaluation/metrics', () => {
    const metrics = [
      createMockEvaluationMetric('answer_relevancy'),
      createMockEvaluationMetric('faithfulness'),
      createMockEvaluationMetric('contextual_relevancy'),
      createMockEvaluationMetric('response_time'),
      createMockEvaluationMetric('user_satisfaction'),
    ];

    return HttpResponse.json({
      metrics,
      overallScore: 0.82,
      lastUpdated: new Date().toISOString(),
    });
  }),

  http.get('/api/evaluation/trends', ({ request }) => {
    const url = new URL(request.url);
    const metric = url.searchParams.get('metric');
    const period = url.searchParams.get('period') || '7d';

    const trends = {
      answer_relevancy: Array.from({ length: 7 }, (_, i) => ({
        timestamp: new Date(Date.now() - (6 - i) * 24 * 60 * 60 * 1000).toISOString(),
        value: 0.7 + Math.random() * 0.3,
      })),
      faithfulness: Array.from({ length: 7 }, (_, i) => ({
        timestamp: new Date(Date.now() - (6 - i) * 24 * 60 * 60 * 1000).toISOString(),
        value: 0.8 + Math.random() * 0.2,
      })),
    };

    return HttpResponse.json(metric && trends[metric as keyof typeof trends] ? trends[metric as keyof typeof trends] : trends.answer_relevancy);
  }),

  http.post('/api/evaluation/run', async ({ request }) => {
    const body = await request.json() as { testSuite: string; config: any };
    const { testSuite, config } = body;

    // Simulate evaluation run
    await delay(3000);
    return HttpResponse.json({
      status: 'completed',
      testSuite,
      results: {
        overallScore: 0.85,
        metrics: [
          { name: 'answer_relevancy', score: 0.87, improvement: 0.03 },
          { name: 'faithfulness', score: 0.92, improvement: 0.02 },
        ],
        recommendations: [
          'Improve contextual relevancy by enhancing entity extraction',
          'Consider adding more diverse test cases',
        ],
        timestamp: new Date().toISOString(),
      }
    });
  }),

  http.get('/api/evaluation/test-suites', () => {
    const testSuites = [
      {
        id: 'suite-1',
        name: 'Core RAG Tests',
        description: 'Basic RAG functionality tests',
        lastRun: '2025-01-18T10:30:00Z',
        status: 'passed',
        score: 0.88,
        duration: 45,
        tests: [
          { id: 'test-1', name: 'Answer Relevancy Test', status: 'passed', score: 0.85 },
          { id: 'test-2', name: 'Faithfulness Test', status: 'passed', score: 0.92 },
          { id: 'test-3', name: 'Contextual Relevancy Test', status: 'failed', score: 0.65 },
        ],
      },
      {
        id: 'suite-2',
        name: 'Performance Tests',
        description: 'Performance and scalability tests',
        lastRun: '2025-01-17T15:45:00Z',
        status: 'warning',
        score: 0.75,
        duration: 120,
        tests: [
          { id: 'test-4', name: 'Response Time Test', status: 'passed', score: 0.80 },
          { id: 'test-5', name: 'Load Test', status: 'warning', score: 0.70 },
        ],
      },
    ];

    return HttpResponse.json({ testSuites });
  }),

  http.post('/api/evaluation/export', async ({ request }) => {
    const body = await request.json() as { format?: string; dateRange?: any };
    const { format = 'csv', dateRange } = body;

    await delay(1000);
    return HttpResponse.json({
      downloadUrl: `/downloads/evaluation-report-${new Date().toISOString().split('T')[0]}.${format}`,
      format,
      dateRange,
      expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
    });
  }),

  // User authentication endpoints
  http.post('/api/auth/login', async ({ request }) => {
    const body = await request.json() as { username: string; password: string };
    const { username, password } = body;

    if (username === 'test@example.com' && password === 'password') {
      return HttpResponse.json({
        success: true,
        user: {
          id: 'user-1',
          username: 'test@example.com',
          email: 'test@example.com',
          role: 'user',
          permissions: ['read', 'write'],
        },
        token: 'mock-jwt-token',
        expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
      });
    }

    return HttpResponse.json(
      {
        success: false,
        error: 'Invalid credentials',
      },
      { status: 401 }
    );
  }),

  http.post('/api/auth/logout', () => {
    return HttpResponse.json({
      success: true,
      message: 'Logged out successfully',
    });
  }),

  http.get('/api/auth/user', ({ request }) => {
    const token = request.headers.get('authorization')?.replace('Bearer ', '');

    if (token === 'mock-jwt-token') {
      return HttpResponse.json({
        id: 'user-1',
        username: 'test@example.com',
        email: 'test@example.com',
        role: 'user',
        permissions: ['read', 'write'],
      });
    }

    return HttpResponse.json(
      {
        error: 'Invalid token',
      },
      { status: 401 }
    );
  }),

  // WebSocket connection mock (for real-time updates)
  http.get('/api/ws', () => {
    return HttpResponse.json({
      message: 'WebSocket connection endpoint',
      connected: true,
    });
  }),

  // Error handling - catch-all for unhandled routes
  http.all('/api/*', ({ request }) => {
    const url = new URL(request.url);
    return HttpResponse.json(
      {
        error: 'Endpoint not found',
        path: url.pathname,
      },
      { status: 404 }
    );
  }),
];

export const server = setupServer(...handlers);
