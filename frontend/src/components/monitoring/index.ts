/**
 * Monitoring Components Index
 * Exports all monitoring-related components for easy importing
 */

// Core Dashboard Components
// Note: Dashboards below require type fixes - commented out for strict mode
// export { default as SystemOverviewDashboard } from './SystemOverviewDashboard';
// export { default as PerformanceMetricsDashboard } from './PerformanceMetricsDashboard';

// Reusable Components
export { default as MetricCard } from './MetricCard';
export { default as StatusGrid } from './StatusGrid';
export { default as AlertList } from './AlertList';

// Export component props types
export type { MetricCardProps } from './MetricCard';
export type { StatusGridProps } from './StatusGrid';
export type { AlertListProps } from './AlertList';