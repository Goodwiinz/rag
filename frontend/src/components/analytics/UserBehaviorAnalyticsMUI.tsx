import React, { useState, useEffect } from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Button,
  IconButton,
  CircularProgress,
  LinearProgress,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Tabs,
  Tab
} from '@mui/material';
import {
  People,
  Search,
  ThumbUp,
  ThumbDown,
  TrendingUp,
  TrendingDown,
  AccessTime,
  Visibility,
  Refresh,
  Download,
  Person,
  Group,
  Timeline
} from '@mui/icons-material';

interface UserBehaviorStats {
  total_users: number;
  active_users_today: number;
  active_users_week: number;
  active_users_month: number;
  total_sessions: number;
  avg_session_duration: number;
  bounce_rate: number;
  search_volume_today: number;
  search_volume_week: number;
  user_satisfaction_score: number;
  returning_users: number;
  new_users: number;
}

interface SearchQuery {
  id: string;
  query: string;
  user_id: string;
  user_email: string;
  timestamp: string;
  results_count: number;
  response_time_ms: number;
  user_rating: 'up' | 'down' | null;
  clicked_results: number;
  filters_used: string[];
  content_types: string[];
}

interface UserSession {
  id: string;
  user_id: string;
  user_email: string;
  start_time: string;
  duration_seconds: number;
  search_count: number;
  document_views: number;
  session_quality: 'high' | 'medium' | 'low';
  satisfaction_score: number | null;
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
      id={`user-behavior-tabpanel-${index}`}
      aria-labelledby={`user-behavior-tab-${index}`}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
};

