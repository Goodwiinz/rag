import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Folder, CheckCircle, RefreshCw, AlertTriangle, LucideIcon } from 'lucide-react';

interface StatItem {
  label: string;
  value: number;
  color: string;
  icon: LucideIcon;
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
    { label: 'TOTAL_DOCS', value: stats.total, color: 'var(--terminal-text)', icon: Folder },
    { label: 'INDEXED', value: stats.visible_indexed, color: 'var(--phosphor-green)', icon: CheckCircle },
    { label: 'PROCESSING', value: stats.visible_processing, color: 'var(--cyan)', icon: RefreshCw },
    { label: 'FAILED', value: stats.visible_failed, color: '#ff4757', icon: AlertTriangle },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {statItems.map((stat) => (
        <Card 
          key={stat.label} 
          className="border-[var(--terminal-border)] bg-[var(--terminal-surface)]/50 backdrop-blur-sm relative overflow-hidden group hover:border-[var(--terminal-border-glow)] transition-colors shadow-none"
        >
          <div 
            className="absolute top-0 left-0 w-0.5 h-full opacity-50 group-hover:opacity-100 transition-all duration-500" 
            style={{ backgroundColor: stat.color }} 
          />
          <CardHeader className="p-4 pb-2">
            <div className="flex justify-between items-start">
              <stat.icon className="w-4 h-4 opacity-50" style={{ color: stat.color }} />
              <div className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest">
                {stat.label}
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <div className="text-2xl font-mono font-bold text-[var(--terminal-text)]">
              {stat.value}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
