'use client';

import { AnalyticsDashboard } from '@/components/analytics/AnalyticsDashboard';
import { initializeAnalytics } from '@/lib/analytics';
import { useEffect } from 'react';

export default function AnalyticsPage() {
  useEffect(() => {
    // Initialize analytics if not already done
    if (typeof window !== 'undefined') {
      initializeAnalytics({
        provider: 'none', // Change to 'google-analytics' or 'plausible' as needed
        trackPageViews: true,
        trackEvents: true,
        enableDebug: process.env.NODE_ENV === 'development',
      });
    }
  }, []);

  return (
    <div
      data-testid="analytics-dashboard"
      className="min-h-screen bg-background p-6 text-foreground"
    >
      <AnalyticsDashboard />
    </div>
  );
}
