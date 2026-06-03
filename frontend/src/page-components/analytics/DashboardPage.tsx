import React from 'react';

const DashboardPage: React.FC = () => {
  return (
    <div className="px-4 sm:px-6 lg:px-8">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-semibold text-foreground">Dashboard</h1>
          <p className="mt-2 text-sm text-foreground">
            Overview of system metrics and performance
          </p>
        </div>
      </div>
      <div className="mt-8">
        <p className="text-muted-foreground">
          Dashboard implementation coming soon...
        </p>
      </div>
    </div>
  );
};

export default DashboardPage;
