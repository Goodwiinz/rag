'use client';

import { use } from 'react';
import { EvidenceMap } from '@/components/research-engine/EvidenceMap';

interface GraphPageProps {
  params: Promise<{ id: string }>;
}

export default function GraphPage({ params }: GraphPageProps) {
  const { id } = use(params);

  return (
    <div className="container mx-auto max-w-7xl p-6">
      <EvidenceMap projectId={id} />
    </div>
  );
}
