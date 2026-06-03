/**
 * EntityFilters Component
 * Advanced filtering controls for entity list
 */

import React, { useState } from 'react';
import {
  Search,
  Filter,
  X,
  ChevronDown,
  SlidersHorizontal,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { IconButtonSm } from '@/components/ui/icon-button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { EntityType } from '@/types/entity';
import { cn } from '@/lib/utils';

export type SortField = 'name' | 'confidence' | 'created_at' | 'type';
export type SortOrder = 'asc' | 'desc';

interface EntityFiltersProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  selectedTypes: EntityType[];
  onTypesChange: (types: EntityType[]) => void;
  confidenceRange: [number, number];
  onConfidenceChange: (range: [number, number]) => void;
  sortField: SortField;
  sortOrder: SortOrder;
  onSortChange: (field: SortField, order: SortOrder) => void;
  onClearFilters: () => void;
  totalCount: number;
  filteredCount: number;
  availableTypes?: string[];
  typeCounts?: Record<string, number>; // Type counts from analytics
}

const DEFAULT_ENTITY_TYPES: EntityType[] = [
  'PERSON',
  'ORGANIZATION',
  'LOCATION',
  'CONCEPT',
  'EVENT',
  'PRODUCT',
  'DATE',
  'TECHNOLOGY',
  'DOCUMENT',
  'TOPIC',
  'OTHER',
];

const typeColors: Record<string, string> = {
  PERSON: 'bg-blue-400/20 text-blue-400 border-blue-400/30',
  ORGANIZATION: 'bg-emerald-400/20 text-emerald-400 border-emerald-400/30',
  LOCATION: 'bg-amber-400/20 text-amber-400 border-amber-400/30',
  CONCEPT: 'bg-purple-400/20 text-purple-400 border-purple-400/30',
  EVENT: 'bg-rose-400/20 text-rose-400 border-rose-400/30',
  PRODUCT: 'bg-indigo-400/20 text-indigo-400 border-indigo-400/30',
  DATE: 'bg-slate-400/20 text-slate-400 border-slate-400/30',
  TECHNOLOGY: 'bg-cyan-400/20 text-cyan-400 border-cyan-400/30',
  DOCUMENT: 'bg-orange-400/20 text-orange-400 border-orange-400/30',
  TOPIC: 'bg-pink-400/20 text-pink-400 border-pink-400/30',
  OTHER: 'bg-gray-400/20 text-muted-foreground border-border/30',
};

