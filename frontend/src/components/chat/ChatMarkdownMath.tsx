'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { rehypeFreshTail } from '@/lib/rehypeFreshTail';
import 'katex/dist/katex.min.css';

import { baseComponents, inlineComponents } from './ChatMarkdown';

/**
 * The math-capable renderer, split into its own module so KaTeX lands in a
 * chunk of its own.
 *
 * KaTeX and its stylesheet are ~557kB — more than 5% of the whole bundle —
 * and most turns contain no math at all, so importing it from ChatMarkdown
 * charged every reader for a feature few messages use. `ChatMarkdown` now
 * loads this lazily and only when the content actually carries delimiters.
 *
 * Single-dollar inline math stays enabled: it is how both arXiv sources and
 * the model write inline expressions, and switching it off makes the feature
 * near-useless on this corpus. The cost is that a sentence pairing two bare
 * dollar amounts ("$5 to $10") renders the span between them as math; flip
 * `singleDollarTextMath: false` here if that ever outweighs the math.
 */
const REMARK_PLUGINS = [remarkGfm, remarkMath];

/**
 * KaTeX runs over model-authored text, so it must not be able to take the
 * message down or reach out of the page:
 * - `throwOnError: false` renders malformed LaTeX as inline red source rather
 *   than throwing inside render and blanking the bubble.
 * - `trust` stays at its default (false), which disables `\href`,
 *   `\includegraphics` and friends — the same reasoning as the `rel` on
 *   LLM-authored links.
 * - `strict: false` keeps unicode and other soft warnings out of the console;
 *   they are not actionable for text we did not author.
 */
const REHYPE_PLUGINS: React.ComponentProps<
  typeof ReactMarkdown
>['rehypePlugins'] = [[rehypeKatex, { throwOnError: false, strict: false }]];

export function ChatMarkdownMath({
  content,
  inline = false,
  freshTail = false,
}: {
  content: string;
  inline?: boolean;
  freshTail?: boolean;
}): React.ReactElement {
  // Fresh-tail runs after KaTeX so it never splits a rendered expression.
  const rehypePlugins = freshTail
    ? [...(REHYPE_PLUGINS ?? []), rehypeFreshTail]
    : REHYPE_PLUGINS;
  return (
    <ReactMarkdown
      remarkPlugins={REMARK_PLUGINS}
      rehypePlugins={rehypePlugins}
      components={inline ? inlineComponents : baseComponents}
    >
      {content}
    </ReactMarkdown>
  );
}

export default ChatMarkdownMath;
