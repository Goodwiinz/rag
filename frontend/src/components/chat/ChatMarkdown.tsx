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
      <pre className="w-full max-w-full overflow-x-auto rounded-lg bg-(--nous-bg-1) p-4 font-mono text-xs">
        <code>Loading...</code>
      </pre>
    ),
    ssr: false,
  }
);

/** remark plugins every chat message renders with (GFM: tables, task lists,
 * strikethrough, autolinks). Shared so the plain and citation-segmented
 * paths can't drift apart again. */
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
const baseComponents: Components = {
  h1({ children }) {
    return (
      <h1 className="mt-8 mb-3 max-w-[72ch] font-(family-name:--nous-font-heading) text-[1.5rem] leading-tight font-semibold tracking-[-0.02em] text-(--nous-fg-1) first:mt-0">
        {children}
      </h1>
    );
  },
  h2({ children }) {
    return (
      <h2 className="mt-7 mb-2.5 max-w-[72ch] font-(family-name:--nous-font-heading) text-[1.25rem] leading-snug font-semibold tracking-[-0.015em] text-(--nous-fg-1) first:mt-0">
        {children}
      </h2>
    );
  },
  h3({ children }) {
    return (
      <h3 className="mt-6 mb-2 max-w-[72ch] font-(family-name:--nous-font-heading) text-[1.0625rem] leading-snug font-semibold text-(--nous-fg-1) first:mt-0">
        {children}
      </h3>
    );
  },
  h4({ children }) {
    return (
      <h4 className="mt-5 mb-1.5 max-w-[72ch] font-(family-name:--nous-font-heading) text-[0.9375rem] leading-snug font-semibold text-(--nous-fg-2) first:mt-0">
        {children}
      </h4>
    );
  },
  p({ children }) {
    return (
      <p className="my-3 max-w-[72ch] text-[15px] leading-7 text-(--nous-fg-1) first:mt-0 last:mb-0">
        {children}
      </p>
    );
  },
  ul({ children }) {
    return (
      <ul className="my-3 max-w-[72ch] list-disc space-y-1 pl-6 marker:text-(--nous-sol)">
        {children}
      </ul>
    );
  },
  ol({ children }) {
    return (
      <ol className="my-3 max-w-[72ch] list-decimal space-y-1 pl-6 marker:font-medium marker:text-(--nous-fg-2)">
        {children}
      </ol>
    );
  },
  li({ children }) {
    return <li className="pl-1 text-[15px] leading-7">{children}</li>;
  },
  blockquote({ children }) {
    return (
      <blockquote className="my-4 max-w-[72ch] border-l-2 border-(--nous-sol)/50 pl-4 text-(--nous-fg-2) italic">
        {children}
      </blockquote>
    );
  },
  strong({ children }) {
    return (
      <strong className="font-semibold text-(--nous-fg-1)">{children}</strong>
    );
  },
  em({ children }) {
    return <em className="italic text-(--nous-fg-2)">{children}</em>;
  },
  hr() {
    return <hr className="my-6 max-w-[72ch] border-(--nous-border-1)" />;
  },
  pre({ children }) {
    const { className, value } = extractCodeChild(children);
    const match = /language-(\w+)/.exec(className);
    const code = value.replace(/\n$/, '');
    if (match) {
      return (
        <div
          data-slot="markdown-code-block"
          className="my-4 w-full max-w-full overflow-x-auto rounded-lg"
        >
          <SyntaxHighlighter style={oneDark} language={match[1]} PreTag="div">
            {code}
          </SyntaxHighlighter>
        </div>
      );
    }
    return (
      <pre
        data-slot="markdown-code-block"
        className="my-4 w-full max-w-full overflow-x-auto rounded-lg bg-(--nous-bg-1) p-4 font-mono text-xs"
      >
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
      <div
        data-slot="markdown-table-scroll"
        className="my-4 w-full max-w-full overflow-x-auto rounded-lg border border-(--nous-border-1)"
      >
        <table className="w-full min-w-[32rem] border-collapse text-left text-[13px]">
          {children}
        </table>
      </div>
    );
  },
  thead({ children }) {
    return <thead className="bg-(--nous-bg-2)">{children}</thead>;
  },
  th({ children }) {
    return (
      <th className="border-b border-(--nous-border-1) px-3 py-2 font-semibold text-(--nous-fg-1)">
        {children}
      </th>
    );
  },
  td({ children }) {
    return (
      <td className="border-b border-(--nous-border-1)/70 px-3 py-2 align-top text-(--nous-fg-2) last:border-b-0">
        {children}
      </td>
    );
  },
};

/** Variant for citation text segments: paragraphs unwrap to spans so a
 * <CitationLink> can sit inline between two markdown fragments. */
const inlineComponents: Components = {
  ...baseComponents,
  p({ children }) {
    return <span>{children}</span>;
  },
};

export interface ChatMarkdownProps {
  content: string;
  /** Unwrap paragraphs to spans (citation-segment interleaving). */
  inline?: boolean;
}

/** The single markdown renderer for chat message bodies. */
export function ChatMarkdown({
  content,
  inline = false,
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

export default ChatMarkdown;
