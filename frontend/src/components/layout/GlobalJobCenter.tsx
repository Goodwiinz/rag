'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Bell, Loader2 } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { entityService, ProcessingJobStatus } from '@/services/entityService';
import { useAuthStore } from '@/stores/authStore';

const isActive = (status: string) =>
  ['queued', 'running', 'retrying'].includes(status);

export function GlobalJobCenter() {
  const [jobs, setJobs] = useState<ProcessingJobStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isAuthLoading = useAuthStore((state) => state.isLoading);

  const fetchJobs = async () => {
    try {
      setLoading(true);
      const response = await entityService.listProcessingJobs({
        limit: 15,
        offset: 0,
      });
      setJobs(response.jobs || []);
    } catch {
      // Keep silent for unauthenticated pages.
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthLoading) {
      return;
    }

    if (!isAuthenticated) {
      setJobs([]);
      setLoading(false);
      return;
    }

    fetchJobs();
    const interval = setInterval(fetchJobs, 3000);
    return () => clearInterval(interval);
  }, [isAuthenticated, isAuthLoading]);

  const activeJobs = useMemo(
    () => jobs.filter((job) => isActive(job.status)),
    [jobs]
  );
  const recentJobs = useMemo(() => jobs.slice(0, 10), [jobs]);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          aria-label="Open job center"
          className="relative h-8 px-2 font-mono text-xs text-[#a1a1aa] hover:text-[#fafafa]"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Bell className="w-4 h-4" />
          )}
          {activeJobs.length > 0 && (
            <span className="absolute -top-1 -right-1 rounded-full bg-sol text-[#080808] text-[10px] w-4 h-4 flex items-center justify-center">
              {activeJobs.length}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="w-[360px] bg-[#0A0A0A] border-[#1A1A1A] text-[#fafafa]"
      >
        <DropdownMenuLabel className="font-mono text-xs uppercase tracking-wider text-sol">
          Job Center
        </DropdownMenuLabel>
        <DropdownMenuSeparator className="bg-[#1A1A1A]" />
        <div className="max-h-96 overflow-y-auto px-2 py-1 space-y-2">
          {recentJobs.length === 0 && (
            <p className="text-xs font-mono text-[#71717a] px-2 py-2">
              No background jobs yet.
            </p>
          )}
          {recentJobs.map((job) => (
            <div key={job.id} className="rounded border border-[#1A1A1A] p-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-mono text-[#d4d4d8] truncate">
                  {job.job_type}
                </span>
                <span className="text-[10px] font-mono uppercase text-[#71717a]">
                  {job.status}
                </span>
              </div>
              <div className="mt-1 text-[10px] font-mono text-[#71717a]">
                {Math.round(job.progress_percentage || 0)}% ·{' '}
                {job.current_step || 'Pending'}
              </div>
            </div>
          ))}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
