'use client';

import React, { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import DOMPurify from 'dompurify';
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
    // Configure DOMPurify to allow KaTeX math markup (MathML and specific HTML elements)
    const cleanHtml = DOMPurify.sanitize(katexHtml, {
      USE_PROFILES: { mathMl: true, html: true },
      ALLOWED_TAGS: [
        'math', 'annotation', 'semantics', 'mtext', 'mn', 'mo', 'mi', 'mspace',
        'mover', 'munder', 'munderover', 'msup', 'msub', 'msubsup', 'mfrac',
        'mroot', 'msqrt', 'mtable', 'mtr', 'mtd', 'mlabeledtr', 'mrow', 'menclose',
        'style', 'span', 'div', 'svg', 'path', 'g', 'line', 'rect', 'circle'
      ],
      ALLOWED_ATTR: [
        'class', 'id', 'style', 'aria-hidden', 'encoding', 'href', 'd', 'viewbox',
        'preserveaspectratio', 'width', 'height', 'xmlns', 'viewBox'
      ],
    });

    return (
      <span
        className={cn(block && 'my-3 flex justify-center')}
        dangerouslySetInnerHTML={{ __html: cleanHtml }}
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
        <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-helios" />
        <code
          className={cn(
            'font-mono text-sm text-gray-300',
            'rounded border border-[#1a1a1a] bg-black/30 px-2 py-1',
            'bg-gradient-to-r from-purple-500/5 to-brand-cyan/5'
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
        'bg-gradient-to-r from-purple-500/5 to-brand-cyan/5',
        block && 'my-3 block text-center'
      )}
    >
      {content}
    </code>
  );
};

export default MathDisplay;
