import { describe, expect, it, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
// Mock fetch for /health used in App BEFORE importing App
const mockFetch = vi.fn().mockResolvedValue({
  json: () => Promise.resolve({ status: 'ok' })
});
(global as any).fetch = mockFetch as any;
(window as any).fetch = mockFetch as any;

// Mock analytics service to avoid axios/ESM issues during routing tests
vi.mock('../services/analyticsService', () => ({
  __esModule: true,
  default: {
    getQualityMetrics: vi.fn().mockResolvedValue({
      metrics: [],
      alerts: []
    })
  }
}));

describe('App routing', () => {
  it('renders app shell and shows Analytics entry points', async () => {
    const App = (await import('../App')).default;
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByText(/Open Analytics Dashboard/i)).toBeInTheDocument();
  });
});
