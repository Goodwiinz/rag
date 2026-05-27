/**
 * @vitest-environment node
 */
import { describe, expect, test, vi } from 'vitest';
import { withRetry } from '../retry';

describe('withRetry', () => {
  test('returns immediately when first attempt succeeds', async () => {
    const fn = vi.fn().mockResolvedValue('ok');
    const out = await withRetry(fn, {
      maxAttempts: 3,
      signal: new AbortController().signal,
      predicate: () => true,
    });
    expect(out).toBe('ok');
    expect(fn).toHaveBeenCalledTimes(1);
  });

  test('retries when predicate is true; returns on success', async () => {
    vi.useFakeTimers();
    const fn = vi
      .fn()
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce('ok');
    const promise = withRetry(fn, {
      maxAttempts: 3,
      signal: new AbortController().signal,
      predicate: () => true,
    });
    // advance backoff (250ms for first retry)
    await vi.advanceTimersByTimeAsync(250);
    const out = await promise;
    expect(out).toBe('ok');
    expect(fn).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  test('does NOT retry when predicate returns false', async () => {
    const fn = vi.fn().mockRejectedValue(new Error('nope'));
    await expect(
      withRetry(fn, {
        maxAttempts: 3,
        signal: new AbortController().signal,
        predicate: () => false,
      })
    ).rejects.toThrow('nope');
    expect(fn).toHaveBeenCalledTimes(1);
  });

  test('throws AbortError when signal is already aborted', async () => {
    const ac = new AbortController();
    ac.abort();
    const fn = vi.fn();
    await expect(
      withRetry(fn, {
        maxAttempts: 3,
        signal: ac.signal,
        predicate: () => true,
      })
    ).rejects.toMatchObject({ name: 'AbortError' });
    expect(fn).not.toHaveBeenCalled();
  });

  test('stops retrying after maxAttempts and rethrows last error', async () => {
    vi.useFakeTimers();
    const err = new Error('persistent');
    const fn = vi.fn().mockRejectedValue(err);
    const promise = withRetry(fn, {
      maxAttempts: 2,
      signal: new AbortController().signal,
      predicate: () => true,
    });
    // Attach the rejection assertion BEFORE advancing timers. Otherwise
    // Vitest 2.x logs the rejection as unhandled during `advanceTimersByTimeAsync`
    // (the rejection fires inside that drain, but `expect(...).rejects` hasn't
    // attached its handler yet), which makes the run exit non-zero even
    // though the assertion itself eventually succeeds.
    const assertion = expect(promise).rejects.toBe(err);
    await vi.advanceTimersByTimeAsync(250);
    await assertion;
    expect(fn).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
});
