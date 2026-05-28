/**
 * MetricCard - A reusable metric display component for monitoring dashboards
 * Supports trends, thresholds, icons, and various display formats
 */

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { TrendData } from '@/types/monitoring';
import {
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  MinusIcon,
  InformationCircleIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline';

export interface MetricCardProps {
  title: string;
  value: number | string;
  unit?: string;
  trend?: TrendData;
  status?: 'success' | 'warning' | 'error' | 'info' | 'default';
  description?: string;
  icon?: React.ReactNode;
  loading?: boolean;
  error?: string | null;
  threshold?: {
    value: number;
    type: 'gt' | 'gte' | 'lt' | 'lte';
    warning_color?: string;
    error_color?: string;
  };
  previousValue?: number | string;
  format?:
    | 'number'
    | 'percentage'
    | 'currency'
    | 'duration'
    | 'bytes'
    | 'custom';
  customFormat?: (value: number | string) => string;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'compact' | 'detailed';
  onClick?: () => void;
  className?: string;
  children?: React.ReactNode;
}

const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  unit,
  trend,
  status = 'default',
  description,
  icon,
  loading = false,
  error,
  threshold,
  previousValue,
  format = 'number',
  customFormat,
  size = 'md',
  variant = 'default',
  onClick,
  className,
  children,
}) => {
  // Format value based on type
  const formatValue = (val: number | string): string => {
    if (customFormat) {
      return customFormat(val);
    }

    if (typeof val === 'string') {
      return val;
    }

    switch (format) {
      case 'percentage':
        return `${val.toFixed(1)}%`;
      case 'currency':
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
        }).format(val);
      case 'duration':
        if (val < 1000) {
          return `${val}ms`;
        } else if (val < 60000) {
          return `${(val / 1000).toFixed(1)}s`;
        } else {
          return `${(val / 60000).toFixed(1)}m`;
        }
      case 'bytes':
        if (val < 1024) {
          return `${val}B`;
        } else if (val < 1024 * 1024) {
          return `${(val / 1024).toFixed(1)}KB`;
        } else if (val < 1024 * 1024 * 1024) {
          return `${(val / (1024 * 1024)).toFixed(1)}MB`;
        } else {
          return `${(val / (1024 * 1024 * 1024)).toFixed(1)}GB`;
        }
      case 'number':
      default:
        return new Intl.NumberFormat('en-US').format(val);
    }
  };

  // Determine status based on threshold and value
  const getComputedStatus = (): MetricCardProps['status'] => {
    if (error) return 'error';
    if (status !== 'default') return status;
    if (!threshold || typeof value !== 'number') return 'default';

    const {
      value: thresholdValue,
      type,
      error_color,
      warning_color,
    } = threshold;
    const isWarning = false;
    let isError = false;

    switch (type) {
      case 'gt':
        isError = value > thresholdValue;
        break;
      case 'gte':
        isError = value >= thresholdValue;
        break;
      case 'lt':
        isError = value < thresholdValue;
        break;
      case 'lte':
        isError = value <= thresholdValue;
        break;
    }

    if (isError && error_color) return 'error';
    if (isWarning && warning_color) return 'warning';
    if (isError) return 'error';
    if (isWarning) return 'warning';
    return 'default';
  };

  const computedStatus = getComputedStatus();

  // Get status colors
  const getStatusColors = () => {
    switch (computedStatus) {
      case 'success':
        return {
          bg: 'bg-green-50',
          border: 'border-green-200',
          text: 'text-green-900',
          value: 'text-green-600',
          badge: 'bg-green-100 text-green-800',
        };
      case 'warning':
        return {
          bg: 'bg-yellow-50',
          border: 'border-yellow-200',
          text: 'text-yellow-900',
          value: 'text-yellow-600',
          badge: 'bg-yellow-100 text-yellow-800',
        };
      case 'error':
        return {
          bg: 'bg-red-50',
          border: 'border-red-200',
          text: 'text-red-900',
          value: 'text-red-600',
          badge: 'bg-red-100 text-red-800',
        };
      case 'info':
        return {
          bg: 'bg-blue-50',
          border: 'border-blue-200',
          text: 'text-blue-900',
          value: 'text-blue-600',
          badge: 'bg-blue-100 text-blue-800',
        };
      default:
        return {
          bg: 'bg-white',
          border: 'border-border',
          text: 'text-foreground',
          value: 'text-foreground',
          badge: 'bg-gray-100 text-foreground',
        };
    }
  };

  const colors = getStatusColors();

  // Get size classes
  const getSizeClasses = () => {
    switch (size) {
      case 'sm':
        return {
          card: 'p-4',
          title: 'text-sm font-medium',
          value: 'text-lg font-semibold',
          description: 'text-xs',
        };
      case 'lg':
        return {
          card: 'p-8',
          title: 'text-xl font-semibold',
          value: 'text-4xl font-bold',
          description: 'text-base',
        };
      case 'md':
      default:
        return {
          card: 'p-6',
          title: 'text-lg font-semibold',
          value: 'text-2xl font-bold',
          description: 'text-sm',
        };
    }
  };

  const sizeClasses = getSizeClasses();

  // Render trend indicator
  const renderTrend = () => {
    if (!trend) return null;

    const TrendIcon =
      trend.direction === 'up'
        ? ArrowTrendingUpIcon
        : trend.direction === 'down'
          ? ArrowTrendingDownIcon
          : MinusIcon;
    const trendColor =
      trend.direction === 'up'
        ? 'text-green-600'
        : trend.direction === 'down'
          ? 'text-red-600'
          : 'text-muted-foreground';

    return (
      <div className={cn('flex items-center space-x-1', trendColor)}>
        <TrendIcon className="h-4 w-4" />
        <span className="text-sm font-medium">
          {Math.abs(trend.percentage).toFixed(1)}%
        </span>
      </div>
    );
  };

  // Render loading state
  if (loading) {
    return (
      <Card className={cn('animate-pulse', className)}>
        <CardContent className={cn(sizeClasses.card)}>
          <div className="space-y-3">
            <div className="h-4 bg-gray-200 rounded w-3/4"></div>
            <div className="h-8 bg-gray-200 rounded w-1/2"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Render error state
  if (error) {
    return (
      <Card className={cn('border-red-200 bg-red-50', className)}>
        <CardContent className={cn(sizeClasses.card)}>
          <div className="flex items-center space-x-2">
            <XCircleIcon className="h-5 w-5 text-red-500" />
            <div>
              <div className={cn('font-medium', colors.text)}>Error</div>
              <div className="text-sm text-red-600">{error}</div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const formattedValue = formatValue(value);
  const formattedPreviousValue =
    previousValue !== undefined ? formatValue(previousValue) : null;

  return (
    <Card
      className={cn(
        'transition-all duration-200 hover:shadow-md cursor-pointer',
        colors.bg,
        colors.border,
        onClick && 'hover:scale-[1.02]',
        className
      )}
      onClick={onClick}
    >
      {variant === 'detailed' && (
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              {icon && <div className={colors.value}>{icon}</div>}
              <CardTitle className={cn(sizeClasses.title, colors.text)}>
                {title}
              </CardTitle>
            </div>
            {trend && renderTrend()}
          </div>
          {description && (
            <p className={cn('text-muted-foreground', sizeClasses.description)}>
              {description}
            </p>
          )}
        </CardHeader>
      )}

      <CardContent
        className={cn(variant === 'default' ? sizeClasses.card : 'px-6 pb-6')}
      >
        {variant === 'default' && (
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              {icon && <div className={colors.value}>{icon}</div>}
              <div>
                <h3 className={cn(sizeClasses.title, colors.text)}>{title}</h3>
                {description && (
                  <p
                    className={cn(
                      'text-muted-foreground',
                      sizeClasses.description
                    )}
                  >
                    {description}
                  </p>
                )}
              </div>
            </div>
            {trend && renderTrend()}
          </div>
        )}

        <div className="flex items-baseline space-x-2">
          <div className={cn(sizeClasses.value, colors.value)}>
            {formattedValue}
          </div>
          {unit && (
            <span
              className={cn('text-muted-foreground', sizeClasses.description)}
            >
              {unit}
            </span>
          )}
          {status !== 'default' && (
            <Badge variant="outline" className={cn('ml-auto', colors.badge)}>
              {status}
            </Badge>
          )}
        </div>

        {formattedPreviousValue && (
          <div className="mt-2 flex items-center space-x-2">
            <span
              className={cn('text-muted-foreground', sizeClasses.description)}
            >
              Previous: {formattedPreviousValue}
            </span>
            {typeof value === 'number' && typeof previousValue === 'number' && (
              <span
                className={cn(
                  'text-sm font-medium',
                  value > previousValue
                    ? 'text-green-600'
                    : value < previousValue
                      ? 'text-red-600'
                      : 'text-muted-foreground'
                )}
              >
                {value > previousValue ? '+' : ''}
                {(((value - previousValue) / previousValue) * 100).toFixed(1)}%
              </span>
            )}
          </div>
        )}

        {threshold && typeof value === 'number' && (
          <div className="mt-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
              <span>Threshold</span>
              <span>{threshold.value}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className={cn(
                  'h-2 rounded-full transition-all duration-300',
                  computedStatus === 'error'
                    ? 'bg-red-500'
                    : computedStatus === 'warning'
                      ? 'bg-yellow-500'
                      : 'bg-green-500'
                )}
                style={{
                  width: `${Math.min((value / threshold.value) * 100, 100)}%`,
                }}
              />
            </div>
          </div>
        )}

        {children && <div className="mt-4">{children}</div>}
      </CardContent>
    </Card>
  );
};

export default MetricCard;
