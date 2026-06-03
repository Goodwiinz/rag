import type { Meta, StoryObj } from '@storybook/react';
import { SystemOverviewDashboard } from './SystemOverviewDashboard';

// Mock data for stories
const mockSystemHealth = {
  overall: 92,
  components: [
    {
      name: 'API Gateway',
      status: 'healthy' as const,
      score: 98,
      last_check: new Date().toISOString(),
      metrics: { response_time: 120, requests_per_second: 450 },
      dependencies: ['Authentication Service', 'Rate Limiter'],
    },
    {
      name: 'Document Processor',
      status: 'degraded' as const,
      score: 75,
      last_check: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      metrics: { queue_depth: 25, processing_rate: 15, error_rate: 2.5 },
      dependencies: ['Storage Service', 'OCR Service'],
    },
    {
      name: 'Search Engine',
      status: 'healthy' as const,
      score: 92,
      last_check: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
      metrics: { query_latency: 85, index_size: '2.5GB', cache_hit_rate: 85 },
      dependencies: ['Vector Database', 'Knowledge Graph'],
    },
  ],
  timestamp: new Date().toISOString(),
  trend: {
    direction: 'stable' as const,
    percentage: 1.2,
    period: '24h',
  },
};

const mockAlerts = [
  {
    id: 'alert-1',
    name: 'High Memory Usage',
    description: 'Memory usage has exceeded 85% threshold',
    severity: 'warning' as const,
    status: 'active' as const,
    source: 'Document Processor',
    rule_id: 'rule-001',
    triggered_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
    metadata: { current_usage: 87, threshold: 85 },
    labels: { component: 'document-processor', metric: 'memory' },
    annotations: { runbook_url: 'https://wiki.company.com/runbooks/memory' },
    actions: [],
  },
  {
    id: 'alert-2',
    name: 'Database Connection Failed',
    description: 'Failed to establish connection to Neo4j database',
    severity: 'critical' as const,
    status: 'active' as const,
    source: 'Knowledge Graph',
    rule_id: 'rule-002',
    triggered_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    metadata: { database: 'neo4j', error_code: 'ECONNREFUSED' },
    labels: { component: 'knowledge-graph', service: 'database' },
    annotations: {
      runbook_url: 'https://wiki.company.com/runbooks/database',
      escalation_policy: 'immediate',
    },
    actions: [],
  },
];

const meta: Meta<typeof SystemOverviewDashboard> = {
  title: 'Monitoring/SystemOverviewDashboard',
  component: SystemOverviewDashboard,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: `
The SystemOverviewDashboard provides a comprehensive view of system health, status, and performance metrics.
It displays real-time information about component health, SLI/SLO metrics, active alerts, and system trends.

Key Features:
- Real-time system health monitoring
- Component status grid with health scores
- SLI/SLO metrics tracking
- Active alerts management
- Historical trend visualization
- Interactive drill-down capabilities
- WebSocket integration for live updates
- Responsive design for all screen sizes
        `,
      },
    },
  },
  argTypes: {
    className: {
      control: 'text',
      description: 'Additional CSS classes to apply to the dashboard container',
    },
    autoRefresh: {
      control: 'boolean',
      description: 'Enable automatic data refresh',
      defaultValue: true,
    },
    refreshInterval: {
      control: 'number',
      description: 'Refresh interval in milliseconds',
      defaultValue: 30000,
    },
    showDetails: {
      control: 'boolean',
      description: 'Show detailed component information',
      defaultValue: true,
    },
    compact: {
      control: 'boolean',
      description: 'Show compact version of the dashboard',
      defaultValue: false,
    },
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof meta>;

// Default story with full features
export const Default: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 30000,
    showDetails: true,
    compact: false,
    onSystemHealthClick: (health) =>
      console.log('System health clicked:', health),
    onAlertClick: (alert) => console.log('Alert clicked:', alert),
    onComponentClick: (component) =>
      console.log('Component clicked:', component),
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <SystemOverviewDashboard {...args} />
    </div>
  ),
};

// Compact version for embedded views
export const Compact: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 60000,
    showDetails: false,
    compact: true,
  },
  render: (args) => (
    <div className="p-4 bg-white">
      <SystemOverviewDashboard {...args} />
    </div>
  ),
};

