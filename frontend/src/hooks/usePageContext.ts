'use client';

import { useMemo } from 'react';
import { usePathname } from 'next/navigation';
import { useProjectStore } from '@/store/projectStore';
import type { PageContext, PageContextType } from '@/types/agent-chat';

const PATH_CONTEXT_MAP: Record<
  string,
  { type: PageContextType; label: string }
> = {
  '/': { type: 'overview', label: 'Overview' },
  '/dashboard': { type: 'overview', label: 'Overview' },
  '/documents': { type: 'documents', label: 'Documents' },
  '/arxiv': { type: 'arxiv', label: 'ArXiv Papers' },
  '/chat': { type: 'chat', label: 'Chat' },
  '/research': { type: 'research', label: 'Research' },
  '/analytics': { type: 'analytics', label: 'Analytics' },
  '/diagnostics': { type: 'diagnostics', label: 'Diagnostics' },
  '/settings': { type: 'settings', label: 'Settings' },
  '/upload': { type: 'upload', label: 'Upload' },
  '/entities': { type: 'entities', label: 'Entities' },
};

export function usePageContext(): PageContext {
  const pathname = usePathname();
  const currentProject = useProjectStore((s) => s.currentProject);

  return useMemo(() => {
    if (!pathname) {
      return { type: 'unknown' as PageContextType, label: 'Dashboard' };
    }

    // Project pages: /projects/:id or /projects/:id/...
    const projectMatch = pathname.match(/^\/projects\/([^/]+)(?:\/(.+))?/);
    if (projectMatch) {
      const projectId = projectMatch[1];
      const subPath = projectMatch[2] || '';

      // Detect active tab from URL or DOM
      let activeTab = 'documents'; // default tab
      if (subPath) {
        activeTab = subPath.split('/')[0];
      }

      return {
        type: 'project' as PageContextType,
        label: currentProject?.name || 'Project',
        projectId,
        projectName: currentProject?.name,
        metadata: {
          activeTab,
          documentCount: currentProject?.document_count,
          description: currentProject?.description,
        },
      };
    }

    // Direct path match
    const match = PATH_CONTEXT_MAP[pathname];
    if (match) {
      return { ...match };
    }

    // Prefix match for nested routes (e.g., /chat/thread-id)
    for (const [path, ctx] of Object.entries(PATH_CONTEXT_MAP)) {
      if (path !== '/' && pathname.startsWith(path + '/')) {
        return { ...ctx };
      }
    }

    return { type: 'unknown' as PageContextType, label: 'Dashboard' };
  }, [pathname, currentProject]);
}
