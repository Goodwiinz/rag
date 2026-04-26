export interface RetryOptions {
  maxAttempts: number;
  signal: AbortSignal;
  predicate: (err: unknown) => boolean;
}

const BACKOFF_MS = [250, 750];

export async function withRetry<T>(
  fn: (attempt: number) => Promise<T>,
  opts: RetryOptions
): Promise<T> {
  if (opts.signal.aborted) throw abortError();

  let lastErr: unknown;
  for (let attempt = 1; attempt <= opts.maxAttempts; attempt++) {
    try {
      return await fn(attempt);
    } catch (err) {
      lastErr = err;
      if (attempt >= opts.maxAttempts || !opts.predicate(err)) throw err;
      const delay = BACKOFF_MS[Math.min(attempt - 1, BACKOFF_MS.length - 1)];
      await sleep(delay, opts.signal);
    }
  }
  throw lastErr;
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(abortError());
    const t = setTimeout(() => {
      signal.removeEventListener('abort', onAbort);
      // Defer by one extra microtask so callers can attach rejection handlers
      // before any synchronous continuation of the awaiting async function runs.
      // This prevents PromiseRejectionHandledWarning in Jest 30's fake-timer drain.
      queueMicrotask(resolve);
    }, ms);
    const onAbort = () => {
      clearTimeout(t);
      reject(abortError());
    };
    signal.addEventListener('abort', onAbort, { once: true });
  });
}

function abortError(): Error {
  const e = new Error('aborted');
  e.name = 'AbortError';
  return e;
}
