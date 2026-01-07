/**
 * AlertList - A component for displaying and managing alerts
 * Supports filtering, acknowledgment, resolution, and detailed alert information
 */

import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { Alert, AlertAction } from '@/types/monitoring';
import { useMonitoringStore } from '@/stores/monitoringStore';
import {
  ExclamationTriangleIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  XCircleIcon,
  BellIcon,
  BellSlashIcon,
  ClockIcon,
  UserIcon,
  TagIcon,
  FunnelIcon,
  MagnifyingGlassIcon,
  ChevronDownIcon,
  ChevronRightIcon
} from '@heroicons/react/24/outline';

export interface AlertListProps {
  alerts?: Alert[];
  title?: string;
  showFilters?: boolean;
  showActions?: boolean;
  maxHeight?: string;
  compact?: boolean;
  allowExpansion?: boolean;
  onAlertClick?: (alert: Alert) => void;
  onFilterChange?: (filters: AlertFilters) => void;
  className?: string;
}

interface AlertFilters {
  severity?: string[];
  status?: string[];
  source?: string[];
  search?: string;
  timeRange?: string;
}

const AlertList: React.FC<AlertListProps> = ({
  alerts: propAlerts,
  title = 'Alerts',
  showFilters = true,
  showActions = true,
  maxHeight = '400px',
  compact = false,
  allowExpansion = true,
  onAlertClick,
  onFilterChange,
  className
}) => {
  // Store integration
  const storeAlerts = useMonitoringStore((state) => state.activeAlerts);
  const acknowledgeAlert = useMonitoringStore((state) => state.acknowledgeAlert);
  const resolveAlert = useMonitoringStore((state) => state.resolveAlert);
  const suppressAlert = useMonitoringStore((state) => state.suppressAlert);
  const acknowledgedAlerts = useMonitoringStore((state) => state.acknowledgedAlerts);

  // Use props alerts or fall back to store
  const alerts = propAlerts || storeAlerts;

  // State
  const [filters, setFilters] = useState<AlertFilters>({});
  const [expandedAlerts, setExpandedAlerts] = useState<Set<string>>(new Set());
  const [showFiltersPanel, setShowFiltersPanel] = useState(false);

  // Derived state
  const filteredAlerts = useMemo(() => {
    return alerts.filter(alert => {
      // Status filter
      if (filters.status && filters.status.length > 0) {
        if (!filters.status.includes(alert.status)) return false;
      }

      // Severity filter
      if (filters.severity && filters.severity.length > 0) {
        if (!filters.severity.includes(alert.severity)) return false;
      }

      // Source filter
      if (filters.source && filters.source.length > 0) {
        if (!filters.source.includes(alert.source)) return false;
      }

      // Search filter
      if (filters.search) {
        const searchTerm = filters.search.toLowerCase();
        if (
          !alert.name.toLowerCase().includes(searchTerm) &&
          !alert.description.toLowerCase().includes(searchTerm)
        ) {
          return false;
        }
      }

      return true;
    });
  }, [alerts, filters]);

  const uniqueSources = useMemo(() => {
    return Array.from(new Set(alerts.map(alert => alert.source))).sort();
  }, [alerts]);

  const alertStats = useMemo(() => {
    const stats = {
      total: filteredAlerts.length,
      active: filteredAlerts.filter(a => a.status === 'active').length,
      acknowledged: filteredAlerts.filter(a => a.status === 'acknowledged').length,
      resolved: filteredAlerts.filter(a => a.status === 'resolved').length,
      suppressed: filteredAlerts.filter(a => a.status === 'suppressed').length,
      critical: filteredAlerts.filter(a => a.severity === 'critical').length,
      warning: filteredAlerts.filter(a => a.severity === 'warning').length,
      info: filteredAlerts.filter(a => a.severity === 'info').length
    };
    return stats;
  }, [filteredAlerts]);

  // Helper functions
  const getSeverityConfig = (severity: string) => {
    switch (severity) {
      case 'critical':
        return {
          icon: XCircleIcon,
          color: 'text-red-600',
          bgColor: 'bg-red-50',
          borderColor: 'border-red-200',
          badgeColor: 'bg-red-100 text-red-800'
        };
      case 'warning':
        return {
          icon: ExclamationTriangleIcon,
          color: 'text-yellow-600',
          bgColor: 'bg-yellow-50',
          borderColor: 'border-yellow-200',
          badgeColor: 'bg-yellow-100 text-yellow-800'
        };
      case 'info':
        return {
          icon: InformationCircleIcon,
          color: 'text-blue-600',
          bgColor: 'bg-blue-50',
          borderColor: 'border-blue-200',
          badgeColor: 'bg-blue-100 text-blue-800'
        };
      default:
        return {
          icon: BellIcon,
          color: 'text-gray-600',
          bgColor: 'bg-gray-50',
          borderColor: 'border-gray-200',
          badgeColor: 'bg-gray-100 text-gray-800'
        };
    }
  };

  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'active':
        return {
          icon: BellIcon,
          color: 'text-green-600',
          label: 'Active'
        };
      case 'acknowledged':
        return {
          icon: CheckCircleIcon,
          color: 'text-blue-600',
          label: 'Acknowledged'
        };
      case 'resolved':
        return {
          icon: CheckCircleIcon,
          color: 'text-gray-600',
          label: 'Resolved'
        };
      case 'suppressed':
        return {
          icon: BellSlashIcon,
          color: 'text-gray-500',
          label: 'Suppressed'
        };
      default:
        return {
          icon: BellIcon,
          color: 'text-gray-600',
          label: status
        };
    }
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleString();
    } catch {
      return 'Invalid date';
    }
  };

  const formatRelativeTime = (timestamp: string) => {
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

  // Event handlers
  const updateFilters = (newFilters: Partial<AlertFilters>) => {
    const updatedFilters = { ...filters, ...newFilters };
    setFilters(updatedFilters);
    onFilterChange?.(updatedFilters);
  };

  const toggleAlertExpansion = (alertId: string) => {
    const newExpanded = new Set(expandedAlerts);
    if (newExpanded.has(alertId)) {
      newExpanded.delete(alertId);
    } else {
      newExpanded.add(alertId);
    }
    setExpandedAlerts(newExpanded);
  };

  const handleAlertAction = async (alert: Alert, action: string) => {
    switch (action) {
      case 'acknowledge':
        acknowledgeAlert(alert.id);
        break;
      case 'resolve':
        resolveAlert(alert.id);
        break;
      case 'suppress':
        suppressAlert(alert.id, 60); // Suppress for 60 minutes
        break;
      default:
        break;
    }
  };

  // Render functions
  const renderAlertItem = (alert: Alert) => {
    const severityConfig = getSeverityConfig(alert.severity);
    const statusConfig = getStatusConfig(alert.status);
    const isExpanded = expandedAlerts.has(alert.id);
    const isAcknowledged = acknowledgedAlerts.has(alert.id);

    return (
      <div
        key={alert.id}
        className={cn(
          'border rounded-lg p-4 transition-all duration-200',
          'hover:shadow-sm cursor-pointer',
          severityConfig.bgColor,
          severityConfig.borderColor,
          isAcknowledged && 'opacity-75'
        )}
        onClick={() => onAlertClick?.(alert)}
      >
        {/* Alert Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-start space-x-3 flex-1">
            <severityConfig.icon className={cn('h-5 w-5 mt-0.5 flex-shrink-0', severityConfig.color)} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center space-x-2 mb-1">
                <h3 className="font-semibold text-gray-900 truncate">{alert.name}</h3>
                <Badge variant="outline" className={severityConfig.badgeColor}>
                  {alert.severity}
                </Badge>
                <Badge variant="outline" className="bg-gray-100 text-gray-800">
                  <statusConfig.icon className="h-3 w-3 mr-1" />
                  {statusConfig.label}
                </Badge>
              </div>
              <p className="text-sm text-gray-600 mb-2">{alert.description}</p>

              {/* Alert Metadata */}
              <div className="flex items-center space-x-4 text-xs text-gray-500">
                <div className="flex items-center space-x-1">
                  <ClockIcon className="h-3 w-3" />
                  <span>{formatRelativeTime(alert.triggered_at)}</span>
                </div>
                <div className="flex items-center space-x-1">
                  <TagIcon className="h-3 w-3" />
                  <span>{alert.source}</span>
                </div>
                {alert.acknowledged_by && (
                  <div className="flex items-center space-x-1">
                    <UserIcon className="h-3 w-3" />
                    <span>By {alert.acknowledged_by}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Actions and Expansion */}
          <div className="flex items-center space-x-2">
            {allowExpansion && (
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  toggleAlertExpansion(alert.id);
                }}
                className="h-8 w-8 p-0"
              >
                {isExpanded ? (
                  <ChevronDownIcon className="h-4 w-4" />
                ) : (
                  <ChevronRightIcon className="h-4 w-4" />
                )}
              </Button>
            )}
          </div>
        </div>

        {/* Expanded Content */}
        {isExpanded && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            {/* Labels */}
            {Object.keys(alert.labels).length > 0 && (
              <div className="mb-3">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Labels</h4>
                <div className="flex flex-wrap gap-1">
                  {Object.entries(alert.labels).map(([key, value]) => (
                    <Badge key={key} variant="outline" className="text-xs">
                      {key}: {value}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Annotations */}
            {Object.keys(alert.annotations).length > 0 && (
              <div className="mb-3">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Annotations</h4>
                <div className="space-y-1">
                  {Object.entries(alert.annotations).map(([key, value]) => (
                    <div key={key} className="text-sm">
                      <span className="font-medium text-gray-700">{key}:</span>
                      <span className="ml-2 text-gray-600">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Actions */}
            {showActions && alert.status === 'active' && (
              <div className="flex items-center space-x-2">
                {!isAcknowledged && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleAlertAction(alert, 'acknowledge');
                    }}
                  >
                    Acknowledge
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleAlertAction(alert, 'resolve');
                  }}
                >
                  Resolve
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleAlertAction(alert, 'suppress');
                  }}
                >
                  Suppress
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <Card className={cn('shadow-sm', className)}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center space-x-2">
              <BellIcon className="h-5 w-5" />
              <span>{title}</span>
              <Badge variant="outline">
                {alertStats.active} active
              </Badge>
            </CardTitle>
            {alertStats.total > 0 && (
              <div className="flex items-center space-x-4 mt-2 text-sm text-gray-600">
                <span>Critical: {alertStats.critical}</span>
                <span>Warning: {alertStats.warning}</span>
                <span>Info: {alertStats.info}</span>
              </div>
            )}
          </div>
          {showFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowFiltersPanel(!showFiltersPanel)}
              className="text-gray-500"
            >
              <FunnelIcon className="h-4 w-4 mr-1" />
              Filters
            </Button>
          )}
        </div>

        {/* Filters Panel */}
        {showFilters && showFiltersPanel && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              {/* Search */}
              <div className="relative">
                <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search alerts..."
                  value={filters.search || ''}
                  onChange={(e) => updateFilters({ search: e.target.value })}
                  className="pl-10"
                />
              </div>

              {/* Severity Filter */}
              <Select
                value={filters.severity?.[0] || ''}
                onValueChange={(value) => updateFilters({ severity: value ? [value] : [] })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Severity" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All Severities</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                  <SelectItem value="warning">Warning</SelectItem>
                  <SelectItem value="info">Info</SelectItem>
                </SelectContent>
              </Select>

              {/* Status Filter */}
              <Select
                value={filters.status?.[0] || ''}
                onValueChange={(value) => updateFilters({ status: value ? [value] : [] })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All Statuses</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="acknowledged">Acknowledged</SelectItem>
                  <SelectItem value="resolved">Resolved</SelectItem>
                  <SelectItem value="suppressed">Suppressed</SelectItem>
                </SelectContent>
              </Select>

              {/* Source Filter */}
              <Select
                value={filters.source?.[0] || ''}
                onValueChange={(value) => updateFilters({ source: value ? [value] : [] })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Source" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All Sources</SelectItem>
                  {uniqueSources.map(source => (
                    <SelectItem key={source} value={source}>{source}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Clear Filters */}
            <div className="flex justify-end">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setFilters({});
                  onFilterChange?.({});
                }}
              >
                Clear Filters
              </Button>
            </div>
          </div>
        )}
      </CardHeader>

      <CardContent className="pt-0">
        <ScrollArea style={{ maxHeight }} className="pr-4">
          {filteredAlerts.length > 0 ? (
            <div className="space-y-3">
              {filteredAlerts.map(renderAlertItem)}
            </div>
          ) : (
            <div className="text-center py-8">
              <BellIcon className="h-12 w-12 text-gray-400 mx-auto mb-2" />
              <p className="text-gray-500">
                {alerts.length === 0 ? 'No alerts' : 'No alerts match your filters'}
              </p>
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export default AlertList;