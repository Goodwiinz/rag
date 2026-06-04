import React from 'react';
import { AnalyticsDashboard } from '@/components/analytics/AnalyticsDashboard';

const AnalyticsOverviewPage: React.FC = () => {
  return (
    <div className="px-4 py-6 sm:px-6 lg:px-8">
      <AnalyticsDashboard />
    </div>
  );
};

export default AnalyticsOverviewPage;
