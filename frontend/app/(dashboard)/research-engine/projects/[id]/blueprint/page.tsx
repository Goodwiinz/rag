'use client';

import { useParams } from 'next/navigation';
import { BlueprintEditor } from '@/components/research-engine/BlueprintEditor';

export default function BlueprintPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  return (
    <div className="container mx-auto max-w-7xl p-6">
      <BlueprintEditor projectId={projectId} />
    </div>
  );
}
