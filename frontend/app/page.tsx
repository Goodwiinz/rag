'use client';

import { CapabilitiesSection } from '@/components/landing/CapabilitiesSection';
import { FooterSection } from '@/components/landing/FooterSection';
import { HeroSection } from '@/components/landing/HeroSection';
import { useAuth } from '@/hooks/useAuth';

export default function HomePage() {
  const { isAuthenticated } = useAuth();

  return (
    <div
      className="min-h-screen flex flex-col bg-(--nous-nyx) text-(--nous-ivory) selection:bg-(--nous-sol) selection:text-(--nous-erebus)"
      suppressHydrationWarning
    >
      <HeroSection isAuthenticated={isAuthenticated} />
      <CapabilitiesSection />
      <FooterSection />
    </div>
  );
}
