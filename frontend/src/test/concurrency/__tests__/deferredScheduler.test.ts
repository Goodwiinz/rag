import { describe, expect, it } from 'vitest';

import {
  createDeferred,
  runInterleaving,
  type Step,
} from '../deferredScheduler';

describe('createDeferred', () => {
  it('resolves the promise with the supplied value', async () => {
    const d = createDeferred<number>();
    d.resolve(42);
    await expect(d.promise).resolves.toBe(42);
  });

  it('rejects the promise with the supplied error', async () => {
    const d = createDeferred<number>();
    d.reject(new Error('boom'));
    await expect(d.promise).rejects.toThrow('boom');
  });

  // Settle-once: the second settle is a silent no-op, matching native Promise
  // semantics (a Promise ignores resolve/reject after it settles). We keep the
  // wrapper's behaviour identical so a scheduler step that double-settles a
  // deferred cannot flip an already-decided outcome — the interleaving stays
  // deterministic instead of throwing mid-schedule.
  it('ignores a second resolve after settling', async () => {
    const d = createDeferred<number>();
    d.resolve(1);
    d.resolve(2);
    await expect(d.promise).resolves.toBe(1);
  });

  it('ignores a reject after it has already resolved', async () => {
    const d = createDeferred<number>();
    d.resolve(1);
    d.reject(new Error('too late'));
    await expect(d.promise).resolves.toBe(1);
  });

  it('ignores a resolve after it has already rejected', async () => {
    const d = createDeferred<number>();
    d.reject(new Error('first'));
    d.resolve(9);
    await expect(d.promise).rejects.toThrow('first');
  });
});

describe('runInterleaving', () => {
  it('executes steps strictly in order and drains after a settle', async () => {
    const log: string[] = [];
    const d = createDeferred<string>();
    await runInterleaving([
      {
        kind: 'run',
        fn: () => {
          log.push('run');
          void d.promise.then((v) => log.push(`then-${v}`));
        },
      },
      { kind: 'resolve', deferred: d, value: 'x' },
    ]);
    // 'then-x' proves the settle step drained microtasks before returning.
    expect(log).toEqual(['run', 'then-x']);
  });

  it('drains queued continuations on an explicit flush step', async () => {
    const log: string[] = [];
    const d = createDeferred<void>();
    await runInterleaving([
      {
        kind: 'run',
        fn: () => {
          void d.promise.then(() => log.push('resumed'));
        },
      },
      { kind: 'resolve', deferred: d },
      { kind: 'flush' },
    ]);
    expect(log).toEqual(['resumed']);
  });

  it('fully drains a deep continuation chain (more than one microtask generation)', async () => {
    const log: number[] = [];
    const d = createDeferred<number>();
    await runInterleaving([
      {
        kind: 'run',
        fn: () => {
          let chain = d.promise;
          for (let i = 0; i < 10; i++) {
            const step = i;
            chain = chain.then((v) => {
              log.push(step);
              return v;
            });
          }
          void chain;
        },
      },
      { kind: 'resolve', deferred: d, value: 0 },
    ]);
    // A single microtask tick would only advance the chain by one link; the
    // multi-pass flush is what carries it to the end. This assertion fails if
    // MICROTASK_FLUSH_PASSES is too small to drain the whole chain.
    expect(log).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  });

  it('routes a reject step to the deferred', async () => {
    const log: string[] = [];
    const d = createDeferred<string>();
    await runInterleaving([
      {
        kind: 'run',
        fn: () => {
          void d.promise.catch((e: unknown) => {
            log.push(`caught-${(e as Error).message}`);
          });
        },
      },
      { kind: 'reject', deferred: d, error: new Error('nope') },
    ]);
    expect(log).toEqual(['caught-nope']);
  });
});

// Realistic mini-example: two in-flight "requests" backed by deferreds, driven
// by a toy last-writer guard that mirrors the stale-response rejection guard in
// messageSlice.ts (drop a response whose request id is no longer the latest).
// Requests start in order A then B; B supersedes A. We resolve them OUT OF
// ORDER (newer B first, stale A last) and assert the guard still keeps B.
interface LastWriterGuard {
  latestRequestId: number;
  winner: string | null;
}

function startRequest(
  guard: LastWriterGuard,
  response: Promise<string>,
): void {
  const myId = ++guard.latestRequestId;
  void response.then((value) => {
    if (myId !== guard.latestRequestId) {
      return; // superseded → drop the stale response
    }
    guard.winner = value;
  });
}

function buildStaleResponseSchedule(guard: LastWriterGuard): {
  steps: Step[];
} {
  const requestA = createDeferred<string>();
  const requestB = createDeferred<string>();
  const steps: Step[] = [
    { kind: 'run', fn: () => startRequest(guard, requestA.promise) },
    { kind: 'run', fn: () => startRequest(guard, requestB.promise) },
    // Newer request resolves first; the stale one resolves LAST.
    { kind: 'resolve', deferred: requestB, value: 'B' },
    { kind: 'resolve', deferred: requestA, value: 'A' },
  ];
  return { steps };
}

describe('stale-response interleaving (mini-example)', () => {
  it('keeps the newest response even when the stale one resolves last', async () => {
    const guard: LastWriterGuard = { latestRequestId: 0, winner: null };
    const { steps } = buildStaleResponseSchedule(guard);
    await runInterleaving(steps);
    expect(guard.winner).toBe('B');
  });

  it('produces the identical outcome across 50 repeated runs', async () => {
    const outcomes = new Set<string | null>();
    for (let run = 0; run < 50; run++) {
      const guard: LastWriterGuard = { latestRequestId: 0, winner: null };
      const { steps } = buildStaleResponseSchedule(guard);
      await runInterleaving(steps);
      outcomes.add(guard.winner);
    }
    // One and only one outcome across every run — no reliance on timers/luck.
    expect([...outcomes]).toEqual(['B']);
  });
});
