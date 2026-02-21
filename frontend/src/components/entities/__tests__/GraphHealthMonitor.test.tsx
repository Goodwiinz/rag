import { render, screen } from '@testing-library/react';
import { GraphHealthMonitor } from '@/components/entities/GraphHealthMonitor';
import { apiClient } from '@/services/apiClient';

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

jest.mock('@/services/apiClient', () => ({
  apiClient: {
    get: jest.fn(),
  },
}));

describe('GraphHealthMonitor', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders health metrics when API returns backend health shape', async () => {
    (apiClient.get as jest.Mock).mockResolvedValue({
      status: 'healthy',
      neo4j_version: '5.0',
      database_size: '1.2 GB',
      node_count: 1234,
      relationship_count: 5678,
      index_count: 4,
      constraint_count: 2,
      uptime: '1d 2h',
      last_error: null,
      response_time_ms: 10,
    });

    render(<GraphHealthMonitor />);

    expect(await screen.findByText('1,234')).toBeInTheDocument();
    expect(screen.getByText('5,678')).toBeInTheDocument();
  });
});
