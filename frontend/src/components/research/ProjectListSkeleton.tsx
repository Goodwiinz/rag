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
          className="rounded-xl border border-border bg-card p-5 shadow-sm animate-pulse"
          style={{ animationDelay: `${idx * 0.1}s` }}
        >
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="h-9 w-9 rounded-lg bg-muted" />
              <div className="h-4 w-32 rounded bg-muted" />
            </div>
            <div className="h-4 w-4 rounded bg-muted" />
          </div>
          <div className="space-y-2 mb-4">
            <div className="h-3 w-full rounded bg-muted" />
            <div className="h-3 w-3/4 rounded bg-muted" />
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1">
              <div className="h-3 w-3 rounded bg-muted" />
              <div className="h-3 w-16 rounded bg-muted" />
            </div>
            <div className="flex items-center gap-1">
              <div className="h-3 w-3 rounded bg-muted" />
              <div className="h-3 w-20 rounded bg-muted" />
            </div>
          </div>
          <div className="mt-3">
            <div className="h-3 w-24 rounded bg-muted" />
          </div>
        </div>
      ))}
    </div>
  );
};

export default ProjectListSkeleton;
