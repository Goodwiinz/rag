'use client';

import React from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import dynamic from 'next/dynamic';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

const SyntaxHighlighter = dynamic(
  () =>
    import('react-syntax-highlighter/dist/esm/prism').then(
      (mod) => mod.default
    ),
  {
    loading: () => (
      <pre className="p-4 rounded-lg bg-(--nous-bg-1) text-xs font-mono overflow-x-auto">
        <code>Loading...</code>
      </pre>
    ),
    ssr: false,
  }
);

/** remark plugins the eager renderer uses (GFM: tables, task lists,
 * strikethrough, autolinks). Math lives in ChatMarkdownMath so KaTeX stays
 * out of this chunk. Shared so the plain and citation-segmented paths can't
 * drift apart again. */
const REMARK_PLUGINS = [remarkGfm];

/** Pull the language class and raw text out of the `<code>` element that
 * react-markdown places inside every block `<pre>`. */
function extractCodeChild(children: React.ReactNode): {
  className: string;
  value: string;
} {
  const child = Array.isArray(children) ? children[0] : children;
  if (React.isValidElement(child)) {
    const props = child.props as {
      className?: string;
      children?: React.ReactNode;
    };
    return {
      className: props.className ?? '',
      value: String(props.children ?? ''),
    };
  }
  return { className: '', value: String(children ?? '') };
}

/**
 * One markdown component config for all assistant-message rendering.
 *
 * react-markdown v9+ no longer passes `inline` to the `code` renderer, so
 * block vs inline is decided structurally: block code is exactly a `code`
 * element whose parent is `pre`, so the `pre` renderer owns every block
 * (fenced and indented) and the `code` renderer only ever sees inline
 * spans. Languaged fences go through the lazy syntax highlighter,
 * unlanguaged/indented blocks get a plain `<pre>`, inline spans get the
 * NOUS pill styling.
 */
export const baseComponents: Components = {
  pre({ children }) {
    const { className, value } = extractCodeChild(children);
    const match = /language-(\w+)/.exec(className);
    const code = value.replace(/\n$/, '');
    if (match) {
      return (
        <SyntaxHighlighter style={oneDark} language={match[1]} PreTag="div">
          {code}
        </SyntaxHighlighter>
      );
    }
    return (
      <pre className="p-4 rounded-lg bg-(--nous-bg-1) text-xs font-mono overflow-x-auto">
        <code>{code}</code>
      </pre>
    );
  },
  code({ children }) {
    return (
      <code className="rounded bg-(--nous-bg-2) px-1.5 py-0.5 text-[11px] font-mono text-(--nous-sol)">
        {children}
      </code>
    );
  },
  // SECURITY (audit #21, PR #692): LLM-authored links open with
  // rel="noopener noreferrer" so a malicious target can't reach back via
  // window.opener (reverse tabnabbing).
  a({ href, children }) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-(--nous-sol) hover:text-(--nous-helios) underline"
      >
        {children}
      </a>
    );
  },
  // GFM tables can exceed the bubble width; scroll them instead of breaking
  // the chat column layout.
  table({ children }) {
    return (
      <div className="overflow-x-auto">
        <table>{children}</table>
      </div>
    );
  },
};

/** Variant for citation text segments: paragraphs unwrap to spans so a
 * <CitationLink> can sit inline between two markdown fragments. */
export const inlineComponents: Components = {
  ...baseComponents,
  p({ children }) {
    return <span>{children}</span>;
  },
};

/**
 * Cheap check for anything KaTeX would render: `$$…$$`, `$…$`, `\(…\)` or
 * `\[…\]`. Only decides whether to fetch the math chunk, so a false positive
 * costs one request and a false negative renders the source as written —
 * neither changes what remark-math itself does with the text.
 */
const MATH_DELIMITERS = /\$\$[\s\S]*?\$\$|\$[^$\n]+\$|\\\(|\\\[/;

/**
 * KaTeX plus its stylesheet is ~557kB, over 5% of the bundle, and most turns
 * carry no math — so it loads only for the messages that need it. Until the
 * chunk arrives the same content renders through the plain path, so the reader
 * sees text rather than a spinner and the math resolves in place.
 */
const ChatMarkdownMath = React.lazy(() =>
  import('./ChatMarkdownMath').then((m) => ({ default: m.ChatMarkdownMath }))
);

export interface ChatMarkdownProps {
  content: string;
  /** Unwrap paragraphs to spans (citation-segment interleaving). */
  inline?: boolean;
}

/** Markdown without math — also the fallback while the math chunk loads. */
function PlainMarkdown({
  content,
  inline,
}: ChatMarkdownProps): React.ReactElement {
  return (
    <ReactMarkdown
      remarkPlugins={REMARK_PLUGINS}
      components={inline ? inlineComponents : baseComponents}
    >
      {content}
    </ReactMarkdown>
  );
}

/** The single markdown renderer for chat message bodies. */
export function ChatMarkdown({
  content,
  inline = false,
}: ChatMarkdownProps): React.ReactElement {
  const plain = <PlainMarkdown content={content} inline={inline} />;
  if (!MATH_DELIMITERS.test(content)) return plain;

  return (
    <React.Suspense fallback={plain}>
      <ChatMarkdownMath content={content} inline={inline} />
    </React.Suspense>
  );
}

export default ChatMarkdown;
