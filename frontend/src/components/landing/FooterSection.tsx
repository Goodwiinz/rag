'use client';

import { Button } from '@/components/ui/button';
import {
  Activity,
  Command,
  Globe,
  LayoutDashboard,
  Terminal,
} from 'lucide-react';
import Link from 'next/link';

export function FooterSection() {
  return (
    <>
      {/* System Metrics CTA */}
      <section className="py-24 border-y border-[var(--terminal-border)] bg-[var(--terminal-surface)] relative overflow-hidden">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute inset-0 bg-[linear-gradient(45deg,transparent_25%,var(--terminal-border)_25%,var(--terminal-border)_50%,transparent_50%,transparent_75%,var(--terminal-border)_75%,var(--terminal-border)_100%)] bg-[length:20px_20px]" />
        </div>

        <div className="max-w-5xl mx-auto px-6 text-center relative z-10">
          <h2 className="text-3xl font-mono font-bold text-[var(--terminal-text)] mb-8">
            SYSTEM_METRICS_OBSERVATORY
          </h2>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-12">
            {[
              { label: 'Documents', val: '1.2M+' },
              { label: 'Entities', val: '54M+' },
              { label: 'Avg Latency', val: '12ms' },
              { label: 'Uptime', val: '99.99%' },
            ].map((stat, i) => (
              <div
                key={i}
                className="p-6 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)]"
              >
                <div className="text-2xl md:text-3xl font-bold font-mono text-[var(--phosphor-green)] mb-1">
                  {stat.val}
                </div>
                <div className="text-[10px] font-mono uppercase tracking-widest text-[var(--terminal-text-muted)] opacity-70">
                  {stat.label}
                </div>
              </div>
            ))}
          </div>

          <Link href="/dashboard">
            <Button
              size="lg"
              className="h-14 px-10 font-mono text-sm font-bold bg-[var(--terminal-text)] text-[var(--terminal-bg)] hover:bg-[var(--terminal-text)]/90 hover:scale-105 transition-all"
            >
              INITIALIZE_DASHBOARD <LayoutDashboard className="w-4 h-4 ml-2" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[var(--terminal-bg)] pt-20 pb-10 border-t border-[var(--terminal-border)]">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-10 mb-16">
            <div className="col-span-2 md:col-span-1">
              <div className="flex items-center gap-2 mb-4">
                <Terminal className="w-5 h-5 text-[var(--phosphor-green)]" />
                <span className="font-mono font-bold text-[var(--terminal-text)]">
                  RAG_OS
                </span>
              </div>
              <p className="font-mono text-xs text-[var(--terminal-text-muted)] leading-relaxed">
                Next-generation knowledge retrieval system for enterprise
                intelligence.
              </p>
            </div>

            {[
              {
                head: 'Product',
                links: ['Features', 'Integrations', 'Security', 'Changelog'],
              },
              {
                head: 'Resources',
                links: [
                  'Documentation',
                  'API Reference',
                  'Status',
                  'Community',
                ],
              },
              {
                head: 'Company',
                links: ['About', 'Blog', 'Careers', 'Contact'],
              },
            ].map((col, i) => (
              <div key={i}>
                <h4 className="font-mono text-xs font-bold text-[var(--terminal-text)] mb-4 uppercase tracking-wider">
                  {col.head}
                </h4>
                <ul className="space-y-2">
                  {col.links.map((l) => (
                    <li key={l}>
                      <Link
                        href="#"
                        className="font-mono text-xs text-[var(--terminal-text-muted)] hover:text-[var(--phosphor-green)] transition-colors"
                      >
                        {l}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="pt-8 border-t border-[var(--terminal-border)] flex flex-col md:flex-row justify-between items-center gap-4">
            <div className="font-mono text-[10px] text-[var(--terminal-text-muted)]">
              &copy; 2024 RAG_OS SYSTEMS INC. ALL RIGHTS RESERVED.
            </div>
            <div className="flex items-center gap-6">
              {[Globe, Activity, Command].map((Icon, i) => (
                <Icon
                  key={i}
                  className="w-4 h-4 text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)] cursor-pointer transition-colors"
                />
              ))}
            </div>
          </div>
        </div>
      </footer>
    </>
  );
}
