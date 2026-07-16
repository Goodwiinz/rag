"use client";

import React from "react";
import { motion } from "framer-motion";

export const StatsCardSkeleton: React.FC = () => {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="relative overflow-hidden rounded-xl bg-gradient-to-br from-amber-50/50 to-orange-50/30 backdrop-blur-lg border border-amber-200/20 shadow-lg"
    >
      <div className="absolute inset-0 bg-gradient-to-br from-amber-400/5 to-orange-400/5" />
      <div className="relative p-6">
        <div className="flex items-center justify-between">
          <div className="space-y-3 flex-1">
            <div className="h-4 bg-gray-200/50 rounded-full w-24 animate-pulse" />
            <div className="h-8 bg-gray-200/50 rounded-full w-32 animate-pulse" />
            <div className="h-3 bg-gray-200/50 rounded-full w-28 animate-pulse" />
          </div>
          <div className="h-12 w-12 bg-gray-200/50 rounded-2xl animate-pulse" />
        </div>
      </div>
    </motion.div>
  );
};

export const AIInsightSkeleton: React.FC = () => {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="relative overflow-hidden rounded-xl bg-gradient-to-br from-blue-50/50 to-indigo-50/30 backdrop-blur-lg border border-blue-200/20 shadow-lg"
    >
      <div className="absolute inset-0 bg-gradient-to-br from-blue-400/5 to-indigo-400/5" />
      <div className="relative p-6">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <div className="h-5 w-5 bg-gray-200/50 rounded-lg animate-pulse" />
            <div className="h-4 bg-gray-200/50 rounded-full w-32 animate-pulse" />
          </div>
          <div className="h-16 bg-gray-200/50 rounded-lg animate-pulse" />
          <div className="flex items-center gap-2">
            <div className="h-2 bg-gray-200/50 rounded-full w-24 animate-pulse" />
            <div className="h-2 bg-gray-200/50 rounded-full w-16 animate-pulse" />
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export const ActivityFeedSkeleton: React.FC = () => {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-4"
    >
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="flex items-start gap-3">
          <div className="h-10 w-10 bg-gray-200/50 rounded-full animate-pulse flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-gray-200/50 rounded-full w-40 animate-pulse" />
            <div className="h-3 bg-gray-200/50 rounded-full w-full animate-pulse" />
            <div className="h-3 bg-gray-200/50 rounded-full w-24 animate-pulse" />
          </div>
        </div>
      ))}
    </motion.div>
  );
};

export const ChartSkeleton: React.FC<{ height: string }> = ({ height }) => {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className={`${height} rounded-xl bg-gradient-to-br from-amber-50/30 to-orange-50/20 backdrop-blur-lg border border-amber-200/20 shadow-lg p-4`}
    >
      <div className="h-full bg-gray-200/30 rounded-lg animate-pulse" />
    </motion.div>
  );
};