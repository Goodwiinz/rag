'use client';

import { ArrowRight } from 'lucide-react';
import Link from 'next/link';

import { GoesOutComesInUnderline } from '@/components/ui/underline-animation';

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
      {/* Closing CTA */}
      <section className="py-24 px-6 border-t border-(--nous-shade) bg-(--nous-obsidian)">
        <div className="max-w-3xl mx-auto text-center">
          <h2
            className="text-3xl md:text-4xl font-bold tracking-tight text-(--nous-ivory) mb-5"
            style={{ fontFamily: 'var(--nous-font-heading)' }}
          >
            Point it at your corpus and start asking.
          </h2>
          <p
            className="text-lg text-(--nous-parchment) leading-relaxed mb-10"
            style={{ fontFamily: 'var(--nous-font-body)' }}
          >
            Hybrid search across millions of documents, 12ms median, every
            answer traceable to its source.
          </p>

          <Link
            href="/register"
            className="group inline-flex items-center gap-2 h-12 px-7 rounded-(--nous-radius-md) text-sm font-semibold bg-(--nous-sol) text-(--nous-erebus) transition-colors hover:bg-(--nous-helios) focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-(--nous-sol)/50 focus-visible:ring-offset-2 focus-visible:ring-offset-(--nous-obsidian)"
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          >
            Get started
            <ArrowRight
              className="w-4 h-4 transition-transform group-hover:translate-x-0.5"
              aria-hidden="true"
            />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="pt-20 pb-10 px-6 border-t border-(--nous-shade)">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-10 mb-16">
            <div className="col-span-2 md:col-span-1">
              <span
                className="text-base font-bold tracking-[0.18em] text-(--nous-ivory)"
                style={{ fontFamily: 'var(--nous-font-heading)' }}
              >
                NOUS
              </span>
              <p
                className="mt-4 text-sm text-(--nous-parchment) leading-relaxed max-w-xs"
                style={{ fontFamily: 'var(--nous-font-body)' }}
              >
                A multimodal intelligence platform for research teams who need
                answers they can cite.
              </p>
            </div>

            {FOOTER_COLS.map((col) => (
              <nav key={col.head} aria-label={col.head}>
                <h3
                  className="text-xs font-semibold uppercase tracking-[0.12em] text-(--nous-parchment) mb-4"
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
                        className="inline-block text-sm text-(--nous-parchment) hover:text-(--nous-ivory) transition-colors rounded-sm focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-(--nous-sol)/40"
                      >
                        <GoesOutComesInUnderline
                          label={l.label}
                          direction="left"
                        />
                      </Link>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>

          <div
            className="pt-8 border-t border-(--nous-shade) text-sm text-(--nous-parchment)"
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          >
            &copy; 2026 NOUS. All rights reserved.
          </div>
        </div>
      </footer>
    </>
  );
}
