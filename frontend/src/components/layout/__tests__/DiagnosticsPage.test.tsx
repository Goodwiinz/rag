import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';

import DiagnosticsPage from '../../../../app/(dashboard)/diagnostics/page';

jest.mock('@/store/authStore', () => ({
  useAuthStore: () => ({
    user: { role: 'admin' },
  }),
}));

jest.mock('@/components/diagnostics/RetrievalDiagnosticsDashboard', () => ({
  RetrievalDiagnosticsDashboard: () => <div>Mocked Diagnostics Dashboard</div>,
}));

describe('Diagnostics page route', () => {
  it('renders diagnostics page shell and dashboard', () => {
    render(<DiagnosticsPage />);

    expect(screen.getByTestId('diagnostics-page')).toBeInTheDocument();
    expect(
      screen.getByText('Mocked Diagnostics Dashboard')
    ).toBeInTheDocument();
  });
});
