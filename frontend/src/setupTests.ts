import '@testing-library/jest-dom';
import { TextEncoder, TextDecoder } from 'util';
import { TransformStream as WebTransformStream } from 'node:stream/web';

Object.assign(global, { TextEncoder, TextDecoder });

const globalWithPolyfills = globalThis as typeof globalThis & {
  TransformStream?: typeof globalThis.TransformStream;
  PerformanceObserver?: typeof globalThis.PerformanceObserver;
};

// Polyfills/mocks for browser APIs missing in JSDOM/Node
// TransformStream (Node 18+ has it under node:stream/web)
try {
  if (typeof globalWithPolyfills.TransformStream === 'undefined') {
    globalWithPolyfills.TransformStream =
      WebTransformStream as unknown as typeof globalThis.TransformStream;
  }
} catch {}

// PerformanceObserver
if (typeof globalWithPolyfills.PerformanceObserver === 'undefined') {
  class MockPerformanceObserver {
    static readonly supportedEntryTypes: string[] = [];

    observe(): void {/* no-op */}
    disconnect(): void {/* no-op */}
    takeRecords(): PerformanceEntryList { return []; }
  }

  globalWithPolyfills.PerformanceObserver =
    MockPerformanceObserver as unknown as typeof globalThis.PerformanceObserver;
}

// Helpful jest mocks
// next/navigation and next/router mocks can be added here if needed
