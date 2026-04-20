// nous-chat-composer.tsx — Serif composer with tool chips and a Sol-accent Send button.
'use client';

import * as React from 'react';

export interface NousChatComposerProps {
  placeholder?: string;
  initialValue?: string;
  chips?: string[];
  onSubmit?: (value: string) => void;
  onChipClick?: (label: string) => void;
}

const DEFAULT_CHIPS = ['Sources', 'Agents', 'Graph'];

export function NousChatComposer({
  placeholder = 'Ask NOUS anything...',
  initialValue = '',
  chips = DEFAULT_CHIPS,
  onSubmit,
  onChipClick,
}: NousChatComposerProps) {
  const [value, setValue] = React.useState(initialValue);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!value.trim()) return;
    onSubmit?.(value);
    setValue('');
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border p-5 transition-all"
      style={{
        borderColor: 'var(--nous-border-1)',
        background: 'var(--nous-bg-2)',
        boxShadow: 'var(--nous-shadow-sm)',
      }}
      onFocus={(e) => {
        e.currentTarget.style.borderColor = 'var(--nous-sol)';
        e.currentTarget.style.boxShadow = 'var(--nous-shadow-lg)';
      }}
      onBlur={(e) => {
        e.currentTarget.style.borderColor = 'var(--nous-border-1)';
        e.currentTarget.style.boxShadow = 'var(--nous-shadow-sm)';
      }}
    >
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        aria-label="Ask NOUS"
        className="w-full bg-transparent outline-none"
        style={{
          fontFamily: 'var(--nous-font-body)',
          fontSize: '18px',
          color: 'var(--nous-fg-1)',
        }}
      />
      <div className="mt-4 flex items-center justify-between">
        <div className="flex flex-wrap gap-2">
          {chips.map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => onChipClick?.(chip)}
              className="rounded-full border px-3 py-1 text-xs font-medium transition-colors"
              style={{
                fontFamily: 'var(--nous-font-ui)',
                borderColor: 'var(--nous-border-1)',
                color: 'var(--nous-fg-2)',
                background: 'transparent',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--nous-sol)';
                e.currentTarget.style.color = 'var(--nous-sol-safe)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--nous-border-1)';
                e.currentTarget.style.color = 'var(--nous-fg-2)';
              }}
            >
              {chip}
            </button>
          ))}
        </div>
        <button
          type="submit"
          className="h-9 rounded-md px-4 text-sm font-medium text-white transition-transform"
          style={{
            fontFamily: 'var(--nous-font-ui)',
            background: 'var(--nous-sol)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-1px)';
            e.currentTarget.style.boxShadow = '0 8px 30px rgba(212,160,57,0.3)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = 'none';
          }}
        >
          Send
        </button>
      </div>
    </form>
  );
}
