/**
 * @jest-environment node
 */
import { withRetry } from '../retry';

describe('withRetry', () => {
  test('returns immediately when first attempt succeeds', async () => {
    const fn = jest.fn().mockResolvedValue('ok');
    const out = await withRetry(fn, {
      maxAttempts: 3,
      signal: new AbortController().signal,
      predicate: () => true,
    });
    expect(out).toBe('ok');
    expect(fn).toHaveBeenCalledTimes(1);
  });

  test('retries when predicate is true; returns on success', async () => {
    jest.useFakeTimers();
    const fn = jest
      .fn()
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce('ok');
    const promise = withRetry(fn, {
      maxAttempts: 3,
      signal: new AbortController().signal,
      predicate: () => true,
    });
    // advance backoff (250ms for first retry)
    await jest.advanceTimersByTimeAsync(250);
    const out = await promise;
    expect(out).toBe('ok');
    expect(fn).toHaveBeenCalledTimes(2);
    jest.useRealTimers();
  });

  test('does NOT retry when predicate returns false', async () => {
    const fn = jest.fn().mockRejectedValue(new Error('nope'));
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
    const fn = jest.fn();
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
    jest.useFakeTimers();
    const err = new Error('persistent');
    const fn = jest.fn().mockRejectedValue(err);
    const promise = withRetry(fn, {
      maxAttempts: 2,
      signal: new AbortController().signal,
      predicate: () => true,
    });
    await jest.advanceTimersByTimeAsync(250);
    await expect(promise).rejects.toBe(err);
    expect(fn).toHaveBeenCalledTimes(2);
    jest.useRealTimers();
  });
});
