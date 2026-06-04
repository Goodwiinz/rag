/**
 * EntityFilters Component
 * Advanced filtering controls for the entity list.
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
    { value: '__null__', label: 'Unknown type', isSpecial: true },
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
          <Search
            aria-hidden="true"
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground group-focus-within:text-primary h-4 w-4 transition-colors"
          />
          <Input
            placeholder="Search entities by name..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            aria-label="Search entities by name"
            className="pl-10 bg-background border-border focus-visible:border-primary/40 text-sm h-10"
          />
          {searchQuery && (
            <IconButtonSm
              variant="ghost"
              icon={<X aria-hidden="true" className="h-3 w-3" />}
              label="Clear search"
              onClick={() => onSearchChange('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground hover:bg-transparent h-6 w-6"
            />
          )}
        </div>

        {/* Type Filter Dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              className={cn(
                'w-48 justify-between text-sm border-border bg-background h-10',
                selectedTypes.length > 0 && 'border-primary/40'
              )}
            >
              <div className="flex items-center gap-2">
                <Filter
                  aria-hidden="true"
                  className="h-3.5 w-3.5 text-muted-foreground"
                />
                <span>
                  {selectedTypes.length === 0
                    ? 'All types'
                    : `${selectedTypes.length} types`}
                </span>
              </div>
              <ChevronDown
                aria-hidden="true"
                className="h-3.5 w-3.5 text-muted-foreground"
              />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-64 bg-card border-border"
            align="start"
          >
            <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">
              Entity types
            </DropdownMenuLabel>
            <DropdownMenuSeparator className="bg-border" />

            {/* Search input for type filtering */}
            <div className="px-2 py-1.5">
              <Input
                placeholder="Search types..."
                value={typeSearchQuery}
                onChange={(e) => setTypeSearchQuery(e.target.value)}
                aria-label="Search entity types"
                className="h-8 text-sm bg-background border-border"
              />
            </div>

            <DropdownMenuSeparator className="bg-border" />
            <DropdownMenuCheckboxItem
              checked={selectedTypes.length === entityTypes.length}
              onCheckedChange={handleSelectAllTypes}
              className="text-sm focus:bg-muted focus:text-primary"
            >
              Select all
            </DropdownMenuCheckboxItem>
            <DropdownMenuSeparator className="bg-border" />

            {/* Scrollable type list */}
            <div className="max-h-64 overflow-y-auto">
              {filteredTypes.length === 0 ? (
                <div className="px-3 py-2 text-sm text-muted-foreground">
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
                        className="text-sm focus:bg-muted focus:text-primary"
                      >
                        <div className="flex items-center justify-between w-full">
                          <div className="flex items-center">
                            <span className="inline-block w-2 h-2 rounded-full mr-2 bg-muted-foreground/40" />
                            {item.label}
                          </div>
                          {nullTypeCount > 0 && (
                            <span className="text-xs text-muted-foreground ml-2 tabular-nums">
                              {nullTypeCount.toLocaleString()}
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
                      className="text-sm focus:bg-muted focus:text-primary"
                    >
                      <div className="flex items-center justify-between w-full">
                        <div className="flex items-center">
                          <span className="inline-block w-2 h-2 rounded-full mr-2 bg-muted-foreground/40" />
                          {type}
                        </div>
                        {typeCounts && typeCounts[type] !== undefined && (
                          <span className="text-xs text-muted-foreground ml-2 tabular-nums">
                            {typeCounts[type].toLocaleString()}
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
                'w-48 justify-between text-sm border-border bg-background h-10',
                (confidenceRange[0] > 0 || confidenceRange[1] < 100) &&
                  'border-primary/40'
              )}
            >
              <div className="flex items-center gap-2">
                <SlidersHorizontal
                  aria-hidden="true"
                  className="h-3.5 w-3.5 text-muted-foreground"
                />
                <span className="tabular-nums">
                  {confidenceRange[0]}% - {confidenceRange[1]}%
                </span>
              </div>
              <ChevronDown
                aria-hidden="true"
                className="h-3.5 w-3.5 text-muted-foreground"
              />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-64 p-4 bg-card border-border"
            align="start"
          >
            <div className="space-y-4">
              <div className="text-xs font-medium text-muted-foreground">
                Confidence range
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
              <div className="flex justify-between text-sm text-muted-foreground tabular-nums">
                <span>{confidenceRange[0]}%</span>
                <span>{confidenceRange[1]}%</span>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onConfidenceChange([80, 100])}
                  className="flex-1 h-7 text-xs"
                >
                  High (80%+)
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onConfidenceChange([0, 100])}
                  className="flex-1 h-7 text-xs"
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
          <SelectTrigger
            aria-label="Sort entities"
            className="w-48 bg-background border-border text-sm h-10"
          >
            <SelectValue placeholder="Sort by..." />
          </SelectTrigger>
          <SelectContent className="bg-card border-border">
            <SelectItem value="name-asc" className="text-sm focus:bg-muted">
              Name A-Z
            </SelectItem>
            <SelectItem value="name-desc" className="text-sm focus:bg-muted">
              Name Z-A
            </SelectItem>
            <SelectItem
              value="confidence-desc"
              className="text-sm focus:bg-muted"
            >
              Confidence high to low
            </SelectItem>
            <SelectItem
              value="confidence-asc"
              className="text-sm focus:bg-muted"
            >
              Confidence low to high
            </SelectItem>
            <SelectItem
              value="created_at-desc"
              className="text-sm focus:bg-muted"
            >
              Newest first
            </SelectItem>
            <SelectItem
              value="created_at-asc"
              className="text-sm focus:bg-muted"
            >
              Oldest first
            </SelectItem>
            <SelectItem value="type-asc" className="text-sm focus:bg-muted">
              Type A-Z
            </SelectItem>
          </SelectContent>
        </Select>

        {/* Results Count */}
        <div className="px-3 py-2 rounded-lg bg-background border border-border text-sm text-muted-foreground shrink-0 flex items-center h-10 tabular-nums">
          {filteredCount === totalCount
            ? `${totalCount.toLocaleString()} ${totalCount === 1 ? 'entity' : 'entities'}`
            : `${filteredCount.toLocaleString()} of ${totalCount.toLocaleString()}`}
        </div>
      </div>

      {/* Active Filters Row */}
      {hasActiveFilters && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-muted-foreground">Active filters</span>

          {searchQuery && (
            <Badge
              variant="outline"
              className="border-primary/30 text-primary bg-primary/5 gap-1 font-normal"
            >
              Search: &quot;{searchQuery}&quot;
              <button
                type="button"
                aria-label="Clear search filter"
                onClick={() => onSearchChange('')}
                className="rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <X aria-hidden="true" className="h-3 w-3" />
              </button>
            </Badge>
          )}

          {selectedTypes.map((type) => (
            <Badge
              key={type}
              variant="outline"
              className="border-border bg-muted text-muted-foreground gap-1 font-normal"
            >
              {type}
              <button
                type="button"
                aria-label={`Remove ${type} filter`}
                onClick={() => removeTypeFilter(type)}
                className="rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <X aria-hidden="true" className="h-3 w-3" />
              </button>
            </Badge>
          ))}

          {(confidenceRange[0] > 0 || confidenceRange[1] < 100) && (
            <Badge
              variant="outline"
              className="border-primary/30 text-primary bg-primary/5 gap-1 font-normal tabular-nums"
            >
              Confidence {confidenceRange[0]}%-{confidenceRange[1]}%
              <button
                type="button"
                aria-label="Clear confidence filter"
                onClick={() => onConfidenceChange([0, 100])}
                className="rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <X aria-hidden="true" className="h-3 w-3" />
              </button>
            </Badge>
          )}

          <Button
            variant="ghost"
            size="sm"
            onClick={onClearFilters}
            className="h-6 text-xs text-muted-foreground hover:text-foreground"
          >
            Clear all
          </Button>
        </div>
      )}
    </div>
  );
};
