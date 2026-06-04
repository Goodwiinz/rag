import { describe, expect, it } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import APIKeyManagementPage from '@/page-components/settings/APIKeyManagementPage';

describe('APIKeyManagementPage', () => {
  it('renders api key sections', () => {
    render(<APIKeyManagementPage />);

    expect(
      screen.getByRole('heading', { name: 'API keys' })
    ).toBeInTheDocument();
    expect(screen.getByText('Your keys')).toBeInTheDocument();
    expect(screen.getByText('Provider access')).toBeInTheDocument();
    expect(screen.getByText('Keeping keys safe')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /back to settings/i })
    ).toBeInTheDocument();
  });
});
