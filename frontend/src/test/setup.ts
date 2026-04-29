// frontend/src/test/setup.ts
import '@testing-library/jest-dom/vitest';
import { TextEncoder, TextDecoder } from 'util';
import { TransformStream as WebTransformStream } from 'node:stream/web';

// Polyfills missing in jsdom
Object.assign(globalThis, { TextEncoder, TextDecoder });

const g = globalThis as unknown as {
  TransformStream?: typeof globalThis.TransformStream;
  PerformanceObserver?: typeof globalThis.PerformanceObserver;
};

if (typeof g.TransformStream === 'undefined') {
  g.TransformStream =
    WebTransformStream as unknown as typeof globalThis.TransformStream;
}

if (typeof g.PerformanceObserver === 'undefined') {
  class MockPerformanceObserver {
    static readonly supportedEntryTypes: string[] = [];
    observe(): void {}
    disconnect(): void {}
    takeRecords(): PerformanceEntryList {
      return [];
    }
  }
  g.PerformanceObserver =
    MockPerformanceObserver as unknown as typeof globalThis.PerformanceObserver;
}

// Mirror existing Supabase test env behavior from src/setupTests.ts.
// Without this the Supabase client module throws at import in tests.
if (!process.env.NEXT_PUBLIC_SUPABASE_URL) {
  process.env.NEXT_PUBLIC_SUPABASE_URL = 'http://localhost:54321';
}
if (!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY) {
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'test-anon-key';
}
