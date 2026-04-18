'use client';

import { motion } from 'framer-motion';
import { CheckCircle } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useEffect, useState } from 'react';

export default function VerifyEmailPage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const timer = setTimeout(() => router.push('/login'), 4000);
    return () => clearTimeout(timer);
  }, [router]);

  if (!mounted) return null;

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--terminal-bg)]">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md w-full mx-6"
      >
        <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-10 text-center">
          <div className="flex items-center justify-center w-16 h-16 rounded-full bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/30 mx-auto mb-6">
            <CheckCircle className="w-8 h-8 text-[var(--phosphor-green)]" />
          </div>
          <h2 className="text-xl font-mono font-bold text-[var(--terminal-text)] uppercase tracking-[0.15em] mb-3">
            Identity Verified
          </h2>
          <p className="text-sm font-mono text-[var(--terminal-text-muted)] mb-6 leading-relaxed">
            Your account has been activated. Redirecting to login...
          </p>
          <div className="h-1 w-24 mx-auto rounded-full bg-[var(--terminal-border)] overflow-hidden mb-6">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: '100%' }}
              transition={{ duration: 4 }}
              className="h-full bg-[var(--phosphor-green)]"
            />
          </div>
          <Link
            href="/login"
            className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest hover:text-[var(--phosphor-green)] transition-colors"
          >
            Go to Access Terminal
          </Link>
        </div>
      </motion.div>
    </div>
  );
}
