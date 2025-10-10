import React, { useState, useEffect } from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  LinearProgress,
  Chip,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  Button,
  CircularProgress,
  Alert
} from '@mui/material';
import {
  CheckCircle,
  Warning,
  Error,
  TrendingUp,
  TrendingDown,
  Info,
  Refresh,
  Download
} from '@mui/icons-material';

interface QualityMetric {
  id: string;
  name: string;
  current_value: number;
  target_value: number;
  threshold: number;
  unit: string;
  trend: 'improving' | 'declining' | 'stable';
  status: 'good' | 'warning' | 'critical';
  last_updated: string;
  description: string;
}

interface QualityAlert {
  id: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description: string;
  metric_name: string;
  recommendation: string;
  created_at: string;
}

const QualityMetricsDashboardMUI: React.FC = () => {
  const [metrics, setMetrics] = useState<QualityMetric[]>([]);
  const [alerts, setAlerts] = useState<QualityAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchQualityMetrics();
    const interval = setInterval(fetchQualityMetrics, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchQualityMetrics = async () => {
    try {
      setError(null);

      // Mock data for demonstration
      const mockMetrics: QualityMetric[] = [
        {
          id: 'answer_relevancy',
          name: 'Answer Relevancy',
          current_value: 94.2,
          target_value: 95.0,
          threshold: 70.0,
          unit: '%',
          trend: 'improving',
          status: 'good',
          last_updated: new Date().toISOString(),
          description: 'Measures how relevant the generated answers are to the user query'
        },
        {
          id: 'faithfulness',
          name: 'Faithfulness',
          current_value: 89.5,
          target_value: 90.0,
          threshold: 90.0,
          unit: '%',
          trend: 'stable',
          status: 'warning',
          last_updated: new Date().toISOString(),
          description: 'Ensures answers are factually consistent with source documents'
        },
        {
          id: 'contextual_relevancy',
          name: 'Contextual Relevancy',
          current_value: 96.1,
          target_value: 95.0,
          threshold: 70.0,
          unit: '%',
          trend: 'improving',
          status: 'good',
          last_updated: new Date().toISOString(),
          description: 'Measures how well retrieved context matches the query'
        },
        {
          id: 'response_time',
          name: 'Response Time',
          current_value: 1.8,
          target_value: 2.0,
          threshold: 5.0,
          unit: 'seconds',
          trend: 'improving',
          status: 'good',
          last_updated: new Date().toISOString(),
          description: 'Average time to generate responses'
        },
        {
          id: 'user_satisfaction',
          name: 'User Satisfaction',
          current_value: 4.3,
          target_value: 4.5,
          threshold: 3.5,
          unit: '/5',
          trend: 'stable',
          status: 'warning',
          last_updated: new Date().toISOString(),
          description: 'Average user rating of response quality'
        },
        {
          id: 'hallucination_rate',
          name: 'Hallucination Rate',
          current_value: 8.2,
          target_value: 5.0,
          threshold: 10.0,
          unit: '%',
          trend: 'declining',
          status: 'warning',
          last_updated: new Date().toISOString(),
          description: 'Percentage of responses with factual inconsistencies'
        }
      ];

      const mockAlerts: QualityAlert[] = [
        {
          id: '1',
          severity: 'medium',
          title: 'Faithfulness Below Target',
          description: 'Faithfulness score has fallen below the 90% threshold',
          metric_name: 'Faithfulness',
          recommendation: 'Review context retrieval and adjust similarity thresholds',
          created_at: new Date(Date.now() - 3600000).toISOString()
        },
        {
          id: '2',
          severity: 'low',
          title: 'Hallucination Rate Increasing',
          description: 'Hallucination rate shows declining trend over past week',
          metric_name: 'Hallucination Rate',
          recommendation: 'Implement additional fact-checking in the response generation pipeline',
          created_at: new Date(Date.now() - 7200000).toISOString()
        }
      ];

      setMetrics(mockMetrics);
      setAlerts(mockAlerts);
    } catch (err) {
      setError('Failed to fetch quality metrics');
      console.error('Error fetching quality metrics:', err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'good': return 'success';
      case 'warning': return 'warning';
      case 'critical': return 'error';
      default: return 'default';
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'low': return 'info';
      case 'medium': return 'warning';
      case 'high': return 'error';
      case 'critical': return 'error';
      default: return 'default';
    }
  };

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'improving': return <TrendingUp color="success" />;
      case 'declining': return <TrendingDown color="error" />;
      default: return <TrendingUp color="action" />;
    }
  };

  const getProgressColor = (status: string) => {
    switch (status) {
      case 'good': return '#4caf50';
      case 'warning': return '#ff9800';
      case 'critical': return '#f44336';
      default: return '#9e9e9e';
    }
  };

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
      <Box mb={4} display="flex" justifyContent="space-between" alignItems="center">
        <Box>
          <Typography variant="h3" component="h1" gutterBottom>
            Quality Metrics
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Monitor RAG system quality and performance metrics
          </Typography>
        </Box>
        <Box>
          <IconButton onClick={fetchQualityMetrics} color="primary">
            <Refresh />
          </IconButton>
          <Button variant="outlined" startIcon={<Download />} sx={{ ml: 1 }}>
            Export Report
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Quality Alerts */}
      {alerts.length > 0 && (
        <Paper sx={{ p: 3, mb:4, bgcolor: 'warning.light' }}>
          <Typography variant="h5" mb={2} color="warning.dark">
            Quality Alerts
          </Typography>
          <List>
            {alerts.map((alert) => (
              <ListItem key={alert.id} alignItems="flex-start">
                <ListItemIcon>
                  <Warning color={getSeverityColor(alert.severity) as any} />
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Box display="flex" alignItems="center" gap={1}>
                      <Typography variant="h6">{alert.title}</Typography>
                      <Chip
                        label={alert.severity.toUpperCase()}
                        color={getSeverityColor(alert.severity) as any}
                        size="small"
                      />
                    </Box>
                  }
                  secondary={
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        {alert.description}
                      </Typography>
                      <Typography variant="body2" color="primary" sx={{ mt: 1 }}>
                        <strong>Recommendation:</strong> {alert.recommendation}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {new Date(alert.created_at).toLocaleString()}
                      </Typography>
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        </Paper>
      )}

      {/* Metrics Grid */}
      <Grid container spacing={3}>
        {metrics.map((metric) => (
          <Grid item xs={12} md={6} lg={4} key={metric.id}>
            <Card
              sx={{
                height: '100%',
                border: 2,
                borderColor: `${getStatusColor(metric.status)}.main`,
                bgcolor: `${getStatusColor(metric.status)}.light`
              }}
            >
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="h6" component="div">
                    {metric.name}
                  </Typography>
                  <Box display="flex" alignItems="center" gap={1}>
                    {getTrendIcon(metric.trend)}
                    <Chip
                      icon={metric.status === 'good' ? <CheckCircle /> :
                            metric.status === 'warning' ? <Warning /> : <Error />}
                      label={metric.status.toUpperCase()}
                      color={getStatusColor(metric.status) as any}
                      size="small"
                    />
                  </Box>
                </Box>

                <Typography variant="body2" color="text.secondary" paragraph>
                  {metric.description}
                </Typography>

                <Box mb={2}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="h4" color="primary">
                      {metric.current_value}{metric.unit}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Target: {metric.target_value}{metric.unit}
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={(metric.current_value / metric.target_value) * 100}
                    sx={{
                      height: 8,
                      borderRadius: 4,
                      bgcolor: 'grey.300',
                      '& .MuiLinearProgress-bar': {
                        bgcolor: getProgressColor(metric.status)
                      }
                    }}
                  />
                </Box>

                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="caption" color="text.secondary">
                    Threshold: {metric.threshold}{metric.unit}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {new Date(metric.last_updated).toLocaleTimeString()}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Summary Statistics */}
      <Paper sx={{ p: 3, mt: 4 }}>
        <Typography variant="h5" mb={3}>
          Quality Summary
        </Typography>
        <Grid container spacing={3}>
          <Grid item xs={12} sm={6} md={3}>
            <Box textAlign="center">
              <Typography variant="h3" color="success.main">
                {metrics.filter(m => m.status === 'good').length}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Good Metrics
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Box textAlign="center">
              <Typography variant="h3" color="warning.main">
                {metrics.filter(m => m.status === 'warning').length}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Warning Metrics
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Box textAlign="center">
              <Typography variant="h3" color="error.main">
                {metrics.filter(m => m.status === 'critical').length}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Critical Metrics
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Box textAlign="center">
              <Typography variant="h3" color="primary.main">
                {Math.round(metrics.reduce((acc, m) => acc + m.current_value, 0) / metrics.length)}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Average Score
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default QualityMetricsDashboardMUI;