# Navigation Restructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Merge DOCUMENTS + RESEARCH sidebar sections into KNOWLEDGE, remove Projects alias, surface Research Engine and ArXiv in both sidebar and rail.

**Architecture:** Three-file edit — nav data arrays + imports in AppSidebar, rail buttons + imports in AppRail, breadcrumb map in SidebarLayout. No new components or routes.

**Tech Stack:** React, Next.js, lucide-react icons, Tailwind CSS

---

### Task 1: Update AppSidebar imports and nav arrays

**Files:**

- Modify: `frontend/src/components/layout/AppSidebar.tsx:26-68`

**Step 1: Replace icon imports**

In `AppSidebar.tsx`, replace the lucide-react import block (lines 26-44) with:

```tsx
import {
  Activity,
  BarChart3,
  Bell,
  BookOpen,
  ChevronsUpDown,
  Files,
  FolderKanban,
  HelpCircle,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Network,
  Search,
  Settings,
  Sparkles,
  Upload,
  Workflow,
} from "lucide-react";
```

Changes: removed `FolderOpen`, added `Workflow`.

**Step 2: Replace nav item arrays**

Replace lines 51-68 (the `mainNavItems` stays, replace `documentsNavItems` and `researchNavItems`) with a single `knowledgeNavItems` array:

```tsx
const mainNavItems = [
  { title: "Overview", url: "/dashboard", icon: LayoutDashboard },
  { title: "Chat", url: "/chat", icon: MessageSquare },
  { title: "Search", url: "/search", icon: Search },
];

const knowledgeNavItems = [
  { title: "Documents", url: "/documents", icon: Files },
  { title: "Upload", url: "/documents/upload", icon: Upload },
  { title: "ArXiv Papers", url: "/arxiv", icon: BookOpen },
  { title: "Entities", url: "/entities", icon: Network },
  { title: "Research", url: "/research", icon: FolderKanban },
  { title: "Research Engine", url: "/research-engine", icon: Workflow },
];

const systemNavItems = [
  { title: "Analytics", url: "/analytics", icon: BarChart3 },
  { title: "Diagnostics", url: "/diagnostics", icon: Activity },
  { title: "Settings", url: "/settings", icon: Settings },
];
```

**Step 3: Replace the two sidebar sections with one KNOWLEDGE section**

Replace the Documents and Research `<SidebarGroup>` blocks (lines 244-266) with:

```tsx
{
  /* Knowledge Navigation */
}
<SidebarGroup className="py-0 mt-4 group-data-[collapsible=icon]:mt-2 group-data-[collapsible=icon]:px-1">
  <SectionLabel>KNOWLEDGE</SectionLabel>
  <SidebarGroupContent>
    <SidebarMenu className="space-y-0.5 group-data-[collapsible=icon]:space-y-1">
      {knowledgeNavItems.map((item) => (
        <NavItem key={item.title} item={item} />
      ))}
    </SidebarMenu>
  </SidebarGroupContent>
</SidebarGroup>;
```

**Step 4: Type-check**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: no errors

**Step 5: Commit**

```bash
git add frontend/src/components/layout/AppSidebar.tsx
git commit -m "feat(nav): merge DOCUMENTS+RESEARCH into KNOWLEDGE section in sidebar"
```

---

### Task 2: Update AppRail with new buttons and dividers

**Files:**

- Modify: `frontend/src/components/layout/AppRail.tsx:6-148`

**Step 1: Replace icon imports**

In `AppRail.tsx`, replace the lucide-react import block (lines 6-15) with:

```tsx
import {
  BarChart3,
  BookOpen,
  FileText,
  FlaskConical,
  LayoutGrid,
  MessageSquare,
  Network,
  Search,
  Settings,
  Workflow,
} from "lucide-react";
```

Changes: removed `FolderOpen`, added `BookOpen`, `FlaskConical`, `Workflow`.

**Step 2: Replace the navigation buttons block**

Replace lines 106-148 (from `{/* Navigation */}` through the Analytics button) with:

