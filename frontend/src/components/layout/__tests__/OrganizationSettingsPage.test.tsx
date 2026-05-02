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
    expect(screen.getByText('Members & Roles')).toBeInTheDocument();
    expect(screen.getByText('Usage & Billing')).toBeInTheDocument();
    expect(screen.getByText('Security & Compliance')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /review developer access/i })
    ).toBeInTheDocument();
  });
});
