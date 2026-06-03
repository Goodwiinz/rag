'use client';

import { InteractiveKnowledgeGraph } from '@/components/InteractiveKnowledgeGraph';
import { motion } from 'framer-motion';
import { ArrowRight, FileCheck, Gauge, ShieldCheck } from 'lucide-react';
import Link from 'next/link';

const EASE_OUT = [0.16, 1, 0.3, 1] as const;

// Honest, specific capabilities that each map to a real feature below.
// No unsubstantiated compliance/uptime badges.
const PROOF = [
  { icon: FileCheck, text: 'Cites every source' },
  { icon: ShieldCheck, text: 'Runs in your browser' },
  { icon: Gauge, text: '12ms median search' },
] as const;

interface HeroSectionProps {
  isAuthenticated: boolean;
}

export function HeroSection({ isAuthenticated }: HeroSectionProps) {
  return (
    <>
      <nav className="fixed top-0 inset-x-0 z-50 h-16 border-b border-[var(--nous-shade)] bg-[var(--nous-nyx)]/85 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between">
          <Link href="/" className="flex flex-col leading-none">
            <span
              className="text-[var(--nous-ivory)] text-base font-bold tracking-[0.18em]"
              style={{ fontFamily: 'var(--nous-font-heading)' }}
            >
              NOUS
            </span>
            <span
              className="text-[11px] text-[var(--nous-parchment)] tracking-[0.12em] mt-1"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Multimodal Intelligence
            </span>
          </Link>

          <div className="flex items-center gap-6">
            <div
              className="hidden md:flex items-center gap-7 text-sm text-[var(--nous-parchment)]"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              <a
                href="#features"
                className="hover:text-[var(--nous-ivory)] transition-colors rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
              >
                Features
              </a>
            </div>
            {isAuthenticated ? (
              <Link
                href="/dashboard"
                className="inline-flex items-center gap-2 h-9 px-4 rounded-[var(--nous-radius-md)] text-sm font-semibold bg-[var(--nous-sol)] text-[var(--nous-erebus)] transition-colors hover:bg-[var(--nous-helios)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--nous-nyx)]"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                Open dashboard
              </Link>
            ) : (
              <div
                className="flex items-center gap-2"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                <Link
                  href="/login"
                  className="h-9 px-3 inline-flex items-center text-sm text-[var(--nous-parchment)] hover:text-[var(--nous-ivory)] transition-colors rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
                >
                  Sign in
                </Link>
                <Link
                  href="/register"
                  className="inline-flex items-center gap-2 h-9 px-4 rounded-[var(--nous-radius-md)] text-sm font-semibold bg-[var(--nous-sol)] text-[var(--nous-erebus)] transition-colors hover:bg-[var(--nous-helios)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--nous-nyx)]"
                >
                  Get started
                </Link>
              </div>
            )}
          </div>
        </div>
      </nav>

      <section className="relative min-h-[88vh] flex items-center overflow-hidden px-6 pt-28 pb-20 md:pt-32">
        {/* The live knowledge graph IS the hero: full-bleed, interactive. */}
        <div className="absolute inset-0">
          <InteractiveKnowledgeGraph nodeCount={30} />
        </div>
        {/* Legibility mask: keeps the text column dark, lets the graph
            breathe toward the right and edges. */}
        <div
          aria-hidden="true"
          className="absolute inset-0 pointer-events-none bg-[radial-gradient(125%_125%_at_18%_42%,var(--nous-nyx)_32%,transparent_78%)]"
        />
        <div
          aria-hidden="true"
          className="absolute inset-x-0 bottom-0 h-32 pointer-events-none bg-[linear-gradient(to_top,var(--nous-nyx),transparent)]"
        />

        <div className="relative z-10 w-full max-w-7xl mx-auto pointer-events-none">
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: EASE_OUT }}
            className="max-w-2xl"
          >
            <p
              className="text-xs font-semibold tracking-[0.16em] uppercase text-[var(--nous-sol)] mb-8"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Multimodal Intelligence Platform
            </p>

            <h1
              className="text-[var(--nous-ivory)] mb-8"
              style={{ fontFamily: 'var(--nous-font-heading)' }}
            >
              <span className="block text-7xl sm:text-8xl md:text-[10rem] font-bold text-[var(--nous-sol)] leading-[0.9] tracking-tight">
                νοῦς
              </span>
              <span className="block text-3xl md:text-5xl font-bold tracking-tight leading-[1.05] mt-5 max-w-[18ch]">
                Knowledge that answers back.
              </span>
            </h1>

            <p
              className="text-lg text-[var(--nous-parchment)] leading-relaxed max-w-[56ch] mb-10"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              Semantic search, knowledge graph extraction, and AI research
              workflows over your documents, papers, and data. One system that
              reads everything and cites its sources.
            </p>

            <div
              className="flex flex-wrap gap-3 pointer-events-auto"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              {isAuthenticated ? (
                <Link
                  href="/dashboard"
                  className="group inline-flex items-center gap-2 h-12 px-6 rounded-[var(--nous-radius-md)] text-sm font-semibold bg-[var(--nous-sol)] text-[var(--nous-erebus)] transition-colors hover:bg-[var(--nous-helios)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--nous-nyx)]"
                >
                  Open dashboard
                  <ArrowRight
                    className="w-4 h-4 transition-transform group-hover:translate-x-0.5"
                    aria-hidden="true"
                  />
                </Link>
              ) : (
                <Link
                  href="/register"
                  className="group inline-flex items-center gap-2 h-12 px-6 rounded-[var(--nous-radius-md)] text-sm font-semibold bg-[var(--nous-sol)] text-[var(--nous-erebus)] transition-colors hover:bg-[var(--nous-helios)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--nous-nyx)]"
                >
                  Get started
                  <ArrowRight
                    className="w-4 h-4 transition-transform group-hover:translate-x-0.5"
                    aria-hidden="true"
                  />
                </Link>
              )}
              <a
                href="#features"
                className="inline-flex items-center gap-2 h-12 px-6 rounded-[var(--nous-radius-md)] text-sm font-semibold border border-[var(--nous-dusk)] text-[var(--nous-ivory)] transition-colors hover:border-[var(--nous-parchment)] hover:bg-[var(--nous-obsidian)]/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
              >
                Explore the platform
              </a>
            </div>

            <ul
              className="mt-14 pt-7 border-t border-[var(--nous-shade)] flex flex-wrap items-center gap-x-8 gap-y-3 text-sm text-[var(--nous-parchment)]"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              {PROOF.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-center gap-2">
                  <Icon
                    className="w-4 h-4 text-[var(--nous-sol)]"
                    aria-hidden="true"
                  />
                  {text}
                </li>
              ))}
            </ul>
          </motion.div>
        </div>
      </section>
    </>
  );
}
