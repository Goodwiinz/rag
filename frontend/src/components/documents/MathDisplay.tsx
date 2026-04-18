'use client';

import React, { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MathDisplayProps {
  content: string;
  format?: 'latex' | 'markdown';
  block?: boolean;
}

export const MathDisplay: React.FC<MathDisplayProps> = ({
  content,
  format = 'latex',
  block = false,
}) => {
  const [katexHtml, setKatexHtml] = useState<string | null>(null);
  const [katexLoaded, setKatexLoaded] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (format !== 'latex') return;

    let cancelled = false;

    const loadKatex = async () => {
      try {
        const katex = (await import('katex')).default;
        await import('katex/dist/katex.min.css');

        if (cancelled) return;

        const html = katex.renderToString(content, {
          throwOnError: false,
          displayMode: block,
        });
        setKatexHtml(html);
        setKatexLoaded(true);
      } catch {
        if (!cancelled) {
          setKatexLoaded(false);
          setError(false);
        }
      }
    };

    loadKatex();
    return () => {
      cancelled = true;
    };
  }, [content, format, block]);

  if (format === 'markdown') {
    return (
      <pre
        className={cn(
          'font-mono text-sm text-gray-300 whitespace-pre-wrap',
          block
            ? 'my-3 rounded-lg border border-[#1a1a1a] bg-black/30 p-4'
            : 'inline rounded bg-black/30 px-1.5 py-0.5'
        )}
      >
        {content}
      </pre>
    );
  }

  if (katexLoaded && katexHtml) {
    return (
      <span
        className={cn(block && 'my-3 flex justify-center')}
        dangerouslySetInnerHTML={{ __html: katexHtml }}
      />
    );
  }

  if (error) {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1.5',
          block && 'my-3 flex justify-center'
        )}
      >
        <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-[#ffb700]" />
        <code
          className={cn(
            'font-mono text-sm text-gray-300',
            'rounded border border-[#1a1a1a] bg-black/30 px-2 py-1',
            'bg-gradient-to-r from-purple-500/5 to-[#00d4ff]/5'
          )}
        >
          {content}
        </code>
      </span>
    );
  }

  return (
    <code
      className={cn(
        'font-mono text-sm text-gray-300',
        'rounded border border-[#1a1a1a] bg-black/30 px-2 py-1',
        'bg-gradient-to-r from-purple-500/5 to-[#00d4ff]/5',
        block && 'my-3 block text-center'
      )}
    >
      {content}
    </code>
  );
};

export default MathDisplay;
