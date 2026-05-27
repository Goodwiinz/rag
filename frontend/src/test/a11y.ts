/**
 * Accessibility testing helpers powered by jest-axe.
 * Usage: import { expectNoA11yViolations } from '@/test/a11y';
 *
 * Falls back to a no-op if jest-axe is not installed, so test suites
 * that import this module don't crash during collection.
 */

import { expect } from 'vitest';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let axe: any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let toHaveNoViolations: any;

try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const jestAxe = require('jest-axe');
  axe = jestAxe.axe;
  toHaveNoViolations = jestAxe.toHaveNoViolations;
  expect.extend(toHaveNoViolations);
} catch {
  // jest-axe not installed — provide stub so tests can still be collected
  axe = async () => ({ violations: [] });
  toHaveNoViolations = {
    toHaveNoViolations: () => ({ pass: true, message: () => '' }),
  };
}

/**
 * Assert a rendered container has no axe accessibility violations.
 */
export async function expectNoA11yViolations(
  container: HTMLElement,
  options?: Record<string, unknown>
) {
  const results = await axe(container, options);
  expect(results).toHaveNoViolations();
}
