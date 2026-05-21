'use client';

import { CapabilitiesSection } from '@/components/landing/CapabilitiesSection';
import { FooterSection } from '@/components/landing/FooterSection';
import { HeroSection } from '@/components/landing/HeroSection';
import { useAuth } from '@/hooks/useAuth';
import { useScroll, useTransform } from 'framer-motion';

export default function HomePage() {
  const { isAuthenticated } = useAuth();
  const { scrollYProgress } = useScroll();
  const opacity = useTransform(scrollYProgress, [0, 0.2], [1, 0]);

  return (
    <div
      className="min-h-screen bg-[var(--terminal-bg)] relative overflow-x-hidden flex flex-col noise-texture selection:bg-[var(--phosphor-green)] selection:text-[var(--terminal-bg)]"
      suppressHydrationWarning
    >
      {/* Dynamic Background */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(212,160,57,0.03),transparent_50%)]" />
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[var(--terminal-border)] to-transparent opacity-20" />
        <div className="hidden md:block absolute inset-0 terminal-grid opacity-[0.03]" />
      </div>

      <HeroSection isAuthenticated={isAuthenticated} scrollOpacity={opacity} />
      <CapabilitiesSection />
      <FooterSection />
    </div>
  );
}
