/**
 * Analytics Dashboard - Displays graph analytics from backend
 *
 * This component ONLY displays analytics data computed by backend services.
 * NO analytics calculations or statistical computations included.
 */

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { analyticsService } from '../../services/graphAnalyticsService';
import {
  AnalyticsDashboard as AnalyticsData,
  CentralityMetrics,
  CommunityAnalytics,
  InsightData,
  GraphFilters
} from '../../types/graph-api';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';

interface AnalyticsDashboardProps {
  filters?: GraphFilters;
  className?: string;
}

export const AnalyticsDashboard: React.FC<AnalyticsDashboardProps> = ({
  filters = {},
  className = ''
}) => {
  const [selectedMetric, setSelectedMetric] = useState<'centrality' | 'communities' | 'insights'>('centrality');

  // Fetch analytics dashboard from backend - NO processing logic
  const {
    data: analyticsData,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['analyticsDashboard', filters],
    queryFn: () => analyticsService.getAnalyticsDashboard(filters),
    staleTime: 10 * 60 * 1000, // 10 minutes
    cacheTime: 30 * 60 * 1000, // 30 minutes
  });

  // Fetch centrality metrics specifically
  const {
    data: centralityData,
    isLoading: isCentralityLoading
  } = useQuery({
    queryKey: ['centralityMetrics', filters],
    queryFn: () => analyticsService.getCentralityMetrics(undefined, ['degree', 'betweenness', 'closeness', 'eigenvector']),
    enabled: selectedMetric === 'centrality',
    staleTime: 15 * 60 * 1000, // 15 minutes
  });

  // Fetch community analytics specifically
  const {
    data: communityData,
    isLoading: isCommunityLoading
  } = useQuery({
    queryKey: ['communityAnalytics', filters],
    queryFn: () => analyticsService.getCommunityAnalytics('louvain', 1.0),
    enabled: selectedMetric === 'communities',
    staleTime: 15 * 60 * 1000, // 15 minutes
  });

  // Fetch insights specifically
  const {
    data: insightsData,
    isLoading: isInsightsLoading
  } = useQuery({
    queryKey: ['topologicalInsights', filters],
    queryFn: () => analyticsService.getTopologicalInsights(['anomaly', 'trend', 'pattern', 'recommendation']),
    enabled: selectedMetric === 'insights',
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  if (isLoading) {
    return (
      <div className={`analytics-dashboard ${className}`}>
        <div className="flex items-center justify-center p-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-3 text-gray-600">Loading analytics data...</span>
        </div>
      </div>
    );
  }

  if (error || !analyticsData) {
    return (
      <div className={`analytics-dashboard ${className}`}>
        <div className="p-4 text-red-600 text-center">
          <h3 className="text-lg font-semibold mb-2">Failed to load analytics</h3>
          <p className="text-sm">{(error as Error)?.message || 'Analytics service unavailable'}</p>
          <button
            onClick={() => refetch()}
            className="mt-3 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const renderOverviewCards = () => (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-600">Total Nodes</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{analyticsData.overview.totalNodes.toLocaleString()}</div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-600">Total Edges</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{analyticsData.overview.totalEdges.toLocaleString()}</div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-600">Avg Degree</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{analyticsData.overview.averageDegree.toFixed(2)}</div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-600">Graph Density</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{(analyticsData.overview.graphDensity * 100).toFixed(1)}%</div>
        </CardContent>
      </Card>
    </div>
  );

  const renderCentralityMetrics = () => {
    if (isCentralityLoading) {
      return (
        <div className="flex items-center justify-center p-8">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-gray-600">Loading centrality metrics...</span>
        </div>
      );
    }

    if (!centralityData || centralityData.length === 0) {
      return (
        <div className="text-center text-gray-500 py-8">
          No centrality data available
        </div>
      );
    }

    // Top nodes by different centrality measures - NO computation, just display
    const topByDegree = centralityData
      .sort((a, b) => b.normalized_degree - a.normalized_degree)
      .slice(0, 5);

    const topByBetweenness = centralityData
      .sort((a, b) => b.normalized_betweenness - a.normalized_betweenness)
      .slice(0, 5);

    const topByCloseness = centralityData
      .sort((a, b) => b.normalized_closeness - a.normalized_closeness)
      .slice(0, 5);

    return (
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-semibold mb-4">Top Nodes by Degree Centrality</h3>
          <div className="space-y-2">
            {topByDegree.map((node, index) => (
              <div key={node.nodeId} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                <div className="flex items-center space-x-3">
                  <span className="font-semibold text-gray-500">#{index + 1}</span>
                  <span className="font-medium">{node.nodeId}</span>
                </div>
                <div className="flex items-center space-x-4">
                  <Progress value={node.normalized_degree * 100} className="w-24" />
                  <span className="text-sm font-medium">{(node.normalized_degree * 100).toFixed(1)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h3 className="text-lg font-semibold mb-4">Top Nodes by Betweenness Centrality</h3>
          <div className="space-y-2">
            {topByBetweenness.map((node, index) => (
              <div key={node.nodeId} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                <div className="flex items-center space-x-3">
                  <span className="font-semibold text-gray-500">#{index + 1}</span>
                  <span className="font-medium">{node.nodeId}</span>
                </div>
                <div className="flex items-center space-x-4">
                  <Progress value={node.normalized_betweenness * 100} className="w-24" />
                  <span className="text-sm font-medium">{(node.normalized_betweenness * 100).toFixed(1)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h3 className="text-lg font-semibold mb-4">Top Nodes by Closeness Centrality</h3>
          <div className="space-y-2">
            {topByCloseness.map((node, index) => (
              <div key={node.nodeId} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                <div className="flex items-center space-x-3">
                  <span className="font-semibold text-gray-500">#{index + 1}</span>
                  <span className="font-medium">{node.nodeId}</span>
                </div>
                <div className="flex items-center space-x-4">
                  <Progress value={node.normalized_closeness * 100} className="w-24" />
                  <span className="text-sm font-medium">{(node.normalized_closeness * 100).toFixed(1)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  const renderCommunities = () => {
    if (isCommunityLoading) {
      return (
        <div className="flex items-center justify-center p-8">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-gray-600">Loading community data...</span>
        </div>
      );
    }

    if (!communityData || communityData.length === 0) {
      return (
        <div className="text-center text-gray-500 py-8">
          No community data available
        </div>
      );
    }

    // Sort communities by size - NO computation, just display
    const sortedCommunities = communityData
      .sort((a, b) => b.nodeCount - a.nodeCount)
      .slice(0, 10);

    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {sortedCommunities.map((community) => (
            <Card key={community.communityId}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium">
                    Community {community.communityId}
                  </CardTitle>
                  <Badge variant="secondary">{community.nodeCount} nodes</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Density:</span>
                    <span className="font-medium">{(community.density * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Modularity:</span>
                    <span className="font-medium">{community.modularity.toFixed(3)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Dominant Type:</span>
                    <Badge variant="outline">{community.dominantEntityType}</Badge>
                  </div>
                </div>

                {community.topNodes.length > 0 && (
                  <div className="mt-3 pt-3 border-t">
                    <div className="text-xs text-gray-600 mb-2">Top Nodes:</div>
                    <div className="space-y-1">
                      {community.topNodes.slice(0, 3).map((node) => (
                        <div key={node.nodeId} className="flex justify-between text-xs">
                          <span className="truncate mr-2">{node.nodeId}</span>
                          <span className="text-gray-500">{(node.centrality * 100).toFixed(1)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  };

  const renderInsights = () => {
    if (isInsightsLoading) {
      return (
        <div className="flex items-center justify-center p-8">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-gray-600">Loading insights...</span>
        </div>
      );
    }

    if (!insightsData || insightsData.length === 0) {
      return (
        <div className="text-center text-gray-500 py-8">
          No insights available
        </div>
      );
    }

    return (
      <div className="space-y-4">
        {insightsData.map((insight, index) => (
          <Card key={index}>
            <CardHeader>
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <CardTitle className="text-base">{insight.title}</CardTitle>
                  <div className="flex items-center space-x-2">
                    <Badge
                      variant={insight.type === 'anomaly' ? 'destructive' :
                              insight.type === 'recommendation' ? 'default' : 'secondary'}
                    >
                      {insight.type}
                    </Badge>
                    <Badge
                      variant={insight.impact === 'high' ? 'destructive' :
                              insight.impact === 'medium' ? 'default' : 'secondary'}
                    >
                      {insight.impact} impact
                    </Badge>
                    {insight.actionable && (
                      <Badge variant="outline">Actionable</Badge>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium text-gray-600">
                    {(insight.confidence * 100).toFixed(1)}% confidence
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-700 mb-3">{insight.description}</p>

              {insight.suggestedActions.length > 0 && (
                <div className="space-y-2">
                  <div className="text-sm font-medium text-gray-600">Suggested Actions:</div>
                  <ul className="text-sm text-gray-700 space-y-1">
                    {insight.suggestedActions.slice(0, 3).map((action, actionIndex) => (
                      <li key={actionIndex} className="flex items-start">
                        <span className="text-blue-600 mr-2">•</span>
                        <span>{action}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    );
  };

  return (
    <div className={`analytics-dashboard ${className}`}>
      {/* Overview Cards */}
      {renderOverviewCards()}

      {/* Metric Selection Tabs */}
      <div className="flex space-x-1 mb-6 bg-gray-100 p-1 rounded-lg">
        {[
          { key: 'centrality', label: 'Centrality Metrics' },
          { key: 'communities', label: 'Communities' },
          { key: 'insights', label: 'AI Insights' }
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setSelectedMetric(tab.key as any)}
            className={`flex-1 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              selectedMetric === tab.key
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Metric Content */}
      <div className="min-h-[400px]">
        {selectedMetric === 'centrality' && renderCentralityMetrics()}
        {selectedMetric === 'communities' && renderCommunities()}
        {selectedMetric === 'insights' && renderInsights()}
      </div>
    </div>
  );
};

export default AnalyticsDashboard;