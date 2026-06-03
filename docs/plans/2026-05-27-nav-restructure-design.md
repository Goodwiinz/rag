# Navigation Restructure Design

**Date:** 2026-05-27
**Status:** Approved

## Problem

- `/projects` and `/research` are aliases (same page) but both appear in sidebar nav
- `/research-engine` (visual blueprint/graph editor) has no nav entry
- ArXiv Papers missing from AppRail
- DOCUMENTS and RESEARCH sections are conceptually one group

## Decision

Merge DOCUMENTS + RESEARCH into a single **KNOWLEDGE** section. Remove the Projects alias from nav. Surface Research Engine and ArXiv in both sidebar and rail.

## AppSidebar — Section Layout

```
// MAIN
  Overview        /dashboard       LayoutDashboard
  Chat            /chat            MessageSquare
  Search          /search          Search

// KNOWLEDGE
  Documents       /documents       Files
  Upload          /documents/upload Upload
  ArXiv Papers    /arxiv           BookOpen
  Entities        /entities        Network
  Research        /research        FolderKanban
  Research Engine /research-engine Workflow

// SYSTEM
  Analytics       /analytics       BarChart3
  Diagnostics     /diagnostics     Activity
  Settings        /settings        Settings
```

Changes from current:

- DOCUMENTS + RESEARCH → KNOWLEDGE
- "All Documents" → "Documents"
- Projects entry removed (alias of Research)
- Research Engine added (icon: Workflow)

## AppRail — Icon Layout

```
[N]  Brand mark
───  divider
Overview      LayoutGrid
Chat          MessageSquare
Documents     FileText
Search        Search
───  divider
ArXiv         BookOpen          (new)
KG            Network
Research      FlaskConical      (was Projects/FolderOpen)
Res. Engine   Workflow          (new)
───  divider
Analytics     BarChart3
Bell          (BellPopover)
Settings      Settings
───  spacer
[Avatar]
```

## Breadcrumb Map

Add `'research-engine': 'Research Engine'` to `pathNameMap` in SidebarLayout.tsx.

## Icon Rationale

| Item            | Icon         | Reason                                            |
| --------------- | ------------ | ------------------------------------------------- |
| Research        | FlaskConical | Lab/research metaphor, distinct from folder icons |
| Research Engine | Workflow     | Visual graph/blueprint tool — flow diagram icon   |
| ArXiv           | BookOpen     | Consistent with sidebar                           |

## Files Changed

1. `frontend/src/components/layout/AppSidebar.tsx` — merge sections, remove Projects, add Research Engine
2. `frontend/src/components/layout/AppRail.tsx` — add ArXiv, swap Projects→Research, add Research Engine, add dividers
3. `frontend/src/components/layout/SidebarLayout.tsx` — add research-engine to breadcrumb map
