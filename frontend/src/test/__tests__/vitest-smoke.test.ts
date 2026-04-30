// frontend/src/test/__tests__/vitest-smoke.test.ts
import { describe, expect, it } from 'vitest';

describe('vitest smoke', () => {
  it('runs basic assertions', () => {
    expect(1 + 1).toBe(2);
  });

  it('can import a TS path alias', async () => {
    // tsconfig has @/* → src/* — proves vite-tsconfig-paths is wired
    const mod = await import('@/types/schemas');
    expect(typeof mod).toBe('object');
  });

  it('has a working DOM', () => {
    const el = document.createElement('div');
    el.textContent = 'hello';
    expect(el.textContent).toBe('hello');
  });
});
