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
  Button,
  IconButton,
  CircularProgress,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  LinearProgress,
  Alert,
  Tabs,
  Tab,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Switch,
  FormControlLabel
} from '@mui/material';
import {
  Lightbulb,
  TrendingUp,
  Warning,
  CheckCircle,
  Schedule,
  PlayArrow,
  Stop,
  Refresh,
  Download,
  ExpandMore,
  ThumbUp,
  ThumbDown,
  Visibility,
  Settings,
  Assessment,
  Speed,
  Storage,
  Code
} from '@mui/icons-material';

interface Recommendation {
  id: string;
  title: string;
  description: string;
  category: 'content' | 'search_algorithm' | 'infrastructure' | 'user_experience' | 'indexing' | 'monitoring';
  priority: 'critical' | 'high' | 'medium' | 'low';
  impact_assessment: string;
  effort_required: 'low' | 'medium' | 'high';
  actionable_steps: string[];
  expected_outcome: string;
  estimated_improvement: number;
  status: 'pending' | 'in_progress' | 'completed' | 'rejected' | 'deferred';
  created_at: string;
  updated_at: string;
  votes: {
    up: number;
    down: number;
  };
  implemented_at?: string;
  results_observed?: string;
}

interface RecommendationRule {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  category: string;
  condition: string;
  recommendation_template: string;
  last_triggered: string;
  trigger_count: number;
}

interface ImprovementMetrics {
  metric_name: string;
  before_value: number;
  after_value: number;
  improvement_percentage: number;
  implementation_date: string;
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
      id={`recommendations-tabpanel-${index}`}
      aria-labelledby={`recommendations-tab-${index}`}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
};

