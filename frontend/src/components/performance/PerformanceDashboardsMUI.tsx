/**
 * Performance Dashboards for the Knowledge Graph Analytics System
 *
 * Comprehensive real-time performance monitoring dashboards with MUI components
 * for visualizing system metrics, alerts, and performance trends.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  IconButton,
  Tooltip,
  Chip,
  Alert,
  LinearProgress,
  Tab,
  Tabs,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Avatar,
  Badge,
  Switch,
  FormControlLabel
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  CheckCircle as CheckCircleIcon,
  Timeline as TimelineIcon,
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  Storage as StorageIcon,
  NetworkCheck as NetworkIcon,
  Settings as SettingsIcon,
  Download as DownloadIcon,
  Fullscreen as FullscreenIcon,
  NotificationsActive as NotificationsIcon
} from '@mui/icons-material';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  RadialBarChart,
  RadialBar,
  ScatterChart,
  Scatter,
  HeatmapGrid
} from 'recharts';
import { useTheme } from '@mui/material/styles';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useDebounce } from '@/hooks/useDebounce';

// Types
interface PerformanceMetric {
  timestamp: string;
  name: string;
  value: number;
  unit: string;
  tags: Record<string, string>;
  source: string;
  severity: 'info' | 'warning' | 'critical';
}

interface Alert {
  id: string;
  name: string;
  description: string;
  severity: 'info' | 'warning' | 'critical';
  isActive: boolean;
  createdAt: string;
  lastTriggered?: string;
  triggerCount: number;
  metricName: string;
}

interface SystemSnapshot {
  timestamp: string;
  systemMetrics: Record<string, any>;
  applicationMetrics: Record<string, any>;
  databaseMetrics: Record<string, any>;
  networkMetrics: Record<string, any>;
  alerts: Alert[];
}

// Performance Metrics Card Component
interface MetricsCardProps {
  title: string;
  value: number;
  unit: string;
  icon: React.ReactNode;
  color: string;
  trend?: number;
  subtitle?: string;
  threshold?: { warning: number; critical: number };
}

const MetricsCard: React.FC<MetricsCardProps> = ({
  title,
  value,
  unit,
  icon,
  color,
  trend,
  subtitle,
  threshold
}) => {
  const theme = useTheme();

  const getStatusColor = useCallback(() => {
    if (!threshold) return color;
    if (value >= threshold.critical) return theme.palette.error.main;
    if (value >= threshold.warning) return theme.palette.warning.main;
    return color;
  }, [value, threshold, color, theme]);

  const getTrendIcon = useCallback(() => {
    if (!trend) return null;
    if (trend > 0) {
      return <Typography color="error" variant="caption">↑{Math.abs(trend).toFixed(1)}%</Typography>;
    }
    return <Typography color="success.main" variant="caption">↓{Math.abs(trend).toFixed(1)}%</Typography>;
  }, [trend]);

  return (
    <Card sx={{ height: '100%', position: 'relative' }}>
      <CardContent>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
          <Avatar sx={{ bgcolor: getStatusColor(), width: 48, height: 48 }}>
            {icon}
          </Avatar>
          {getTrendIcon()}
        </Box>

        <Typography variant="h4" component="div" fontWeight="bold" color={getStatusColor()}>
          {value.toFixed(1)}
          <Typography component="span" variant="h6" color="text.secondary">
            {unit}
          </Typography>
        </Typography>

        <Typography variant="body2" color="text.secondary" mt={1}>
          {title}
        </Typography>

        {subtitle && (
          <Typography variant="caption" color="text.secondary">
            {subtitle}
          </Typography>
        )}

        {threshold && (
          <Box mt={2}>
            <LinearProgress
              variant="determinate"
              value={Math.min(100, (value / threshold.critical) * 100)}
              color={getStatusColor() === theme.palette.error.main ? 'error' :
                     getStatusColor() === theme.palette.warning.main ? 'warning' : 'primary'}
            />
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

// Real-time Chart Component
interface RealTimeChartProps {
  data: any[];
  metricName: string;
  title: string;
  color: string;
  height?: number;
  showArea?: boolean;
}

const RealTimeChart: React.FC<RealTimeChartProps> = ({
  data,
  metricName,
  title,
  color,
  height = 300,
  showArea = false
}) => {
  const theme = useTheme();
  const [timeRange, setTimeRange] = useState('1h');

  const filteredData = useMemo(() => {
    const now = new Date();
    const ranges = {
      '5m': 5 * 60 * 1000,
      '15m': 15 * 60 * 1000,
      '1h': 60 * 60 * 1000,
      '6h': 6 * 60 * 60 * 1000,
      '24h': 24 * 60 * 60 * 1000
    };

    const cutoff = now.getTime() - ranges[timeRange as keyof typeof ranges];
    return data.filter(d => new Date(d.timestamp).getTime() > cutoff);
  }, [data, timeRange]);

  const ChartComponent = showArea ? AreaChart : LineChart;
  const DataComponent = showArea ? Area : Line;

  return (
    <Card>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6">{title}</Typography>
          <FormControl size="small" sx={{ minWidth: 80 }}>
            <Select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
            >
              <MenuItem value="5m">5m</MenuItem>
              <MenuItem value="15m">15m</MenuItem>
              <MenuItem value="1h">1h</MenuItem>
              <MenuItem value="6h">6h</MenuItem>
              <MenuItem value="24h">24h</MenuItem>
            </Select>
          </FormControl>
        </Box>

        <ResponsiveContainer width="100%" height={height}>
          <ChartComponent data={filteredData}>
            <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
            <XAxis
              dataKey="timestamp"
              tickFormatter={(value) => new Date(value).toLocaleTimeString()}
              stroke={theme.palette.text.secondary}
            />
            <YAxis stroke={theme.palette.text.secondary} />
            <RechartsTooltip
              labelFormatter={(value) => new Date(value).toLocaleString()}
              contentStyle={{
                backgroundColor: theme.palette.background.paper,
                border: `1px solid ${theme.palette.divider}`,
                borderRadius: theme.shape.borderRadius
              }}
            />
            <DataComponent
              type="monotone"
              dataKey={metricName}
              stroke={color}
              strokeWidth={2}
              fill={color}
              fillOpacity={0.3}
              dot={false}
            />
          </ChartComponent>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

// Alert Panel Component
interface AlertPanelProps {
  alerts: Alert[];
  onDismiss: (alertId: string) => void;
  onAcknowledge: (alertId: string) => void;
}

const AlertPanel: React.FC<AlertPanelProps> = ({
  alerts,
  onDismiss,
  onAcknowledge
}) => {
  const theme = useTheme();

  const getAlertIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <ErrorIcon sx={{ color: theme.palette.error.main }} />;
      case 'warning':
        return <WarningIcon sx={{ color: theme.palette.warning.main }} />;
      default:
        return <InfoIcon sx={{ color: theme.palette.info.main }} />;
    }
  };

  const getAlertColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return theme.palette.error.main;
      case 'warning':
        return theme.palette.warning.main;
      default:
        return theme.palette.info.main;
    }
  };

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" mb={2}>Active Alerts</Typography>

        {alerts.length === 0 ? (
          <Box textAlign="center" py={4}>
            <CheckCircleIcon sx={{ fontSize: 48, color: theme.palette.success.main }} />
            <Typography variant="body2" color="text.secondary" mt={1}>
              No active alerts
            </Typography>
          </Box>
        ) : (
          <List>
            {alerts.map((alert) => (
              <React.Fragment key={alert.id}>
                <ListItem>
                  <ListItemIcon>
                    {getAlertIcon(alert.severity)}
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Box display="flex" alignItems="center" gap={1}>
                        <Typography variant="subtitle2">{alert.name}</Typography>
                        <Chip
                          label={alert.severity.toUpperCase()}
                          size="small"
                          sx={{
                            backgroundColor: getAlertColor(alert.severity),
                            color: 'white'
                          }}
                        />
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          {alert.description}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Triggered {alert.triggerCount} times
                          {alert.lastTriggered && (
                            <> • Last: {new Date(alert.lastTriggered).toLocaleString()}</>
                          )}
                        </Typography>
                      </Box>
                    }
                  />
                  <Box>
                    <IconButton
                      size="small"
                      onClick={() => onAcknowledge(alert.id)}
                      title="Acknowledge"
                    >
                      <CheckCircleIcon />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => onDismiss(alert.id)}
                      title="Dismiss"
                    >
                      ×
                    </IconButton>
                  </Box>
                </ListItem>
                <Divider />
              </React.Fragment>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
};

// Main Performance Dashboard
const PerformanceDashboard: React.FC = () => {
  const theme = useTheme();
  const [currentTab, setCurrentTab] = useState(0);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(5000);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const [latestSnapshot, setLatestSnapshot] = useState<SystemSnapshot | null>(null);
  const [historicalData, setHistoricalData] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'error'>('disconnected');

  // WebSocket connection for real-time updates
  const { lastMessage, sendMessage, readyState } = useWebSocket('ws://localhost:8000/ws/performance');

  useEffect(() => {
    setConnectionStatus(readyState === WebSocket.OPEN ? 'connected' : readyState === WebSocket.CLOSED ? 'disconnected' : 'error');
  }, [readyState]);

  useEffect(() => {
    if (lastMessage) {
      try {
        const data = JSON.parse(lastMessage.data);

        if (data.type === 'snapshot') {
          setLatestSnapshot(data.data);
          setHistoricalData(prev => [...prev.slice(-100), data.data]);
        } else if (data.type === 'alert') {
          setAlerts(prev => {
            const existing = prev.findIndex(a => a.id === data.data.id);
            if (existing >= 0) {
              const updated = [...prev];
              updated[existing] = data.data;
              return updated;
            }
            return [...prev, data.data];
          });
        } else if (data.type === 'alert_cleared') {
          setAlerts(prev => prev.filter(a => a.id !== data.data.id));
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    }
  }, [lastMessage]);

  // Manual refresh
  const handleRefresh = useCallback(() => {
    sendMessage(JSON.stringify({ type: 'request_latest' }));
  }, [sendMessage]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      handleRefresh();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, handleRefresh]);

  // Handle alert actions
  const handleAcknowledgeAlert = useCallback((alertId: string) => {
    sendMessage(JSON.stringify({ type: 'acknowledge_alert', alertId }));
  }, [sendMessage]);

  const handleDismissAlert = useCallback((alertId: string) => {
    sendMessage(JSON.stringify({ type: 'dismiss_alert', alertId }));
    setAlerts(prev => prev.filter(a => a.id !== alertId));
  }, [sendMessage]);

  // Export metrics
  const handleExportMetrics = useCallback(() => {
    const data = {
      timestamp: new Date().toISOString(),
      snapshot: latestSnapshot,
      alerts,
      historicalData: historicalData.slice(-100)
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `performance-metrics-${new Date().toISOString()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [latestSnapshot, alerts, historicalData]);

  // Prepare chart data
  const cpuData = useMemo(() => {
    return historicalData.map(snapshot => ({
      timestamp: snapshot.timestamp,
      value: snapshot.systemMetrics?.cpu_percent || 0
    }));
  }, [historicalData]);

  const memoryData = useMemo(() => {
    return historicalData.map(snapshot => ({
      timestamp: snapshot.timestamp,
      value: snapshot.systemMetrics?.memory_percent || 0
    }));
  }, [historicalData]);

  const responseTimeData = useMemo(() => {
    return historicalData.map(snapshot => ({
      timestamp: snapshot.timestamp,
      value: snapshot.applicationMetrics?.avg_response_time || 0
    }));
  }, [historicalData]);

  const throughputData = useMemo(() => {
    return historicalData.map(snapshot => ({
      timestamp: snapshot.timestamp,
      value: snapshot.applicationMetrics?.requests_per_second || 0
    }));
  }, [historicalData]);

  if (!latestSnapshot) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CardContent>
          <Typography variant="h6" color="text.secondary" textAlign="center">
            {connectionStatus === 'connected' ? 'Loading performance data...' : 'Connecting to performance monitor...'}
          </Typography>
          <LinearProgress sx={{ mt: 2, width: 300 }} />
        </CardContent>
      </Box>
    );
  }

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Performance Dashboard
        </Typography>

        <Box display="flex" alignItems="center" gap={2}>
          <Badge
            color={connectionStatus === 'connected' ? 'success' : 'error'}
            variant="dot"
          >
            <Chip
              label={connectionStatus}
              size="small"
              color={connectionStatus === 'connected' ? 'success' : 'error'}
            />
          </Badge>

          <FormControlLabel
            control={
              <Switch
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
              />
            }
            label="Auto Refresh"
          />

          <Select
            size="small"
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            disabled={!autoRefresh}
          >
            <MenuItem value={1000}>1s</MenuItem>
            <MenuItem value={5000}>5s</MenuItem>
            <MenuItem value={10000}>10s</MenuItem>
            <MenuItem value={30000}>30s</MenuItem>
          </Select>

          <Tooltip title="Refresh">
            <IconButton onClick={handleRefresh}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>

          <Tooltip title="Export Metrics">
            <IconButton onClick={handleExportMetrics}>
              <DownloadIcon />
            </IconButton>
          </Tooltip>

          <Tooltip title="Fullscreen">
            <IconButton onClick={() => setIsFullscreen(!isFullscreen)}>
              <FullscreenIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Alert Banner */}
      {alerts.length > 0 && (
        <Alert
          severity={alerts.some(a => a.severity === 'critical') ? 'error' : 'warning'}
          action={
            <IconButton
              size="small"
              color="inherit"
              onClick={() => setCurrentTab(3)} // Switch to alerts tab
            >
              <NotificationsIcon />
            </IconButton>
          }
          sx={{ mb: 3 }}
        >
          {alerts.length} active alert{alerts.length > 1 ? 's' : ''} - {alerts.filter(a => a.severity === 'critical').length} critical
        </Alert>
      )}

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={currentTab}
          onChange={(e, newValue) => setCurrentTab(newValue)}
          variant="scrollable"
          scrollButtons="auto"
        >
          <Tab label="Overview" icon={<SpeedIcon />} />
          <Tab label="System Metrics" icon={<MemoryIcon />} />
          <Tab label="Application Metrics" icon={<TimelineIcon />} />
          <Tab label="Alerts" icon={<WarningIcon />} badgeContent={alerts.length} />
          <Tab label="Database" icon={<StorageIcon />} />
          <Tab label="Network" icon={<NetworkIcon />} />
        </Tabs>
      </Paper>

      {/* Tab Content */}
      {currentTab === 0 && (
        <Grid container spacing={3}>
          {/* Overview Metrics Cards */}
          <Grid item xs={12} md={3}>
            <MetricsCard
              title="CPU Usage"
              value={latestSnapshot.systemMetrics?.cpu_percent || 0}
              unit="%"
              icon={<SpeedIcon />}
              color={theme.palette.primary.main}
              threshold={{ warning: 70, critical: 90 }}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <MetricsCard
              title="Memory Usage"
              value={latestSnapshot.systemMetrics?.memory_percent || 0}
              unit="%"
              icon={<MemoryIcon />}
              color={theme.palette.secondary.main}
              threshold={{ warning: 75, critical: 90 }}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <MetricsCard
              title="Response Time"
              value={latestSnapshot.applicationMetrics?.avg_response_time || 0}
              unit="ms"
              icon={<TimelineIcon />}
              color={theme.palette.info.main}
              threshold={{ warning: 500, critical: 1000 }}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <MetricsCard
              title="Throughput"
              value={latestSnapshot.applicationMetrics?.requests_per_second || 0}
              unit="req/s"
              icon={<NetworkIcon />}
              color={theme.palette.success.main}
            />
          </Grid>

          {/* Charts */}
          <Grid item xs={12} md={6}>
            <RealTimeChart
              data={cpuData}
              metricName="value"
              title="CPU Usage"
              color={theme.palette.primary.main}
              showArea
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <RealTimeChart
              data={memoryData}
              metricName="value"
              title="Memory Usage"
              color={theme.palette.secondary.main}
              showArea
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <RealTimeChart
              data={responseTimeData}
              metricName="value"
              title="Response Time"
              color={theme.palette.info.main}
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <RealTimeChart
              data={throughputData}
              metricName="value"
              title="Request Throughput"
              color={theme.palette.success.main}
              showArea
            />
          </Grid>
        </Grid>
      )}

      {currentTab === 1 && (
        <Grid container spacing={3}>
          {/* Detailed System Metrics */}
          <Grid item xs={12} md={4}>
            <MetricsCard
              title="Disk Usage"
              value={latestSnapshot.systemMetrics?.disk_percent || 0}
              unit="%"
              icon={<StorageIcon />}
              color={theme.palette.warning.main}
              threshold={{ warning: 80, critical: 95 }}
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <MetricsCard
              title="Process Count"
              value={latestSnapshot.systemMetrics?.process_num_threads || 0}
              unit="threads"
              icon={<SettingsIcon />}
              color={theme.palette.info.main}
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <MetricsCard
              title="Swap Usage"
              value={latestSnapshot.systemMetrics?.swap_percent || 0}
              unit="%"
              icon={<MemoryIcon />}
              color={theme.palette.error.main}
              threshold={{ warning: 50, critical: 80 }}
            />
          </Grid>

          {/* Resource Usage Chart */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" mb={2}>Resource Usage Overview</Typography>
                <ResponsiveContainer width="100%" height={400}>
                  <RadialBarChart
                    cx="50%"
                    cy="50%"
                    innerRadius="10%"
                    outerRadius="80%"
                    data={[
                      {
                        name: 'CPU',
                        value: latestSnapshot.systemMetrics?.cpu_percent || 0,
                        fill: theme.palette.primary.main
                      },
                      {
                        name: 'Memory',
                        value: latestSnapshot.systemMetrics?.memory_percent || 0,
                        fill: theme.palette.secondary.main
                      },
                      {
                        name: 'Disk',
                        value: latestSnapshot.systemMetrics?.disk_percent || 0,
                        fill: theme.palette.warning.main
                      }
                    ]}
                  >
                    <RadialBar
                      dataKey="value"
                      cornerRadius={10}
                      fill="#8884d8"
                    />
                    <RechartsTooltip />
                  </RadialBarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {currentTab === 2 && (
        <Grid container spacing={3}>
          {/* Application Metrics */}
          <Grid item xs={12} md={3}>
            <MetricsCard
              title="Active Connections"
              value={latestSnapshot.applicationMetrics?.active_connections || 0}
              unit="conn"
              icon={<NetworkIcon />}
              color={theme.palette.primary.main}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <MetricsCard
              title="Cache Hit Ratio"
              value={(latestSnapshot.applicationMetrics?.cache_hit_ratio || 0) * 100}
              unit="%"
              icon={<SpeedIcon />}
              color={theme.palette.success.main}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <MetricsCard
              title="Error Rate"
              value={(latestSnapshot.applicationMetrics?.error_rate || 0) * 100}
              unit="%"
              icon={<ErrorIcon />}
              color={theme.palette.error.main}
              threshold={{ warning: 1, critical: 5 }}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <MetricsCard
              title="Queue Size"
              value={latestSnapshot.applicationMetrics?.queue_size || 0}
              unit="items"
              icon={<TimelineIcon />}
              color={theme.palette.info.main}
            />
          </Grid>

          {/* Performance Charts */}
          <Grid item xs={12}>
            <AlertPanel
              alerts={alerts.filter(a => a.metricName.startsWith('app.'))}
              onDismiss={handleDismissAlert}
              onAcknowledge={handleAcknowledgeAlert}
            />
          </Grid>
        </Grid>
      )}

      {currentTab === 3 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={8}>
            <AlertPanel
              alerts={alerts}
              onDismiss={handleDismissAlert}
              onAcknowledge={handleAcknowledgeAlert}
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" mb={2}>Alert Statistics</Typography>
                <Box mb={2}>
                  <Typography variant="body2" color="text.secondary">
                    Total Active Alerts
                  </Typography>
                  <Typography variant="h4">
                    {alerts.length}
                  </Typography>
                </Box>
                <Box mb={2}>
                  <Typography variant="body2" color="text.secondary">
                    Critical Alerts
                  </Typography>
                  <Typography variant="h6" color="error">
                    {alerts.filter(a => a.severity === 'critical').length}
                  </Typography>
                </Box>
                <Box mb={2}>
                  <Typography variant="body2" color="text.secondary">
                    Warning Alerts
                  </Typography>
                  <Typography variant="h6" color="warning.main">
                    {alerts.filter(a => a.severity === 'warning').length}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="body2" color="text.secondary">
                    Info Alerts
                  </Typography>
                  <Typography variant="h6" color="info.main">
                    {alerts.filter(a => a.severity === 'info').length}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {currentTab === 4 && (
        <Grid container spacing={3}>
          {/* Database Metrics */}
          <Grid item xs={12} md={3}>
            <MetricsCard
              title="Active Connections"
              value={latestSnapshot.databaseMetrics?.connections_active || 0}
              unit="conn"
              icon={<StorageIcon />}
              color={theme.palette.primary.main}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <MetricsCard
              title="Query Time (P95)"
              value={latestSnapshot.databaseMetrics?.avg_query_time || 0}
              unit="ms"
              icon={<TimelineIcon />}
              color={theme.palette.warning.main}
              threshold={{ warning: 100, critical: 500 }}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <MetricsCard
              title="Cache Hit Ratio"
              value={(latestSnapshot.databaseMetrics?.cache_hit_ratio || 0) * 100}
              unit="%"
              icon={<SpeedIcon />}
              color={theme.palette.success.main}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <MetricsCard
              title="Slow Queries"
              value={latestSnapshot.databaseMetrics?.slow_queries || 0}
              unit="queries"
              icon={<WarningIcon />}
              color={theme.palette.error.main}
            />
          </Grid>
        </Grid>
      )}

      {currentTab === 5 && (
        <Grid container spacing={3}>
          {/* Network Metrics */}
          <Grid item xs={12} md={3}>
            <MetricsCard
              title="Bytes Sent"
              value={(latestSnapshot.networkMetrics?.bytes_sent || 0) / 1024 / 1024}
              unit="MB"
              icon={<NetworkIcon />}
              color={theme.palette.primary.main}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <MetricsCard
              title="Bytes Received"
              value={(latestSnapshot.networkMetrics?.bytes_recv || 0) / 1024 / 1024}
              unit="MB"
              icon={<NetworkIcon />}
              color={theme.palette.secondary.main}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <MetricsCard
              title="Active Connections"
              value={latestSnapshot.networkMetrics?.connections || 0}
              unit="conn"
              icon={<NetworkIcon />}
              color={theme.palette.info.main}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <MetricsCard
              title="Packet Loss"
              value={latestSnapshot.networkMetrics?.packet_loss || 0}
              unit="%"
              icon={<WarningIcon />}
              color={theme.palette.error.main}
            />
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default PerformanceDashboard;