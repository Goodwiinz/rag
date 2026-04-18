/**
 * Accessibility testing helpers powered by jest-axe.
 * Usage: import { expectNoA11yViolations } from '@/test/a11y';
 */
import { axe, toHaveNoViolations } from 'jest-axe';

expect.extend(toHaveNoViolations);

/**
 * Assert a rendered container has no axe accessibility violations.
 */
export async function expectNoA11yViolations(
  container: HTMLElement,
  options?: Parameters<typeof axe>[1]
) {
  const results = await axe(container, options);
  expect(results).toHaveNoViolations();
}
