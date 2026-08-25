#!/usr/bin/env node
/* eslint-disable @typescript-eslint/explicit-function-return-type -- plain node script, no TS annotations */
/**
 * Automated guard mutants as living meta-tests (ADVISORY — not in blocking CI).
 *
 * Each mutant neuters ONE concurrency guard in the chat store/hook, then runs
 * the deterministic interleaving test that is supposed to catch it. A guard is
 * only worth its comment if a test dies when the guard dies: this script proves
 * that empirically. If a mutant SURVIVES (the covering test still passes with
 * the guard gone), the test is decorative — fail loudly.
 *
 * Usage:
 *   pnpm --dir frontend run test:mutants
 *   (or)  cd frontend && pnpm run test:mutants
 *
 * Exit non-zero if any mutant survives, any `find` string no longer matches
 * (mutant definition is stale — fix the definition, never skip), any restore
 * mismatch, or the post-restore sanity run fails. Files are always restored
 * from an in-memory copy (never via git), including on SIGINT/SIGTERM.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';

// cwd is frontend/ (invoked via package.json script).
const FRONTEND = process.cwd();
const abs = (p) => resolve(FRONTEND, p);

const INTERLEAVINGS =
  'src/test/concurrency/__tests__/chatStore.interleavings.test.ts';

/**
 * EXACTLY TWO mutants. `find` must match the current source byte-for-byte
 * (precise string replacement, no regex fuzz) — read the file if it drifts.
 */
const MUTANTS = [
  {
    name: 'stale-response identity guard (messageSlice)',
    file: 'src/store/chat/slices/messageSlice.ts',
    // The identity check `if (newestPageRequests.get(threadId) !== request)`
    // appears TWICE — the success-path guard (in the try) and its error-path
    // twin (in the catch). We target only the success-path guard, so the `find`
    // is anchored on the line that follows it (the try-block array check) to
    // stay unique. Neutering it lets a stale successful response commit its page.
    find:
      'if (newestPageRequests.get(threadId) !== request) {\n' +
      '        return false;\n' +
      '      }\n' +
      '      if (!Array.isArray(response.messages)) {',
    replace:
      'if (false && newestPageRequests.get(threadId) !== request) {\n' +
      '        return false;\n' +
      '      }\n' +
      '      if (!Array.isArray(response.messages)) {',
    // group 1 asserts stale refreshes return false and never commit their page;
    // neutering the identity check lets a stale response win → these die.
    coveringTest: { file: INTERLEAVINGS, nameFilter: 'group 1' },
  },
  {
    name: 'submit single-flight (useChatStreaming)',
    file: 'src/hooks/chat/useChatStreaming.ts',
    find:
      'if (submitLockRef.current) {\n' +
      "        console.warn('[Chat] Send ignored: submit already in flight');\n" +
      '        return;\n' +
      '      }',
    replace:
      'if (false && submitLockRef.current) {\n' +
      "        console.warn('[Chat] Send ignored: submit already in flight');\n" +
      '        return;\n' +
      '      }',
    // group 5 asserts a synchronous double-submit fires streamMessage once;
    // neutering the lock fires it twice → these die.
    coveringTest: { file: INTERLEAVINGS, nameFilter: 'group 5' },
  },
];

// --- Restore safety: track any file currently mutated so a signal can undo it.
/** @type {{path: string, original: string} | null} */
let inFlight = null;
function restoreInFlight() {
  if (inFlight) {
    writeFileSync(inFlight.path, inFlight.original);
    inFlight = null;
  }
}
for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => {
    restoreInFlight();
    process.exit(130);
  });
}

function runCovering({ file, nameFilter }) {
  const args = [
    'exec',
    'vitest',
    'run',
    '--project',
    'unit',
    file,
    '-t',
    nameFilter,
  ];
  return spawnSync('pnpm', args, { cwd: FRONTEND, stdio: 'inherit' });
}

/** @returns {'KILLED' | never} throws on any failure so the loop can record it. */
function runMutant(mutant) {
  const path = abs(mutant.file);
  const original = readFileSync(path, 'utf8');

  const occurrences = original.split(mutant.find).length - 1;
  if (occurrences !== 1) {
    throw new Error(
      `find string is stale — expected exactly 1 match in ${mutant.file}, ` +
        `found ${occurrences}. Re-read the file and update the mutant definition.\n` +
        `  find: ${JSON.stringify(mutant.find)}`
    );
  }

  const mutated = original.replace(mutant.find, mutant.replace);
  try {
    inFlight = { path, original };
    writeFileSync(path, mutated);

    const result = runCovering(mutant.coveringTest);
    if (result.status === 0) {
      throw new Error(
        `SURVIVED — covering test "${mutant.coveringTest.nameFilter}" passed ` +
          `with the guard neutered. The guard is untested.`
      );
    }
    if (result.status === null) {
      throw new Error(
        `covering test did not run cleanly (signal ${result.signal}).`
      );
    }
    return 'KILLED';
  } finally {
    // Restore from memory (never git) and prove byte-identity.
    writeFileSync(path, original);
    inFlight = null;
    const readBack = readFileSync(path, 'utf8');
    if (readBack !== original) {
      throw new Error(
        `restore mismatch for ${mutant.file} — file not byte-identical after restore.`
      );
    }
  }
}

function verifyPostRestore(mutant) {
  const result = runCovering(mutant.coveringTest);
  if (result.status !== 0) {
    throw new Error(
      `post-restore sanity run failed for "${mutant.coveringTest.nameFilter}" ` +
        `(exit ${result.status}) — the covering test does not pass on clean source.`
    );
  }
}

// --- Drive all mutants; collect results, never let one failure skip restore.
const summary = [];
let hadFailure = false;

for (const mutant of MUTANTS) {
  console.log(`\n=== Mutant: ${mutant.name} ===`);
  try {
    const verdict = runMutant(mutant);
    console.log(`--- verifying clean source still passes ---`);
    verifyPostRestore(mutant);
    summary.push({ name: mutant.name, verdict });
  } catch (err) {
    hadFailure = true;
    // Belt-and-suspenders: runMutant's finally already restored, but if the
    // throw came before the try (stale find), nothing was written anyway.
    restoreInFlight();
    summary.push({ name: mutant.name, verdict: 'SURVIVED/ERROR' });
    console.error(`\n!! ${mutant.name}: ${err.message}`);
  }
}

console.log('\n===== Mutant summary =====');
for (const row of summary) {
  console.log(`  ${row.verdict.padEnd(14)} ${row.name}`);
}

if (hadFailure) {
  console.error('\nFAIL: at least one guard mutant survived or errored.');
  process.exit(1);
}
console.log('\nPASS: every guard mutant was KILLED by its covering test.');
