import React from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Paper,
  LinearProgress,
  useTheme
} from '@mui/material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area
} from 'recharts';

interface ChartData {
  name: string;
  value: number;
  timestamp?: string;
  category?: string;
}

interface AnalyticsChartsMUIProps {
  data?: {
    qualityMetrics?: ChartData[];
    userBehavior?: ChartData[];
    performanceMetrics?: ChartData[];
    searchVolume?: ChartData[];
    responseTime?: ChartData[];
  };
  loading?: boolean;
}

const AnalyticsChartsMUI: React.FC<AnalyticsChartsMUIProps> = ({
  data,
  loading = false
}) => {
  const theme = useTheme();

  // Mock data for demonstration
  const mockQualityData: ChartData[] = [
    { name: 'Mon', value: 92, timestamp: '2025-10-06' },
    { name: 'Tue', value: 94, timestamp: '2025-10-07' },
    { name: 'Wed', value: 91, timestamp: '2025-10-08' },
    { name: 'Thu', value: 95, timestamp: '2025-10-09' },
    { name: 'Fri', value: 93, timestamp: '2025-10-10' },
    { name: 'Sat', value: 96, timestamp: '2025-10-11' },
    { name: 'Sun', value: 94, timestamp: '2025-10-12' }
  ];

  const mockUserBehaviorData: ChartData[] = [
    { name: 'Week 1', value: 1234, category: 'Sessions' },
    { name: 'Week 2', value: 1456, category: 'Sessions' },
    { name: 'Week 3', value: 1678, category: 'Sessions' },
    { name: 'Week 4', value: 1890, category: 'Sessions' }
  ];

  const mockPerformanceData: ChartData[] = [
    { name: 'CPU', value: 45, category: 'System' },
    { name: 'Memory', value: 68, category: 'System' },
    { name: 'Disk', value: 34, category: 'System' },
    { name: 'Network', value: 25, category: 'System' }
  ];

  const mockSearchVolumeData: ChartData[] = [
    { name: '00:00', value: 12 },
    { name: '04:00', value: 8 },
    { name: '08:00', value: 45 },
    { name: '12:00', value: 78 },
    { name: '16:00', value: 92 },
    { name: '20:00', value: 34 },
    { name: '23:59', value: 18 }
  ];

  const mockResponseTimeData: ChartData[] = [
    { name: 'Jan', value: 320, timestamp: '2025-01' },
    { name: 'Feb', value: 280, timestamp: '2025-02' },
    { name: 'Mar', value: 250, timestamp: '2025-03' },
    { name: 'Apr', value: 220, timestamp: '2025-04' },
    { name: 'May', value: 195, timestamp: '2025-05' },
    { name: 'Jun', value: 180, timestamp: '2025-06' }
  ];

  const pieData = [
    { name: 'Documents', value: 45, color: theme.palette.primary.main },
    { name: 'Images', value: 20, color: theme.palette.secondary.main },
    { name: 'Audio', value: 15, color: theme.palette.success.main },
    { name: 'Video', value: 20, color: theme.palette.warning.main }
  ];

  const qualityData = data?.qualityMetrics || mockQualityData;
  const userBehaviorData = data?.userBehavior || mockUserBehaviorData;
  const performanceData = data?.performanceMetrics || mockPerformanceData;
  const searchVolumeData = data?.searchVolume || mockSearchVolumeData;
  const responseTimeData = data?.responseTime || mockResponseTimeData;

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="400px">
        <LinearProgress sx={{ width: '50%' }} />
      </Box>
    );
  }

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      <Typography variant="h4" component="h2" gutterBottom>
        Analytics Overview
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        Real-time visualization of system performance and user behavior metrics
      </Typography>

      <Grid container spacing={3}>
        {/* Quality Metrics Trend */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Quality Metrics Trend
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Search relevance and accuracy over time
              </Typography>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={qualityData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke={theme.palette.primary.main}
                    strokeWidth={2}
                    dot={{ fill: theme.palette.primary.main }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* User Behavior */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                User Engagement
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Weekly user sessions and activity
              </Typography>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={userBehaviorData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="value" fill={theme.palette.secondary.main} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* System Performance */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Resource Usage
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Current resource utilization across services
              </Typography>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={performanceData} layout="horizontal">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis dataKey="name" type="category" />
                  <Tooltip />
                  <Bar dataKey="value" fill={theme.palette.success.main} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Search Volume Pattern */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Daily Search Pattern
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Search volume distribution throughout the day
              </Typography>
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={searchVolumeData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke={theme.palette.warning.main}
                    fill={theme.palette.warning.main}
                    fillOpacity={0.3}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Response Time Improvement */}
        <Grid size={{ xs: 12, md: 8 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Response Time Trend
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                System response time improvements over months
              </Typography>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={responseTimeData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke={theme.palette.info.main}
                    strokeWidth={2}
                    dot={{ fill: theme.palette.info.main }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Content Distribution */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Content Distribution
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                File types in the knowledge base
              </Typography>
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <Box display="flex" flexWrap="wrap" gap={1} mt={2}>
                {pieData.map((item) => (
                  <Box
                    key={item.name}
                    display="flex"
                    alignItems="center"
                    gap={0.5}
                    sx={{ mr: 1 }}
                  >
                    <Box
                      sx={{
                        width: 12,
                        height: 12,
                        bgcolor: item.color,
                        borderRadius: '50%'
                      }}
                    />
                    <Typography variant="caption">
                      {item.name} ({item.value}%)
                    </Typography>
                  </Box>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default AnalyticsChartsMUI;