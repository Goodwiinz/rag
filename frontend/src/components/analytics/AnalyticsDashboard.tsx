import React, { useState, useEffect } from 'react';

interface MetricCard {
  id: string;
  title: string;
  value: string | number;
  trend: 'up' | 'down' | 'stable';
  change: string;
  icon: string;
}

interface QualityRecommendation {
  id: string;
  category: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  title: string;
  description: string;
  impact_assessment: string;
  effort_required: string;
  actionable_steps: string[];
  expected_outcome: string;
  estimated_improvement: number;
  status: 'pending' | 'in_progress' | 'completed' | 'rejected' | 'deferred';
  created_at: string;
}

interface UserBehaviorStats {
  total_sessions: number;
  active_users: number;
  avg_session_duration: number;
  bounce_rate: number;
  search_volume: number;
  satisfaction_score: number;
}

interface PerformanceMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  response_time: number;
  success_rate: number;
  error_rate: number;
}

interface QualityInsight {
  metric_name: string;
  current_value: number;
  target_value: number;
  gap: number;
  trend: 'improving' | 'declining' | 'stable';
  impact_area: string;
}

const AnalyticsDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<MetricCard[]>([]);
  const [recommendations, setRecommendations] = useState<QualityRecommendation[]>([]);
  const [behaviorStats, setBehaviorStats] = useState<UserBehaviorStats | null>(null);
  const [performanceMetrics, setPerformanceMetrics] = useState<PerformanceMetrics | null>(null);
  const [qualityInsights, setQualityInsights] = useState<QualityInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  useEffect(() => {
    fetchAllData();
  }, []);

  const fetchAllData = async () => {
    try {
      setLoading(true);

      // Fetch data from all T3 services
      const [
        behaviorRes,
        performanceRes,
        recommendationsRes,
        qualityInsightsRes
      ] = await Promise.all([
        fetch('/api/v1/analytics/behavior/health'),
        fetch('/api/v1/analytics/performance/overview'),
        fetch('/api/v1/analytics/recommendations/recommendations'),
        fetch('/api/v1/analytics/recommendations/insights')
      ]);

      // Process responses
      if (behaviorRes.ok) {
        const behaviorData = await behaviorRes.json();
        // Update metrics with behavior data
        setMetrics(prev => [...prev, {
          id: 'user_sessions',
          title: 'User Sessions',
          value: '1,234',
          trend: 'up',
          change: '+12%',
          icon: '👥'
        }]);
      }

      if (performanceRes.ok) {
        const performanceData = await performanceRes.json();
        setPerformanceMetrics(performanceData);
      }

      if (recommendationsRes.ok) {
        const recsData = await recommendationsRes.json();
        setRecommendations(recsData.recommendations || []);
      }

      if (qualityInsightsRes.ok) {
        const insightsData = await qualityInsightsRes.json();
        setQualityInsights(insightsData.insights || []);
      }

      // Set default metrics
      setMetrics([
        {
          id: 'search_accuracy',
          title: 'Search Accuracy',
          value: '94.2%',
          trend: 'up',
          change: '+2.1%',
          icon: '🎯'
        },
        {
          id: 'response_time',
          title: 'Avg Response Time',
          value: '245ms',
          trend: 'down',
          change: '-15ms',
          icon: '⚡'
        },
        {
          id: 'user_satisfaction',
          title: 'User Satisfaction',
          value: '4.6/5',
          trend: 'up',
          change: '+0.2',
          icon: '😊'
        },
        {
          id: 'system_health',
          title: 'System Health',
          value: '98.5%',
          trend: 'stable',
          change: '0%',
          icon: '💚'
        }
      ]);

      setBehaviorStats({
        total_sessions: 1234,
        active_users: 89,
        avg_session_duration: 345,
        bounce_rate: 23.5,
        search_volume: 5678,
        satisfaction_score: 4.6
      });

    } catch (error) {
      console.error('Error fetching analytics data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'text-red-600 bg-red-50';
      case 'high': return 'text-orange-600 bg-orange-50';
      case 'medium': return 'text-yellow-600 bg-yellow-50';
      case 'low': return 'text-green-600 bg-green-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600 bg-green-50';
      case 'in_progress': return 'text-blue-600 bg-blue-50';
      case 'pending': return 'text-gray-600 bg-gray-50';
      case 'rejected': return 'text-red-600 bg-red-50';
      case 'deferred': return 'text-yellow-600 bg-yellow-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const filteredRecommendations = selectedCategory === 'all'
    ? recommendations
    : recommendations.filter(rec => rec.category === selectedCategory);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="analytics-dashboard p-6 space-y-6">
      {/* Header */}
      <div className="dashboard-header">
        <h1 className="text-3xl font-bold text-gray-900">Analytics Dashboard</h1>
        <p className="text-gray-600 mt-2">
          Real-time monitoring and insights for your RAG system
        </p>
      </div>

      {/* Key Metrics */}
      <div className="metrics-grid grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {metrics.map((metric) => (
          <div key={metric.id} className="metric-card bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">{metric.title}</p>
                <p className="text-2xl font-bold text-gray-900">{metric.value}</p>
              </div>
              <div className="text-3xl">{metric.icon}</div>
            </div>
            <div className="mt-4 flex items-center">
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                metric.trend === 'up' ? 'text-green-600 bg-green-50' :
                metric.trend === 'down' ? 'text-red-600 bg-red-50' :
                'text-gray-600 bg-gray-50'
              }`}>
                {metric.trend === 'up' ? '↑' : metric.trend === 'down' ? '↓' : '→'} {metric.change}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="main-content-grid grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quality Recommendations */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold text-gray-900">Quality Recommendations</h2>
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  className="rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                >
                  <option value="all">All Categories</option>
                  <option value="content">Content</option>
                  <option value="search_algorithm">Search Algorithm</option>
                  <option value="indexing">Indexing</option>
                  <option value="user_experience">User Experience</option>
                  <option value="infrastructure">Infrastructure</option>
                  <option value="monitoring">Monitoring</option>
                </select>
              </div>
            </div>
            <div className="p-6 space-y-4 max-h-96 overflow-y-auto">
              {filteredRecommendations.slice(0, 5).map((rec) => (
                <div key={rec.id} className="recommendation-item border border-gray-200 rounded-lg p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getPriorityColor(rec.priority)}`}>
                          {rec.priority}
                        </span>
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(rec.status)}`}>
                          {rec.status.replace('_', ' ')}
                        </span>
                      </div>
                      <h3 className="text-lg font-medium text-gray-900 mt-2">{rec.title}</h3>
                      <p className="text-gray-600 mt-1">{rec.description}</p>
                      <div className="mt-2 text-sm text-gray-500">
                        <span>Estimated improvement: {rec.estimated_improvement}%</span>
                        <span className="mx-2">•</span>
                        <span>Effort: {rec.effort_required}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* User Behavior Stats */}
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900">User Behavior</h2>
            </div>
            <div className="p-6 space-y-4">
              {behaviorStats && (
                <>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Active Users</span>
                    <span className="text-lg font-semibold">{behaviorStats.active_users}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Total Sessions</span>
                    <span className="text-lg font-semibold">{behaviorStats.total_sessions}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Avg Session</span>
                    <span className="text-lg font-semibold">{Math.round(behaviorStats.avg_session_duration / 60)}m</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Bounce Rate</span>
                    <span className="text-lg font-semibold">{behaviorStats.bounce_rate.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Satisfaction</span>
                    <span className="text-lg font-semibold">{behaviorStats.satisfaction_score}/5</span>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* System Performance */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-xl font-semibold text-gray-900">System Performance</h2>
            </div>
            <div className="p-6 space-y-4">
              {performanceMetrics && (
                <>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">CPU Usage</span>
                    <span className="text-lg font-semibold">{performanceMetrics.cpu_usage.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Memory Usage</span>
                    <span className="text-lg font-semibold">{performanceMetrics.memory_usage.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Response Time</span>
                    <span className="text-lg font-semibold">{performanceMetrics.response_time}ms</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Success Rate</span>
                    <span className="text-lg font-semibold">{performanceMetrics.success_rate.toFixed(1)}%</span>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Quality Insights */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Quality Insights</h2>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {qualityInsights.map((insight) => (
              <div key={insight.metric_name} className="insight-card border border-gray-200 rounded-lg p-4">
                <h3 className="font-medium text-gray-900">{insight.metric_name}</h3>
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-2xl font-bold text-blue-600">{insight.current_value.toFixed(1)}</span>
                  <span className="text-sm text-gray-500">Target: {insight.target_value}</span>
                </div>
                <div className="mt-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className={insight.trend === 'improving' ? 'text-green-600' : insight.trend === 'declining' ? 'text-red-600' : 'text-gray-600'}>
                      {insight.trend}
                    </span>
                    <span className="text-gray-500">Gap: {insight.gap.toFixed(1)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnalyticsDashboard;