// nous-nav.tsx — Sticky top nav with NOUS wordmark, tabs, and avatar.
// Cosmetic: anchors are hrefs, not Next links, because this is a showcase component.
import * as React from 'react';

export interface NousNavItem {
  label: string;
  href: string;
}

interface NousNavProps {
  items?: NousNavItem[];
  activeHref?: string;
  user?: string;
  onInvite?: () => void;
}

const DEFAULT_ITEMS: NousNavItem[] = [
  { label: 'Workspace', href: '#workspace' },
  { label: 'Agents', href: '#chat' },
  { label: 'Sources', href: '#search' },
  { label: 'Graph', href: '#primitives' },
];

export function NousNav({
  items = DEFAULT_ITEMS,
  activeHref,
  user = 'Maya Chen',
  onInvite,
}: NousNavProps) {
  const active = activeHref ?? items[0]?.href;
  const initials = user
    .split(' ')
    .map((n) => n[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('');

  return (
    <nav
      className="sticky top-0 z-40 h-14 border-b backdrop-blur-md"
      style={{
        borderColor: 'var(--nous-border-1)',
        background: 'color-mix(in oklab, var(--nous-bg-1) 90%, transparent)',
      }}
    >
      <div className="mx-auto flex h-full max-w-[1400px] items-center justify-between px-6">
        <div className="flex items-center gap-8">
          <span className="nous-wordmark text-[15px]">NOUS</span>
          <div className="hidden gap-6 md:flex">
            {items.map((item) => {
              const isActive = item.href === active;
              return (
                <a
                  key={item.href}
                  href={item.href}
                  className="text-sm font-medium transition-colors"
                  style={{
                    fontFamily: 'var(--nous-font-ui)',
                    color: isActive ? 'var(--nous-fg-1)' : 'var(--nous-fg-3)',
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive)
                      e.currentTarget.style.color = 'var(--nous-fg-1)';
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive)
                      e.currentTarget.style.color = 'var(--nous-fg-3)';
                  }}
                >
                  {item.label}
                </a>
              );
            })}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onInvite}
            className="h-9 rounded-md px-3 text-sm font-medium transition-colors"
            style={{
              fontFamily: 'var(--nous-font-ui)',
              color: 'var(--nous-fg-2)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--nous-fg-1)';
              e.currentTarget.style.background = 'var(--nous-aurum)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--nous-fg-2)';
              e.currentTarget.style.background = 'transparent';
            }}
          >
            Invite
          </button>
          <div
            className="grid h-8 w-8 place-items-center rounded-full text-xs font-semibold text-white"
            style={{
              background: 'var(--nous-sol)',
              fontFamily: 'var(--nous-font-ui)',
            }}
            aria-label={`Signed in as ${user}`}
          >
            {initials || '•'}
          </div>
        </div>
      </div>
    </nav>
  );
}
