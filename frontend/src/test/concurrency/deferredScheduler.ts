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
 * A promise paired with its resolvers, with settle-once semantics: the first
 * resolve/reject decides the outcome and every later settle is a silent no-op
 * (matching native Promise behaviour). No-op rather than throw so a schedule
 * that double-settles a deferred can't blow up mid-run — the interleaving stays
 * deterministic.
 */
export function createDeferred<T>(): Deferred<T> {
  let resolveFn!: (value: T) => void;
  let rejectFn!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolveFn = res;
    rejectFn = rej;
  });
  let settled = false;
  return {
    promise,
    resolve(value: T): void {
      if (settled) {
        return;
      }
      settled = true;
      resolveFn(value);
    },
    reject(error: unknown): void {
      if (settled) {
        return;
      }
      settled = true;
      rejectFn(error);
    },
  };
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