// Dashboard with critical alerts
export const WithCriticalAlerts: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 15000,
    showDetails: true,
    compact: false,
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-foreground mb-2">
          System with Critical Alerts
        </h2>
        <p className="text-foreground">
          This dashboard displays multiple critical alerts requiring immediate
          attention
        </p>
      </div>
      <SystemOverviewDashboard {...args} />
    </div>
  ),
};

// Dashboard in degraded state
export const DegradedSystem: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 30000,
    showDetails: true,
    compact: false,
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-foreground mb-2">
          Degraded System State
        </h2>
        <p className="text-foreground">
          System is experiencing performance issues with some components
        </p>
      </div>
      <SystemOverviewDashboard {...args} />
    </div>
  ),
};

// Dashboard with no data/loading state
export const LoadingState: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 30000,
    showDetails: true,
    compact: false,
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-foreground mb-2">
          Loading State
        </h2>
        <p className="text-foreground">
          Dashboard showing loading states while fetching data
        </p>
      </div>
      <SystemOverviewDashboard {...args} />
    </div>
  ),
};

// Mobile responsive view
export const MobileView: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 30000,
    showDetails: true,
    compact: false,
  },
  parameters: {
    viewport: {
      defaultViewport: 'iphone12',
    },
  },
  render: (args) => (
    <div className="p-4 bg-gray-50 min-h-screen">
      <SystemOverviewDashboard {...args} />
    </div>
  ),
};

// Tablet responsive view
export const TabletView: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 30000,
    showDetails: true,
    compact: false,
  },
  parameters: {
    viewport: {
      defaultViewport: 'ipad',
    },
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <SystemOverviewDashboard {...args} />
    </div>
  ),
};

// Dark mode theme
export const DarkMode: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 30000,
    showDetails: true,
    compact: false,
  },
  parameters: {
    backgrounds: {
      default: 'dark',
      values: [
        {
          name: 'dark',
          value: '#1a1a1a',
        },
      ],
    },
  },
  render: (args) => (
    <div className="p-6 bg-gray-900 min-h-screen">
      <SystemOverviewDashboard {...args} />
    </div>
  ),
};

// High frequency refresh for operations center
export const OperationsCenter: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 5000, // 5 seconds for operations center
    showDetails: true,
    compact: false,
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-foreground mb-2">
          Operations Center View
        </h2>
        <p className="text-foreground">
          High-frequency refresh monitoring dashboard for operations teams
        </p>
      </div>
      <SystemOverviewDashboard {...args} />
    </div>
  ),
};

// Executive summary view
export const ExecutiveSummary: Story = {
  args: {
    className: '',
    autoRefresh: false, // Manual refresh for executive view
    refreshInterval: 300000, // 5 minutes if enabled
    showDetails: false,
    compact: true,
  },
  render: (args) => (
    <div className="p-6 bg-white">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-foreground mb-2">
          Executive Dashboard
        </h2>
        <p className="text-foreground">
          High-level system overview for executive stakeholders
        </p>
      </div>
      <SystemOverviewDashboard {...args} />
    </div>
  ),
};

// Interactive playground with event handlers
export const Interactive: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 10000,
    showDetails: true,
    compact: false,
    onSystemHealthClick: (health) => {
      console.log('System health clicked:', health);
      alert(
        `System health: ${health.overall}% - Click to view detailed analytics`
      );
    },
    onAlertClick: (alert) => {
      console.log('Alert clicked:', alert);
      alert(`Alert: ${alert.name} - ${alert.description}`);
    },
    onComponentClick: (component) => {
      console.log('Component clicked:', component);
      alert(`Component: ${component.name} - Status: ${component.status}`);
    },
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-foreground mb-2">
          Interactive Dashboard
        </h2>
        <p className="text-foreground">
          Click on any component, alert, or metric to see interactive responses
        </p>
      </div>
      <SystemOverviewDashboard {...args} />
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: `
This story demonstrates the interactive capabilities of the SystemOverviewDashboard.
Click on various elements to see event handlers in action:

- Click the system health score to view detailed analytics
- Click on individual alerts to see alert details
- Click on components in the status grid to view component-specific information
- Navigate through different tabs to explore various aspects of system monitoring

The dashboard includes real-time updates, comprehensive filtering, and drill-down capabilities
for effective system monitoring and management.
        `,
      },
    },
  },
};
