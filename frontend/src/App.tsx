import React, { useState, useEffect } from 'react';
import './App.css';
import AnalyticsRouterMUI from './components/analytics/AnalyticsRouterMUI';
import {
  Container,
  Typography,
  Grid,
  Card,
  CardContent,
  Box,
  AppBar,
  Toolbar,
  Button,
  Chip
} from '@mui/material';

interface SystemInfo {
  [key: string]: any;
}

function App() {
  const [backendStatus, setBackendStatus] = useState<string>('checking...');
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [currentView, setCurrentView] = useState<'home' | 'analytics'>('home');

  useEffect(() => {
    // Check backend health
    fetch('/health')
      .then(response => response.json())
      .then((data: SystemInfo) => {
        setBackendStatus('healthy');
        setSystemInfo(data);
      })
      .catch(error => {
        setBackendStatus('unreachable');
        console.error('Backend health check failed:', error);
      });
  }, []);

  const Navigation = () => (
    <AppBar position="static">
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          Multimodal Enterprise RAG System
        </Typography>
        <Button
          color="inherit"
          onClick={() => setCurrentView('home')}
          variant={currentView === 'home' ? 'outlined' : 'text'}
          sx={{ mr: 1 }}
        >
          Home
        </Button>
        <Button
          color="inherit"
          onClick={() => setCurrentView('analytics')}
          variant={currentView === 'analytics' ? 'outlined' : 'text'}
          sx={{ mr: 2 }}
        >
          📊 Analytics
        </Button>
        <Chip
          icon={
            <Box
              sx={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                bgcolor: backendStatus === 'healthy' ? 'success.main' : 'error.main',
                ml: 0.5
              }}
            />
          }
          label={backendStatus === 'healthy' ? 'Connected' : 'Offline'}
          color={backendStatus === 'healthy' ? 'success' : 'error'}
          variant="outlined"
        />
      </Toolbar>
    </AppBar>
  );

  if (currentView === 'analytics') {
    return (
      <Box>
        <Navigation />
        <AnalyticsRouterMUI />
      </Box>
    );
  }

  return (
    <Box>
      <Navigation />
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box textAlign="center" mb={6}>
          <Typography variant="h3" component="h1" gutterBottom color="primary">
            Multimodal Enterprise RAG System
          </Typography>
          <Typography variant="h6" color="text.secondary" paragraph>
            Intelligent cross-modal search across documents, images, audio, and video
          </Typography>
        </Box>

        <Box mb={6}>
          <Typography variant="h4" component="h2" gutterBottom>
            System Status
          </Typography>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card sx={{
                bgcolor: backendStatus === 'healthy' ? 'success.light' : 'error.light',
                borderColor: backendStatus === 'healthy' ? 'success.main' : 'error.main'
              }}>
                <CardContent>
                  <Typography variant="h6" component="div" gutterBottom>
                    Backend API
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Status: {backendStatus}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card sx={{ bgcolor: 'info.light', borderColor: 'info.main' }}>
                <CardContent>
                  <Typography variant="h6" component="div" gutterBottom>
                    Frontend
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Status: running
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>

        {systemInfo && (
          <Box mb={6}>
            <Typography variant="h4" component="h3" gutterBottom>
              System Information
            </Typography>
            <Card>
              <CardContent>
                <Box component="pre" sx={{
                  fontSize: '0.875rem',
                  overflowX: 'auto',
                  bgcolor: 'grey.100',
                  p: 2,
                  borderRadius: 1
                }}>
                  {JSON.stringify(systemInfo, null, 2)}
                </Box>
              </CardContent>
            </Card>
          </Box>
        )}

        <Box mb={6}>
          <Typography variant="h4" component="h2" gutterBottom>
            Features
          </Typography>
          <Grid container spacing={3}>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Box textAlign="center">
                    <Typography variant="h3" gutterBottom>🔍</Typography>
                    <Typography variant="h6" gutterBottom>
                      Semantic Search
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      AI-powered search across all content types
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Box textAlign="center">
                    <Typography variant="h3" gutterBottom>🖼️</Typography>
                    <Typography variant="h6" gutterBottom>
                      Multimodal Analysis
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Search text, images, audio, and video
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Box textAlign="center">
                    <Typography variant="h3" gutterBottom>🧠</Typography>
                    <Typography variant="h6" gutterBottom>
                      Knowledge Graph
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Connected entity relationships
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Box textAlign="center">
                    <Typography variant="h3" gutterBottom>⚡</Typography>
                    <Typography variant="h6" gutterBottom>
                      Real-time Processing
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Background document ingestion
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>

        <Card sx={{
          bgcolor: 'primary.light',
          textAlign: 'center',
          py: 4,
          border: 2,
          borderColor: 'primary.main'
        }}>
          <CardContent>
            <Typography variant="h4" component="h2" gutterBottom color="primary.contrastText">
              📊 Advanced Analytics Available
            </Typography>
            <Typography variant="h6" color="primary.contrastText" paragraph>
              Monitor system performance, user behavior, and quality metrics with our comprehensive T3 analytics dashboard.
            </Typography>
            <Button
              variant="contained"
              size="large"
              onClick={() => setCurrentView('analytics')}
              sx={{ mt: 2 }}
            >
              Open Analytics Dashboard
            </Button>
          </CardContent>
        </Card>
      </Container>
    </Box>
  );
}

export default App;