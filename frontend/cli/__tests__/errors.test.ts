/**
 * @jest-environment node
 */
import { classifyError } from '../errors';

describe('classifyError — network', () => {
  test('Error with code ECONNREFUSED → network, retryable', () => {
    const err = Object.assign(new Error('connect ECONNREFUSED'), {
      code: 'ECONNREFUSED',
    });
    const c = classifyError(err);
    expect(c.kind).toBe('network');
    expect(c.retryable).toBe(true);
    expect(c.userMessage).toMatch(/not reachable/i);
  });

  test('Error message containing "fetch failed" → network', () => {
    const c = classifyError(new Error('fetch failed'));
    expect(c.kind).toBe('network');
    expect(c.retryable).toBe(true);
  });

  test('nested cause with ECONNREFUSED → network', () => {
    const err = Object.assign(new Error('wrapped'), {
      cause: { code: 'ECONNREFUSED' },
    });
    expect(classifyError(err).kind).toBe('network');
  });
});

describe('classifyError — auth', () => {
  test('"Not logged in" → auth, not retryable', () => {
    const c = classifyError(new Error('Not logged in. Run: ./nous login'));
    expect(c.kind).toBe('auth');
    expect(c.retryable).toBe(false);
    expect(c.hint).toMatch(/login/i);
  });

  test('message containing 401 → auth', () => {
    expect(classifyError('Stream failed: 401').kind).toBe('auth');
  });

  test('does NOT misclassify "401" embedded in a longer number', () => {
    // word-boundary anchor prevents e.g. document ids or rate-limit
    // counters like "4012/s" from being treated as auth failures
    expect(classifyError('processed item 4012').kind).not.toBe('auth');
  });
});

describe('classifyError — unknown', () => {
  test('null input → unknown, not retryable', () => {
    const c = classifyError(null);
    expect(c.kind).toBe('unknown');
    expect(c.retryable).toBe(false);
  });

  test('Error without message → unknown', () => {
    const c = classifyError(new Error(''));
    expect(c.kind).toBe('unknown');
  });
});
