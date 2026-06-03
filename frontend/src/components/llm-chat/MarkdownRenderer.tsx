'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CodeBlock } from './CodeBlock';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

const MarkdownComponents = {
  code: ({ inline, className, children, ...props }: any) => {
    const match = /language-(\w+)/.exec(className || '');
    const language = match ? match[1] : '';
    const value = String(children).replace(/\n$/, '');
    return <CodeBlock language={language} value={value} inline={inline} />;
  },
  p: ({ children }: any) => (
    <p className="mb-4 last:mb-0 leading-relaxed text-muted-foreground">
      {children}
    </p>
  ),
  ul: ({ children }: any) => (
    <ul className="list-disc list-inside mb-4 space-y-1.5 text-muted-foreground">
      {children}
    </ul>
  ),
  ol: ({ children }: any) => (
    <ol className="list-decimal list-inside mb-4 space-y-1.5 text-muted-foreground">
      {children}
    </ol>
  ),
  li: ({ children }: any) => <li className="leading-relaxed">{children}</li>,
  h1: ({ children }: any) => (
    <h1 className="text-2xl font-bold mb-4 mt-6 first:mt-0 text-white">
      {children}
    </h1>
  ),
  h2: ({ children }: any) => (
    <h2 className="text-xl font-bold mb-3 mt-5 first:mt-0 text-white">
      {children}
    </h2>
  ),
  h3: ({ children }: any) => (
    <h3 className="text-lg font-semibold mb-2 mt-4 first:mt-0 text-white">
      {children}
    </h3>
  ),
  blockquote: ({ children }: any) => (
    <blockquote className="rounded-[var(--nous-radius-md)] bg-[var(--nous-bg-2)] px-4 py-2 my-4 italic text-muted-foreground">
      {children}
    </blockquote>
  ),
  a: ({ children, href }: any) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-purple-400 hover:text-purple-300 underline"
    >
      {children}
    </a>
  ),
  table: ({ children }: any) => (
    <div className="my-4 overflow-x-auto rounded-lg border border-[#27272A]">
      <table className="min-w-full divide-y divide-[#27272A]">{children}</table>
    </div>
  ),
  thead: ({ children }: any) => (
    <thead className="bg-[#1A1A1A]">{children}</thead>
  ),
  tbody: ({ children }: any) => (
    <tbody className="divide-y divide-[#27272A] bg-[#0E1015]">{children}</tbody>
  ),
  tr: ({ children }: any) => <tr>{children}</tr>,
  th: ({ children }: any) => (
    <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase">
      {children}
    </th>
  ),
  td: ({ children }: any) => (
    <td className="px-4 py-3 text-sm text-muted-foreground">{children}</td>
  ),
  hr: () => <hr className="my-6 border-[#27272A]" />,
  strong: ({ children }: any) => (
    <strong className="font-semibold text-white">{children}</strong>
  ),
};

export function MarkdownRenderer({
  content,
  className = '',
}: MarkdownRendererProps) {
  return (
    <div className={`prose-chat ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={MarkdownComponents}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
