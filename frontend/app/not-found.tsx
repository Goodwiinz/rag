'use client';

import Link from 'next/link';
import { Home, Search } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--nous-bg-1)]">
      <div className="max-w-2xl mx-auto px-6 py-20 text-center">
        <div className="mb-8">
          <h1 className="text-[120px] font-bold text-[var(--nous-sol)] font-mono leading-none mb-4">
            404
          </h1>
          <div className="flex items-center justify-center gap-3 mb-6">
            <Search className="w-8 h-8 text-[var(--nous-helios)]" />
            <h2 className="text-3xl font-bold text-[var(--nous-fg-1)] font-mono">
              PAGE NOT FOUND
            </h2>
          </div>
          <p className="text-lg text-[var(--nous-fg-3)] font-mono mb-8">
            The page you're looking for doesn't exist or has been moved.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 px-6 py-3 bg-[var(--nous-bg-3)] border-2 border-[var(--nous-sol)] text-[var(--nous-sol)] font-mono font-bold rounded-lg hover:bg-[var(--nous-sol)] hover:text-[var(--nous-bg-1)] transition-all shadow-[0_0_15px_var(--nous-sol-glow)]"
          >
            <Home className="w-5 h-5" />
            <span>GO TO DASHBOARD</span>
          </Link>
          <Link
            href="/search"
            className="inline-flex items-center gap-2 px-6 py-3 bg-[var(--nous-bg-2)] border-2 border-[var(--nous-border-1)] text-[var(--nous-fg-1)] font-mono font-bold rounded-lg hover:border-[var(--nous-helios)] hover:text-[var(--nous-helios)] transition-all"
          >
            <Search className="w-5 h-5" />
            <span>SEARCH</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
