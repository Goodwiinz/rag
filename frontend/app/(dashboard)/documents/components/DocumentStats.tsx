import { Card, CardContent } from '@/components/ui/card';
import {
  FolderOpen,
  CheckCircle2,
  Loader,
  AlertTriangle,
  LucideIcon,
} from 'lucide-react';

interface StatItem {
  label: string;
  value: number;
  icon: LucideIcon;
  iconClass: string;
}

interface DocumentStatsProps {
  stats: {
    total: number;
    visible_indexed: number;
    visible_processing: number;
    visible_failed: number;
  };
}

export function DocumentStats({ stats }: DocumentStatsProps) {
  const statItems: StatItem[] = [
    {
      label: 'Total documents',
      value: stats.total,
      icon: FolderOpen,
      iconClass: 'text-primary',
    },
    {
      label: 'Indexed',
      value: stats.visible_indexed,
      icon: CheckCircle2,
      iconClass: 'text-[var(--nous-terra)]',
    },
    {
      label: 'Processing',
      value: stats.visible_processing,
      icon: Loader,
      iconClass: 'text-[var(--nous-helios)]',
    },
    {
      label: 'Failed',
      value: stats.visible_failed,
      icon: AlertTriangle,
      iconClass: 'text-[var(--nous-mars)]',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {statItems.map((stat) => (
        <Card key={stat.label} className="border-border bg-card shadow-sm">
          <CardContent className="p-5">
            <div className="flex items-start justify-between mb-4">
              <div className="p-2 rounded-lg bg-muted">
                <stat.icon
                  aria-hidden="true"
                  className={`w-4 h-4 ${stat.iconClass}`}
                />
              </div>
            </div>
            <div className="text-2xl font-semibold text-foreground tabular-nums">
              {stat.value}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {stat.label}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
