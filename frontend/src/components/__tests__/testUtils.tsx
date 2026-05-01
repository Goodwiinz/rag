/**
 * Test utilities for React components
 */

import { vi } from 'vitest';
import React, { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';

// Mock WebSocket for tests
const mockWebSocket = {
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  send: vi.fn(),
  close: vi.fn(),
  readyState: 1,
  CONNECTING: 0,
  OPEN: 1,
  CLOSING: 2,
  CLOSED: 3,
};

// Global WebSocket mock
global.WebSocket = vi.fn(() => mockWebSocket) as any;

// Create a test query client
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });

// Test wrapper with providers
const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  const queryClient = createTestQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {children}
        <Toaster />
      </BrowserRouter>
    </QueryClientProvider>
  );
};

// Custom render function
const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => render(ui, { wrapper: AllTheProviders, ...options });

// Mock data factories
export const createMockDocument = (overrides = {}) => ({
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
    ...overrides,
  },
});

export const createMockSearchResult = (overrides = {}) => ({
  id: 'result-1',
  content: 'Sample search result content',
  score: 0.95,
  source: 'document-1',
  sourceType: 'text',
  metadata: {
    page: 1,
    chunk: 1,
    confidence: 0.95,
    ...overrides,
  },
});

export const createMockUser = (overrides = {}) => ({
  id: 'user-1',
  username: 'testuser',
  email: 'test@example.com',
  role: 'user',
  permissions: ['read', 'write'],
  createdAt: '2025-01-01T00:00:00Z',
  lastLogin: '2025-01-18T10:30:00Z',
  ...overrides,
});

export const createMockGraphData = (overrides = {}) => ({
  nodes: [
    {
      id: 'node-1',
      label: 'Test Node',
      type: 'entity',
      properties: {
        name: 'Test Node',
        type: 'Person',
        ...overrides,
      },
    },
  ],
  edges: [
    {
      id: 'edge-1',
      from: 'node-1',
      to: 'node-2',
      label: 'RELATED_TO',
      weight: 0.8,
      properties: {
        relationship: 'RELATED_TO',
        confidence: 0.8,
        ...overrides,
      },
    },
  ],
});

export const createMockEvaluationMetric = (overrides = {}) => ({
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
});

// Mock API responses
export const createMockApiResponse = (data: any, status = 200) => ({
  data,
  status,
  statusText: 'OK',
  headers: {},
  config: {},
});

// Mock fetch responses
export const mockFetchResponse = (data: any, status = 200) => {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
    headers: new Headers(),
    url: 'http://localhost:8000/api/test',
  });
};

// File mock helpers
export const createMockFile = (
  name = 'test.pdf',
  type = 'application/pdf',
  size = 1024
) => {
  const content = new Array(size).fill('a').join('');
  const file = new File([content], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
};

export const createMockFileList = (files: File[]) => {
  const fileList = {
    length: files.length,
    item: (index: number) => files[index] || null,
    [Symbol.iterator]: function* () {
      for (const file of files) {
        yield file;
      }
    },
  };
  Object.setPrototypeOf(fileList, FileList.prototype);
  return fileList as FileList;
};

// Performance testing utilities
export const createMockPerformanceMetrics = () => ({
  fcp: 1200,
  lcp: 2500,
  fid: 45,
  cls: 0.1,
  ttfb: 300,
  loadTime: 3200,
  domInteractive: 1800,
});

// Error boundary testing utilities
export const createMockError = (
  message = 'Test error',
  stack = 'Error: Test error\n    at test'
) => {
  const error = new Error(message);
  error.stack = stack;
  return error;
};

// Intersection Observer mock
const createMockIntersectionObserver = vi
  .fn()
  .mockImplementation((callback) => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
  }));

global.IntersectionObserver = createMockIntersectionObserver as any;

