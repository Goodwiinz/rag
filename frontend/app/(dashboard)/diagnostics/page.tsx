'use client';

import { RetrievalDiagnosticsDashboard } from '@/components/diagnostics/RetrievalDiagnosticsDashboard';
import { useAuthStore } from '@/stores/authStore';

export default function DiagnosticsPage() {
  const { user } = useAuthStore();

  if (user?.role !== 'admin') {
    return (
      <div
        data-testid="diagnostics-page"
        className="container mx-auto max-w-7xl p-6"
      >
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <h1 className="text-xl font-mono font-bold text-[var(--nous-fg-1)] uppercase tracking-widest mb-4">
            Access Denied
          </h1>
          <p className="text-sm font-mono text-[var(--nous-fg-3)]">
            You do not have permission to view this page. Admin role is
            required.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="diagnostics-page"
      className="container mx-auto max-w-7xl p-6"
    >
      <RetrievalDiagnosticsDashboard />
    </div>
  );
}