export const EntityFilters: React.FC<EntityFiltersProps> = ({
  searchQuery,
  onSearchChange,
  selectedTypes,
  onTypesChange,
  confidenceRange,
  onConfidenceChange,
  sortField,
  sortOrder,
  onSortChange,
  onClearFilters,
  totalCount,
  filteredCount,
  availableTypes,
  typeCounts,
}) => {
  const [confidenceOpen, setConfidenceOpen] = useState(false);
  const [typeSearchQuery, setTypeSearchQuery] = useState('');

  // Special filter for null/unknown types
  const SPECIAL_FILTERS = [
    { value: '__null__', label: 'Unknown Type', isSpecial: true },
  ];

  // Use available types from props or fall back to defaults
  const entityTypes = (availableTypes || DEFAULT_ENTITY_TYPES) as EntityType[];

  // Combine special filters with regular types
  const allFilterOptions = [...SPECIAL_FILTERS, ...entityTypes];

  // Filter types based on search query
  const filteredTypes = allFilterOptions.filter((item) => {
    const label = typeof item === 'string' ? item : item.label;
    return label.toLowerCase().includes(typeSearchQuery.toLowerCase());
  });

  // Calculate null type count (total entities - sum of known type counts)
  const nullTypeCount = typeCounts
    ? Object.keys(typeCounts).length > 0
      ? Math.max(
          0,
          totalCount -
            Object.values(typeCounts).reduce((sum, count) => sum + count, 0)
        )
      : 0
    : 0;

  const hasActiveFilters =
    searchQuery ||
    selectedTypes.length > 0 ||
    confidenceRange[0] > 0 ||
    confidenceRange[1] < 100;

  const handleTypeToggle = (type: EntityType) => {
    if (selectedTypes.includes(type)) {
      onTypesChange(selectedTypes.filter((t) => t !== type));
    } else {
      onTypesChange([...selectedTypes, type]);
    }
  };

  const handleSelectAllTypes = () => {
    if (selectedTypes.length === entityTypes.length) {
      onTypesChange([]);
    } else {
      onTypesChange([...entityTypes]);
    }
  };

  const removeTypeFilter = (type: EntityType) => {
    onTypesChange(selectedTypes.filter((t) => t !== type));
  };

  return (
    <div className="space-y-3">
      {/* Main Filter Bar */}
      <div className="flex flex-col md:flex-row gap-3">
        {/* Search Input */}
        <div className="flex-1 relative group">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--nous-fg-3)] group-focus-within:text-[var(--nous-sol)] h-4 w-4 transition-colors" />
          <Input
            placeholder="Search entities by name..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-10 bg-[var(--nous-bg-1)] border-[var(--nous-border-1)] focus:border-[var(--nous-sol)]/30 font-mono text-sm h-10"
          />
          {searchQuery && (
            <IconButtonSm
              variant="ghost"
              icon={<X className="h-3 w-3" />}
              label="Clear search"
              onClick={() => onSearchChange('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--nous-fg-3)] hover:text-white hover:bg-transparent h-6 w-6"
            />
          )}
        </div>

        {/* Type Filter Dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              className={cn(
                'w-48 justify-between font-mono text-xs border-[var(--nous-border-1)] bg-[var(--nous-bg-1)] h-10',
                selectedTypes.length > 0 && 'border-[var(--nous-sol)]/30'
              )}
            >
              <div className="flex items-center gap-2">
                <Filter className="h-3.5 w-3.5 text-[var(--nous-fg-3)]" />
                <span>
                  {selectedTypes.length === 0
                    ? 'All Types'
                    : `${selectedTypes.length} Types`}
                </span>
              </div>
              <ChevronDown className="h-3.5 w-3.5 text-[var(--nous-fg-3)]" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-64 bg-[var(--nous-bg-2)] border-[var(--nous-border-1)]"
            align="start"
          >
            <DropdownMenuLabel className="font-mono text-[10px] uppercase tracking-widest text-[var(--nous-fg-3)]">
              Entity Types
            </DropdownMenuLabel>
            <DropdownMenuSeparator className="bg-[var(--nous-border-1)]" />

            {/* Search input for type filtering */}
            <div className="px-2 py-1.5">
              <Input
                placeholder="Search types..."
                value={typeSearchQuery}
                onChange={(e) => setTypeSearchQuery(e.target.value)}
                className="h-8 font-mono text-xs bg-[var(--nous-bg-1)] border-[var(--nous-border-1)]"
              />
            </div>

            <DropdownMenuSeparator className="bg-[var(--nous-border-1)]" />
            <DropdownMenuCheckboxItem
              checked={selectedTypes.length === entityTypes.length}
              onCheckedChange={handleSelectAllTypes}
              className="font-mono text-xs focus:bg-[var(--nous-bg-3)] focus:text-[var(--nous-sol)]"
            >
              Select All
            </DropdownMenuCheckboxItem>
            <DropdownMenuSeparator className="bg-[var(--nous-border-1)]" />

            {/* Scrollable type list */}
            <div className="max-h-64 overflow-y-auto">
              {filteredTypes.length === 0 ? (
                <div className="px-3 py-2 text-xs text-[var(--nous-fg-3)] font-mono">
                  No types found
                </div>
              ) : (
                filteredTypes.map((item) => {
                  // Handle special filters (like null type)
                  if (
                    typeof item === 'object' &&
                    'isSpecial' in item &&
                    item.isSpecial
                  ) {
                    return (
                      <DropdownMenuCheckboxItem
                        key={item.value}
                        checked={selectedTypes.includes(item.value as any)}
                        onCheckedChange={() =>
                          handleTypeToggle(item.value as any)
                        }
                        className="font-mono text-xs focus:bg-[var(--nous-bg-3)] focus:text-[var(--amber)] bg-amber-400/10"
                      >
                        <div className="flex items-center justify-between w-full">
                          <div className="flex items-center">
                            <span className="inline-block w-2 h-2 rounded-full mr-2 bg-amber-400/40" />
                            {item.label}
                          </div>
                          {nullTypeCount > 0 && (
                            <span className="text-[10px] text-amber-400 ml-2">
                              ({nullTypeCount.toLocaleString()})
                            </span>
                          )}
                        </div>
                      </DropdownMenuCheckboxItem>
                    );
                  }

                  // Handle regular entity types
                  const type = item as EntityType;
                  return (
                    <DropdownMenuCheckboxItem
                      key={type}
                      checked={selectedTypes.includes(type)}
                      onCheckedChange={() => handleTypeToggle(type)}
                      className="font-mono text-xs focus:bg-[var(--nous-bg-3)] focus:text-[var(--nous-sol)]"
                    >
                      <div className="flex items-center justify-between w-full">
                        <div className="flex items-center">
                          <span
                            className={cn(
                              'inline-block w-2 h-2 rounded-full mr-2',
                              typeColors[type]?.split(' ')[0] ||
                                'bg-gray-400/20'
                            )}
                          />
                          {type}
                        </div>
                        {typeCounts && typeCounts[type] !== undefined && (
                          <span className="text-[10px] text-[var(--nous-fg-3)] ml-2">
                            ({typeCounts[type].toLocaleString()})
                          </span>
                        )}
                      </div>
                    </DropdownMenuCheckboxItem>
                  );
                })
              )}
            </div>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Confidence Filter */}
        <DropdownMenu open={confidenceOpen} onOpenChange={setConfidenceOpen}>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              className={cn(
                'w-48 justify-between font-mono text-xs border-[var(--nous-border-1)] bg-[var(--nous-bg-1)] h-10',
                (confidenceRange[0] > 0 || confidenceRange[1] < 100) &&
                  'border-[var(--nous-sol)]/30'
              )}
            >
              <div className="flex items-center gap-2">
                <SlidersHorizontal className="h-3.5 w-3.5 text-[var(--nous-fg-3)]" />
                <span>
                  {confidenceRange[0]}% - {confidenceRange[1]}%
                </span>
              </div>
              <ChevronDown className="h-3.5 w-3.5 text-[var(--nous-fg-3)]" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-64 p-4 bg-[var(--nous-bg-2)] border-[var(--nous-border-1)]"
            align="start"
          >
            <div className="space-y-4">
              <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--nous-fg-3)]">
                Confidence Range
              </div>
              <Slider
                value={confidenceRange}
                onValueChange={(value) =>
                  onConfidenceChange(value as [number, number])
                }
                min={0}
                max={100}
                step={5}
                className="w-full"
              />
              <div className="flex justify-between text-xs font-mono text-[var(--nous-fg-3)]">
                <span>{confidenceRange[0]}%</span>
                <span>{confidenceRange[1]}%</span>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onConfidenceChange([80, 100])}
                  className="flex-1 h-7 text-[10px] font-mono"
                >
                  High (80%+)
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onConfidenceChange([0, 100])}
                  className="flex-1 h-7 text-[10px] font-mono"
                >
                  Reset
                </Button>
              </div>
            </div>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Sort Dropdown */}
        <Select
          value={`${sortField}-${sortOrder}`}
          onValueChange={(value) => {
            const [field, order] = value.split('-') as [SortField, SortOrder];
            onSortChange(field, order);
          }}
        >
          <SelectTrigger className="w-48 bg-[var(--nous-bg-1)] border-[var(--nous-border-1)] font-mono text-xs h-10">
            <SelectValue placeholder="Sort by..." />
          </SelectTrigger>
          <SelectContent className="bg-[var(--nous-bg-2)] border-[var(--nous-border-1)]">
            <SelectItem
              value="name-asc"
              className="font-mono text-xs focus:bg-[var(--nous-bg-3)]"
            >
              Name A-Z
            </SelectItem>
            <SelectItem
              value="name-desc"
              className="font-mono text-xs focus:bg-[var(--nous-bg-3)]"
            >
              Name Z-A
            </SelectItem>
            <SelectItem
              value="confidence-desc"
              className="font-mono text-xs focus:bg-[var(--nous-bg-3)]"
            >
              Confidence High-Low
            </SelectItem>
            <SelectItem
              value="confidence-asc"
              className="font-mono text-xs focus:bg-[var(--nous-bg-3)]"
            >
              Confidence Low-High
            </SelectItem>
            <SelectItem
              value="created_at-desc"
              className="font-mono text-xs focus:bg-[var(--nous-bg-3)]"
            >
              Newest First
            </SelectItem>
            <SelectItem
              value="created_at-asc"
              className="font-mono text-xs focus:bg-[var(--nous-bg-3)]"
            >
              Oldest First
            </SelectItem>
            <SelectItem
              value="type-asc"
              className="font-mono text-xs focus:bg-[var(--nous-bg-3)]"
            >
              Type A-Z
            </SelectItem>
          </SelectContent>
        </Select>

        {/* Results Count */}
        <div className="px-3 py-2 rounded-lg bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)] text-[10px] font-mono text-[var(--nous-fg-3)] uppercase font-bold shrink-0 flex items-center h-10">
          {filteredCount === totalCount
            ? `${totalCount} NODES`
            : `${filteredCount} / ${totalCount}`}
        </div>
      </div>

      {/* Active Filters Row */}
      {hasActiveFilters && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-mono text-[var(--nous-fg-3)] uppercase">
            Active:
          </span>

          {searchQuery && (
            <Badge
              variant="outline"
              className="font-mono text-[10px] border-[var(--nous-sol)]/30 text-[var(--nous-sol)] bg-[var(--nous-sol)]/5 gap-1"
            >
              Search: "{searchQuery}"
              <X
                className="h-3 w-3 cursor-pointer hover:text-white"
                onClick={() => onSearchChange('')}
              />
            </Badge>
          )}

          {selectedTypes.map((type) => (
            <Badge
              key={type}
              variant="outline"
              className={cn(
                'font-mono text-[10px] gap-1 border',
                typeColors[type]
              )}
            >
              {type}
              <X
                className="h-3 w-3 cursor-pointer hover:text-white"
                onClick={() => removeTypeFilter(type)}
              />
            </Badge>
          ))}

          {(confidenceRange[0] > 0 || confidenceRange[1] < 100) && (
            <Badge
              variant="outline"
              className="font-mono text-[10px] border-[var(--nous-helios)]/30 text-[var(--nous-helios)] bg-[var(--nous-helios)]/5 gap-1"
            >
              Conf: {confidenceRange[0]}%-{confidenceRange[1]}%
              <X
                className="h-3 w-3 cursor-pointer hover:text-white"
                onClick={() => onConfidenceChange([0, 100])}
              />
            </Badge>
          )}

          <Button
            variant="ghost"
            size="sm"
            onClick={onClearFilters}
            className="h-6 text-[10px] font-mono text-[var(--nous-fg-3)] hover:text-red-400"
          >
            Clear All
          </Button>
        </div>
      )}
    </div>
  );
};
