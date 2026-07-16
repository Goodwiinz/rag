/**
 * Contract tests for scripts/ci/check_frontend_quality.mjs.
 *
 * The comparator consumes an ESLint JSON report plus the committed
 * baseline (frontend/quality-baseline.json) and enforces:
 *  - no errors in changed files (touching a file means fixing its errors);
 *  - warnings in a changed file may not exceed that file's baselined
 *    count (removing one buys headroom, net growth fails);
 *  - global error/warning totals may never exceed the baseline.
 *
 * Unchanged files with pre-existing findings are only constrained by the
 * global caps — the ratchet rejects new debt without demanding a
 * whole-tree cleanup.
 */
import { describe, expect, it } from 'vitest';

// @ts-expect-error — plain .mjs module outside the frontend package root
import { compareEslint } from '../../../../../scripts/ci/check_frontend_quality.mjs';

interface LintFileResult {
  filePath: string;
  errorCount: number;
  warningCount: number;
}

const ROOT = '/repo/frontend';

function result(
  relPath: string,
  errors: number,
  warnings: number,
): LintFileResult {
  return {
    filePath: `${ROOT}/${relPath}`,
    errorCount: errors,
    warningCount: warnings,
  };
}

interface EslintBaseline {
  errors: number;
  warnings: number;
  byFile: Record<string, { errors: number; warnings: number }>;
}

function baseline(
  errors: number,
  warnings: number,
  byFile: Record<string, { errors: number; warnings: number }> = {},
): EslintBaseline {
  return { errors, warnings, byFile };
}

describe('compareEslint', () => {
  it('passes when nothing changed and totals equal the baseline', () => {
    const violations = compareEslint({
      results: [result('src/a.ts', 1, 2)],
      baseline: baseline(1, 2, { 'src/a.ts': { errors: 1, warnings: 2 } }),
      changedFiles: [],
      frontendRoot: ROOT,
    });
    expect(violations).toEqual([]);
  });

  it('fails on any error in a changed file, even a pre-existing one', () => {
    const violations = compareEslint({
      results: [result('src/a.ts', 1, 0)],
      baseline: baseline(1, 0, { 'src/a.ts': { errors: 1, warnings: 0 } }),
      changedFiles: ['frontend/src/a.ts'],
      frontendRoot: ROOT,
    });
    expect(violations).toHaveLength(1);
    expect(violations[0]).toContain('src/a.ts');
    expect(violations[0].toLowerCase()).toContain('error');
  });

  it('fails when warnings grow in a changed file', () => {
    const violations = compareEslint({
      results: [result('src/a.ts', 0, 3)],
      baseline: baseline(0, 3, { 'src/a.ts': { errors: 0, warnings: 2 } }),
      changedFiles: ['frontend/src/a.ts'],
      frontendRoot: ROOT,
    });
    expect(violations).toHaveLength(1);
    expect(violations[0]).toContain('src/a.ts');
  });

  it('allows a changed file to keep warnings at or below its baseline', () => {
    const violations = compareEslint({
      results: [result('src/a.ts', 0, 2)],
      baseline: baseline(0, 2, { 'src/a.ts': { errors: 0, warnings: 2 } }),
      changedFiles: ['frontend/src/a.ts'],
      frontendRoot: ROOT,
    });
    expect(violations).toEqual([]);
  });

  it('treats a changed file absent from the baseline as zero-budget', () => {
    const violations = compareEslint({
      results: [result('src/new.ts', 0, 1)],
      baseline: baseline(0, 1, {}),
      changedFiles: ['frontend/src/new.ts'],
      frontendRoot: ROOT,
    });
    expect(violations).toHaveLength(1);
    expect(violations[0]).toContain('src/new.ts');
  });

  it('ignores pre-existing findings in unchanged files', () => {
    const violations = compareEslint({
      results: [result('src/old.ts', 5, 9)],
      baseline: baseline(5, 9, { 'src/old.ts': { errors: 5, warnings: 9 } }),
      changedFiles: ['frontend/src/other.ts'],
      frontendRoot: ROOT,
    });
    expect(violations).toEqual([]);
  });

  it('fails when the global error total exceeds the baseline', () => {
    const violations = compareEslint({
      results: [result('src/a.ts', 2, 0), result('src/b.ts', 1, 0)],
      baseline: baseline(2, 0, {}),
      changedFiles: [],
      frontendRoot: ROOT,
    });
    expect(violations).toHaveLength(1);
    expect(violations[0]).toMatch(/global/i);
    expect(violations[0]).toContain('3');
    expect(violations[0]).toContain('2');
  });

  it('fails when the global warning total exceeds the baseline', () => {
    const violations = compareEslint({
      results: [result('src/a.ts', 0, 4)],
      baseline: baseline(0, 3, {}),
      changedFiles: [],
      frontendRoot: ROOT,
    });
    expect(violations).toHaveLength(1);
    expect(violations[0]).toMatch(/global/i);
  });

  it('passes when totals shrink below the baseline', () => {
    const violations = compareEslint({
      results: [result('src/a.ts', 0, 1)],
      baseline: baseline(4, 10, { 'src/a.ts': { errors: 0, warnings: 5 } }),
      changedFiles: ['frontend/src/a.ts'],
      frontendRoot: ROOT,
    });
    expect(violations).toEqual([]);
  });
});
