// nous-source-card.tsx — Retrieved source with citation pill, excerpt, and relevance score.
import * as React from 'react';

export interface NousSourceCardProps {
  title: string;
  excerpt: string;
  /** Human-readable source, e.g. "Dao et al. 2022 · flash_attn.pdf" */
  source: string;
  page?: number;
  /** Relevance score 0..1 */
  score: number;
  /** 1-indexed citation number rendered inline in chat */
  citationIndex: number;
}

export function NousSourceCard({
  title,
  excerpt,
  source,
  page,
  score,
  citationIndex,
}: NousSourceCardProps) {
  const isHighRelevance = score > 0.8;
  const scorePercent = Math.round(score * 100);

  return (
    <article
      className="rounded-xl border p-5 transition-all"
      style={{
        borderColor: 'var(--nous-border-1)',
        background: 'var(--nous-bg-2)',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = 'var(--nous-helios)';
        e.currentTarget.style.transform = 'translateY(-2px)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--nous-border-1)';
        e.currentTarget.style.transform = 'translateY(0)';
      }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span
            className="grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-semibold"
            style={{
              background: 'var(--nous-aurum)',
              color: 'var(--nous-sol-safe)',
              fontFamily: 'var(--nous-font-ui)',
            }}
          >
            {citationIndex}
          </span>
          <div>
            <h4
              className="text-sm font-semibold"
              style={{
                fontFamily: 'var(--nous-font-ui)',
                color: 'var(--nous-fg-1)',
              }}
            >
              {title}
            </h4>
            <p
              className="mt-0.5 text-xs"
              style={{
                fontFamily: 'var(--nous-font-mono)',
                color: 'var(--nous-fg-3)',
              }}
            >
              {source}
              {typeof page === 'number' ? ` · p. ${page}` : ''}
            </p>
          </div>
        </div>
        <span
          className="inline-flex items-center rounded-full px-3 py-1 text-xs font-medium"
          style={{
            fontFamily: 'var(--nous-font-ui)',
            background: isHighRelevance
              ? 'var(--nous-sol)'
              : 'var(--nous-aurum)',
            color: isHighRelevance ? '#FFFFFF' : 'var(--nous-sol-safe)',
          }}
        >
          {scorePercent}%
        </span>
      </div>
      <p
        className="mt-3 pl-9 text-sm leading-relaxed"
        style={{
          fontFamily: 'var(--nous-font-body)',
          color: 'var(--nous-fg-2)',
        }}
      >
        {excerpt}
      </p>
    </article>
  );
}
