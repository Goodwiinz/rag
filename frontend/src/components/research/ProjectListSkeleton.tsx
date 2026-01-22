'use client';

/**
 * Project List Skeleton
 * Loading placeholder for the project list component
 */

import React from 'react';

interface ProjectListSkeletonProps {
  count?: number;
}

export const ProjectListSkeleton: React.FC<ProjectListSkeletonProps> = ({
  count = 6,
}) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, idx) => (
        <div
          key={idx}
          className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-4 animate-pulse"
          style={{ animationDelay: `${idx * 0.1}s` }}
        >
          {/* Header */}
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded bg-[#1a1a1a]" />
              <div className="h-4 w-32 bg-[#1a1a1a] rounded" />
            </div>
            <div className="w-4 h-4 bg-[#1a1a1a] rounded" />
          </div>

          {/* Description */}
          <div className="space-y-2 mb-3">
            <div className="h-3 w-full bg-[#1a1a1a] rounded" />
            <div className="h-3 w-3/4 bg-[#1a1a1a] rounded" />
          </div>

          {/* Stats */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 bg-[#1a1a1a] rounded" />
              <div className="h-3 w-12 bg-[#1a1a1a] rounded" />
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 bg-[#1a1a1a] rounded" />
              <div className="h-3 w-16 bg-[#1a1a1a] rounded" />
            </div>
          </div>

          {/* Date */}
          <div className="mt-3">
            <div className="h-3 w-24 bg-[#1a1a1a] rounded" />
          </div>
        </div>
      ))}
    </div>
  );
};

export default ProjectListSkeleton;
