'use client';

import Link from 'next/link';
import { ArrowRight, FolderOpen, GitBranch, Unlink } from 'lucide-react';
import { ProjectPickerPopover } from './ProjectPickerPopover';

interface ProjectBindingCardProps {
  projectId?: string;
  projectName?: string | null;
  workspaceName?: string | null;
  fileCount?: number;
  threadLabel?: string | null;
  threadId?: string | null;
  workspaceId?: string;
  onProjectBound?: (projectId: string, projectName: string) => void;
}

export function ProjectBindingCard({
  projectId,
  projectName,
  workspaceName,
  fileCount,
  threadLabel,
  threadId,
  workspaceId,
  onProjectBound,
}: ProjectBindingCardProps) {
  const isBound = Boolean(projectId);

  return (
    <section
      className={
        'relative overflow-hidden border bg-[var(--nous-bg-2)] dark:bg-[var(--nous-obsidian)] rounded-lg ' +
        (isBound
          ? 'border-[rgba(212,160,57,0.25)] dark:border-[rgba(232,184,74,0.3)]'
          : 'border-[var(--nous-border-1)] dark:border-[var(--nous-shade)]')
      }
    >
      {isBound && (
        <span
          aria-hidden
          className="absolute left-0 top-0 bottom-0 w-[2px] bg-[var(--nous-sol)] dark:bg-[var(--nous-helios)]"
        />
      )}

      <div className="px-3.5 py-3">
        <div className="flex items-center justify-between mb-2">
          <span
            className="text-[9px] uppercase text-[var(--nous-fg-3)]"
            style={{
              fontFamily: 'var(--nous-font-mono)',
              letterSpacing: '0.22em',
            }}
          >
            {isBound ? 'Bound to project' : 'Detached chat'}
          </span>
          {threadLabel && (
            <span
              className="text-[9px] text-[var(--nous-fg-3)] tabular-nums"
              style={{
                fontFamily: 'var(--nous-font-mono)',
                letterSpacing: '0.06em',
              }}
            >
              {threadLabel}
            </span>
          )}
        </div>

        <div className="flex items-start gap-2.5">
          <span
            className={
              'mt-[2px] grid place-items-center h-7 w-7 shrink-0 rounded-md ' +
              (isBound
                ? 'bg-[var(--nous-aurum)] dark:bg-[var(--nous-ember)] text-[var(--nous-sol-safe)] dark:text-[var(--nous-helios)] border border-[rgba(212,160,57,0.25)]'
                : 'bg-[var(--nous-bg-1)] dark:bg-[var(--nous-nyx)] text-[var(--nous-fg-3)] border border-[var(--nous-border-1)] dark:border-[var(--nous-shade)]')
            }
          >
            {isBound ? (
              <FolderOpen className="h-3.5 w-3.5" strokeWidth={1.7} />
            ) : (
              <Unlink className="h-3.5 w-3.5" strokeWidth={1.7} />
            )}
          </span>
          <div className="flex-1 min-w-0">
            <p
              className="text-[14px] font-semibold truncate text-[var(--nous-fg-1)]"
              style={{
                fontFamily: 'var(--nous-font-ui)',
                letterSpacing: '-0.005em',
              }}
            >
              {isBound
                ? projectName || 'Untitled project'
                : 'No project attached'}
            </p>
            <p
              className="text-[10px] mt-0.5 truncate text-[var(--nous-fg-3)]"
              style={{
                fontFamily: 'var(--nous-font-mono)',
                letterSpacing: '0.04em',
              }}
            >
              {isBound ? (
                <>
                  {fileCount != null && (
                    <>
                      {fileCount} file{fileCount === 1 ? '' : 's'}
                    </>
                  )}
                  {fileCount != null && workspaceName && (
                    <span className="px-1.5 opacity-50">·</span>
                  )}
                  {workspaceName && <>{workspaceName}</>}
                </>
              ) : (
                <>Chat is not anchored to any working set</>
              )}
            </p>
          </div>
        </div>

        {isBound ? (
          <Link
            href={`/projects/${projectId}`}
            className="mt-3 inline-flex items-center gap-1 text-[11px] font-medium text-[var(--nous-sol-safe)] dark:text-[var(--nous-helios)] hover:opacity-80 transition-opacity group"
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          >
            <GitBranch className="h-3 w-3" strokeWidth={1.7} />
            View project
            <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
          </Link>
        ) : threadId && onProjectBound ? (
          <ProjectPickerPopover
            threadId={threadId}
            workspaceId={workspaceId}
            onProjectBound={onProjectBound}
          >
            <button
              className="mt-3 inline-flex items-center justify-center gap-1.5 w-full py-1.5 px-2.5 rounded-md bg-[var(--nous-erebus)] dark:bg-[var(--nous-umber)] dark:border dark:border-[var(--nous-shade)] text-white text-[11px] font-semibold hover:-translate-y-px hover:shadow-sm transition-all"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Attach to a project
              <ArrowRight className="h-3 w-3" />
            </button>
          </ProjectPickerPopover>
        ) : (
          <Link
            href="/projects"
            className="mt-3 inline-flex items-center justify-center gap-1.5 w-full py-1.5 px-2.5 rounded-md bg-[var(--nous-erebus)] dark:bg-[var(--nous-umber)] dark:border dark:border-[var(--nous-shade)] text-white text-[11px] font-semibold hover:-translate-y-px hover:shadow-sm transition-all"
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          >
            Attach to a project
            <ArrowRight className="h-3 w-3" />
          </Link>
        )}
      </div>
    </section>
  );
}
