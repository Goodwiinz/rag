'use client';

import { InteractiveKnowledgeGraph } from '@/components/InteractiveKnowledgeGraph';
import { motion } from 'framer-motion';
import { ArrowRight, Lock, Search, Shield, Zap } from 'lucide-react';
import Link from 'next/link';

const EASE_OUT = [0.16, 1, 0.3, 1] as const;

const TRUST = [
  { icon: Shield, text: 'SOC 2 ready' },
  { icon: Zap, text: 'Sub-20ms search' },
  { icon: Lock, text: 'End-to-end encrypted' },
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
              className="text-[10px] text-[var(--nous-parchment)] tracking-[0.12em] mt-1"
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
              <Link
                href="/search"
                className="hover:text-[var(--nous-ivory)] transition-colors rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
              >
                Search
              </Link>
            </div>
            {isAuthenticated ? (
              <Link
                href="/dashboard"
                className="inline-flex items-center gap-2 h-9 px-4 rounded-[var(--nous-radius-md)] text-sm font-semibold bg-[var(--nous-sol)] text-[var(--nous-erebus)] transition-colors hover:bg-[var(--nous-helios)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--nous-nyx)]"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                Dashboard
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

      <section className="relative pt-32 pb-24 md:pt-44 md:pb-28 px-6">
        <div className="max-w-7xl mx-auto grid lg:grid-cols-[1.05fr_1fr] gap-16 items-center">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: EASE_OUT }}
          >
            <p
              className="text-xs font-semibold tracking-[0.16em] uppercase text-[var(--nous-sol)] mb-6"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Multimodal Intelligence Platform
            </p>

            <h1
              className="text-[var(--nous-ivory)] mb-8"
              style={{ fontFamily: 'var(--nous-font-heading)' }}
            >
              <span className="block text-6xl md:text-8xl font-bold text-[var(--nous-sol)] leading-none">
                νοῦς
              </span>
              <span className="block text-3xl md:text-5xl font-bold tracking-tight leading-[1.05] mt-4 max-w-[16ch]">
                Knowledge that answers back.
              </span>
            </h1>

            <p
              className="text-lg text-[var(--nous-parchment)] leading-relaxed max-w-[58ch] mb-10"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              Semantic search, knowledge graph extraction, and AI research
              workflows over your documents, papers, and data. One system that
              reads everything and cites its sources.
            </p>

            <div
              className="flex flex-wrap gap-3"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              <Link
                href="/documents/upload"
                className="group inline-flex items-center gap-2 h-12 px-6 rounded-[var(--nous-radius-md)] text-sm font-semibold bg-[var(--nous-sol)] text-[var(--nous-erebus)] transition-colors hover:bg-[var(--nous-helios)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--nous-nyx)]"
              >
                Start exploring
                <ArrowRight
                  className="w-4 h-4 transition-transform group-hover:translate-x-0.5"
                  aria-hidden="true"
                />
              </Link>
              <Link
                href="/search"
                className="inline-flex items-center gap-2 h-12 px-6 rounded-[var(--nous-radius-md)] text-sm font-semibold border border-[var(--nous-dusk)] text-[var(--nous-ivory)] transition-colors hover:border-[var(--nous-parchment)] hover:bg-[var(--nous-obsidian)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
              >
                <Search className="w-4 h-4" aria-hidden="true" />
                See it live
              </Link>
            </div>

            <ul
              className="mt-14 pt-7 border-t border-[var(--nous-shade)] flex flex-wrap items-center gap-x-8 gap-y-3 text-sm text-[var(--nous-parchment)]"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              {TRUST.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-center gap-2">
                  <Icon
                    className="w-4 h-4 text-[var(--nous-parchment)]"
                    aria-hidden="true"
                  />
                  {text}
                </li>
              ))}
            </ul>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.7, ease: EASE_OUT, delay: 0.1 }}
            className="relative rounded-[var(--nous-radius-xl)] border border-[var(--nous-shade)] bg-[var(--nous-obsidian)] overflow-hidden"
          >
            <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--nous-shade)]">
              <span
                className="text-sm text-[var(--nous-parchment)]"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                Live knowledge graph
              </span>
              <span
                className="flex items-center gap-2 text-xs text-[var(--nous-parchment)]"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full bg-[var(--nous-sol)]"
                  aria-hidden="true"
                />
                Connected
              </span>
            </div>
            <div
              className="h-[420px] md:h-[480px]"
              role="img"
              aria-label="Animated knowledge graph showing entities extracted from documents and the relationships connecting them"
            >
              <InteractiveKnowledgeGraph />
            </div>
          </motion.div>
        </div>
      </section>
    </>
  );
}
