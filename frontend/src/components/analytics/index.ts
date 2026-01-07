/**
 * Analytics Components Index
 * Exports all analytics-related components
 */

export { default as AnalyticsDashboard, AnalyticsDashboard as AnalyticsDashboardComponent } from './AnalyticsDashboard';
export { default as AnalyticsOverview, AnalyticsOverview as AnalyticsOverviewComponent } from './AnalyticsOverview';
export { default as AnalyticsChart, AnalyticsChart as AnalyticsChartComponent } from './AnalyticsChart';
export {
  default as AnalyticsTable,
  AnalyticsTable as AnalyticsTableComponent,
  createDocumentAnalyticsTable,
  createSearchAnalyticsTable
} from './AnalyticsTable';
// Note: AnalyticsProvider requires type fixes - commented out for strict mode
// export { AnalyticsProvider } from './AnalyticsProvider';
