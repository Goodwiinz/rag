/**
 * @vitest-environment node
 */
import { describe, expect, test } from 'vitest';
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

  test('network classification embeds URL from error message in hint', () => {
    const err = Object.assign(
      new Error('fetch failed at http://localhost:8000/api/v1/agent/stream'),
      { code: 'ECONNREFUSED' }
    );
    const c = classifyError(err);
    expect(c.kind).toBe('network');
    expect(c.userMessage).toContain('http://localhost:8000');
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

describe('classifyError — not_found_thread', () => {
  test('"Thread not found" → not_found_thread, retryable', () => {
    const c = classifyError(new Error('Thread not found'));
    expect(c.kind).toBe('not_found_thread');
    expect(c.retryable).toBe(true);
    expect(c.userMessage).toMatch(/expired/i);
  });
});

describe('classifyError — transient_5xx', () => {
  test('"Stream failed: 502" → transient_5xx, retryable', () => {
    expect(classifyError('Stream failed: 502').kind).toBe('transient_5xx');
  });
  test('"Stream failed: 503" → transient_5xx', () => {
    expect(classifyError('Stream failed: 503').kind).toBe('transient_5xx');
  });
  test('generic "timed out" → transient_5xx', () => {
    expect(classifyError(new Error('request timed out')).kind).toBe(
      'transient_5xx'
    );
  });
});

describe('classifyError — idle_timeout', () => {
  test('IDLE_TIMEOUT:90 sentinel → idle_timeout, retryable', () => {
    const c = classifyError('IDLE_TIMEOUT:90');
    expect(c.kind).toBe('idle_timeout');
    expect(c.retryable).toBe(true);
    expect(c.userMessage).toMatch(/silent at 90s/);
  });
});

describe('classifyError — cancelled', () => {
  test('AbortError → cancelled, not retryable', () => {
    const err = Object.assign(new Error('aborted'), { name: 'AbortError' });
    const c = classifyError(err);
    expect(c.kind).toBe('cancelled');
    expect(c.retryable).toBe(false);
  });
});

describe('classifyError — precedence', () => {
  test('IDLE_TIMEOUT does NOT match generic transient_5xx timeout rule', () => {
    expect(classifyError('IDLE_TIMEOUT:30').kind).toBe('idle_timeout');
  });
  test('not_found_thread beats unknown even when message has noise', () => {
    expect(
      classifyError(new Error('Stream failed: Thread not found')).kind
    ).toBe('not_found_thread');
  });
});
