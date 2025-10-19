import React from 'react';

export const PageSkeleton: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 animate-pulse">
      <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {/* Header skeleton */}
        <div className="mb-8">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        </div>

        {/* Content skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-white p-6 rounded-lg shadow">
              <div className="h-4 bg-gray-200 rounded w-3/4 mb-4"></div>
              <div className="h-8 bg-gray-200 rounded w-1/2"></div>
            </div>
          ))}
        </div>

        {/* Table skeleton */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6">
            <div className="h-6 bg-gray-200 rounded w-1/4 mb-4"></div>
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-12 bg-gray-100 rounded mb-2"></div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
