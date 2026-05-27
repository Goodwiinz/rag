import { Metadata } from 'next';
import DashboardLayoutClient from './dashboard-layout-client';

export const metadata: Metadata = {
  title: {
    template: '%s | NOUS',
    default: 'Dashboard | NOUS',
  },
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardLayoutClient>{children}</DashboardLayoutClient>;
}