```tsx
      {/* Navigation — hub */}
      <RailButton
        icon={LayoutGrid}
        tip="Overview"
        href="/dashboard"
        active={isActive('/dashboard')}
      />
      <RailButton
        icon={MessageSquare}
        tip="Chat"
        href="/chat"
        active={isActive('/chat')}
      />
      <RailButton
        icon={FileText}
        tip="Documents"
        href="/documents"
        active={isActive('/documents')}
      />
      <RailButton
        icon={Search}
        tip="Search"
        href="/search"
        active={isActive('/search')}
      />

      {/* Divider — knowledge */}
      <div className="w-[22px] h-px bg-[var(--nous-border-1)] dark:bg-[var(--nous-shade)] my-1.5" />

      <RailButton
        icon={BookOpen}
        tip="ArXiv Papers"
        href="/arxiv"
        active={isActive('/arxiv')}
      />
      <RailButton
        icon={Network}
        tip="Knowledge graph"
        href="/entities"
        active={isActive('/entities')}
      />
      <RailButton
        icon={FlaskConical}
        tip="Research"
        href="/research"
        active={isActive('/research')}
      />
      <RailButton
        icon={Workflow}
        tip="Research Engine"
        href="/research-engine"
        active={isActive('/research-engine')}
      />

      {/* Divider — system */}
      <div className="w-[22px] h-px bg-[var(--nous-border-1)] dark:bg-[var(--nous-shade)] my-1.5" />

      <RailButton
        icon={BarChart3}
        tip="Analytics"
        href="/analytics"
        active={isActive('/analytics')}
      />
```

**Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: no errors

**Step 4: Commit**

```bash
git add frontend/src/components/layout/AppRail.tsx
git commit -m "feat(nav): add ArXiv, Research, Research Engine to AppRail with section dividers"
```

---

### Task 3: Add research-engine to breadcrumb map

**Files:**

- Modify: `frontend/src/components/layout/SidebarLayout.tsx:25-47`

**Step 1: Add entry to pathNameMap**

Add `'research-engine': 'Research Engine',` after the `projects` entry (line 35) in the `pathNameMap` object:

```tsx
const pathNameMap: Record<string, string> = {
  "": "Home",
  dashboard: "Overview",
  search: "Search",
  documents: "Documents",
  upload: "Upload",
  arxiv: "ArXiv Papers",
  analytics: "Analytics",
  diagnostics: "Diagnostics",
  entities: "Entities",
  projects: "Projects",
  "research-engine": "Research Engine",
  realtime: "Real-time",
  settings: "Settings",
  team: "Team",
  secrets: "API Keys",
  notifications: "Notifications",
  help: "Help Center",
  login: "Sign In",
  register: "Register",
  chat: "Chat",
  new: "New",
  "quality-metrics-demo": "Quality Metrics",
};
```

**Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: no errors

**Step 3: Commit**

```bash
git add frontend/src/components/layout/SidebarLayout.tsx
git commit -m "feat(nav): add research-engine to breadcrumb map"
```

---

### Task 4: Visual verification

**Step 1: Start dev server**

Run: `cd frontend && npm run dev`

**Step 2: Verify sidebar**

Navigate to `http://localhost:3000/dashboard`. Expand sidebar. Confirm:

- MAIN section: Overview, Chat, Search
- KNOWLEDGE section: Documents, Upload, ArXiv Papers, Entities, Research, Research Engine
- SYSTEM section: Analytics, Diagnostics, Settings
- No "Projects" entry visible

**Step 3: Verify AppRail**

Collapse sidebar or view on narrow viewport. Confirm:

- Top group: Overview, Chat, Documents, Search
- Divider
- Knowledge group: ArXiv, KG, Research (flask icon), Research Engine (workflow icon)
- Divider
- System group: Analytics, Bell, Settings

**Step 4: Verify breadcrumbs**

Navigate to `/research-engine`. Confirm breadcrumb reads: `Dashboard / Research Engine`

**Step 5: Verify active states**

Click each new rail button (ArXiv, Research, Research Engine). Confirm gold highlight and left accent bar appear on active item.
