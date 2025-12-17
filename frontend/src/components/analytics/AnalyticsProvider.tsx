'use client';

import { useEffect, useRef } from 'react';
import { initializeAnalytics, getAnalytics } from '@/lib/analytics';

interface AnalyticsProviderProps {
  children: React.ReactNode;
}

export function AnalyticsProvider({ children }: AnalyticsProviderProps) {
  const initialized = useRef(false);

  useEffect(() => {
    if (!initialized.current && typeof window !== 'undefined') {
      // Initialize analytics based on environment
      const analyticsConfig = {
        provider: (process.env.NEXT_PUBLIC_ANALYTICS_PROVIDER as any) || 'none',
        measurementId: process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID,
        customEndpoint: process.env.NEXT_PUBLIC_ANALYTICS_ENDPOINT,
        trackPageViews: true,
        trackEvents: true,
        enableDebug: process.env.NODE_ENV === 'development',
      };

      initializeAnalytics(analyticsConfig);
      initialized.current = true;

      // Track initial page view
      const analytics = getAnalytics();
      analytics.trackPageView(window.location.pathname, document.title);
    }
  }, []);

  return <>{children}</>;
}