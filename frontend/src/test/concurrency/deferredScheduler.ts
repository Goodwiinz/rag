/**
 * Deterministic interleaving scheduler for store/hook concurrency tests.
 *
 * Lets a test express a specific ordering of async events — start an operation,
 * settle a promise it awaits, drain microtasks — with no real timers and no
 * randomness, so the same script yields the same outcome every run. Task 4.2
 * uses this to table-drive the chat-store guard interleavings documented in
 * docs/testing/chat-mutation-checks.md.
 */

export interface Deferred<T> {
  promise: Promise<T>;
  resolve(value: T): void;
  reject(error: unknown): void;
}

/**
 * A promise paired with its resolvers. Settle-once is inherited from the native
 * Promise: the first resolve/reject decides the outcome and every later settle
 * is a silent no-op, so a schedule that double-settles a deferred observes a
 * stable outcome without any wrapper bookkeeping.
 */
export function createDeferred<T>(): Deferred<T> {
  let resolveFn!: (value: T) => void;
  let rejectFn!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolveFn = res;
    rejectFn = rej;
  });
  return { promise, resolve: resolveFn, reject: rejectFn };
}

export type Step =
  /** Start an async operation without awaiting its completion. */
  | { kind: 'run'; fn: () => void | Promise<unknown> }
  /** Settle a deferred so any awaiting continuation resumes. */
  | { kind: 'resolve'; deferred: Deferred<unknown>; value?: unknown }
  /** Reject a deferred so any awaiting continuation observes the error. */
  | { kind: 'reject'; deferred: Deferred<unknown>; error: unknown }
  /** Drain currently-queued microtasks. */
  | { kind: 'flush' };

// ponytail: fixed-count microtask drain — each pass drains one generation of
// already-queued microtasks (queue is FIFO). Continuation chains in the chat
// store are shallow, so a generous constant fully drains them without timers.
// Bump this if a deeper continuation chain ever under-drains.
// Steering: any Task 4.2 schedule with a deeper await chain than the drain-depth
// assertion at __tests__/deferredScheduler.test.ts:83 must extend that assertion
// or bump this constant in lockstep — otherwise a fixed drain can silently under-run.
const MICROTASK_FLUSH_PASSES = 25;

async function flushMicrotasks(): Promise<void> {
  for (let pass = 0; pass < MICROTASK_FLUSH_PASSES; pass++) {
    await Promise.resolve();
  }
}

/**
 * Execute steps strictly in order. `run` starts an operation and returns
 * immediately (its continuations stay queued as microtasks). Each settle step
 * drains microtasks before the next step so continuations observe a
 * deterministic order; `flush` drains on demand after a `run`.
 *
 * Advisory: a `run` fn that rejects asynchronously floats as an unhandled
 * rejection — 4.2 helpers should attach their own `.catch` or assert the
 * rejection via a deferred.
 */
export async function runInterleaving(steps: Step[]): Promise<void> {
  for (const step of steps) {
    switch (step.kind) {
      case 'run':
        // Deliberately not awaited: starting the operation, not finishing it.
        void step.fn();
        break;
      case 'resolve':
        step.deferred.resolve(step.value);
        await flushMicrotasks();
        break;
      case 'reject':
        step.deferred.reject(step.error);
        await flushMicrotasks();
        break;
      case 'flush':
        await flushMicrotasks();
        break;
    }
  }
}
