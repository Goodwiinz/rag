import { describe, expect, it } from 'vitest';
import React from 'react';
import { render } from '@testing-library/react';
import { ThinkingMatrix } from '../ThinkingMatrix';

describe('ThinkingMatrix', () => {
  it('renders nine decorative cells on a staggered sweep', () => {
    const { container } = render(<ThinkingMatrix />);
    const cells = container.querySelectorAll<HTMLElement>('.nous-matrix-cell');

    expect(cells).toHaveLength(9);
    // Decorative: the hosting pill is the live region and carries the phase.
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull();

    // Cells on the same anti-diagonal share a delay; opposite corners differ,
    // which is what makes the sweep read as a sweep rather than a blink.
    const delay = (i: number): string => cells[i].style.animationDelay;
    expect(delay(0)).not.toBe(delay(8));
    expect(delay(1)).toBe(delay(3));
  });
});
