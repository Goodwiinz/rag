import { describe, expect, it } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import OrganizationSettingsPage from '@/page-components/settings/OrganizationSettingsPage';

describe('OrganizationSettingsPage', () => {
  it('renders workspace governance sections', () => {
    render(<OrganizationSettingsPage />);

    expect(
      screen.getByRole('heading', { name: 'Organization Settings' })
    ).toBeInTheDocument();
    expect(screen.getByText('Members and roles')).toBeInTheDocument();
    expect(screen.getByText('Usage and billing')).toBeInTheDocument();
    expect(screen.getByText('Developer access')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /open developer access/i })
    ).toBeInTheDocument();
  });
});
