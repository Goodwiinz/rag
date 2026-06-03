import React from 'react';

export const SystemMonitoringPage: React.FC = () => {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">
          System Monitoring
        </h1>
      </div>
      <div className="bg-white rounded-lg shadow p-6">
        <p className="text-foreground">
          Monitor system health and performance metrics.
        </p>
      </div>
    </div>
  );
};

export default SystemMonitoringPage;