// Resize Observer mock
const createMockResizeObserver = vi.fn().mockImplementation((callback) => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

global.ResizeObserver = createMockResizeObserver as any;

// Mutation Observer mock
const createMockMutationObserver = vi.fn().mockImplementation((callback) => ({
  observe: vi.fn(),
  disconnect: vi.fn(),
  takeRecords: vi.fn(() => []),
}));

global.MutationObserver = createMockMutationObserver as any;

// Canvas mock
const createMockCanvas = (width = 100, height = 100) => {
  const mockContext2D = {
    canvas: null,
    fillRect: vi.fn(),
    clearRect: vi.fn(),
    getImageData: vi.fn(() => ({
      data: new Array(width * height * 4).fill(0),
      width,
      height,
      colorSpace: 'srgb',
    })),
    putImageData: vi.fn(),
    createImageData: vi.fn(() => ({
      data: new Array(width * height * 4).fill(0),
      width,
      height,
      colorSpace: 'srgb',
    })),
    setTransform: vi.fn(),
    drawImage: vi.fn(),
    save: vi.fn(),
    fillText: vi.fn(),
    restore: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    closePath: vi.fn(),
    stroke: vi.fn(),
    translate: vi.fn(),
    scale: vi.fn(),
    rotate: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    measureText: vi.fn(() => ({
      width: 0,
      actualBoundingBoxLeft: 0,
      actualBoundingBoxRight: 0,
    })),
    transform: vi.fn(),
    rect: vi.fn(),
    // Additional context properties
    globalAlpha: 1,
    globalCompositeOperation: 'source-over',
    strokeStyle: '#000000',
    fillStyle: '#000000',
    lineWidth: 1,
    lineCap: 'butt',
    lineJoin: 'miter',
    miterLimit: 10,
    shadowOffsetX: 0,
    shadowOffsetY: 0,
    shadowBlur: 0,
    shadowColor: 'rgba(0,0,0,0)',
    font: '10px sans-serif',
    textAlign: 'start',
    textBaseline: 'alphabetic',
    direction: 'ltr',
    imageSmoothingEnabled: true,
    // Additional methods
    createLinearGradient: vi.fn(() => ({
      addColorStop: vi.fn(),
    })),
    createRadialGradient: vi.fn(() => ({
      addColorStop: vi.fn(),
    })),
    createPattern: vi.fn(),
    getContextAttributes: vi.fn(() => ({})),
    isPointInPath: vi.fn(),
    isPointInStroke: vi.fn(),
    quadraticCurveTo: vi.fn(),
    bezierCurveTo: vi.fn(),
    arcTo: vi.fn(),
    ellipse: vi.fn(),
    clearHitRegions: vi.fn(),
    drawFocusIfNeeded: vi.fn(),
    createImageData_fromImage: vi.fn(),
    getLineDash: vi.fn(() => []),
    setLineDash: vi.fn(),
    scrollPathIntoView: vi.fn(),
    clip: vi.fn(),
    reset: vi.fn(),
    roundRect: vi.fn(),
    isContextLost: vi.fn(() => false),
    commit: vi.fn(),
    drawWidget: vi.fn(),
    setPath: vi.fn(),
    hitTest: vi.fn(),
  };

  const canvas = {
    width,
    height,
    getContext: vi.fn((contextId) => {
      if (contextId === '2d') return mockContext2D;
      return null;
    }),
    toDataURL: vi.fn(
      () =>
        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=='
    ),
    toBlob: vi.fn(),
    toOffscreen: vi.fn(),
    transferControlToOffscreen: vi.fn(),
    convertToBlob: vi.fn(),
    getContextAttributes: vi.fn(),
    isPointInPath: vi.fn(),
    isPointInStroke: vi.fn(),
    drawFocusIfNeeded: vi.fn(),
    createImageBitmap: vi.fn(),
    // Additional HTMLCanvasElement properties
    style: {},
    className: '',
    id: '',
    innerHTML: '',
    textContent: '',
    parentElement: null,
    parentNode: null,
    appendChild: vi.fn(),
    removeChild: vi.fn(),
    querySelector: vi.fn(),
    querySelectorAll: vi.fn(() => []),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
    getBoundingClientRect: vi.fn(() => ({
      x: 0,
      y: 0,
      width,
      height,
      top: 0,
      left: 0,
      right: width,
      bottom: height,
    })),
    clientWidth: width,
    clientHeight: height,
    offsetWidth: width,
    offsetHeight: height,
    scrollWidth: width,
    scrollHeight: height,
    scrollTop: 0,
    scrollLeft: 0,
    focus: vi.fn(),
    blur: vi.fn(),
    click: vi.fn(),
    cloneNode: vi.fn(),
    hasAttribute: vi.fn(),
    getAttribute: vi.fn(),
    setAttribute: vi.fn(),
    removeAttribute: vi.fn(),
    hasAttributes: vi.fn(),
    getAttributeNames: vi.fn(() => []),
    toggleAttribute: vi.fn(),
    matches: vi.fn(),
    closest: vi.fn(),
    classList: {
      add: vi.fn(),
      remove: vi.fn(),
      contains: vi.fn(),
      toggle: vi.fn(),
    },
    dataset: {},
  };

  mockContext2D.canvas = canvas;
  return canvas as any;
};

// Mock HTMLCanvasElement
global.HTMLCanvasElement = vi.fn(createMockCanvas) as any;

// localStorage mock
const createLocalStorageMock = () => {
  let store: Record<string, string> = {};

  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value.toString();
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    key: vi.fn((index: number) => {
      const keys = Object.keys(store);
      return keys[index] || null;
    }),
    get length() {
      return Object.keys(store).length;
    },
  };
};

