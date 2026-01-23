'use client';

/**
 * Citation Graph Controls Component
 *
 * Provides filtering and configuration options for the citation graph.
 * Includes year range, depth, and external papers toggle.
 */

import React from 'react';
import { Filter, RefreshCw } from 'lucide-react';

export interface GraphFilters {
  yearRange: [number, number];
  depth: number;
  includeExternal: boolean;
}

export interface CitationGraphControlsProps {
  filters: GraphFilters;
  onFiltersChange: (filters: GraphFilters) => void;
  onRefresh?: () => void;
  loading?: boolean;
  minYear?: number;
  maxYear?: number;
}

export const CitationGraphControls: React.FC<CitationGraphControlsProps> = ({
  filters,
  onFiltersChange,
  onRefresh,
  loading = false,
  minYear = 1990,
  maxYear = new Date().getFullYear(),
}) => {
  const handleYearMinChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value, 10);
    onFiltersChange({
      ...filters,
      yearRange: [value, filters.yearRange[1]],
    });
  };

  const handleYearMaxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value, 10);
    onFiltersChange({
      ...filters,
      yearRange: [filters.yearRange[0], value],
    });
  };

  const handleDepthChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value, 10);
    onFiltersChange({
      ...filters,
      depth: value,
    });
  };

  const handleExternalToggle = () => {
    onFiltersChange({
      ...filters,
      includeExternal: !filters.includeExternal,
    });
  };

  return (
    <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 text-[#00ff9f]">
          <Filter className="h-4 w-4" />
          <span className="font-mono text-sm font-medium">Graph Filters</span>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={loading}
            className="p-2 text-gray-500 hover:text-[#00ff9f] transition-colors disabled:opacity-50"
            title="Refresh Graph"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        )}
      </div>

      <div className="space-y-4">
        {/* Year Range */}
        <div>
          <label className="text-xs text-gray-500 font-mono uppercase tracking-wide block mb-2">
            Year Range
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={filters.yearRange[0]}
              onChange={handleYearMinChange}
              min={minYear}
              max={filters.yearRange[1]}
              className="w-20 px-2 py-1.5 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 focus:outline-none focus:border-[#00ff9f]"
            />
            <span className="text-gray-500">—</span>
            <input
              type="number"
              value={filters.yearRange[1]}
              onChange={handleYearMaxChange}
              min={filters.yearRange[0]}
              max={maxYear}
              className="w-20 px-2 py-1.5 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 focus:outline-none focus:border-[#00ff9f]"
            />
          </div>
          <div className="mt-2">
            <input
              type="range"
              min={minYear}
              max={maxYear}
              value={filters.yearRange[0]}
              onChange={handleYearMinChange}
              className="w-full h-1 bg-[#333] rounded-lg appearance-none cursor-pointer accent-[#00ff9f]"
            />
          </div>
        </div>

        {/* Depth Selector */}
        <div>
          <label className="text-xs text-gray-500 font-mono uppercase tracking-wide block mb-2">
            Traversal Depth: <span className="text-[#00ff9f]">{filters.depth}</span>
          </label>
          <input
            type="range"
            min={1}
            max={5}
            value={filters.depth}
            onChange={handleDepthChange}
            className="w-full h-1 bg-[#333] rounded-lg appearance-none cursor-pointer accent-[#00ff9f]"
          />
          <div className="flex justify-between text-xs text-gray-500 font-mono mt-1">
            <span>1</span>
            <span>2</span>
            <span>3</span>
            <span>4</span>
            <span>5</span>
          </div>
        </div>

        {/* Include External Toggle */}
        <div className="flex items-center justify-between">
          <label className="text-xs text-gray-500 font-mono uppercase tracking-wide">
            Include External Papers
          </label>
          <button
            onClick={handleExternalToggle}
            className={`relative w-12 h-6 rounded-full transition-colors ${
              filters.includeExternal
                ? 'bg-[#00ff9f]/30 border-[#00ff9f]'
                : 'bg-[#333] border-[#555]'
            } border`}
          >
            <span
              className={`absolute top-0.5 w-5 h-5 rounded-full transition-transform ${
                filters.includeExternal
                  ? 'translate-x-6 bg-[#00ff9f]'
                  : 'translate-x-0.5 bg-gray-500'
              }`}
            />
          </button>
        </div>

        {/* Quick Filters */}
        <div>
          <label className="text-xs text-gray-500 font-mono uppercase tracking-wide block mb-2">
            Quick Filters
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() =>
                onFiltersChange({
                  ...filters,
                  yearRange: [maxYear - 5, maxYear],
                })
              }
              className="px-2 py-1 text-xs font-mono bg-[#1a1a1a] border border-[#333] rounded hover:border-[#00ff9f] hover:text-[#00ff9f] transition-colors"
            >
              Last 5 years
            </button>
            <button
              onClick={() =>
                onFiltersChange({
                  ...filters,
                  yearRange: [maxYear - 10, maxYear],
                })
              }
              className="px-2 py-1 text-xs font-mono bg-[#1a1a1a] border border-[#333] rounded hover:border-[#00ff9f] hover:text-[#00ff9f] transition-colors"
            >
              Last 10 years
            </button>
            <button
              onClick={() =>
                onFiltersChange({
                  ...filters,
                  yearRange: [minYear, maxYear],
                  depth: 2,
                  includeExternal: true,
                })
              }
              className="px-2 py-1 text-xs font-mono bg-[#1a1a1a] border border-[#333] rounded hover:border-[#00ff9f] hover:text-[#00ff9f] transition-colors"
            >
              Reset All
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CitationGraphControls;
