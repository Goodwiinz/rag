/**
 * Math rendering in assistant message bodies.
 *
 * The arXiv corpus and the model both write expressions as `$…$` / `$$…$$`,
 * which rendered as literal dollar-delimited source until remark-math and
 * rehype-katex were wired in.
 */

import { describe, expect, it } from 'vitest';
import React from 'react';
import { render, waitFor } from '@testing-library/react';
import { ChatMarkdown } from '../ChatMarkdown';

describe('ChatMarkdown math', () => {
  it('renders inline math instead of the raw source', async () => {
    const { container } = render(
      <ChatMarkdown content={'Attention scales as $O(n^2)$ in sequence length.'} />
    );

    // KaTeX is a lazily-loaded chunk, so the plain text renders first and the
    // math resolves in place once it arrives.
    await waitFor(() =>
      expect(container.querySelector('.katex')).not.toBeNull()
    );
    expect(container.textContent).not.toContain('$O(n^2)$');
  });

  it('renders display math as its own block', async () => {
    const { container } = render(
      <ChatMarkdown content={'$$\n\\frac{1}{\\sqrt{d_k}}\n$$'} />
    );

    await waitFor(() =>
      expect(container.querySelector('.katex-display')).not.toBeNull()
    );
  });

  it('renders prose without reaching for the math chunk', () => {
    // The guard that keeps KaTeX (~557kB) off every page load: content with
    // no delimiters must render synchronously, through the plain path.
    const { container } = render(
      <ChatMarkdown content={'Plain prose with no expressions in it.'} />
    );

    expect(container.textContent).toContain('Plain prose');
    expect(container.querySelector('.katex')).toBeNull();
  });

  it('leaves dollar signs inside code fences alone', () => {
    const { container } = render(
      <ChatMarkdown content={'```\nexport COST=$5 to $10\n```'} />
    );

    expect(container.querySelector('.katex')).toBeNull();
    expect(container.textContent).toContain('$5 to $10');
  });

  it('renders malformed LaTeX as source rather than throwing', () => {
    // Model output is not guaranteed well-formed; a bad expression must not
    // take the whole message bubble down.
    expect(() =>
      render(<ChatMarkdown content={'Broken: $\\frac{1}{$'} />)
    ).not.toThrow();
  });

  it('renders math in the citation-segment inline variant', async () => {
    const { container } = render(
      <ChatMarkdown content={'bound by $\\epsilon$'} inline />
    );

    await waitFor(() =>
      expect(container.querySelector('.katex')).not.toBeNull()
    );
    // The inline variant unwraps paragraphs so a citation chip can sit beside
    // the text — that must still hold with math present.
    expect(container.querySelector('p')).toBeNull();
  });
});
