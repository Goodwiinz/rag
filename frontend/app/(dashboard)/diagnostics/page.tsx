'use client';

import { RetrievalDiagnosticsDashboard } from '@/components/diagnostics/RetrievalDiagnosticsDashboard';

export default function DiagnosticsPage() {
  return (
    <div data-testid="diagnostics-page" className="container mx-auto max-w-7xl p-6">
      <RetrievalDiagnosticsDashboard />
    </div>
  );
}
