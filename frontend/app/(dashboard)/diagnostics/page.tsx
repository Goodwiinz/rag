'use client';

import { RetrievalDiagnosticsDashboard } from '@/components/diagnostics/RetrievalDiagnosticsDashboard';
import { useAuthStore } from '@/stores/authStore';

export default function DiagnosticsPage() {
  const { user } = useAuthStore();

  if (user?.role !== 'admin') {
    return (
      <div
        data-testid="diagnostics-page"
        className="container mx-auto max-w-7xl p-4 sm:p-6"
      >
        <div
          role="alert"
          className="mx-auto flex max-w-md flex-col items-center justify-center rounded-xl border border-border bg-card py-16 text-center shadow-sm"
        >
          <h1 className="text-lg font-semibold text-foreground">
            Access restricted
          </h1>
          <p className="mt-2 max-w-sm text-sm text-muted-foreground">
            Retrieval diagnostics are available to admins only. Ask a workspace
            admin for access if you need to inspect the pipeline.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="diagnostics-page"
      className="container mx-auto max-w-7xl p-4 sm:p-6"
    >
      <RetrievalDiagnosticsDashboard />
    </div>
  );
}