const UserBehaviorAnalyticsMUI: React.FC = () => {
  const [stats, setStats] = useState<UserBehaviorStats | null>(null);
  const [recentQueries, setRecentQueries] = useState<SearchQuery[]>([]);
  const [userSessions, setUserSessions] = useState<UserSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<string>('7d');
  const [tabValue, setTabValue] = useState(0);

  useEffect(() => {
    fetchUserBehaviorData();
    const interval = setInterval(fetchUserBehaviorData, 60000); // Update every minute
    return () => clearInterval(interval);
  }, [timeRange]);

  const fetchUserBehaviorData = async () => {
    try {
      setError(null);

      // Mock data for demonstration
      const mockStats: UserBehaviorStats = {
        total_users: 1250,
        active_users_today: 89,
        active_users_week: 342,
        active_users_month: 789,
        total_sessions: 5678,
        avg_session_duration: 345,
        bounce_rate: 23.5,
        search_volume_today: 1234,
        search_volume_week: 5678,
        user_satisfaction_score: 4.6,
        returning_users: 890,
        new_users: 360
      };

      const mockQueries: SearchQuery[] = [
        {
          id: '1',
          query: 'quarterly financial report Q3 2024',
          user_id: 'user_123',
          user_email: 'john.doe@company.com',
          timestamp: new Date(Date.now() - 3600000).toISOString(),
          results_count: 12,
          response_time_ms: 1250,
          user_rating: 'up',
          clicked_results: 3,
          filters_used: ['date_range', 'content_type'],
          content_types: ['PDF', 'DOCX']
        },
        {
          id: '2',
          query: 'customer feedback analysis',
          user_id: 'user_456',
          user_email: 'jane.smith@company.com',
          timestamp: new Date(Date.now() - 7200000).toISOString(),
          results_count: 8,
          response_time_ms: 890,
          user_rating: 'down',
          clicked_results: 1,
          filters_used: ['content_type'],
          content_types: ['PDF']
        },
        {
          id: '3',
          query: 'marketing campaign performance metrics',
          user_id: 'user_789',
          user_email: 'mike.jones@company.com',
          timestamp: new Date(Date.now() - 10800000).toISOString(),
          results_count: 15,
          response_time_ms: 2100,
          user_rating: null,
          clicked_results: 5,
          filters_used: [],
          content_types: ['PDF', 'PPTX', 'XLSX']
        }
      ];

      const mockSessions: UserSession[] = [
        {
          id: 'session_1',
          user_id: 'user_123',
          user_email: 'john.doe@company.com',
          start_time: new Date(Date.now() - 1800000).toISOString(),
          duration_seconds: 1800,
          search_count: 8,
          document_views: 12,
          session_quality: 'high',
          satisfaction_score: 5.0
        },
        {
          id: 'session_2',
          user_id: 'user_456',
          user_email: 'jane.smith@company.com',
          start_time: new Date(Date.now() - 900000).toISOString(),
          duration_seconds: 600,
          search_count: 3,
          document_views: 2,
          session_quality: 'low',
          satisfaction_score: 2.5
        }
      ];

      setStats(mockStats);
      setRecentQueries(mockQueries);
      setUserSessions(mockSessions);
    } catch (err) {
      setError('Failed to fetch user behavior data');
      console.error('Error fetching user behavior data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const getQualityColor = (quality: string) => {
    switch (quality) {
      case 'high': return 'success';
      case 'medium': return 'warning';
      case 'low': return 'error';
      default: return 'default';
    }
  };

  const formatDuration = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
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
            User Behavior Analytics
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Monitor user engagement, search patterns, and satisfaction metrics
          </Typography>
        </Box>
        <Box display="flex" alignItems="center" gap={2}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Time Range</InputLabel>
            <Select
              value={timeRange}
              label="Time Range"
              onChange={(e) => setTimeRange(e.target.value)}
            >
              <MenuItem value="1d">Last 24h</MenuItem>
              <MenuItem value="7d">Last 7 days</MenuItem>
              <MenuItem value="30d">Last 30 days</MenuItem>
              <MenuItem value="90d">Last 90 days</MenuItem>
            </Select>
          </FormControl>
          <IconButton onClick={fetchUserBehaviorData} color="primary">
            <Refresh />
          </IconButton>
          <Button variant="outlined" startIcon={<Download />}>
            Export Data
          </Button>
        </Box>
      </Box>

      {error && (
        <Box mb={3}>
          <Typography color="error">{error}</Typography>
        </Box>
      )}

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          aria-label="User behavior analytics tabs"
        >
          <Tab label="Overview" icon={<People />} />
          <Tab label="Recent Searches" icon={<Search />} />
          <Tab label="User Sessions" icon={<AccessTime />} />
          <Tab label="Satisfaction Analysis" icon={<ThumbUp />} />
        </Tabs>
      </Paper>

      {/* Overview Tab */}
      <TabPanel value={tabValue} index={0}>
        {stats && (
          <Grid container spacing={3}>
            {/* User Metrics */}
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h5" mb={3} display="flex" alignItems="center" gap={1}>
                  <Group /> User Metrics
                </Typography>
                <Grid container spacing={2}>
                  <Grid size={{ xs: 6 }}>
                    <Box textAlign="center">
                      <Typography variant="h3" color="primary.main">
                        {stats.total_users.toLocaleString()}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Total Users
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid size={{ xs: 6 }}>
                    <Box textAlign="center">
                      <Typography variant="h3" color="success.main">
                        {stats.active_users_today}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Active Today
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid size={{ xs: 6 }}>
                    <Box textAlign="center">
                      <Typography variant="h3" color="info.main">
                        {stats.active_users_week}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Active This Week
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid size={{ xs: 6 }}>
                    <Box textAlign="center">
                      <Typography variant="h3" color="warning.main">
                        {stats.new_users}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        New Users
                      </Typography>
                    </Box>
                  </Grid>
                </Grid>
              </Paper>
            </Grid>

            {/* Engagement Metrics */}
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h5" mb={3} display="flex" alignItems="center" gap={1}>
                  <Timeline /> Engagement Metrics
                </Typography>
                <List>
                  <ListItem>
                    <ListItemText
                      primary="Total Sessions"
                      secondary={stats.total_sessions.toLocaleString()}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Avg Session Duration"
                      secondary={formatDuration(stats.avg_session_duration)}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Bounce Rate"
                      secondary={`${stats.bounce_rate.toFixed(1)}%`}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Returning Users"
                      secondary={`${((stats.returning_users / stats.total_users) * 100).toFixed(1)}%`}
                    />
                  </ListItem>
                </List>
              </Paper>
            </Grid>

            {/* Search Volume */}
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h5" mb={3} display="flex" alignItems="center" gap={1}>
                  <Search /> Search Volume
                </Typography>
                <Grid container spacing={2}>
                  <Grid size={{ xs: 6 }}>
                    <Box textAlign="center">
                      <Typography variant="h3" color="primary.main">
                        {stats.search_volume_today.toLocaleString()}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Today
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid size={{ xs: 6 }}>
                    <Box textAlign="center">
                      <Typography variant="h3" color="info.main">
                        {stats.search_volume_week.toLocaleString()}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        This Week
                      </Typography>
                    </Box>
                  </Grid>
                </Grid>
                <Box mt={2}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Daily Average: {Math.round(stats.search_volume_week / 7).toLocaleString()}
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={(stats.search_volume_today / 2000) * 100}
                    sx={{ height: 8, borderRadius: 4 }}
                  />
                </Box>
              </Paper>
            </Grid>

            {/* Satisfaction Score */}
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h5" mb={3} display="flex" alignItems="center" gap={1}>
                  <ThumbUp /> User Satisfaction
                </Typography>
                <Box textAlign="center">
                  <Typography variant="h2" color="success.main">
                    {stats.user_satisfaction_score}/5.0
                  </Typography>
                  <Typography variant="body2" color="text.secondary" paragraph>
                    Average Satisfaction Score
                  </Typography>
                  <Box display="flex" justifyContent="center" gap={1}>
                    {[1, 2, 3, 4, 5].map((star) => (
                      <ThumbUp
                        key={star}
                        color={star <= Math.floor(stats.user_satisfaction_score) ? 'success' : 'disabled'}
                      />
                    ))}
                  </Box>
                </Box>
              </Paper>
            </Grid>
          </Grid>
        )}
      </TabPanel>

      {/* Recent Searches Tab */}
      <TabPanel value={tabValue} index={1}>
        <Paper sx={{ p: 3 }}>
          <Typography variant="h5" mb={3}>
            Recent Search Queries
          </Typography>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Query</TableCell>
                  <TableCell>User</TableCell>
                  <TableCell>Time</TableCell>
                  <TableCell>Results</TableCell>
                  <TableCell>Response Time</TableCell>
                  <TableCell>Rating</TableCell>
                  <TableCell>Clicks</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {recentQueries.map((query) => (
                  <TableRow key={query.id}>
                    <TableCell>
                      <Typography variant="body2" sx={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {query.query}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{query.user_email}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {new Date(query.timestamp).toLocaleString()}
                      </Typography>
                    </TableCell>
                    <TableCell>{query.results_count}</TableCell>
                    <TableCell>{query.response_time_ms}ms</TableCell>
                    <TableCell>
                      {query.user_rating ? (
                        query.user_rating === 'up' ? (
                          <ThumbUp color="success" fontSize="small" />
                        ) : (
                          <ThumbDown color="error" fontSize="small" />
                        )
                      ) : (
                        <Typography variant="body2" color="text.secondary">No rating</Typography>
                      )}
                    </TableCell>
                    <TableCell>{query.clicked_results}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      </TabPanel>

      {/* User Sessions Tab */}
      <TabPanel value={tabValue} index={2}>
        <Paper sx={{ p: 3 }}>
          <Typography variant="h5" mb={3}>
            Recent User Sessions
          </Typography>
          <List>
            {userSessions.map((session) => (
              <ListItem key={session.id} alignItems="flex-start">
                <ListItemIcon>
                  <Person color={getQualityColor(session.session_quality) as any} />
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Box display="flex" alignItems="center" gap={1}>
                      <Typography variant="h6">{session.user_email}</Typography>
                      <Chip
                        label={session.session_quality.toUpperCase()}
                        color={getQualityColor(session.session_quality) as any}
                        size="small"
                      />
                    </Box>
                  }
                  secondary={
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Duration: {formatDuration(session.duration_seconds)} |
                        Searches: {session.search_count} |
                        Document Views: {session.document_views}
                      </Typography>
                      {session.satisfaction_score && (
                        <Typography variant="body2" color="primary">
                          Satisfaction: {session.satisfaction_score}/5.0
                        </Typography>
                      )}
                      <Typography variant="caption" color="text.secondary">
                        Started: {new Date(session.start_time).toLocaleString()}
                      </Typography>
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        </Paper>
      </TabPanel>

      {/* Satisfaction Analysis Tab */}
      <TabPanel value={tabValue} index={3}>
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, md: 6 }}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h5" mb={3}>
                Rating Distribution
              </Typography>
              <Box>
                <Box mb={2}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="body2">Positive Ratings</Typography>
                    <Typography variant="body2">68%</Typography>
                  </Box>
                  <LinearProgress variant="determinate" value={68} color="success" />
                </Box>
                <Box mb={2}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="body2">Negative Ratings</Typography>
                    <Typography variant="body2">12%</Typography>
                  </Box>
                  <LinearProgress variant="determinate" value={12} color="error" />
                </Box>
                <Box>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="body2">No Rating</Typography>
                    <Typography variant="body2">20%</Typography>
                  </Box>
                  <LinearProgress variant="determinate" value={20} />
                </Box>
              </Box>
            </Paper>
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h5" mb={3}>
                Satisfaction Trends
              </Typography>
              <Typography variant="body2" color="text.secondary">
                User satisfaction has been improving over the past week with a 12% increase
                in positive ratings compared to the previous period.
              </Typography>
              <Box mt={2}>
                <Chip icon={<TrendingUp />} label="Improving" color="success" />
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </TabPanel>
    </Box>
  );
};

export default UserBehaviorAnalyticsMUI;