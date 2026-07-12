'use client';

import { CapabilitiesSection } from '@/components/landing/CapabilitiesSection';
import { FooterSection } from '@/components/landing/FooterSection';
import { HeroSection } from '@/components/landing/HeroSection';
import { useAuth } from '@/hooks/useAuth';

export default function HomePage() {
  const { isAuthenticated } = useAuth();

  return (
    <div
      className="min-h-screen flex flex-col bg-[var(--nous-nyx)] text-[var(--nous-ivory)] selection:bg-[var(--nous-sol)] selection:text-[var(--nous-erebus)]"
      suppressHydrationWarning
    >
      <HeroSection isAuthenticated={isAuthenticated} />
      <CapabilitiesSection />
      <FooterSection />
    </div>
  );
}
