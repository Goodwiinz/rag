import React, { useState } from 'react';
import {
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
  AppBar,
  Toolbar,
  IconButton,
  Chip,
  Divider
} from '@mui/material';
import {
  Dashboard,
  TrendingUp,
  People,
  Speed,
  Lightbulb,
  Menu,
  Refresh,
  Download
} from '@mui/icons-material';
import AnalyticsDashboardMUI from './AnalyticsDashboardMUI';
import QualityMetricsDashboardMUI from './QualityMetricsDashboardMUI';
import UserBehaviorAnalyticsMUI from './UserBehaviorAnalyticsMUI';
import PerformanceMonitoringMUI from './PerformanceMonitoringMUI';
import RecommendationsEngineMUI from './RecommendationsEngineMUI';

interface AnalyticsRouterProps {
  activeView?: string;
}

const AnalyticsRouterMUI: React.FC<AnalyticsRouterProps> = ({ activeView = 'overview' }) => {
  const [currentView, setCurrentView] = useState(activeView);
  const [mobileOpen, setMobileOpen] = useState(false);

  const navigationItems = [
    {
      id: 'overview',
      label: 'Dashboard Overview',
      icon: <Dashboard />,
      description: 'Main dashboard view'
    },
    {
      id: 'quality',
      label: 'Quality Metrics',
      icon: <TrendingUp />,
      description: 'Search quality metrics'
    },
    {
      id: 'behavior',
      label: 'User Behavior',
      icon: <People />,
      description: 'User analytics'
    },
    {
      id: 'performance',
      label: 'Performance',
      icon: <Speed />,
      description: 'System performance'
    },
    {
      id: 'recommendations',
      label: 'Recommendations',
      icon: <Lightbulb />,
      description: 'AI recommendations'
    }
  ];

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const renderView = () => {
    switch (currentView) {
      case 'overview':
        return <AnalyticsDashboardMUI />;
      case 'quality':
        return <QualityMetricsDashboardMUI />;
      case 'behavior':
        return <UserBehaviorAnalyticsMUI />;
      case 'performance':
        return <PerformanceMonitoringMUI />;
      case 'recommendations':
        return <RecommendationsEngineMUI />;
      default:
        return <AnalyticsDashboardMUI />;
    }
  };

  const drawer = (
    <Box>
      <Toolbar>
        <Typography variant="h6" noWrap component="div">
          Analytics
        </Typography>
      </Toolbar>
      <Divider />
      <List>
        {navigationItems.map((item) => (
          <ListItem key={item.id} disablePadding>
            <ListItemButton
              selected={currentView === item.id}
              onClick={() => {
                setCurrentView(item.id);
                setMobileOpen(false);
              }}
              sx={{
                '&.Mui-selected': {
                  bgcolor: 'primary.main',
                  color: 'primary.contrastText',
                  '& .MuiListItemIcon-root': {
                    color: 'primary.contrastText',
                  },
                  '&:hover': {
                    bgcolor: 'primary.dark',
                  },
                },
              }}
            >
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText
                primary={item.label}
                secondary={item.description}
                primaryTypographyProps={{
                  fontWeight: currentView === item.id ? 'bold' : 'normal'
                }}
              />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
      <Divider />
      <Box sx={{ p: 2, mt: 'auto' }}>
        <Box display="flex" alignItems="center" gap={1} mb={1}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              bgcolor: 'success.main',
            }}
          />
          <Typography variant="body2" color="text.secondary">
            All systems operational
          </Typography>
        </Box>
        <Typography variant="caption" color="text.secondary">
          Last updated: {new Date().toLocaleTimeString()}
        </Typography>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - 240px)` },
          ml: { sm: `240px` },
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { sm: 'none' } }}
          >
            <Menu />
          </IconButton>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            {navigationItems.find(item => item.id === currentView)?.label}
          </Typography>
          <IconButton color="inherit" sx={{ ml: 1 }}>
            <Refresh />
          </IconButton>
          <IconButton color="inherit" sx={{ ml: 1 }}>
            <Download />
          </IconButton>
          <Chip
            label="T3 Analytics"
            color="secondary"
            size="small"
            sx={{ ml: 2 }}
          />
        </Toolbar>
      </AppBar>

      <Box
        component="nav"
        sx={{ width: { sm: 240 }, flexShrink: { sm: 0 } }}
        aria-label="analytics navigation"
      >
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{
            keepMounted: true, // Better open performance on mobile.
          }}
          sx={{
            display: { xs: 'block', sm: 'none' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: 240,
            },
          }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', sm: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: 240,
            },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { sm: `calc(100% - 240px)` },
          mt: 8, // AppBar height
        }}
      >
        <Typography variant="body2" color="text.secondary" paragraph>
          Monitor and analyze your RAG system performance and quality metrics
        </Typography>
        {renderView()}
      </Box>
    </Box>
  );
};

export default AnalyticsRouterMUI;