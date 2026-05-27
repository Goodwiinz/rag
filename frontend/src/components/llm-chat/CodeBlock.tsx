'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

const SyntaxHighlighter = dynamic(
  () => import('react-syntax-highlighter/dist/esm/prism').then((mod) => mod.default),
  {
    loading: () => (
      <pre className="p-4 rounded bg-[var(--terminal-bg)] text-xs font-mono overflow-x-auto">
        <code>Loading...</code>
      </pre>
    ),
    ssr: false,
  }
);
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Copy, Check } from 'lucide-react';

interface CodeBlockProps {
  language: string;
  value: string;
  inline?: boolean;
}

export function CodeBlock({ language, value, inline }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (inline) {
    return (
      <code className="px-1.5 py-0.5 rounded bg-[#1A1A1A] text-purple-400 text-sm font-mono border border-[#27272A]">
        {value}
      </code>
    );
  }

  return (
    <div className="my-4 rounded-lg overflow-hidden border border-[#27272A] shadow-lg">
      <div className="flex items-center justify-between px-4 py-2 bg-[#1A1A1A] border-b border-[#27272A]">
        <span className="text-xs text-gray-400 font-mono uppercase">{language || 'text'}</span>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                onClick={handleCopy}
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs text-gray-400 hover:text-white hover:bg-white/5"
              >
                {copied ? (
                  <>
                    <Check className="w-3 h-3 mr-1 text-green-400" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3 mr-1" />
                    Copy
                  </>
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>Copy code</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
      <SyntaxHighlighter
        language={language || 'text'}
        style={vscDarkPlus}
        customStyle={{
          margin: 0,
          padding: '1rem',
          background: '#0E1015',
          fontSize: '0.875rem',
          lineHeight: '1.5',
        }}
        showLineNumbers={value.split('\n').length > 10}
      >
        {value}
      </SyntaxHighlighter>
    </div>
  );
}
