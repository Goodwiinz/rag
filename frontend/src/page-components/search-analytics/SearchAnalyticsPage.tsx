import React from 'react';

export const SearchAnalyticsPage: React.FC = () => {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Search Analytics</h1>
      </div>
      <div className="bg-white rounded-lg shadow p-6">
        <p className="text-foreground">
          Analyze search patterns and query performance.
        </p>
      </div>
    </div>
  );
};

export default SearchAnalyticsPage;
