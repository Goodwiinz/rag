/**
 * Test setup file for Jest
 */

import '@testing-library/jest-dom';
import { configure } from '@testing-library/react';
import { server } from './mocks/server';

// Configure React Testing Library
configure({ testIdAttribute: 'data-testid' });

// Establish API mocking before all tests
beforeAll(() => server.listen());

// Reset any request handlers that we may add during the tests,
// so they don't affect other tests.
afterEach(() => server.resetHandlers());

// Clean up after all tests are complete
afterAll(() => server.close());

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(), // deprecated
    removeListener: jest.fn(), // deprecated
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// Mock window.getComputedStyle
Object.defineProperty(window, 'getComputedStyle', {
  value: () => ({
    getPropertyValue: () => '',
    ...({
      appearance: ['-webkit-appearance'],
    }),
  }),
});

// Mock ResizeObserver
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Mock IntersectionObserver
global.IntersectionObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Mock fetch globally
global.fetch = jest.fn();

// Mock TextEncoder/TextDecoder
global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;

// Mock URL.createObjectURL and URL.revokeObjectURL
global.URL.createObjectURL = jest.fn(() => 'mocked-url');
global.URL.revokeObjectURL = jest.fn();

// Mock File and FileReader
global.File = class File {
  constructor(chunks: any[], filename: string, options: any = {}) {
    this.chunks = chunks;
    this.name = filename;
    this.size = chunks.reduce((acc: number, chunk: any) => acc + chunk.length, 0);
    this.type = options.type || '';
    this.lastModified = Date.now();
    this.webkitRelativePath = '';
  }
  chunks: any[];
  name: string;
  size: number;
  type: string;
  lastModified: number;
  webkitRelativePath: string;

  slice(): Blob {
    return this;
  }

  stream(): ReadableStream {
    return new ReadableStream({
      start(controller) {
        controller.enqueue(new Uint8Array(this.chunks));
        controller.close();
      }
    });
  }

  text(): Promise<string> {
    return Promise.resolve(this.chunks.join(''));
  }

  arrayBuffer(): Promise<ArrayBuffer> {
    return Promise.resolve(new ArrayBuffer(this.size));
  }
} as any;

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

  onload: ((event: any) => void) | null = null;
  onerror: ((event: any) => void) | null = null;
  onloadstart: ((event: any) => void) | null = null;
  onloadend: ((event: any) => void) | null = null;
  onprogress: ((event: any) => void) | null = null;
  onabort: ((event: any) => void) | null = null;

  readAsDataURL(blob: Blob): void {
    this.readyState = this.LOADING;
    setTimeout(() => {
      this.result = `data:${blob.type};base64,${btoa('test')}`;
      this.readyState = this.DONE;
      if (this.onload) this.onload({ target: this } as any);
    }, 0);
  }

  readAsText(blob: Blob): void {
    this.readyState = this.LOADING;
    setTimeout(() => {
      this.result = 'test';
      this.readyState = this.DONE;
      if (this.onload) this.onload({ target: this } as any);
    }, 0);
  }

  readAsArrayBuffer(blob: Blob): void {
    this.readyState = this.LOADING;
    setTimeout(() => {
      this.result = new ArrayBuffer(blob.size);
      this.readyState = this.DONE;
      if (this.onload) this.onload({ target: this } as any);
    }, 0);
  }

  abort(): void {
    this.readyState = this.DONE;
    if (this.onabort) this.onabort({ target: this } as any);
  }
} as any;

// Mock WebSocket
const webSocketMock = jest.fn().mockImplementation(() => ({
  readyState: 1,
  url: 'ws://localhost:8000/ws',
  protocol: '',
  extensions: '',
  binaryType: 'blob',
  bufferedAmount: 0,
  send: jest.fn(),
  close: jest.fn(),
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  dispatchEvent: jest.fn(),
  onopen: null,
  onclose: null,
  onmessage: null,
  onerror: null,
}));

Object.assign(webSocketMock, {
  CONNECTING: 0,
  OPEN: 1,
  CLOSING: 2,
  CLOSED: 3
});

global.WebSocket = webSocketMock as any;

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
  key: jest.fn(),
  length: 0,
};
Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
  writable: true,
});

// Mock sessionStorage
Object.defineProperty(window, 'sessionStorage', {
  value: localStorageMock,
  writable: true,
});

// Mock navigator
Object.defineProperty(window, 'navigator', {
  value: {
    userAgent: 'Mozilla/5.0 (Test Browser)',
    clipboard: {
      writeText: jest.fn(),
      readText: jest.fn().mockResolvedValue(''),
    },
  },
  writable: true,
});

// Mock location
Object.defineProperty(window, 'location', {
  value: {
    href: 'http://localhost:3000',
    origin: 'http://localhost:3000',
    protocol: 'http:',
    host: 'localhost:3000',
    hostname: 'localhost',
    port: '3000',
    pathname: '/',
    search: '',
    hash: '',
  },
  writable: true,
});

// Mock performance
Object.defineProperty(window, 'performance', {
  value: {
    now: jest.fn(() => Date.now()),
    mark: jest.fn(),
    measure: jest.fn(),
    getEntriesByName: jest.fn(() => []),
    getEntriesByType: jest.fn(() => []),
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
  },
  writable: true,
});

// Mock crypto for UUID generation
Object.defineProperty(global, 'crypto', {
  value: {
    randomUUID: jest.fn(() => 'test-uuid-' + Math.random().toString(36).substr(2, 9)),
    getRandomValues: jest.fn(() => new Uint8Array(16)),
  },
  writable: true,
});

// Mock Canvas for components that use it
HTMLCanvasElement.prototype.getContext = jest.fn(() => ({
  canvas: document.createElement('canvas'),
  fillRect: jest.fn(),
  clearRect: jest.fn(),
  getImageData: jest.fn(() => ({
    data: new Array(4).fill(0),
    width: 1,
    height: 1,
    colorSpace: 'srgb'
  })),
  putImageData: jest.fn(),
  createImageData: jest.fn(() => ({
    data: new Array(4).fill(0),
    width: 1,
    height: 1,
    colorSpace: 'srgb'
  })),
  setTransform: jest.fn(),
  drawImage: jest.fn(),
  save: jest.fn(),
  fillText: jest.fn(),
  restore: jest.fn(),
  beginPath: jest.fn(),
  moveTo: jest.fn(),
  lineTo: jest.fn(),
  closePath: jest.fn(),
  stroke: jest.fn(),
  translate: jest.fn(),
  scale: jest.fn(),
  rotate: jest.fn(),
  arc: jest.fn(),
  fill: jest.fn(),
  measureText: jest.fn(() => ({ width: 0, actualBoundingBoxLeft: 0, actualBoundingBoxRight: 0 })),
  transform: jest.fn(),
  rect: jest.fn(),
  clip: jest.fn(),
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
}));

// Suppress console warnings during tests
const originalError = console.error;
const originalWarn = console.warn;

beforeEach(() => {
  console.error = jest.fn();
  console.warn = jest.fn();
});

afterEach(() => {
  console.error = originalError;
  console.warn = originalWarn;
});

// Add custom matchers for better assertions
expect.extend({
  toBeInTheDocument: (received) => {
    const pass = received && document.body.contains(received);
    if (pass) {
      return {
        message: () =>
          `expected element not to be in the document`,
        pass: true,
      };
    } else {
      return {
        message: () =>
          `expected element to be in the document`,
        pass: false,
      };
    }
  },
});

// Mock process.env for testing
process.env = {
  ...process.env,
  NODE_ENV: 'test',
};