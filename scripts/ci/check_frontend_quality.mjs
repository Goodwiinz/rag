#!/usr/bin/env node
/**
 * Frontend lint-debt ratchet.
 *
 * Compares an ESLint JSON report against the committed baseline in
 * frontend/quality-baseline.json (key "eslint") and fails when:
 *  - a changed file has any error (touching a file means fixing its errors);
 *  - a changed file's warning count exceeds its baselined count
 *    (removing a warning buys headroom; net growth fails);
 *  - the global error or warning total exceeds the baseline.
 *
 * Unchanged files are constrained only by the global caps, so the ratchet
 * rejects new debt without demanding a whole-tree cleanup.
 *
 * Usage (from repo root or frontend/):
 *   node scripts/ci/check_frontend_quality.mjs \
 *     --report <eslint-json> [--changed <repo-relative-path> ...] [--base <ref>]
 *   node scripts/ci/check_frontend_quality.mjs --report <eslint-json> --emit-baseline
 *
 * With --base, changed frontend files are resolved via
 * scripts/ci/changed_source_files.py. --emit-baseline prints the "eslint"
 * baseline object for the current report (reviewed, committed updates only).
 */

import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPT_DIR, '..', '..');

/**
 * Pure comparison: returns an array of violation strings (empty = pass).
 *
 * @param {object} input
 * @param {Array<{filePath: string, errorCount: number, warningCount: number}>} input.results
 * @param {{errors: number, warnings: number, byFile: Record<string, {errors: number, warnings: number}>}} input.baseline
 * @param {string[]} input.changedFiles repo-relative paths (frontend/...)
 * @param {string} input.frontendRoot absolute path ESLint results are under
 */
export function compareEslint({ results, baseline, changedFiles, frontendRoot }) {
  const violations = [];
  const byRelPath = new Map();
  let totalErrors = 0;
  let totalWarnings = 0;
  for (const result of results) {
    const rel = path.relative(frontendRoot, result.filePath).split(path.sep).join('/');
    byRelPath.set(rel, result);
    totalErrors += result.errorCount;
    totalWarnings += result.warningCount;
  }

  for (const repoPath of changedFiles) {
    if (!repoPath.startsWith('frontend/')) continue;
    const rel = repoPath.slice('frontend/'.length);
    const current = byRelPath.get(rel);
    if (!current) continue; // not linted (deleted, non-lintable, excluded)
    if (current.errorCount > 0) {
      violations.push(
        `CHANGED-FILE-ERRORS: ${rel} was changed and has ` +
          `${current.errorCount} ESLint error(s). Errors in touched files ` +
          'must be fixed in the same PR.',
      );
    }
    const allowed = baseline.byFile?.[rel]?.warnings ?? 0;
    if (current.warningCount > allowed) {
      violations.push(
        `CHANGED-FILE-WARNINGS: ${rel} has ${current.warningCount} warning(s), ` +
          `baseline allows ${allowed}. Fix the new warnings (or more old ones).`,
      );
    }
  }

  if (totalErrors > baseline.errors) {
    violations.push(
      `GLOBAL-ERRORS: ${totalErrors} ESLint errors exceed the baseline of ` +
        `${baseline.errors}.`,
    );
  }
  if (totalWarnings > baseline.warnings) {
    violations.push(
      `GLOBAL-WARNINGS: ${totalWarnings} ESLint warnings exceed the baseline ` +
        `of ${baseline.warnings}.`,
    );
  }
  return violations;
}

/** Build the baseline object for --emit-baseline. */
export function buildBaseline(results, frontendRoot) {
  const byFile = {};
  let errors = 0;
  let warnings = 0;
  for (const result of results) {
    errors += result.errorCount;
    warnings += result.warningCount;
    if (result.errorCount || result.warningCount) {
      const rel = path
        .relative(frontendRoot, result.filePath)
        .split(path.sep)
        .join('/');
      byFile[rel] = { errors: result.errorCount, warnings: result.warningCount };
    }
  }
  const sorted = Object.fromEntries(
    Object.entries(byFile).sort(([a], [b]) => a.localeCompare(b)),
  );
  return { errors, warnings, byFile: sorted };
}

function parseArgs(argv) {
  const args = { changed: [], report: null, base: null, emitBaseline: false };
  for (let i = 0; i < argv.length; i += 1) {
    switch (argv[i]) {
      case '--report':
        args.report = argv[++i];
        break;
      case '--changed':
        args.changed.push(argv[++i]);
        break;
      case '--base':
        args.base = argv[++i];
        break;
      case '--emit-baseline':
        args.emitBaseline = true;
        break;
      default:
        console.error(`Unknown argument: ${argv[i]}`);
        process.exit(2);
    }
  }
  return args;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.report) {
    console.error('ERROR: --report <eslint-json> is required.');
    process.exit(2);
  }
  const results = JSON.parse(readFileSync(args.report, 'utf8'));
  const frontendRoot = path.join(REPO_ROOT, 'frontend');

  if (args.emitBaseline) {
    console.log(JSON.stringify(buildBaseline(results, frontendRoot), null, 2));
    return;
  }

  const baselinePath = path.join(frontendRoot, 'quality-baseline.json');
  const baselineDoc = JSON.parse(readFileSync(baselinePath, 'utf8'));
  const baseline = baselineDoc.eslint;
  if (!baseline) {
    console.error(`ERROR: ${baselinePath} has no "eslint" key.`);
    process.exit(2);
  }

  let changedFiles = args.changed;
  if (args.base) {
    const output = execFileSync(
      'python3',
      [
        path.join(SCRIPT_DIR, 'changed_source_files.py'),
        '--base',
        args.base,
        '--kind',
        'frontend',
      ],
      { cwd: REPO_ROOT, encoding: 'utf8' },
    );
    changedFiles = changedFiles.concat(output.split('\n').filter(Boolean));
  }

  const violations = compareEslint({ results, baseline, changedFiles, frontendRoot });
  if (violations.length > 0) {
    console.log(`${violations.length} frontend quality violation(s):\n`);
    for (const violation of violations) console.log(`  ${violation}`);
    console.log(
      '\nIf debt intentionally shrank, refresh the baseline in the same PR:\n' +
        '  pnpm --filter multimodal-rag-frontend exec eslint app src ' +
        '--format json --output-file /tmp/eslint.json\n' +
        '  node scripts/ci/check_frontend_quality.mjs --report /tmp/eslint.json ' +
        '--emit-baseline  # paste into frontend/quality-baseline.json "eslint"',
    );
    process.exit(1);
  }
  console.log(
    `OK: frontend lint debt within baseline (errors ${baseline.errors}, ` +
      `warnings ${baseline.warnings}).`,
  );
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
