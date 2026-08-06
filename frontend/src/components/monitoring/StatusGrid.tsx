/**
 * StatusGrid - A grid component for displaying system status and health indicators
 * Supports various status types, descriptions, and interactive actions
 */

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ComponentHealth } from '@/types/monitoring';
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
  QuestionMarkCircleIcon,
  ArrowPathIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';

export interface StatusGridProps {
  components: ComponentHealth[];
  title?: string;
  description?: string;
  showDetails?: boolean;
  showActions?: boolean;
  compact?: boolean;
  columns?: number;
  onComponentClick?: (component: ComponentHealth) => void;
  onRefresh?: (componentName: string) => void;
  className?: string;
}

type StatusType = 'healthy' | 'degraded' | 'unhealthy' | 'unknown';

const StatusGrid: React.FC<StatusGridProps> = ({
  components,
  title = 'System Status',
  description,
  showDetails = true,
  showActions = true,
  compact = false,
  columns = 3,
  onComponentClick,
  onRefresh,
  className,
}) => {
  // Get status configuration
  const getStatusConfig = (status: StatusType) => {
    switch (status) {
      case 'healthy':
        return {
          icon: CheckCircleIcon,
          color: 'text-green-500',
          bgColor: 'bg-green-50',
          borderColor: 'border-green-200',
          badgeColor: 'bg-green-100 text-green-800',
          label: 'Healthy',
        };
      case 'degraded':
        return {
          icon: ExclamationTriangleIcon,
          color: 'text-yellow-500',
          bgColor: 'bg-yellow-50',
          borderColor: 'border-yellow-200',
          badgeColor: 'bg-yellow-100 text-yellow-800',
          label: 'Degraded',
        };
      case 'unhealthy':
        return {
          icon: XCircleIcon,
          color: 'text-red-500',
          bgColor: 'bg-red-50',
          borderColor: 'border-red-200',
          badgeColor: 'bg-red-100 text-red-800',
          label: 'Unhealthy',
        };
      case 'unknown':
      default:
        return {
          icon: QuestionMarkCircleIcon,
          color: 'text-muted-foreground',
          bgColor: 'bg-gray-50',
          borderColor: 'border-border',
          badgeColor: 'bg-gray-100 text-foreground',
          label: 'Unknown',
        };
    }
  };

  // Get score color based on value
  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-600';
    if (score >= 70) return 'text-yellow-600';
    if (score >= 50) return 'text-orange-600';
    return 'text-red-600';
  };

  // Get grid columns class
  const getGridClass = () => {
    const gridMap: Record<number, string> = {
      1: 'grid-cols-1',
      2: 'grid-cols-1 md:grid-cols-2',
      3: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3',
      4: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4',
      5: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5',
      6: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6',
    };
    return gridMap[columns] || gridMap[3];
  };

  // Calculate overall health
  const overallHealth = React.useMemo(() => {
    if (components.length === 0)
      return { status: 'unknown' as StatusType, score: 0 };

    const healthyCount = components.filter(
      (c) => c.status === 'healthy'
    ).length;
    const unhealthyCount = components.filter(
      (c) => c.status === 'unhealthy'
    ).length;
    const totalScore = components.reduce((sum, c) => sum + c.score, 0);
    const avgScore = totalScore / components.length;

    let status: StatusType;
    if (unhealthyCount > 0) {
      status = 'unhealthy';
    } else if (healthyCount === components.length) {
      status = 'healthy';
    } else {
      status = 'degraded';
    }

    return { status, score: Math.round(avgScore) };
  }, [components]);

  const overallConfig = getStatusConfig(overallHealth.status);

  const formatLastCheck = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / (1000 * 60));

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
      return `${Math.floor(diffMins / 1440)}d ago`;
    } catch {
      return 'Unknown';
    }
  };

  if (compact) {
    return (
      <Card className={cn('border-0 shadow-sm', className)}>
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold text-foreground">{title}</h3>
              {description && (
                <p className="text-sm text-foreground">{description}</p>
              )}
            </div>
            <div className="flex items-center space-x-2">
              <overallConfig.icon
                className={cn('h-5 w-5', overallConfig.color)}
              />
              <span className="text-lg font-bold">{overallHealth.score}%</span>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {components.slice(0, 8).map((component) => {
              const config = getStatusConfig(component.status);
              return (
                <div
                  key={component.name}
                  className={cn(
                    'flex items-center space-x-2 p-2 rounded-lg border cursor-pointer hover:bg-gray-50',
                    config.bgColor,
                    config.borderColor
                  )}
                  onClick={() => onComponentClick?.(component)}
                >
                  <config.icon
                    className={cn('h-4 w-4 flex-shrink-0', config.color)}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-foreground truncate">
                      {component.name}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {formatLastCheck(component.last_check)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn('shadow-sm', className)}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center space-x-2">
              <overallConfig.icon
                className={cn('h-6 w-6', overallConfig.color)}
              />
              <span>{title}</span>
              <Badge className={overallConfig.badgeColor}>
                {overallConfig.label} ({overallHealth.score}%)
              </Badge>
            </CardTitle>
            {description && (
              <p className="text-sm text-foreground mt-1">{description}</p>
            )}
          </div>
          {showActions && (
            <div className="flex items-center space-x-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onRefresh?.('all')}
                className="text-muted-foreground hover:text-foreground"
              >
                <ArrowPathIcon className="h-4 w-4 mr-1" />
                Refresh
              </Button>
              <Button variant="ghost" size="sm">
                <InformationCircleIcon className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        <div className={cn('grid gap-4', getGridClass())}>
          {components.map((component) => {
            const config = getStatusConfig(component.status);

            return (
              <div
                key={component.name}
                className={cn(
                  'relative rounded-lg border p-4 transition-all duration-200',
                  'hover:shadow-md hover:scale-[1.02] cursor-pointer',
                  config.bgColor,
                  config.borderColor,
                  onComponentClick && 'cursor-pointer'
                )}
                onClick={() => onComponentClick?.(component)}
              >
                {/* Status Header */}
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center space-x-2">
                    <config.icon
                      className={cn('h-5 w-5 flex-shrink-0', config.color)}
                    />
                    <h3 className="font-semibold text-foreground">
                      {component.name}
                    </h3>
                  </div>
                  <Badge variant="outline" className={config.badgeColor}>
                    {config.label}
                  </Badge>
                </div>

                {/* Score Display */}
                <div className="mb-3">
                  <div className="flex items-baseline justify-between">
                    <span
                      className={cn(
                        'text-2xl font-bold',
                        getScoreColor(component.score)
                      )}
                    >
                      {component.score}%
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {formatLastCheck(component.last_check)}
                    </span>
                  </div>
                  <div className="mt-2 w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={cn(
                        'h-2 rounded-full transition-all duration-300',
                        component.score >= 90
                          ? 'bg-green-500'
                          : component.score >= 70
                            ? 'bg-yellow-500'
                            : component.score >= 50
                              ? 'bg-orange-500'
                              : 'bg-red-500'
                      )}
                      style={{ width: `${component.score}%` }}
                    />
                  </div>
                </div>

                {/* Additional Details */}
                {showDetails && (
                  <div className="space-y-2">
                    {component.metrics &&
                      Object.keys(component.metrics).length > 0 && (
                        <div className="space-y-1">
                          {Object.entries(component.metrics)
                            .slice(0, 3)
                            .map(([key, value]) => (
                              <div
                                key={key}
                                className="flex justify-between text-sm"
                              >
                                <span className="text-foreground capitalize">
                                  {key.replace(/_/g, ' ')}:
                                </span>
                                <span className="font-medium text-foreground">
                                  {typeof value === 'number'
                                    ? value.toFixed(1)
                                    : value}
                                </span>
                              </div>
                            ))}
                        </div>
                      )}

                    {component.dependencies &&
                      component.dependencies.length > 0 && (
                        <div className="text-sm">
                          <span className="text-foreground">
                            Dependencies:{' '}
                          </span>
                          <span className="text-foreground">
                            {component.dependencies.slice(0, 2).join(', ')}
                            {component.dependencies.length > 2 &&
                              ` +${component.dependencies.length - 2}`}
                          </span>
                        </div>
                      )}
                  </div>
                )}

                {/* Actions */}
                {showActions && (
                  <div className="absolute top-2 right-2 opacity-0 hover:opacity-100 transition-opacity">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        onRefresh?.(component.name);
                      }}
                      className="h-8 w-8 p-0"
                    >
                      <ArrowPathIcon className="h-4 w-4" />
                    </Button>
                  </div>
                )}

                {/* Status Indicator */}
                <div
                  className={cn(
                    'absolute top-2 right-2 h-3 w-3 rounded-full',
                    component.status === 'healthy'
                      ? 'bg-green-500'
                      : component.status === 'degraded'
                        ? 'bg-yellow-500'
                        : component.status === 'unhealthy'
                          ? 'bg-red-500'
                          : 'bg-gray-500',
                    'animate-pulse'
                  )}
                />
              </div>
            );
          })}
        </div>

        {components.length === 0 && (
          <div className="text-center py-8">
            <QuestionMarkCircleIcon className="h-12 w-12 text-muted-foreground mx-auto mb-2" />
            <p className="text-muted-foreground">
              No component status data available
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default StatusGrid;
