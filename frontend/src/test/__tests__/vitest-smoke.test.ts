// frontend/src/test/__tests__/vitest-smoke.test.ts
import { describe, expect, it } from 'vitest';

describe('vitest smoke', () => {
  it('runs basic assertions', () => {
    expect(1 + 1).toBe(2);
  });

  it('can import a TS path alias and resolves to src/, not app/', async () => {
    const mod = await import('@/types/schemas');
    // DocumentSchema is defined in src/types/schemas.ts; if @/* ever
    // silently re-resolves to app/, this assertion catches it.
    expect(mod.DocumentSchema).toBeDefined();
    expect(typeof mod.DocumentSchema.parse).toBe('function');
  });

  it('has a working DOM', () => {
    const el = document.createElement('div');
    el.textContent = 'hello';
    expect(el.textContent).toBe('hello');
  });
});
