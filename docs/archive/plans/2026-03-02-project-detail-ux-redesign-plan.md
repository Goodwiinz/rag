# Project Detail Page UX/UI Redesign - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Overhaul the `/projects/[id]` page from Terminal Observatory aesthetic to modern dark (Vercel/Linear-style) with richer document interactions, better hierarchy, and proper use of shadcn/ui tokens.

**Architecture:** Refactor the monolithic 912-line `page.tsx` by extracting header, tabs, and document list into dedicated components. Replace hardcoded hex colors with CSS variable tokens. Add multi-select, sort, and search to the document list.

**Tech Stack:** Next.js 15, React 18, TypeScript, shadcn/ui (Badge, Breadcrumb, Checkbox, DropdownMenu, Select, Input, IconButton), Tailwind CSS, Zustand (projectStore), Lucide icons.

---

### Task 1: Add dark-mode Badge variants

**Files:**

- Modify: `frontend/src/components/ui/badge.tsx`

**Step 1: Update badge variants for dark mode**

The current `success`, `warning`, `info` variants use light-mode colors (green-100, yellow-100, blue-100). Add dark-appropriate variants:

```tsx
// In badgeVariants, replace the success/warning/info variants:
success:
  "border-transparent bg-emerald-500/15 text-emerald-400",
warning:
  "border-transparent bg-amber-500/15 text-amber-400",
info:
  "border-transparent bg-sky-500/15 text-sky-400",
```

**Step 2: Verify no regressions**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

**Step 3: Commit**

```bash
git add frontend/src/components/ui/badge.tsx
git commit -m "style: update Badge success/warning/info variants for dark theme"
```

---

### Task 2: Extract ProjectHeader component

**Files:**

- Create: `frontend/src/components/research/ProjectHeader.tsx`
- Modify: `frontend/app/(dashboard)/projects/[id]/page.tsx`

**Step 1: Create ProjectHeader component**

```tsx
"use client";

import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  FileText,
  BookOpen,
  StickyNote,
  Sparkles,
  Calendar,
  Clock,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { Project } from "@/services/projectService";

interface ProjectHeaderProps {
  project: Project;
}

const statusVariant: Record<
  string,
  "success" | "warning" | "info" | "secondary"
> = {
  active: "success",
  paused: "warning",
  completed: "info",
  archived: "secondary",
};

const typeLabels: Record<string, string> = {
  research: "Research",
  literature_review: "Literature Review",
  thesis: "Thesis",
  paper: "Paper",
};

function formatRelativeDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return `${Math.abs(diffDays)}d overdue`;
  if (diffDays === 0) return "Due today";
  if (diffDays <= 7) return `Due in ${diffDays}d`;
  if (diffDays <= 30) return `Due in ${Math.round(diffDays / 7)}w`;
  return `Due ${date.toLocaleDateString()}`;
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg bg-muted/50 px-4 py-3">
      <div className="text-muted-foreground">{icon}</div>
      <div>
        <p className="text-lg font-semibold text-foreground">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

export function ProjectHeader({ project }: ProjectHeaderProps) {
  const router = useRouter();

  return (
    <div className="mb-8 space-y-4">
      {/* Back link */}
      <button
        onClick={() => router.push("/projects")}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Projects
      </button>

      {/* Hero card */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          {/* Left: Title + metadata */}
          <div className="min-w-0 flex-1 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight text-foreground">
                {project.name}
              </h1>
              {project.project_type && (
                <Badge variant="outline" className="text-xs">
                  {typeLabels[project.project_type] || project.project_type}
                </Badge>
              )}
              {project.research_status && (
                <Badge
                  variant={
                    statusVariant[project.research_status] || "secondary"
                  }
                  className="text-xs capitalize"
                >
                  {project.research_status}
                </Badge>
              )}
            </div>

            {project.description && (
              <p className="text-sm text-muted-foreground leading-relaxed max-w-2xl">
                {project.description}
              </p>
            )}

            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              {project.deadline && (
                <span className="inline-flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  {formatRelativeDate(project.deadline)}
                </span>
              )}
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3 w-3" />
                Created {new Date(project.created_at).toLocaleDateString()}
              </span>
            </div>

            {project.tags && project.tags.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {project.tags.map((tag) => (
                  <Badge
                    key={tag}
                    variant="secondary"
                    className="text-xs font-normal"
                  >
                    {tag}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Right: Stats grid */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 shrink-0">
            <StatCard
              icon={<FileText className="h-4 w-4" />}
              label="Documents"
              value={project.document_count || 0}
            />
            <StatCard
              icon={<BookOpen className="h-4 w-4" />}
              label="Citations"
              value={project.citation_count || 0}
            />
            <StatCard
              icon={<StickyNote className="h-4 w-4" />}
              label="Notes"
              value={project.note_count || 0}
            />
            <StatCard
              icon={<Sparkles className="h-4 w-4" />}
              label="Drafts"
              value={project.draft_count || 0}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Wire ProjectHeader into page.tsx**

In `page.tsx`, replace the header section (lines 360-383) with:

```tsx
import { ProjectHeader } from "@/components/research/ProjectHeader";

