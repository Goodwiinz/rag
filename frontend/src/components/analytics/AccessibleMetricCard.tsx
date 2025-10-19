import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useAnnouncements } from '@/components/common/AccessibilityProvider';
import { MetricCardProps } from '@/types/analytics';

export const AccessibleMetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  threshold,
  trend,
  unit = '%',
  description,
  onClick,
  loading = false,
  error = null,
}) => {
  const { announce } = useAnnouncements();

  // Determine status based on threshold
  const getStatus = () => {
    if (error) return 'error';
    if (loading) return 'loading';
    if (!threshold) return 'info';
    if (typeof value === 'number' && value >= threshold) return 'good';
    if (typeof value === 'number' && value >= threshold * 0.9) return 'warning';
    return 'critical';
  };

  const status = getStatus();
  const statusColor = {
    good: 'text-green-600',
    warning: 'text-yellow-600',
    critical: 'text-red-600',
    loading: 'text-gray-400',
    error: 'text-red-600',
    info: 'text-blue-600',
  }[status];

  const trendDirection = trend?.direction || 'stable';
  const trendIcon: Record<string, string> = {
    up: '↗',
    down: '↘',
    stable: '→',
  };

  const trendColor: Record<string, string> = {
    up: 'text-green-600',
    down: 'text-red-600',
    stable: 'text-gray-600',
  };

  // Announce changes when value updates
  React.useEffect(() => {
    if (value !== undefined) {
      announce(`${title}: ${value}${unit}, status: ${status}`);
    }
  }, [value, title, unit, status, announce]);

  const handleCardClick = () => {
    if (onClick) {
      onClick();
      announce(`Opened details for ${title}`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleCardClick();
    }
  };

  return (
    <Card
      className={`metric-card ${onClick ? 'cursor-pointer hover:shadow-lg transition-shadow' : ''} ${status}`}
      role="region"
      aria-label={`${title}: ${value}${unit}. Status: ${status}. ${description ? `Description: ${description}` : ''}`}
      tabIndex={onClick ? 0 : undefined}
      onClick={handleCardClick}
      onKeyDown={handleKeyDown}
      aria-busy={loading}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium text-gray-600">
            {title}
          </CardTitle>
          {trend && (
            <div
              className={`flex items-center text-sm ${trendColor[trendDirection]}`}
              aria-label={`Trend: ${trend.direction}, ${trend.percentage}% change`}
            >
              <span className="mr-1" aria-hidden="true">
                {trendIcon[trendDirection]}
              </span>
              <span>{trend.percentage}%</span>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center h-12" aria-label="Loading">
            <div
              className="animate-spin rounded-full h-6 w-6 border-b-2 border-gray-400"
              role="status"
              aria-label="Loading metric data"
            />
          </div>
        ) : error ? (
          <div className="text-center text-red-600" role="alert" aria-live="polite">
            <span className="text-sm">Error loading data</span>
          </div>
        ) : (
          <div className="space-y-2">
            <div className={`text-2xl font-bold ${statusColor}`} aria-label={`Current value: ${value}${unit}`}>
              {value}
              <span className="text-sm font-normal ml-1">{unit}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500">
                Threshold: {threshold}{unit}
              </span>
              <Badge
                variant={status === 'good' ? 'default' : status === 'warning' ? 'secondary' : 'destructive'}
                aria-label={`Status: ${status}`}
              >
                {status}
              </Badge>
            </div>
            {description && (
              <p className="text-xs text-gray-600 mt-2" id={`description-${title.replace(/\s+/g, '-')}`}>
                {description}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Accessible Chart Container
export const AccessibleChartContainer: React.FC<{
  title: string;
  description?: string;
  children: React.ReactNode;
  data?: any[];
  ariaLabel?: string;
}> = ({ title, description, children, data, ariaLabel }) => {
  const { announce } = useAnnouncements();

  const chartRef = React.useRef<HTMLDivElement>(null);

  // Announce chart availability
  React.useEffect(() => {
    if (data && data.length > 0) {
      announce(`${title} chart loaded with ${data.length} data points`);
    }
  }, [data, title, announce]);

  return (
    <div
      ref={chartRef}
      role="img"
      aria-label={ariaLabel || `${title} chart${description ? `. ${description}` : ''}`}
      tabIndex={0}
      className="chart-container"
    >
      <div className="chart-header">
        <h3 className="text-lg font-semibold">{title}</h3>
        {description && (
          <p className="text-sm text-gray-600">{description}</p>
        )}
      </div>

      <div className="chart-content">
        {children}
      </div>

      {/* Data table for screen readers */}
      {data && data.length > 0 && (
        <div className="sr-only" role="table" aria-label={`${title} data table`}>
          <div role="rowgroup">
            {data.map((item, index) => (
              <div key={index} role="row">
                {Object.entries(item).map(([key, value]) => (
                  <span key={key} role="cell" className="pr-4">
                    {key}: {String(value)}
                  </span>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// Accessible Filter Component
export const AccessibleFilterPanel: React.FC<{
  title: string;
  filters: Array<{
    id: string;
    label: string;
    type: 'select' | 'checkbox' | 'range';
    options?: Array<{ value: string; label: string }>;
    value?: any;
    onChange: (value: any) => void;
  }>;
}> = ({ title, filters }) => {
  const { announce } = useAnnouncements();

  const handleFilterChange = (filterId: string, value: any, filterLabel: string) => {
    announce(`Filter ${filterLabel} changed to ${value}`);
  };

  return (
    <section
      className="filter-panel"
      aria-labelledby="filter-panel-title"
    >
      <h2 id="filter-panel-title" className="text-lg font-semibold mb-4">
        {title}
      </h2>

      <div className="space-y-4" role="group" aria-label="Filters">
        {filters.map((filter) => (
          <div key={filter.id} className="filter-item">
            <label
              htmlFor={filter.id}
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              {filter.label}
            </label>

            {filter.type === 'select' && (
              <select
                id={filter.id}
                value={filter.value || ''}
                onChange={(e) => {
                  filter.onChange(e.target.value);
                  handleFilterChange(filter.id, e.target.value, filter.label);
                }}
                className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                aria-describedby={`${filter.id}-description`}
              >
                {filter.options?.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            )}

            {filter.type === 'checkbox' && (
              <div className="space-y-2">
                {filter.options?.map((option) => (
                  <label key={option.value} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={Array.isArray(filter.value) ? filter.value.includes(option.value) : false}
                      onChange={(e) => {
                        const currentValue = Array.isArray(filter.value) ? filter.value : [];
                        const newValue = e.target.checked
                          ? [...currentValue, option.value]
                          : currentValue.filter(v => v !== option.value);
                        filter.onChange(newValue);
                        handleFilterChange(filter.id, option.value, filter.label);
                      }}
                      className="mr-2"
                      aria-describedby={`${filter.id}-description`}
                    />
                    <span>{option.label}</span>
                  </label>
                ))}
              </div>
            )}

            {filter.type === 'range' && (
              <input
                type="range"
                id={filter.id}
                value={filter.value || 0}
                onChange={(e) => {
                  filter.onChange(e.target.value);
                  handleFilterChange(filter.id, e.target.value, filter.label);
                }}
                className="w-full"
                min={0}
                max={100}
                aria-describedby={`${filter.id}-description ${filter.id}-value`}
                aria-valuenow={filter.value}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            )}

            <div
              id={`${filter.id}-description`}
              className="text-xs text-gray-500"
              aria-live="polite"
            >
              {filter.type === 'range' && (
                <span id={`${filter.id}-value`}>Current value: {filter.value}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};