'use client';

/**
 * Citation Graph Skeleton
 * Loading placeholder for the citation graph component
 */

import React from 'react';

interface CitationGraphSkeletonProps {
  height?: string | number;
  className?: string;
}

export const CitationGraphSkeleton: React.FC<CitationGraphSkeletonProps> = ({
  height = 600,
  className = '',
}) => {
  return (
    <div
      className={`relative bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg overflow-hidden ${className}`}
      style={{ height }}
    >
      {/* Animated gradient background */}
      <div className="absolute inset-0 bg-gradient-to-r from-[#0a0a0a] via-[#1a1a1a] to-[#0a0a0a] animate-pulse" />

      {/* Fake nodes */}
      <div className="absolute inset-0 p-8">
        {/* Central node */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
          <div className="w-16 h-16 rounded-full bg-[#D4A039]/10 border-2 border-[#D4A039]/30 animate-pulse" />
        </div>

        {/* Surrounding nodes */}
        {[
          { top: '20%', left: '30%' },
          { top: '25%', left: '65%' },
          { top: '45%', left: '20%' },
          { top: '50%', left: '75%' },
          { top: '70%', left: '35%' },
          { top: '65%', left: '60%' },
        ].map((pos, idx) => (
          <div
            key={idx}
            className="absolute"
            style={{ top: pos.top, left: pos.left }}
          >
            <div
              className={`rounded-full bg-[#ffb700]/10 border-2 border-[#ffb700]/30 animate-pulse`}
              style={{
                width: 24 + Math.random() * 24,
                height: 24 + Math.random() * 24,
                animationDelay: `${idx * 0.1}s`,
              }}
            />
          </div>
        ))}

        {/* Fake edges (lines) */}
        <svg className="absolute inset-0 w-full h-full" style={{ opacity: 0.3 }}>
          <line x1="50%" y1="50%" x2="30%" y2="20%" stroke="#333" strokeWidth="1" />
          <line x1="50%" y1="50%" x2="65%" y2="25%" stroke="#333" strokeWidth="1" />
          <line x1="50%" y1="50%" x2="20%" y2="45%" stroke="#333" strokeWidth="1" />
          <line x1="50%" y1="50%" x2="75%" y2="50%" stroke="#333" strokeWidth="1" />
          <line x1="50%" y1="50%" x2="35%" y2="70%" stroke="#333" strokeWidth="1" />
          <line x1="50%" y1="50%" x2="60%" y2="65%" stroke="#333" strokeWidth="1" />
        </svg>
      </div>

      {/* Loading text */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2">
        <div className="w-4 h-4 border-2 border-[#D4A039]/30 border-t-[#D4A039] rounded-full animate-spin" />
        <span className="text-sm text-gray-500 font-mono">Loading citation graph...</span>
      </div>

      {/* Stats skeleton */}
      <div className="absolute top-4 left-4 bg-[#1a1a1a]/80 rounded px-3 py-2">
        <div className="flex items-center gap-4">
          <div className="h-3 w-16 bg-[#333] rounded animate-pulse" />
          <div className="h-3 w-20 bg-[#333] rounded animate-pulse" />
        </div>
      </div>

      {/* Controls skeleton */}
      <div className="absolute top-4 right-4 flex flex-col gap-2">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="w-8 h-8 bg-[#1a1a1a] border border-[#333] rounded animate-pulse"
          />
        ))}
      </div>
    </div>
  );
};

export default CitationGraphSkeleton;
