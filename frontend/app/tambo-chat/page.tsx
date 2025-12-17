'use client';

import { SimpleLayout } from '@/components/layout/SimpleLayout';
import { MessageThreadFull } from '@/components/tambo/message-thread-full';

export default function TamboChatPage() {
  return (
    <SimpleLayout showHeader={true}>
      <div className="flex h-[calc(100vh-4rem)] w-full bg-background">
        <MessageThreadFull />
      </div>
    </SimpleLayout>
  );
}
