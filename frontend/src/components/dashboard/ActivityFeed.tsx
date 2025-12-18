'use client';

import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import {
    Clock,
    FileText,
    MessageSquare,
    Search,
    Sparkles,
    Upload,
} from 'lucide-react';

interface ActivityItem {
  id: string;
  type: 'upload' | 'search' | 'chat' | 'insight';
  title: string;
  description?: string;
  timestamp: Date;
}

interface ActivityFeedProps {
  activities?: ActivityItem[];
  className?: string;
}

const activityConfig = {
  upload: {
    icon: Upload,
    color: 'text-emerald-500',
    bgColor: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/20',
  },
  search: {
    icon: Search,
    color: 'text-blue-500',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/20',
  },
  chat: {
    icon: MessageSquare,
    color: 'text-amber-500',
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500/20',
  },
  insight: {
    icon: Sparkles,
    color: 'text-purple-500',
    bgColor: 'bg-purple-500/10',
    borderColor: 'border-purple-500/20',
  },
};

// Sample data for demonstration
const sampleActivities: ActivityItem[] = [
  {
    id: '1',
    type: 'upload',
    title: 'Document uploaded',
    description: 'quarterly-report-2024.pdf',
    timestamp: new Date(Date.now() - 1000 * 60 * 5),
  },
  {
    id: '2',
    type: 'search',
    title: 'Semantic search',
    description: '"machine learning best practices"',
    timestamp: new Date(Date.now() - 1000 * 60 * 23),
  },
  {
    id: '3',
    type: 'chat',
    title: 'AI chat session',
    description: 'Discussed data analysis strategies',
    timestamp: new Date(Date.now() - 1000 * 60 * 60),
  },
  {
    id: '4',
    type: 'insight',
    title: 'AI insight generated',
    description: 'Found 3 related documents',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2),
  },
  {
    id: '5',
    type: 'upload',
    title: 'Document uploaded',
    description: 'meeting-notes.docx',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 4),
  },
];

export function ActivityFeed({ activities = sampleActivities, className }: ActivityFeedProps) {
  return (
    <div className={cn('rounded-xl border border-border bg-card', className)}>
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-amber-500/10 to-orange-500/10">
            <Clock className="h-4 w-4 text-amber-500" />
          </div>
          <div>
            <h3 className="font-semibold text-foreground">Recent Activity</h3>
            <p className="text-xs text-muted-foreground">Your latest actions</p>
          </div>
        </div>
        <button className="text-xs font-medium text-amber-600 hover:text-amber-500 transition-colors">
          View all
        </button>
      </div>

      <div className="divide-y divide-border">
        {activities.map((activity, index) => {
          const config = activityConfig[activity.type];
          const Icon = config.icon;

          return (
            <div
              key={activity.id}
              className={cn(
                'flex items-start gap-4 px-5 py-4',
                'hover:bg-muted/30 transition-colors cursor-pointer',
                'animate-fade-in'
              )}
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <div
                className={cn(
                  'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg',
                  config.bgColor
                )}
              >
                <Icon className={cn('h-4 w-4', config.color)} />
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground">{activity.title}</p>
                {activity.description && (
                  <p className="text-sm text-muted-foreground truncate mt-0.5">
                    {activity.description}
                  </p>
                )}
              </div>

              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {formatDistanceToNow(activity.timestamp, { addSuffix: true })}
              </span>
            </div>
          );
        })}
      </div>

      {activities.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <div className="h-12 w-12 rounded-xl bg-muted flex items-center justify-center mb-3">
            <FileText className="h-6 w-6 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium text-foreground">No recent activity</p>
          <p className="text-xs text-muted-foreground mt-1">
            Your actions will appear here
          </p>
        </div>
      )}
    </div>
  );
}