// ... in the return, replace the header div:
<ProjectHeader project={currentProject} />;
```

Remove the `ArrowLeft` import if no longer used elsewhere in the file.

**Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

**Step 4: Commit**

```bash
git add frontend/src/components/research/ProjectHeader.tsx frontend/app/\(dashboard\)/projects/\[id\]/page.tsx
git commit -m "feat: extract ProjectHeader component with hero card, stats, and metadata badges"
```

---

### Task 3: Modernize Tab Navigation

**Files:**

- Modify: `frontend/app/(dashboard)/projects/[id]/page.tsx`

**Step 1: Replace tab bar with modern design**

Replace the tab navigation section (lines 398-466) with a cleaner implementation that uses:

- Count badges on each tab
- Filled background for active state (not just bottom border)
- Visual gap between content tabs and tool tabs
- Sans-serif typography (remove `font-mono`)

```tsx
{
  /* Tabs */
}
<div className="flex items-center gap-1 mb-6 border-b border-border">
  {[
    {
      id: "documents" as TabType,
      label: "Documents",
      icon: FileText,
      count: projectDocuments.length,
    },
    {
      id: "notes" as TabType,
      label: "Notes",
      icon: StickyNote,
      count: projectNotes.length,
    },
    { id: "bibliography" as TabType, label: "Bibliography", icon: BookOpen },
    {
      id: "drafts" as TabType,
      label: "Drafts",
      icon: Sparkles,
      count: draftVersions.length || undefined,
    },
    { id: "chat" as TabType, label: "Chat", icon: MessageSquare },
    { id: "matrix" as TabType, label: "Matrix", icon: Grid3X3 },
  ].map((tab, index) => (
    <React.Fragment key={tab.id}>
      {index === 3 && <div className="w-px h-5 bg-border mx-1" />}
      <button
        onClick={() => handleTabChange(tab.id)}
        className={`relative flex items-center gap-2 px-3 py-2.5 text-sm rounded-t-md transition-colors ${
          activeTab === tab.id
            ? "text-foreground bg-muted/60 border-b-2 border-primary"
            : "text-muted-foreground hover:text-foreground hover:bg-muted/30"
        }`}
      >
        <tab.icon className="h-4 w-4" />
        {tab.label}
        {tab.count !== undefined && tab.count > 0 && (
          <span
            className={`ml-1 text-xs rounded-full px-1.5 py-0.5 ${
              activeTab === tab.id
                ? "bg-primary/15 text-primary"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {tab.count}
          </span>
        )}
      </button>
    </React.Fragment>
  ))}
</div>;
```

Add `import React from 'react'` if not already a default import (it's imported as `{ useEffect, useState, useCallback }` — need to add `Fragment`).

**Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

**Step 3: Commit**

```bash
git add frontend/app/\(dashboard\)/projects/\[id\]/page.tsx
git commit -m "style: modernize tab navigation with count badges, filled active state, and visual grouping"
```

---

### Task 4: Extract DocumentList component with search, sort, and multi-select

**Files:**

- Create: `frontend/src/components/research/DocumentList.tsx`
- Modify: `frontend/app/(dashboard)/projects/[id]/page.tsx`

**Step 1: Create DocumentList component**

```tsx
"use client";

import { useState, useMemo, useCallback } from "react";
import {
  FileText,
  Search,
  Trash2,
  MoreHorizontal,
  ArrowUpDown,
  ExternalLink,
  X,
  File,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { IconButton } from "@/components/ui/icon-button";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ProjectDocument } from "@/services/projectService";

interface DocumentListProps {
  documents: ProjectDocument[];
  loading: boolean;
  onRemove: (documentId: string) => void;
}

type SortKey = "title" | "added_at";
type SortDir = "asc" | "desc";

const statusConfig: Record<
  string,
  { label: string; variant: "success" | "warning" | "info" | "secondary" }
> = {
  completed: { label: "Indexed", variant: "success" },
  indexed: { label: "Indexed", variant: "success" },
  processing: { label: "Processing", variant: "warning" },
  pending: { label: "Queued", variant: "info" },
  queued: { label: "Queued", variant: "info" },
  failed: { label: "Failed", variant: "secondary" },
};

function getFileIcon(filename?: string) {
  if (!filename) return <FileText className="h-5 w-5" />;
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "pdf") return <File className="h-5 w-5 text-red-400" />;
  return <FileText className="h-5 w-5" />;
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export function DocumentList({
  documents,
  loading,
  onRemove,
}: DocumentListProps) {
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("added_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const filtered = useMemo(() => {
    let result = documents;
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (doc) =>
          (doc.document?.title || "").toLowerCase().includes(q) ||
          (doc.document?.filename || "").toLowerCase().includes(q),
      );
    }
    result = [...result].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "title") {
        cmp = (a.document?.title || "").localeCompare(b.document?.title || "");
      } else {
        cmp =
          new Date(a.added_at || a.document?.created_at || 0).getTime() -
          new Date(b.added_at || b.document?.created_at || 0).getTime();
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return result;
  }, [documents, search, sortKey, sortDir]);

  const allSelected =
    filtered.length > 0 &&
    filtered.every((d) => selectedIds.has(d.document_id));

  const toggleAll = useCallback(() => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map((d) => d.document_id)));
    }
  }, [allSelected, filtered]);

  const toggleOne = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleBulkRemove = useCallback(() => {
    if (!confirm(`Remove ${selectedIds.size} document(s) from the project?`))
      return;
    selectedIds.forEach((id) => onRemove(id));
    setSelectedIds(new Set());
  }, [selectedIds, onRemove]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 rounded-xl border border-dashed border-border">
        <FileText className="h-10 w-10 text-muted-foreground/40 mb-3" />
        <p className="text-sm font-medium text-muted-foreground">
          No documents yet
        </p>
        <p className="text-xs text-muted-foreground/60 mt-1">
          Add documents from the Documents page
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search documents..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9 text-sm"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        <Select
          value={`${sortKey}-${sortDir}`}
          onValueChange={(v) => {
            const [k, d] = v.split("-") as [SortKey, SortDir];
            setSortKey(k);
            setSortDir(d);
          }}
        >
          <SelectTrigger className="w-[160px] h-9 text-sm">
            <ArrowUpDown className="h-3.5 w-3.5 mr-2 text-muted-foreground" />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="added_at-desc">Newest first</SelectItem>
            <SelectItem value="added_at-asc">Oldest first</SelectItem>
            <SelectItem value="title-asc">Name A-Z</SelectItem>
            <SelectItem value="title-desc">Name Z-A</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Bulk action bar */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg bg-primary/10 border border-primary/20 px-4 py-2.5">
          <span className="text-sm font-medium text-primary">
            {selectedIds.size} selected
          </span>
          <div className="flex-1" />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSelectedIds(new Set())}
            className="text-muted-foreground hover:text-foreground text-xs"
          >
            Clear
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleBulkRemove}
            className="text-destructive hover:text-destructive hover:bg-destructive/10 text-xs"
          >
            <Trash2 className="h-3.5 w-3.5 mr-1.5" />
            Remove
          </Button>
        </div>
      )}

      {/* Column header */}
      <div className="flex items-center gap-3 px-4 py-2 text-xs text-muted-foreground">
        <Checkbox
          checked={allSelected}
          onCheckedChange={toggleAll}
          aria-label="Select all documents"
        />
        <span className="flex-1">Document</span>
        <span className="w-24 text-right">Status</span>
        <span className="w-24 text-right">Added</span>
        <span className="w-10" />
      </div>

      {/* Document rows */}
      <div className="space-y-1">
        {filtered.map((doc) => {
          const status =
            statusConfig[(doc.document?.status || "").toLowerCase()];
          return (
            <div
              key={doc.id}
              className={`group flex items-center gap-3 rounded-lg border px-4 py-3 transition-all ${
                selectedIds.has(doc.document_id)
                  ? "border-primary/30 bg-primary/5"
                  : "border-border bg-card hover:bg-muted/30 hover:border-border"
              }`}
            >
              <Checkbox
                checked={selectedIds.has(doc.document_id)}
                onCheckedChange={() => toggleOne(doc.document_id)}
                aria-label={`Select ${doc.document?.title || "document"}`}
              />
              <div className="text-muted-foreground shrink-0">
                {getFileIcon(doc.document?.filename)}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground truncate">
                  {doc.document?.title || doc.document?.filename || "Untitled"}
                </p>
                {doc.document?.filename && doc.document?.title && (
                  <p className="text-xs text-muted-foreground truncate font-mono">
                    {doc.document.filename}
                  </p>
                )}
              </div>
              <div className="w-24 text-right shrink-0">
                {status ? (
                  <Badge variant={status.variant} className="text-[10px]">
                    {status.label}
                  </Badge>
                ) : (
                  <span className="text-xs text-muted-foreground">
                    {doc.document?.status || "—"}
                  </span>
                )}
              </div>
              <div className="w-24 text-right shrink-0">
                <span className="text-xs text-muted-foreground">
                  {formatRelativeTime(
                    doc.added_at ||
                      doc.document?.created_at ||
                      new Date().toISOString(),
                  )}
                </span>
              </div>
              <div className="w-10 shrink-0 flex justify-end">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <IconButton
                      icon={<MoreHorizontal className="h-4 w-4" />}
                      label="Document actions"
                      variant="ghost"
                      className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                    />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onClick={() =>
                        window.open(`/documents/${doc.document_id}`, "_blank")
                      }
                    >
                      <ExternalLink className="h-4 w-4 mr-2" />
                      View document
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        if (confirm("Remove this document from the project?")) {
                          onRemove(doc.document_id);
                        }
                      }}
                      className="text-destructive focus:text-destructive"
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Remove from project
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          );
        })}
      </div>

      {/* Search no results */}
      {search && filtered.length === 0 && (
        <div className="text-center py-8">
          <p className="text-sm text-muted-foreground">
            No documents matching &quot;{search}&quot;
          </p>
        </div>
      )}
    </div>
  );
}
```

**Step 2: Wire DocumentList into page.tsx**

Replace the entire Documents tab content (lines 471-523) with:

```tsx
import { DocumentList } from "@/components/research/DocumentList";

// In the documents tab section:
{
  activeTab === "documents" && (
    <DocumentList
      documents={projectDocuments}
      loading={documentsLoading}
      onRemove={(documentId) => {
        void handleRemoveDocument(documentId);
      }}
    />
  );
}
```

Remove `Trash2` from page.tsx imports if no longer used there.

**Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

**Step 4: Commit**

```bash
git add frontend/src/components/research/DocumentList.tsx frontend/app/\(dashboard\)/projects/\[id\]/page.tsx
git commit -m "feat: extract DocumentList with search, sort, multi-select, and context menu"
```

---

### Task 5: Modernize remaining page typography and styling

**Files:**

- Modify: `frontend/app/(dashboard)/projects/[id]/page.tsx`

**Step 1: Replace hardcoded hex colors and font-mono throughout**

Across the remaining tab content (Notes toolbar, Bibliography section, Drafts section, error display), do a sweep to:

1. Replace `bg-[#0a0a0a]` → `bg-card`
2. Replace `border-[#1a1a1a]` → `border-border`
3. Replace `border-[#333]` → `border-border`
4. Replace `text-gray-400` → `text-muted-foreground`
5. Replace `text-gray-500` → `text-muted-foreground`
6. Replace `text-gray-600` → `text-muted-foreground/60`
7. Replace `text-gray-300` → `text-foreground`
8. Replace `text-gray-200` → `text-foreground`
9. Replace `text-[#00ff9f]` → `text-primary`
10. Replace `bg-[#00ff9f]/10` → `bg-primary/10`
11. Replace `border-[#00ff9f]/30` → `border-primary/30`
12. Replace `hover:bg-[#00ff9f]/20` → `hover:bg-primary/20`
13. Replace `bg-[#1a1a1a]` → `bg-muted`
14. Replace `hover:border-[#555]` → `hover:border-muted-foreground/30`
15. Replace `hover:border-[#333]` → `hover:border-border`
16. Replace `bg-red-500/10 border border-red-500/30` → `bg-destructive/10 border border-destructive/30`
17. Replace `text-red-400` → `text-destructive`
18. Remove `font-mono` from non-technical text (keep it on bibliography `<pre>`, filenames, version numbers)

**Step 2: Update the Notes tab "New Note" button styling**

Replace:

```tsx
className =
  "flex items-center gap-2 px-4 py-2 bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30 rounded font-mono text-sm hover:bg-[#00ff9f]/20 transition-colors";
```

With:

```tsx
className =
  "flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary border border-primary/30 rounded-md text-sm hover:bg-primary/20 transition-colors";
```

**Step 3: Update the Bibliography section similarly**

Replace hardcoded hex in the format select, download button, bibliography container, and empty state.

**Step 4: Update Drafts section**

Replace hex values in the drafts container, version selector, compare panel, and empty state.

**Step 5: Update the loading spinner**

Replace:

```tsx
<Loader2 className="h-8 w-8 animate-spin text-[#00ff9f]" />
```

With:

```tsx
<div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
```

And all other Loader2 spinners similarly, or keep Loader2 but use `text-primary`.

**Step 6: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

**Step 7: Commit**

```bash
git add frontend/app/\(dashboard\)/projects/\[id\]/page.tsx
git commit -m "style: replace hardcoded hex colors with CSS tokens and modernize typography"
```

---

### Task 6: Update breadcrumb in layout (if applicable)

**Files:**

- Explore: `frontend/app/(dashboard)/layout.tsx` or whichever layout renders the breadcrumb seen in the screenshot (`Dashboard / Projects / <UUID>`)

**Step 1: Investigate where the top breadcrumb is rendered**

Search for the breadcrumb that shows `Dashboard / Projects / 42e805e9...` in the screenshot. It's likely in the dashboard layout or a shared header component.

Run: `grep -r "breadcrumb\|Breadcrumb\|BreadcrumbList" frontend/app/ frontend/src/components/ --include="*.tsx" -l`

**Step 2: Update to show project name instead of UUID**

The breadcrumb should display `Dashboard / Projects / Test Project for Chat Integration` (truncated if needed) instead of the raw project ID. This may require passing the project name via route params, a layout context, or reading from the project store.

**Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

**Step 4: Commit**

```bash
git commit -am "fix: show project name instead of UUID in breadcrumb"
```

---

### Task 7: Visual QA and final polish

**Files:**

- Modify: Any files touched in previous tasks as needed

**Step 1: Run dev server and visually verify**

Run: `cd frontend && npm run dev`

Check:

- [ ] Header hero card renders with title, badges, stats
- [ ] Tab count badges show correct numbers
- [ ] Tab visual grouping with separator between Bibliography and Drafts
- [ ] Document list search filters correctly
- [ ] Document list sort changes order
- [ ] Multi-select works, bulk action bar appears
- [ ] Context menu (three-dot) appears on hover
- [ ] No hardcoded hex colors remaining (search for `#00ff9f`, `#0a0a0a`, `#1a1a1a`, `#333`)
- [ ] All text is sans-serif except filenames, code, bibliography pre
- [ ] Empty states look clean with dashed borders

**Step 2: Type-check + lint**

Run: `cd frontend && npm run type-check && npm run lint`
Expected: PASS

**Step 3: Final commit**

```bash
git commit -am "polish: final visual QA fixes for project detail redesign"
```
