'use client';

import Link from 'next/link';
import { Home, Search } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--terminal-bg)]">
      <div className="max-w-2xl mx-auto px-6 py-20 text-center">
        <div className="mb-8">
          <h1 className="text-[120px] font-bold text-[var(--phosphor-green)] font-mono leading-none mb-4">
            404
          </h1>
          <div className="flex items-center justify-center gap-3 mb-6">
            <Search className="w-8 h-8 text-[var(--cyan)]" />
            <h2 className="text-3xl font-bold text-[var(--terminal-text)] font-mono">
              PAGE NOT FOUND
            </h2>
          </div>
          <p className="text-lg text-[var(--terminal-text-dim)] font-mono mb-8">
            The page you're looking for doesn't exist or has been moved.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 px-6 py-3 bg-[var(--terminal-elevated)] border-2 border-[var(--phosphor-green)] text-[var(--phosphor-green)] font-mono font-bold rounded-lg hover:bg-[var(--phosphor-green)] hover:text-[var(--terminal-bg)] transition-all shadow-[0_0_15px_var(--phosphor-green-glow)]"
          >
            <Home className="w-5 h-5" />
            <span>GO TO DASHBOARD</span>
          </Link>
          <Link
            href="/search"
            className="inline-flex items-center gap-2 px-6 py-3 bg-[var(--terminal-surface)] border-2 border-[var(--terminal-border)] text-[var(--terminal-text)] font-mono font-bold rounded-lg hover:border-[var(--cyan)] hover:text-[var(--cyan)] transition-all"
          >
            <Search className="w-5 h-5" />
            <span>SEARCH</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
