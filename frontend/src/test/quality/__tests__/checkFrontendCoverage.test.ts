/**
 * Contract tests for scripts/ci/check_frontend_coverage.mjs.
 *
 * The comparator reads Vitest's json-summary totals and fails when any
 * global metric (lines/statements/functions/branches) falls below the
 * floor committed in frontend/quality-baseline.json. Raising the floor
 * is an intentional JSON edit in the same PR — never automatic.
 */
import { describe, expect, it } from 'vitest';

// @ts-expect-error — plain .mjs module outside the frontend package root
import { compareCoverage } from '../../../../../scripts/ci/check_frontend_coverage.mjs';

interface MetricTotals {
  lines: { pct: number };
  statements: { pct: number };
  functions: { pct: number };
  branches: { pct: number };
}

function totals(
  lines: number,
  statements: number,
  functions: number,
  branches: number,
): MetricTotals {
  return {
    lines: { pct: lines },
    statements: { pct: statements },
    functions: { pct: functions },
    branches: { pct: branches },
  };
}

const BASELINE = { lines: 19, statements: 19, functions: 52, branches: 76 };

describe('compareCoverage', () => {
  it('passes when every metric meets its floor exactly', () => {
    expect(compareCoverage(totals(19, 19, 52, 76), BASELINE)).toEqual([]);
  });

  it('passes when metrics exceed their floors', () => {
    expect(compareCoverage(totals(25, 24, 60, 80), BASELINE)).toEqual([]);
  });

  it('fails a single metric below its floor with old and new values', () => {
    const violations = compareCoverage(totals(18.5, 19, 52, 76), BASELINE);
    expect(violations).toHaveLength(1);
    expect(violations[0]).toContain('lines');
    expect(violations[0]).toContain('18.5');
    expect(violations[0]).toContain('19');
  });

  it('reports every regressed metric independently', () => {
    const violations = compareCoverage(totals(10, 10, 10, 10), BASELINE);
    expect(violations).toHaveLength(4);
  });

  it('is not fooled by float noise at the boundary', () => {
    // 19.0000001 vs floor 19 must pass; 18.9999 must fail.
    expect(compareCoverage(totals(19.0000001, 19, 52, 76), BASELINE)).toEqual(
      [],
    );
    expect(
      compareCoverage(totals(18.9999, 19, 52, 76), BASELINE),
    ).toHaveLength(1);
  });
});
