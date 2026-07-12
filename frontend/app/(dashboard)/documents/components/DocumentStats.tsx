import { FolderOpen, CheckCircle2, Loader, AlertTriangle } from 'lucide-react';

interface DocumentStatsProps {
  stats: {
    total: number;
    visible_indexed: number;
    visible_processing: number;
    visible_failed: number;
  };
}

export function DocumentStats({ stats }: DocumentStatsProps) {
  return (
    <div className="inline-flex items-center gap-4 flex-wrap">
      <StatPill
        icon={FolderOpen}
        value={stats.total}
        label="Total"
        color="text-muted-foreground"
        bg="bg-muted"
      />
      <StatPill
        icon={CheckCircle2}
        value={stats.visible_indexed}
        label="Indexed"
        color="text-[var(--nous-terra)]"
        bg="bg-[var(--nous-terra)]/10"
      />
      <StatPill
        icon={Loader}
        value={stats.visible_processing}
        label="Processing"
        color="text-[var(--nous-helios)]"
        bg="bg-[var(--nous-helios)]/10"
      />
      <StatPill
        icon={AlertTriangle}
        value={stats.visible_failed}
        label="Failed"
        color="text-[var(--nous-mars)]"
        bg="bg-[var(--nous-mars)]/10"
      />
    </div>
  );
}

function StatPill({
  icon: Icon,
  value,
  label,
  color,
  bg,
}: {
  icon: typeof FolderOpen;
  value: number;
  label: string;
  color: string;
  bg: string;
}) {
  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg ${bg} ${color}`}>
      <Icon aria-hidden="true" className="w-3.5 h-3.5" />
      <span className="text-sm font-semibold tabular-nums">{value}</span>
      <span className="text-xs opacity-70">{label}</span>
    </div>
  );
}
