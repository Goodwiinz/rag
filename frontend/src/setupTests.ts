import '@testing-library/jest-dom';
import { TextEncoder, TextDecoder } from 'util';
import { TransformStream as WebTransformStream } from 'node:stream/web';

Object.assign(global, { TextEncoder, TextDecoder });

type PerformanceObserverLike = new () => {
  observe(): void;
  disconnect(): void;
};

const globalWithPolyfills = globalThis as typeof globalThis & {
  TransformStream?: typeof WebTransformStream;
  PerformanceObserver?: PerformanceObserverLike;
};

// Polyfills/mocks for browser APIs missing in JSDOM/Node
// TransformStream (Node 18+ has it under node:stream/web)
try {
  if (typeof globalWithPolyfills.TransformStream === 'undefined') {
    globalWithPolyfills.TransformStream = WebTransformStream;
  }
} catch {}

// PerformanceObserver
if (typeof globalWithPolyfills.PerformanceObserver === 'undefined') {
  globalWithPolyfills.PerformanceObserver = class {
    observe(): void {/* no-op */}
    disconnect(): void {/* no-op */}
  };
}

// Helpful jest mocks
// next/navigation and next/router mocks can be added here if needed
