/**
 * Math rendering in assistant message bodies.
 *
 * The arXiv corpus and the model both write expressions as `$…$` / `$$…$$`,
 * which rendered as literal dollar-delimited source until remark-math and
 * rehype-katex were wired in.
 */

import { describe, expect, it } from 'vitest';
import React from 'react';
import { render } from '@testing-library/react';
import { ChatMarkdown } from '../ChatMarkdown';

describe('ChatMarkdown math', () => {
  it('renders inline math instead of the raw source', () => {
    const { container } = render(
      <ChatMarkdown content={'Attention scales as $O(n^2)$ in sequence length.'} />
    );

    expect(container.querySelector('.katex')).not.toBeNull();
    expect(container.textContent).not.toContain('$O(n^2)$');
  });

  it('renders display math as its own block', () => {
    const { container } = render(
      <ChatMarkdown content={'$$\n\\frac{1}{\\sqrt{d_k}}\n$$'} />
    );

    expect(container.querySelector('.katex-display')).not.toBeNull();
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

  it('renders math in the citation-segment inline variant', () => {
    const { container } = render(
      <ChatMarkdown content={'bound by $\\epsilon$'} inline />
    );

    expect(container.querySelector('.katex')).not.toBeNull();
    // The inline variant unwraps paragraphs so a citation chip can sit beside
    // the text — that must still hold with math present.
    expect(container.querySelector('p')).toBeNull();
  });
});