Object.defineProperty(window, 'localStorage', {
  value: createLocalStorageMock(),
});

// sessionStorage mock
Object.defineProperty(window, 'sessionStorage', {
  value: createLocalStorageMock(),
});

// Performance API mock
const createMockPerformance = () => ({
  now: vi.fn(() => Date.now()),
  mark: vi.fn(),
  measure: vi.fn(),
  getEntriesByName: vi.fn(() => []),
  getEntriesByType: vi.fn(() => []),
  timing: {
    navigationStart: 0,
    domContentLoadedEventEnd: 1000,
    loadEventEnd: 2000,
    domInteractive: 800,
    responseStart: 300,
  },
  navigation: {
    type: 0,
    redirectCount: 0,
  },
});

Object.defineProperty(window, 'performance', {
  value: createMockPerformance(),
});

// Mock URL constructor
global.URL = {
  createObjectURL: vi.fn(() => 'blob:http://localhost:3000/test-file'),
  revokeObjectURL: vi.fn(),
} as any;

// Mock Blob
global.Blob = class Blob {
  constructor(parts: any[], options: BlobPropertyBag = {}) {
    this.parts = parts;
    this.type = options.type || '';
  }
  parts: any[];
  type: string;
  size = 0;
  stream = vi.fn();
  text = vi.fn();
  arrayBuffer = vi.fn();
  slice = vi.fn();
} as any;

// Mock File
global.File = class File extends Blob {
  constructor(parts: any[], name: string, options: BlobPropertyBag = {}) {
    super(parts, options);
    this.name = name;
    this.lastModified = Date.now();
    this.webkitRelativePath = '';
  }
  name: string;
  lastModified: number;
  webkitRelativePath: string;
} as any;

// Mock FileReader
global.FileReader = class FileReader {
  result: string | ArrayBuffer | null = null;
  error: any = null;
  readyState = 0;
  static EMPTY = 0;
  static LOADING = 1;
  static DONE = 2;
  EMPTY = 0;
  LOADING = 1;
  DONE = 2;
  onload: any = null;
  onerror: any = null;
  onabort: any = null;
  onloadstart: any = null;
  onloadend: any = null;
  onprogress: any = null;

  readAsDataURL = vi.fn(() => {
    this.result = 'data:text/plain;base64,dGVzdA==';
    this.readyState = this.DONE;
    if (this.onload) this.onload({ target: this });
  });

  readAsText = vi.fn(() => {
    this.result = 'test';
    this.readyState = this.DONE;
    if (this.onload) this.onload({ target: this });
  });

  readAsArrayBuffer = vi.fn(() => {
    this.result = new ArrayBuffer(4);
    this.readyState = this.DONE;
    if (this.onload) this.onload({ target: this });
  });

  abort = vi.fn();
} as any;

// Re-export everything
export * from '@testing-library/react';
export { customRender as render };
export { AllTheProviders };
export { mockWebSocket, createTestQueryClient };

// Helper functions for testing
export const waitForElement = (
  selector: string,
  timeout = 5000
): Promise<Element> => {
  return new Promise((resolve, reject) => {
    const element = document.querySelector(selector);
    if (element) {
      resolve(element);
      return;
    }

    const observer = new MutationObserver(() => {
      const element = document.querySelector(selector);
      if (element) {
        observer.disconnect();
        resolve(element);
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });

    setTimeout(() => {
      observer.disconnect();
      reject(new Error(`Element ${selector} not found within ${timeout}ms`));
    }, timeout);
  });
};

export const flushPromises = () =>
  new Promise((resolve) => setTimeout(resolve, 0));

export const act = async (callback: () => void | Promise<void>) => {
  await callback();
  await flushPromises();
};
