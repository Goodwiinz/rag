import { describe, expect, it } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import APIKeyManagementPage from '@/page-components/settings/APIKeyManagementPage';

describe('APIKeyManagementPage', () => {
  it('renders developer access sections', () => {
    render(<APIKeyManagementPage />);

    expect(
      screen.getByRole('heading', { name: 'API Key Management' })
    ).toBeInTheDocument();
    expect(screen.getByText('Active Tokens')).toBeInTheDocument();
    expect(screen.getByText('Provider Access')).toBeInTheDocument();
    expect(screen.getByText('Rotation Guidance')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /return to settings overview/i })
    ).toBeInTheDocument();
  });
});
