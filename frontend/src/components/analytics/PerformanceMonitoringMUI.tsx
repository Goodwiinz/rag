import React, { useState, useEffect } from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Paper,
  LinearProgress,
  Chip,
  Button,
  IconButton,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Alert,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Switch,
  FormControlLabel,
  Divider
} from '@mui/material';
import {
  Speed,
  Memory,
  Storage,
  NetworkWifi,
  Warning,
  Error,
  CheckCircle,
  Refresh,
  Download,
  Timeline,
  Dashboard,
  Cloud,
  Dns,
  Storage as StorageIcon
} from '@mui/icons-material';

interface SystemMetrics {
  timestamp: string;
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  network_io: {
    bytes_in: number;
    bytes_out: number;
  };
  response_time: number;
  request_rate: number;
  error_rate: number;
  active_connections: number;
}

interface ServiceStatus {
  name: string;
  status: 'healthy' | 'warning' | 'critical' | 'unknown';
  response_time: number;
  last_check: string;
  uptime: number;
  error_count: number;
}

interface PerformanceAlert {
  id: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  type: 'performance' | 'availability' | 'capacity';
  title: string;
  description: string;
  service: string;
  timestamp: string;
  resolved: boolean;
}

interface ResourceUsage {
  resource: string;
  current: number;
  max: number;
  threshold: number;
  unit: string;
  trend: 'increasing' | 'decreasing' | 'stable';
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`performance-tabpanel-${index}`}
      aria-labelledby={`performance-tab-${index}`}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
};

