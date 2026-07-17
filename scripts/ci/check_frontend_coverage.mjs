#!/usr/bin/env node
/**
 * Frontend coverage ratchet.
 *
 * Reads Vitest's json-summary totals and fails when any global metric
 * (lines/statements/functions/branches) falls below the floor committed
 * in frontend/quality-baseline.json under "coverage". The floor only
 * moves through an intentional, reviewed edit of that JSON — the
 * comparator never rewrites it.
 *
 * Usage:
 *   node scripts/ci/check_frontend_coverage.mjs frontend/coverage/coverage-summary.json
 *   node scripts/ci/check_frontend_coverage.mjs <summary> --emit-baseline
 */

import { readFileSync } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPT_DIR, '..', '..');
const METRICS = ['lines', 'statements', 'functions', 'branches'];

/**
 * Pure comparison: returns violation strings (empty = pass).
 *
 * @param {Record<string, {pct: number}>} totals json-summary "total" object
 * @param {Record<string, number>} baseline committed floors (pct)
 */
export function compareCoverage(totals, baseline) {
  const violations = [];
  for (const metric of METRICS) {
    const current = totals[metric]?.pct;
    const floor = baseline[metric];
    if (typeof current !== 'number' || typeof floor !== 'number') {
      violations.push(
        `COVERAGE-METRIC-MISSING: ${metric} absent from summary or baseline.`,
      );
      continue;
    }
    // Tiny epsilon guards pure float artifacts; any real drop fails.
    if (current < floor - 1e-9) {
      violations.push(
        `COVERAGE-REGRESSION: ${metric} ${current}% fell below the ` +
          `committed floor of ${floor}%. Add or fix tests; if the drop is ` +
          'intentional, lower the floor in frontend/quality-baseline.json ' +
          'in this PR with justification.',
      );
    }
  }
  return violations;
}

function main() {
  const args = process.argv.slice(2);
  const summaryPath = args.find((a) => !a.startsWith('--'));
  const emitBaseline = args.includes('--emit-baseline');
  if (!summaryPath) {
    console.error(
      'Usage: check_frontend_coverage.mjs <coverage-summary.json> [--emit-baseline]',
    );
    process.exit(2);
  }
  const totals = JSON.parse(readFileSync(summaryPath, 'utf8')).total;

  if (emitBaseline) {
    const floors = Object.fromEntries(
      METRICS.map((m) => [m, Math.floor(totals[m].pct * 100) / 100]),
    );
    console.log(JSON.stringify(floors, null, 2));
    return;
  }

  const baselinePath = path.join(REPO_ROOT, 'frontend', 'quality-baseline.json');
  const baseline = JSON.parse(readFileSync(baselinePath, 'utf8')).coverage;
  if (!baseline) {
    console.error(`ERROR: ${baselinePath} has no "coverage" key.`);
    process.exit(2);
  }

  const violations = compareCoverage(totals, baseline);
  if (violations.length > 0) {
    console.log(`${violations.length} coverage violation(s):\n`);
    for (const violation of violations) console.log(`  ${violation}`);
    process.exit(1);
  }

  const summary = METRICS.map(
    (m) => `${m} ${totals[m].pct}% (floor ${baseline[m]}%)`,
  ).join(', ');
  console.log(`OK: coverage at or above committed floors — ${summary}.`);
  const raisable = METRICS.filter((m) => totals[m].pct >= baseline[m] + 1);
  if (raisable.length > 0) {
    console.log(
      `Floors could be raised for: ${raisable.join(', ')} — regenerate with ` +
        '--emit-baseline and commit the update.',
    );
  }
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  main();
}
