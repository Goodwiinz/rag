'use client';

import { ArrowRight } from 'lucide-react';
import Link from 'next/link';

const STATS = [
  { label: 'Median latency', val: '12ms' },
  { label: 'Uptime', val: '99.99%' },
] as const;

const FOOTER_COLS = [
  {
    head: 'Product',
    links: [
      { label: 'Features', href: '/#features' },
      { label: 'Search', href: '/search' },
      { label: 'Dashboard', href: '/dashboard' },
    ],
  },
  {
    head: 'Account',
    links: [
      { label: 'Sign in', href: '/login' },
      { label: 'Get started', href: '/register' },
    ],
  },
] as const;

export function FooterSection() {
  return (
    <>
      {/* Closing CTA + metrics */}
      <section className="py-24 px-6 border-t border-[var(--nous-shade)] bg-[var(--nous-obsidian)]">
        <div className="max-w-5xl mx-auto text-center">
          <h2
            className="text-3xl md:text-4xl font-bold tracking-tight text-[var(--nous-ivory)] mb-12"
            style={{ fontFamily: 'var(--nous-font-heading)' }}
          >
            Built to scale with what you know.
          </h2>

          <dl className="flex flex-wrap justify-center gap-x-16 gap-y-8 mb-14">
            {STATS.map((stat) => (
              <div key={stat.label} className="text-center">
                <dt
                  className="text-3xl md:text-4xl font-bold text-[var(--nous-sol)]"
                  style={{ fontFamily: 'var(--nous-font-heading)' }}
                >
                  {stat.val}
                </dt>
                <dd
                  className="mt-1 text-sm text-[var(--nous-parchment)]"
                  style={{ fontFamily: 'var(--nous-font-ui)' }}
                >
                  {stat.label}
                </dd>
              </div>
            ))}
          </dl>

          <Link
            href="/dashboard"
            className="group inline-flex items-center gap-2 h-12 px-7 rounded-[var(--nous-radius-md)] text-sm font-semibold bg-[var(--nous-sol)] text-[var(--nous-erebus)] transition-colors hover:bg-[var(--nous-helios)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--nous-obsidian)]"
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          >
            Open dashboard
            <ArrowRight
              className="w-4 h-4 transition-transform group-hover:translate-x-0.5"
              aria-hidden="true"
            />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="pt-20 pb-10 px-6 border-t border-[var(--nous-shade)]">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-10 mb-16">
            <div className="col-span-2 md:col-span-1">
              <span
                className="text-base font-bold tracking-[0.18em] text-[var(--nous-ivory)]"
                style={{ fontFamily: 'var(--nous-font-heading)' }}
              >
                NOUS
              </span>
              <p
                className="mt-4 text-sm text-[var(--nous-parchment)] leading-relaxed max-w-xs"
                style={{ fontFamily: 'var(--nous-font-body)' }}
              >
                A multimodal intelligence platform for research teams who need
                answers they can cite.
              </p>
            </div>

            {FOOTER_COLS.map((col) => (
              <nav key={col.head} aria-label={col.head}>
                <h3
                  className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--nous-parchment)] mb-4"
                  style={{ fontFamily: 'var(--nous-font-ui)' }}
                >
                  {col.head}
                </h3>
                <ul
                  className="space-y-2.5"
                  style={{ fontFamily: 'var(--nous-font-ui)' }}
                >
                  {col.links.map((l) => (
                    <li key={l.label}>
                      <Link
                        href={l.href}
                        className="text-sm text-[var(--nous-parchment)] hover:text-[var(--nous-ivory)] transition-colors rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
                      >
                        {l.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>

          <div
            className="pt-8 border-t border-[var(--nous-shade)] text-sm text-[var(--nous-parchment)]"
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          >
            &copy; 2026 NOUS. All rights reserved.
          </div>
        </div>
      </footer>
    </>
  );
}