const PerformanceMonitoringMUI: React.FC = () => {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [alerts, setAlerts] = useState<PerformanceAlert[]>([]);
  const [resourceUsage, setResourceUsage] = useState<ResourceUsage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tabValue, setTabValue] = useState(0);
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    fetchPerformanceData();
    let interval: NodeJS.Timeout;

    if (autoRefresh) {
      interval = setInterval(fetchPerformanceData, 10000); // Update every 10 seconds
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  const fetchPerformanceData = async () => {
    try {
      setError(null);

      // Mock data for demonstration
      const mockMetrics: SystemMetrics = {
        timestamp: new Date().toISOString(),
        cpu_usage: 45.2,
        memory_usage: 67.8,
        disk_usage: 34.1,
        network_io: {
          bytes_in: 1024000,
          bytes_out: 2048000
        },
        response_time: 245,
        request_rate: 125.5,
        error_rate: 1.2,
        active_connections: 89
      };

      const mockServices: ServiceStatus[] = [
        {
          name: 'Backend API',
          status: 'healthy',
          response_time: 245,
          last_check: new Date().toISOString(),
          uptime: 99.9,
          error_count: 0
        },
        {
          name: 'Database',
          status: 'healthy',
          response_time: 12,
          last_check: new Date().toISOString(),
          uptime: 99.95,
          error_count: 0
        },
        {
          name: 'Vector Store',
          status: 'warning',
          response_time: 450,
          last_check: new Date().toISOString(),
          uptime: 97.2,
          error_count: 3
        },
        {
          name: 'Knowledge Graph',
          status: 'healthy',
          response_time: 89,
          last_check: new Date().toISOString(),
          uptime: 99.8,
          error_count: 0
        },
        {
          name: 'Redis Cache',
          status: 'healthy',
          response_time: 5,
          last_check: new Date().toISOString(),
          uptime: 100,
          error_count: 0
        },
        {
          name: 'Processing Queue',
          status: 'healthy',
          response_time: 156,
          last_check: new Date().toISOString(),
          uptime: 98.5,
          error_count: 1
        }
      ];

      const mockAlerts: PerformanceAlert[] = [
        {
          id: '1',
          severity: 'medium',
          type: 'performance',
          title: 'High Response Time',
          description: 'Vector store response time is above threshold',
          service: 'Vector Store',
          timestamp: new Date(Date.now() - 300000).toISOString(),
          resolved: false
        },
        {
          id: '2',
          severity: 'low',
          type: 'capacity',
          title: 'Memory Usage High',
          description: 'Memory usage approaching 70% threshold',
          service: 'System',
          timestamp: new Date(Date.now() - 600000).toISOString(),
          resolved: false
        }
      ];

      const mockResourceUsage: ResourceUsage[] = [
        {
          resource: 'CPU',
          current: 45.2,
          max: 100,
          threshold: 80,
          unit: '%',
          trend: 'stable'
        },
        {
          resource: 'Memory',
          current: 67.8,
          max: 100,
          threshold: 85,
          unit: '%',
          trend: 'increasing'
        },
        {
          resource: 'Disk',
          current: 34.1,
          max: 100,
          threshold: 90,
          unit: '%',
          trend: 'stable'
        },
        {
          resource: 'Network',
          current: 3.2,
          max: 10,
          threshold: 8,
          unit: 'Gbps',
          trend: 'stable'
        }
      ];

      setMetrics(mockMetrics);
      setServices(mockServices);
      setAlerts(mockAlerts);
      setResourceUsage(mockResourceUsage);
    } catch (err) {
      setError('Failed to fetch performance data');
      console.error('Error fetching performance data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'success';
      case 'warning': return 'warning';
      case 'critical': return 'error';
      default: return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return <CheckCircle color="success" />;
      case 'warning': return <Warning color="warning" />;
      case 'critical': return <Error color="error" />;
      default: return <Warning color="disabled" />;
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'low': return 'info';
      case 'medium': return 'warning';
      case 'high': return 'warning';
      case 'critical': return 'error';
      default: return 'default';
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
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
            Performance Monitoring
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Monitor system performance, service health, and resource utilization
          </Typography>
        </Box>
        <Box display="flex" alignItems="center" gap={2}>
          <FormControlLabel
            control={
              <Switch
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                color="primary"
              />
            }
            label="Auto Refresh"
          />
          <IconButton onClick={fetchPerformanceData} color="primary">
            <Refresh />
          </IconButton>
          <Button variant="outlined" startIcon={<Download />}>
            Export Metrics
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Active Alerts */}
      {alerts.filter(a => !a.resolved).length > 0 && (
        <Paper sx={{ p: 3, mb: 3, bgcolor: 'error.light' }}>
          <Typography variant="h5" mb={2} color="error.dark">
            Active Alerts
          </Typography>
          <List>
            {alerts.filter(a => !a.resolved).map((alert) => (
              <ListItem key={alert.id} alignItems="flex-start">
                <ListItemIcon>
                  <Error color={getSeverityColor(alert.severity) as any} />
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
                      <Typography variant="caption" color="text.secondary">
                        Service: {alert.service} | {new Date(alert.timestamp).toLocaleString()}
                      </Typography>
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        </Paper>
      )}

      {/* Overview Cards */}
      {metrics && (
        <Grid container spacing={3} mb={4}>
          <Grid size={{ xs: 12, sm: 6 }} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="h6">CPU Usage</Typography>
                  <Speed color="info" />
                </Box>
                <Typography variant="h4" component="div" gutterBottom>
                  {metrics.cpu_usage.toFixed(1)}%
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={metrics.cpu_usage}
                  color={metrics.cpu_usage > 80 ? 'error' : 'primary'}
                />
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="h6">Memory Usage</Typography>
                  <Memory color="primary" />
                </Box>
                <Typography variant="h4" component="div" gutterBottom>
                  {metrics.memory_usage.toFixed(1)}%
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={metrics.memory_usage}
                  color={metrics.memory_usage > 85 ? 'error' : 'primary'}
                />
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="h6">Response Time</Typography>
                  <Timeline color="success" />
                </Box>
                <Typography variant="h4" component="div" gutterBottom>
                  {metrics.response_time}ms
                </Typography>
                <Typography variant="body2" color={metrics.response_time > 500 ? 'error' : 'success'}>
                  {metrics.response_time > 500 ? 'Slow' : 'Good'}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }} md={3}>
            <Card>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="h6">Error Rate</Typography>
                  <Error color={metrics.error_rate > 5 ? 'error' : 'success'} />
                </Box>
                <Typography variant="h4" component="div" gutterBottom>
                  {metrics.error_rate.toFixed(1)}%
                </Typography>
                <Typography variant="body2" color={metrics.error_rate > 5 ? 'error' : 'success'}>
                  {metrics.error_rate > 5 ? 'High' : 'Normal'}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          aria-label="Performance monitoring tabs"
        >
          <Tab label="Services" icon={<Dashboard />} />
          <Tab label="Resources" icon={<StorageIcon />} />
          <Tab label="Network" icon={<NetworkWifi />} />
          <Tab label="Alerts" icon={<Warning />} />
        </Tabs>
      </Paper>

      {/* Services Tab */}
      <TabPanel value={tabValue} index={0}>
        <Paper sx={{ p: 3 }}>
          <Typography variant="h5" mb={3}>
            Service Status
          </Typography>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Service</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Response Time</TableCell>
                  <TableCell>Uptime</TableCell>
                  <TableCell>Errors</TableCell>
                  <TableCell>Last Check</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {services.map((service) => (
                  <TableRow key={service.name}>
                    <TableCell>
                      <Box display="flex" alignItems="center" gap={1}>
                        {service.name.includes('API') ? <Dns fontSize="small" /> :
                         service.name.includes('Database') ? <Storage fontSize="small" /> :
                         service.name.includes('Redis') ? <Memory fontSize="small" /> :
                         <Cloud fontSize="small" />}
                        {service.name}
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Box display="flex" alignItems="center" gap={1}>
                        {getStatusIcon(service.status)}
                        <Chip
                          label={service.status.toUpperCase()}
                          color={getStatusColor(service.status) as any}
                          size="small"
                        />
                      </Box>
                    </TableCell>
                    <TableCell>{service.response_time}ms</TableCell>
                    <TableCell>{service.uptime.toFixed(2)}%</TableCell>
                    <TableCell>{service.error_count}</TableCell>
                    <TableCell>
                      {new Date(service.last_check).toLocaleTimeString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      </TabPanel>

      {/* Resources Tab */}
      <TabPanel value={tabValue} index={1}>
        <Grid container spacing={3}>
          {resourceUsage.map((resource) => (
            <Grid size={{ xs: 12, md: 6 }} key={resource.resource}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h6" mb={2}>
                  {resource.resource} Usage
                </Typography>
                <Box mb={2}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="h4" color="primary">
                      {resource.current}{resource.unit}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Threshold: {resource.threshold}{resource.unit}
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={(resource.current / resource.max) * 100}
                    color={resource.current > resource.threshold ? 'error' : 'primary'}
                  />
                </Box>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="body2" color="text.secondary">
                    Max: {resource.max}{resource.unit}
                  </Typography>
                  <Chip
                    label={resource.trend}
                    color={resource.trend === 'increasing' ? 'warning' : 'success'}
                    size="small"
                  />
                </Box>
              </Paper>
            </Grid>
          ))}
        </Grid>
      </TabPanel>

      {/* Network Tab */}
      <TabPanel value={tabValue} index={2}>
        {metrics && (
          <Grid container spacing={3}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h5" mb={3}>
                  Network Traffic
                </Typography>
                <List>
                  <ListItem>
                    <ListItemText
                      primary="Incoming Traffic"
                      secondary={formatBytes(metrics.network_io.bytes_in)}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Outgoing Traffic"
                      secondary={formatBytes(metrics.network_io.bytes_out)}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Active Connections"
                      secondary={metrics.active_connections}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Request Rate"
                      secondary={`${metrics.request_rate.toFixed(1)} req/s`}
                    />
                  </ListItem>
                </List>
              </Paper>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h5" mb={3}>
                  Performance Summary
                </Typography>
                <List>
                  <ListItem>
                    <ListItemText
                      primary="Average Response Time"
                      secondary={`${metrics.response_time}ms`}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Error Rate"
                      secondary={`${metrics.error_rate.toFixed(1)}%`}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="System Uptime"
                      secondary="99.8%"
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Last Updated"
                      secondary={new Date(metrics.timestamp).toLocaleString()}
                    />
                  </ListItem>
                </List>
              </Paper>
            </Grid>
          </Grid>
        )}
      </TabPanel>

      {/* Alerts Tab */}
      <TabPanel value={tabValue} index={3}>
        <Paper sx={{ p: 3 }}>
          <Typography variant="h5" mb={3}>
            All Alerts
          </Typography>
          <List>
            {alerts.map((alert) => (
              <React.Fragment key={alert.id}>
                <ListItem alignItems="flex-start">
                  <ListItemIcon>
                    {alert.resolved ? (
                      <CheckCircle color="success" />
                    ) : (
                      <Error color={getSeverityColor(alert.severity) as any} />
                    )}
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
                        <Chip
                          label={alert.type.toUpperCase()}
                          variant="outlined"
                          size="small"
                        />
                        {alert.resolved && (
                          <Chip
                            label="RESOLVED"
                            color="success"
                            size="small"
                          />
                        )}
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          {alert.description}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Service: {alert.service} | {new Date(alert.timestamp).toLocaleString()}
                        </Typography>
                      </Box>
                    }
                  />
                </ListItem>
                <Divider />
              </React.Fragment>
            ))}
          </List>
        </Paper>
      </TabPanel>
    </Box>
  );
};

export default PerformanceMonitoringMUI;