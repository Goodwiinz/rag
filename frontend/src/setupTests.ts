import '@testing-library/jest-dom';
import { TextEncoder, TextDecoder } from 'util';

Object.assign(global, { TextEncoder, TextDecoder });

// Polyfills/mocks for browser APIs missing in JSDOM/Node
// TransformStream (Node 18+ has it under node:stream/web)
try {
  if (typeof (global as any).TransformStream === 'undefined') {
    const WebStream = require('node:stream/web');
    (global as any).TransformStream = WebStream.TransformStream || class {};
  }
} catch {}

// PerformanceObserver
if (typeof (global as any).PerformanceObserver === 'undefined') {
  (global as any).PerformanceObserver = class {
    observe() {/* no-op */}
    disconnect() {/* no-op */}
  } as any;
}

// Helpful jest mocks
// next/navigation and next/router mocks can be added here if needed
