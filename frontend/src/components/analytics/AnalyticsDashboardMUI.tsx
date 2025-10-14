import React, { useState, useEffect } from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  Paper,
  List,
  ListItem,
  ListItemText,
  Divider,
  CircularProgress,
  Stack
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  TrendingFlat,
  People,
  Speed,
  SentimentVerySatisfied,
  Favorite
} from '@mui/icons-material';

interface MetricCard {
  id: string;
  title: string;
  value: string | number;
  trend: 'up' | 'down' | 'stable';
  change: string;
  icon: React.ReactNode;
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

const AnalyticsDashboardMUI: React.FC = () => {
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

      // Mock data for demonstration
      setMetrics([
        {
          id: 'search_accuracy',
          title: 'Search Accuracy',
          value: '94.2%',
          trend: 'up',
          change: '+2.1%',
          icon: <TrendingUp color="success" />
        },
        {
          id: 'response_time',
          title: 'Avg Response Time',
          value: '245ms',
          trend: 'down',
          change: '-15ms',
          icon: <Speed color="info" />
        },
        {
          id: 'user_satisfaction',
          title: 'User Satisfaction',
          value: '4.6/5',
          trend: 'up',
          change: '+0.2',
          icon: <SentimentVerySatisfied color="warning" />
        },
        {
          id: 'system_health',
          title: 'System Health',
          value: '98.5%',
          trend: 'stable',
          change: '0%',
          icon: <Favorite color="success" />
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

      setPerformanceMetrics({
        cpu_usage: 45.2,
        memory_usage: 67.8,
        disk_usage: 34.1,
        response_time: 245,
        success_rate: 98.5,
        error_rate: 1.5
      });

      setRecommendations([
        {
          id: '1',
          category: 'content',
          priority: 'high',
          title: 'Improve Document Quality Scores',
          description: 'Update outdated content and enhance metadata for better search relevance',
          impact_assessment: 'High impact on search accuracy',
          effort_required: 'Medium',
          actionable_steps: ['Audit existing documents', 'Update metadata', 'Implement quality scoring'],
          expected_outcome: '15-20% improvement in search relevance',
          estimated_improvement: 18,
          status: 'pending',
          created_at: '2025-10-09T21:41:00Z'
        },
        {
          id: '2',
          category: 'search_algorithm',
          priority: 'critical',
          title: 'Optimize Vector Search Parameters',
          description: 'Fine-tune embedding similarity thresholds for better results',
          impact_assessment: 'Critical impact on result quality',
          effort_required: 'Low',
          actionable_steps: ['Analyze current thresholds', 'A/B test new parameters', 'Deploy optimized settings'],
          expected_outcome: '10-15% improvement in result relevance',
          estimated_improvement: 12,
          status: 'in_progress',
          created_at: '2025-10-09T20:30:00Z'
        }
      ]);

      setQualityInsights([
        {
          metric_name: 'Search Relevance',
          current_value: 0.89,
          target_value: 0.95,
          gap: 0.06,
          trend: 'improving',
          impact_area: 'User Experience'
        },
        {
          metric_name: 'Response Time',
          current_value: 245,
          target_value: 200,
          gap: 45,
          trend: 'stable',
          impact_area: 'Performance'
        },
        {
          metric_name: 'User Satisfaction',
          current_value: 4.6,
          target_value: 4.8,
          gap: 0.2,
          trend: 'improving',
          impact_area: 'User Experience'
        }
      ]);

    } catch (error) {
      console.error('Error fetching analytics data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'error';
      case 'high': return 'warning';
      case 'medium': return 'info';
      case 'low': return 'success';
      default: return 'default';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'in_progress': return 'info';
      case 'pending': return 'default';
      case 'rejected': return 'error';
      case 'deferred': return 'warning';
      default: return 'default';
    }
  };

  const filteredRecommendations = selectedCategory === 'all'
    ? recommendations
    : recommendations.filter(rec => rec.category === selectedCategory);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="400px">
        <CircularProgress size={60} />
      </Box>
    );
  }

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      {/* Header */}
      <Box mb={4}>
        <Typography variant="h3" component="h1" gutterBottom>
          Analytics Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Real-time monitoring and insights for your RAG system
        </Typography>
      </Box>

      {/* Key Metrics */}
      <Grid container spacing={3} mb={4}>
        {metrics.map((metric) => (
          <Grid item xs={12} sm={6} md={3} key={metric.id}>
            <Card>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="h6" component="div">
                    {metric.title}
                  </Typography>
                  {metric.icon}
                </Box>
                <Typography variant="h4" component="div" gutterBottom>
                  {metric.value}
                </Typography>
                <Chip
                  label={`${metric.trend === 'up' ? '↑' : metric.trend === 'down' ? '↓' : '→'} ${metric.change}`}
                  color={metric.trend === 'up' ? 'success' : metric.trend === 'down' ? 'error' : 'default'}
                  size="small"
                />
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Main Content Grid */}
      <Grid container spacing={3}>
        {/* Quality Recommendations */}
        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 3 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
              <Typography variant="h5">Quality Recommendations</Typography>
              <FormControl size="small" sx={{ minWidth: 150 }}>
                <InputLabel>Category</InputLabel>
                <Select
                  value={selectedCategory}
                  label="Category"
                  onChange={(e) => setSelectedCategory(e.target.value)}
                >
                  <MenuItem value="all">All Categories</MenuItem>
                  <MenuItem value="content">Content</MenuItem>
                  <MenuItem value="search_algorithm">Search Algorithm</MenuItem>
                  <MenuItem value="indexing">Indexing</MenuItem>
                  <MenuItem value="user_experience">User Experience</MenuItem>
                  <MenuItem value="infrastructure">Infrastructure</MenuItem>
                  <MenuItem value="monitoring">Monitoring</MenuItem>
                </Select>
              </FormControl>
            </Box>
            <List>
              {filteredRecommendations.map((rec, index) => (
                <React.Fragment key={rec.id}>
                  <ListItem alignItems="flex-start">
                    <Box sx={{ width: '100%' }}>
                      <Box display="flex" alignItems="center" gap={1} mb={1}>
                        <Chip
                          label={rec.priority}
                          color={getPriorityColor(rec.priority) as any}
                          size="small"
                        />
                        <Chip
                          label={rec.status.replace('_', ' ')}
                          color={getStatusColor(rec.status) as any}
                          size="small"
                        />
                      </Box>
                      <Typography variant="h6" gutterBottom>
                        {rec.title}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" paragraph>
                        {rec.description}
                      </Typography>
                      <Box display="flex" gap={2} mt={1}>
                        <Typography variant="caption" color="text.secondary">
                          Est. improvement: {rec.estimated_improvement}%
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          •
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Effort: {rec.effort_required}
                        </Typography>
                      </Box>
                    </Box>
                  </ListItem>
                  {index < filteredRecommendations.length - 1 && <Divider />}
                </React.Fragment>
              ))}
            </List>
          </Paper>
        </Grid>

        {/* User Behavior Stats */}
        <Grid item xs={12} lg={4}>
          <Stack spacing={3}>
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="h5" mb={2}>
                User Behavior
              </Typography>
              {behaviorStats && (
                <List dense>
                  <ListItem>
                    <ListItemText
                      primary="Active Users"
                      secondary={behaviorStats.active_users}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Total Sessions"
                      secondary={behaviorStats.total_sessions}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Avg Session"
                      secondary={`${Math.round(behaviorStats.avg_session_duration / 60)}m`}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Bounce Rate"
                      secondary={`${behaviorStats.bounce_rate.toFixed(1)}%`}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Satisfaction"
                      secondary={`${behaviorStats.satisfaction_score}/5`}
                    />
                  </ListItem>
                </List>
              )}
            </Paper>

            <Paper sx={{ p: 3 }}>
              <Typography variant="h5" mb={2}>
                System Performance
              </Typography>
              {performanceMetrics && (
                <List dense>
                  <ListItem>
                    <ListItemText
                      primary="CPU Usage"
                      secondary={`${performanceMetrics.cpu_usage.toFixed(1)}%`}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Memory Usage"
                      secondary={`${performanceMetrics.memory_usage.toFixed(1)}%`}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Response Time"
                      secondary={`${performanceMetrics.response_time}ms`}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Success Rate"
                      secondary={`${performanceMetrics.success_rate.toFixed(1)}%`}
                    />
                  </ListItem>
                </List>
              )}
            </Paper>
          </Stack>
        </Grid>
      </Grid>

      {/* Quality Insights */}
      <Paper sx={{ p: 3, mt: 3 }}>
        <Typography variant="h5" mb={3}>
          Quality Insights
        </Typography>
        <Grid container spacing={3}>
          {qualityInsights.map((insight) => (
            <Grid item xs={12} sm={6} md={4} key={insight.metric_name}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    {insight.metric_name}
                  </Typography>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="h4" color="primary">
                      {insight.current_value.toFixed(1)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Target: {insight.target_value}
                    </Typography>
                  </Box>
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Chip
                      label={insight.trend}
                      color={insight.trend === 'improving' ? 'success' : insight.trend === 'declining' ? 'error' : 'default'}
                      size="small"
                    />
                    <Typography variant="body2" color="text.secondary">
                      Gap: {insight.gap.toFixed(1)}
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Paper>

      {/* Action Buttons */}
      <Box display="flex" gap={2} mt={3}>
        <Button variant="outlined" onClick={fetchAllData}>
          Refresh Data
        </Button>
        <Button variant="contained" color="primary">
          Export Report
        </Button>
      </Box>
    </Box>
  );
};

export default AnalyticsDashboardMUI;