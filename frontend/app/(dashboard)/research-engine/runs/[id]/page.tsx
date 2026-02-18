'use client';

import { use } from 'react';
import { RunView } from '@/components/research-engine/RunView';

interface RunPageProps {
  params: Promise<{ id: string }>;
}

export default function RunPage({ params }: RunPageProps) {
  const { id } = use(params);

  return (
    <div className="container mx-auto max-w-7xl p-6">
      <RunView runId={id} />
    </div>
  );
}