const RecommendationsEngineMUI: React.FC = () => {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [rules, setRules] = useState<RecommendationRule[]>([]);
  const [improvements, setImprovements] = useState<ImprovementMetrics[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tabValue, setTabValue] = useState(0);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedPriority, setSelectedPriority] = useState<string>('all');
  const [detailsDialogOpen, setDetailsDialogOpen] = useState(false);
  const [selectedRecommendation, setSelectedRecommendation] = useState<Recommendation | null>(null);
  const [autoGenerate, setAutoGenerate] = useState(true);

  useEffect(() => {
    fetchRecommendationsData();
    const interval = setInterval(fetchRecommendationsData, 60000); // Update every minute
    return () => clearInterval(interval);
  }, [autoGenerate]);

  const fetchRecommendationsData = async () => {
    try {
      setError(null);

      // Mock data for demonstration
      const mockRecommendations: Recommendation[] = [
        {
          id: '1',
          title: 'Improve Document Quality Scores',
          description: 'Update outdated content and enhance metadata for better search relevance',
          category: 'content',
          priority: 'high',
          impact_assessment: 'High impact on search accuracy and user satisfaction',
          effort_required: 'medium',
          actionable_steps: [
            'Audit existing documents for quality issues',
            'Update document metadata and tags',
            'Implement content quality scoring system',
            'Set up automated quality monitoring'
          ],
          expected_outcome: '15-20% improvement in search relevance and user satisfaction',
          estimated_improvement: 18,
          status: 'pending',
          created_at: '2025-10-09T21:41:00Z',
          updated_at: '2025-10-09T21:41:00Z',
          votes: { up: 5, down: 1 }
        },
        {
          id: '2',
          title: 'Optimize Vector Search Parameters',
          description: 'Fine-tune embedding similarity thresholds for better results',
          category: 'search_algorithm',
          priority: 'critical',
          impact_assessment: 'Critical impact on result quality and system performance',
          effort_required: 'low',
          actionable_steps: [
            'Analyze current similarity thresholds',
            'Run A/B tests with different parameters',
            'Implement optimized similarity settings',
            'Monitor impact on search quality'
          ],
          expected_outcome: '10-15% improvement in result relevance and reduced response time',
          estimated_improvement: 12,
          status: 'in_progress',
          created_at: '2025-10-09T20:30:00Z',
          updated_at: '2025-10-09T22:15:00Z',
          votes: { up: 8, down: 0 }
        },
        {
          id: '3',
          title: 'Upgrade Database Indexing Strategy',
          description: 'Implement hybrid indexing approach for faster query performance',
          category: 'infrastructure',
          priority: 'medium',
          impact_assessment: 'Significant improvement in query response times',
          effort_required: 'high',
          actionable_steps: [
            'Analyze current database query patterns',
            'Design hybrid indexing strategy',
            'Implement new indexes with minimal downtime',
            'Monitor performance improvements'
          ],
          expected_outcome: '30-40% reduction in query response times',
          estimated_improvement: 35,
          status: 'completed',
          created_at: '2025-10-08T15:20:00Z',
          updated_at: '2025-10-09T18:45:00Z',
          implemented_at: '2025-10-09T16:00:00Z',
          results_observed: 'Query response times reduced by 32%',
          votes: { up: 12, down: 2 }
        },
        {
          id: '4',
          title: 'Enhance User Interface Navigation',
          description: 'Redesign search interface to improve user experience and discoverability',
          category: 'user_experience',
          priority: 'medium',
          impact_assessment: 'Improved user engagement and satisfaction',
          effort_required: 'medium',
          actionable_steps: [
            'Conduct user experience analysis',
            'Design improved navigation patterns',
            'Implement UI enhancements',
            'Run user acceptance testing'
          ],
          expected_outcome: '25% improvement in user engagement metrics',
          estimated_improvement: 25,
          status: 'deferred',
          created_at: '2025-10-07T10:15:00Z',
          updated_at: '2025-10-08T14:30:00Z',
          votes: { up: 3, down: 4 }
        }
      ];

      const mockRules: RecommendationRule[] = [
        {
          id: '1',
          name: 'High Response Time Alert',
          description: 'Triggers when average response time exceeds 2 seconds',
          enabled: true,
          category: 'performance',
          condition: 'avg_response_time > 2000ms',
          recommendation_template: 'Optimize {service} performance to reduce response time by {improvement}%',
          last_triggered: '2025-10-09T20:30:00Z',
          trigger_count: 15
        },
        {
          id: '2',
          name: 'Low Search Quality Alert',
          description: 'Triggers when search quality metrics fall below threshold',
          enabled: true,
          category: 'quality',
          condition: 'search_relevancy < 0.85',
          recommendation_template: 'Improve {metric_name} by implementing {recommended_action}',
          last_triggered: '2025-10-09T19:45:00Z',
          trigger_count: 8
        },
        {
          id: '3',
          name: 'Resource Usage Alert',
          description: 'Triggers when system resources exceed 80% utilization',
          enabled: false,
          category: 'infrastructure',
          condition: 'resource_usage > 80%',
          recommendation_template: 'Scale {resource} or optimize usage to maintain performance',
          last_triggered: '2025-10-08T12:20:00Z',
          trigger_count: 3
        }
      ];

      const mockImprovements: ImprovementMetrics[] = [
        {
          metric_name: 'Query Response Time',
          before_value: 450,
          after_value: 305,
          improvement_percentage: 32.2,
          implementation_date: '2025-10-09T16:00:00Z'
        },
        {
          metric_name: 'Search Relevancy',
          before_value: 0.82,
          after_value: 0.91,
          improvement_percentage: 11.0,
          implementation_date: '2025-10-07T14:30:00Z'
        },
        {
          metric_name: 'User Satisfaction',
          before_value: 4.1,
          after_value: 4.6,
          improvement_percentage: 12.2,
          implementation_date: '2025-10-05T10:15:00Z'
        }
      ];

      setRecommendations(mockRecommendations);
      setRules(mockRules);
      setImprovements(mockImprovements);
    } catch (err) {
      setError('Failed to fetch recommendations data');
      console.error('Error fetching recommendations data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
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

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'error';
      case 'high': return 'warning';
      case 'medium': return 'info';
      case 'low': return 'success';
      default: return 'default';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'content': return <Assessment />;
      case 'search_algorithm': return <Code />;
      case 'infrastructure': return <Storage />;
      case 'user_experience': return <Visibility />;
      case 'indexing': return <Speed />;
      case 'monitoring': return <Assessment />;
      default: return <Lightbulb />;
    }
  };

  const handleVote = (recommendationId: string, voteType: 'up' | 'down') => {
    setRecommendations(prev =>
      prev.map(rec =>
        rec.id === recommendationId
          ? { ...rec, votes: { ...rec.votes, [voteType]: rec.votes[voteType] + 1 } }
          : rec
      )
    );
  };

  const handleStatusChange = (recommendationId: string, newStatus: Recommendation['status']) => {
    setRecommendations(prev =>
      prev.map(rec =>
        rec.id === recommendationId
          ? { ...rec, status: newStatus, updated_at: new Date().toISOString() }
          : rec
      )
    );
  };

  const handleRecommendationClick = (recommendation: Recommendation) => {
    setSelectedRecommendation(recommendation);
    setDetailsDialogOpen(true);
  };

  const filteredRecommendations = recommendations.filter(rec => {
    const categoryMatch = selectedCategory === 'all' || rec.category === selectedCategory;
    const priorityMatch = selectedPriority === 'all' || rec.priority === selectedPriority;
    return categoryMatch && priorityMatch;
  });

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
            AI Recommendations Engine
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Intelligent recommendations for improving RAG system performance and quality
          </Typography>
        </Box>
        <Box display="flex" alignItems="center" gap={2}>
          <FormControlLabel
            control={
              <Switch
                checked={autoGenerate}
                onChange={(e) => setAutoGenerate(e.target.checked)}
                color="primary"
              />
            }
            label="Auto Generate"
          />
          <IconButton onClick={fetchRecommendationsData} color="primary">
            <Refresh />
          </IconButton>
          <Button variant="outlined" startIcon={<Download />}>
            Export Report
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Summary Stats */}
      <Grid container spacing={3} mb={4}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box textAlign="center">
                <Typography variant="h3" color="primary.main">
                  {recommendations.length}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Total Recommendations
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box textAlign="center">
                <Typography variant="h3" color="error.main">
                  {recommendations.filter(r => r.priority === 'critical').length}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Critical Priority
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box textAlign="center">
                <Typography variant="h3" color="success.main">
                  {recommendations.filter(r => r.status === 'completed').length}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Completed
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box textAlign="center">
                <Typography variant="h3" color="warning.main">
                  {Math.round(recommendations.reduce((acc, r) => acc + r.estimated_improvement, 0) / recommendations.length)}%
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Avg. Improvement
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box display="flex" gap={2} alignItems="center">
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
              <MenuItem value="infrastructure">Infrastructure</MenuItem>
              <MenuItem value="user_experience">User Experience</MenuItem>
              <MenuItem value="indexing">Indexing</MenuItem>
              <MenuItem value="monitoring">Monitoring</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Priority</InputLabel>
            <Select
              value={selectedPriority}
              label="Priority"
              onChange={(e) => setSelectedPriority(e.target.value)}
            >
              <MenuItem value="all">All Priorities</MenuItem>
              <MenuItem value="critical">Critical</MenuItem>
              <MenuItem value="high">High</MenuItem>
              <MenuItem value="medium">Medium</MenuItem>
              <MenuItem value="low">Low</MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Paper>

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          aria-label="Recommendations tabs"
        >
          <Tab label="Recommendations" icon={<Lightbulb />} />
          <Tab label="Rules Engine" icon={<Settings />} />
          <Tab label="Improvements" icon={<TrendingUp />} />
          <Tab label="Analytics" icon={<Assessment />} />
        </Tabs>
      </Paper>

      {/* Recommendations Tab */}
      <TabPanel value={tabValue} index={0}>
        <List>
          {filteredRecommendations.map((recommendation) => (
            <React.Fragment key={recommendation.id}>
              <ListItem alignItems="flex-start" sx={{ flexDirection: 'column', alignItems: 'stretch' }}>
                <Paper sx={{ p: 3, width: '100%' }}>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                    <Box display="flex" alignItems="center" gap={1} mb={1}>
                      {getCategoryIcon(recommendation.category)}
                      <Typography variant="h6">{recommendation.title}</Typography>
                      <Chip
                        label={recommendation.priority.toUpperCase()}
                        color={getPriorityColor(recommendation.priority) as any}
                        size="small"
                      />
                      <Chip
                        label={recommendation.status.replace('_', ' ')}
                        color={getStatusColor(recommendation.status) as any}
                        size="small"
                      />
                    </Box>
                    <Box display="flex" alignItems="center" gap={1}>
                      <IconButton
                        size="small"
                        onClick={() => handleVote(recommendation.id, 'up')}
                        color={recommendation.votes.up > 0 ? 'success' : 'default'}
                      >
                        <ThumbUp />
                      </IconButton>
                      <Typography variant="body2">{recommendation.votes.up}</Typography>
                      <IconButton
                        size="small"
                        onClick={() => handleVote(recommendation.id, 'down')}
                        color={recommendation.votes.down > 0 ? 'error' : 'default'}
                      >
                        <ThumbDown />
                      </IconButton>
                      <Typography variant="body2">{recommendation.votes.down}</Typography>
                    </Box>
                  </Box>

                  <Typography variant="body2" color="text.secondary" paragraph>
                    {recommendation.description}
                  </Typography>

                  <Box display="flex" gap={2} mb={2}>
                    <Typography variant="caption" color="text.secondary">
                      Est. improvement: {recommendation.estimated_improvement}%
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      •
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Effort: {recommendation.effort_required}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      •
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {recommendation.expected_outcome}
                    </Typography>
                  </Box>

                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Typography variant="caption" color="text.secondary">
                      Created: {new Date(recommendation.created_at).toLocaleDateString()}
                    </Typography>
                    <Box display="flex" gap={1}>
                      <Button
                        size="small"
                        onClick={() => handleRecommendationClick(recommendation)}
                      >
                        View Details
                      </Button>
                      {recommendation.status === 'pending' && (
                        <Button
                          size="small"
                          variant="contained"
                          onClick={() => handleStatusChange(recommendation.id, 'in_progress')}
                        >
                          Start Implementation
                        </Button>
                      )}
                      {recommendation.status === 'in_progress' && (
                        <Button
                          size="small"
                          variant="contained"
                          color="success"
                          onClick={() => handleStatusChange(recommendation.id, 'completed')}
                        >
                          Mark Complete
                        </Button>
                      )}
                    </Box>
                  </Box>
                </Paper>
              </ListItem>
              <Divider />
            </React.Fragment>
          ))}
        </List>
      </TabPanel>

      {/* Rules Engine Tab */}
      <TabPanel value={tabValue} index={1}>
        <List>
          {rules.map((rule) => (
            <React.Fragment key={rule.id}>
              <ListItem alignItems="flex-start">
                <ListItemIcon>
                  <Settings color={rule.enabled ? 'primary' : 'disabled'} />
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Box display="flex" alignItems="center" gap={1}>
                      <Typography variant="h6">{rule.name}</Typography>
                      <Chip
                        label={rule.enabled ? 'ENABLED' : 'DISABLED'}
                        color={rule.enabled ? 'success' : 'default'}
                        size="small"
                      />
                    </Box>
                  }
                  secondary={
                    <Box>
                      <Typography variant="body2" color="text.secondary" paragraph>
                        {rule.description}
                      </Typography>
                      <Typography variant="body2" component="pre" sx={{ bgcolor: 'grey.100', p: 1, borderRadius: 1, fontSize: '0.875rem' }}>
                        Condition: {rule.condition}
                      </Typography>
                      <Box display="flex" gap={2} mt={1}>
                        <Typography variant="caption" color="text.secondary">
                          Category: {rule.category}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Triggered: {rule.trigger_count} times
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Last: {new Date(rule.last_triggered).toLocaleString()}
                        </Typography>
                      </Box>
                    </Box>
                  }
                />
              </ListItem>
              <Divider />
            </React.Fragment>
          ))}
        </List>
      </TabPanel>

      {/* Improvements Tab */}
      <TabPanel value={tabValue} index={2}>
        <Grid container spacing={3}>
          {improvements.map((improvement, index) => (
            <Grid item xs={12} md={4} key={index}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    {improvement.metric_name}
                  </Typography>
                  <Box mb={2}>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                      <Typography variant="body2" color="text.secondary">
                        Before: {improvement.before_value}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        After: {improvement.after_value}
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={improvement.improvement_percentage}
                      color="success"
                    />
                  </Box>
                  <Typography variant="h5" color="success.main" textAlign="center">
                    +{improvement.improvement_percentage.toFixed(1)}%
                  </Typography>
                  <Typography variant="caption" color="text.secondary" display="block" textAlign="center">
                    {new Date(improvement.implementation_date).toLocaleDateString()}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </TabPanel>

      {/* Analytics Tab */}
      <TabPanel value={tabValue} index={3}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h5" mb={3}>
                Recommendation Performance
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                The AI recommendations engine has generated {recommendations.length} recommendations with an average
                estimated improvement of {Math.round(recommendations.reduce((acc, r) => acc + r.estimated_improvement, 0) / recommendations.length)}%.
              </Typography>
              <List>
                <ListItem>
                  <ListItemText
                    primary="Implementation Rate"
                    secondary={`${((recommendations.filter(r => r.status === 'completed').length / recommendations.length) * 100).toFixed(1)}%`}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Average Time to Implement"
                    secondary="2.5 days"
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="User Satisfaction Score"
                    secondary="4.2/5.0"
                  />
                </ListItem>
              </List>
            </Paper>
          </Grid>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h5" mb={3}>
                Category Distribution
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Recommendations are distributed across multiple categories to ensure comprehensive system improvement.
              </Typography>
              <List>
                <ListItem>
                  <ListItemText
                    primary="Content Quality"
                    secondary={`${recommendations.filter(r => r.category === 'content').length} recommendations`}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Search Algorithm"
                    secondary={`${recommendations.filter(r => r.category === 'search_algorithm').length} recommendations`}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Infrastructure"
                    secondary={`${recommendations.filter(r => r.category === 'infrastructure').length} recommendations`}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="User Experience"
                    secondary={`${recommendations.filter(r => r.category === 'user_experience').length} recommendations`}
                  />
                </ListItem>
              </List>
            </Paper>
          </Grid>
        </Grid>
      </TabPanel>

      {/* Details Dialog */}
      <Dialog
        open={detailsDialogOpen}
        onClose={() => setDetailsDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        {selectedRecommendation && (
          <>
            <DialogTitle>
              {selectedRecommendation.title}
              <Box display="flex" gap={1} mt={1}>
                <Chip
                  label={selectedRecommendation.priority.toUpperCase()}
                  color={getPriorityColor(selectedRecommendation.priority) as any}
                  size="small"
                />
                <Chip
                  label={selectedRecommendation.status.replace('_', ' ')}
                  color={getStatusColor(selectedRecommendation.status) as any}
                  size="small"
                />
              </Box>
            </DialogTitle>
            <DialogContent>
              <Typography variant="body1" paragraph>
                {selectedRecommendation.description}
              </Typography>

              <Typography variant="h6" gutterBottom>
                Impact Assessment
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                {selectedRecommendation.impact_assessment}
              </Typography>

              <Typography variant="h6" gutterBottom>
                Actionable Steps
              </Typography>
              <List>
                {selectedRecommendation.actionable_steps.map((step, index) => (
                  <ListItem key={index}>
                    <ListItemText primary={`${index + 1}. ${step}`} />
                  </ListItem>
                ))}
              </List>

              <Typography variant="h6" gutterBottom>
                Expected Outcome
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                {selectedRecommendation.expected_outcome}
              </Typography>

              <Box display="flex" gap={2} mt={2}>
                <Typography variant="body2" color="text.secondary">
                  Estimated Improvement: {selectedRecommendation.estimated_improvement}%
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Effort Required: {selectedRecommendation.effort_required}
                </Typography>
              </Box>

              {selectedRecommendation.results_observed && (
                <>
                  <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
                    Results Observed
                  </Typography>
                  <Typography variant="body2" color="success.main">
                    {selectedRecommendation.results_observed}
                  </Typography>
                </>
              )}
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setDetailsDialogOpen(false)}>
                Close
              </Button>
              {selectedRecommendation.status === 'pending' && (
                <Button
                  variant="contained"
                  onClick={() => {
                    handleStatusChange(selectedRecommendation.id, 'in_progress');
                    setDetailsDialogOpen(false);
                  }}
                >
                  Start Implementation
                </Button>
              )}
              {selectedRecommendation.status === 'in_progress' && (
                <Button
                  variant="contained"
                  color="success"
                  onClick={() => {
                    handleStatusChange(selectedRecommendation.id, 'completed');
                    setDetailsDialogOpen(false);
                  }}
                >
                  Mark Complete
                </Button>
              )}
            </DialogActions>
          </>
        )}
      </Dialog>
    </Box>
  );
};

export default RecommendationsEngineMUI;