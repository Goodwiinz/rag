// app/(dashboard)/notifications/page.tsx
'use client';

import { NotificationList } from '@/components/notifications/NotificationList';

export default function NotificationsPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <NotificationList />
    </div>
  );
}
