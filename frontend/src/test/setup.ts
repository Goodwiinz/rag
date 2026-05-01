// frontend/src/test/setup.ts
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
import { TextEncoder, TextDecoder } from 'util';
import { TransformStream as WebTransformStream } from 'node:stream/web';

// `@testing-library/react`'s automatic cleanup only fires when test globals
// are present (Jest's `afterEach`). Vitest is configured with
// `globals: false`, so the library never registers. Run cleanup explicitly
// after every test — without this, every test leaks its rendered DOM into
// the next, breaking `getByRole(...)` queries that expect a unique match.
afterEach(() => {
  cleanup();
});

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

// jsdom doesn't implement matchMedia / IntersectionObserver / ResizeObserver.
// Several UI libs (Radix, framer-motion, virtualizers) read these at module
// scope, so polyfilling globally beats per-test setup.
if (typeof window !== 'undefined' && typeof window.matchMedia !== 'function') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

class MockIntersectionObserver {
  readonly root: Element | null = null;
  readonly rootMargin: string = '';
  readonly thresholds: ReadonlyArray<number> = [];
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

class MockResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

const gObservers = globalThis as unknown as {
  IntersectionObserver?: typeof globalThis.IntersectionObserver;
  ResizeObserver?: typeof globalThis.ResizeObserver;
};
if (typeof gObservers.IntersectionObserver === 'undefined') {
  gObservers.IntersectionObserver =
    MockIntersectionObserver as unknown as typeof globalThis.IntersectionObserver;
}
if (typeof gObservers.ResizeObserver === 'undefined') {
  gObservers.ResizeObserver =
    MockResizeObserver as unknown as typeof globalThis.ResizeObserver;
}

// Mirror existing Supabase test env behavior from src/setupTests.ts.
// Without this the Supabase client module throws at import in tests.
if (!process.env.NEXT_PUBLIC_SUPABASE_URL) {
  process.env.NEXT_PUBLIC_SUPABASE_URL = 'http://localhost:54321';
}
if (!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY) {
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'test-anon-key';
}
