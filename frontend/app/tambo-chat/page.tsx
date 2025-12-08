'use client';

import { DashboardLayout } from '@/components/layout/dashboard/DashboardLayout';
import { MessageThreadFull } from '@/components/tambo/message-thread-full';

export default function TamboChatPage() {
  return (
    <DashboardLayout fullHeight>
      <div className="flex h-full w-full bg-background">
        <MessageThreadFull />
      </div>
    </DashboardLayout>
  );
}
