# Project Detail Page UX/UI Redesign

**Date:** 2026-03-02
**Scope:** Full UX/UI overhaul of `/projects/[id]` page
**Theme direction:** Evolve from Terminal Observatory to modern dark (Vercel/Linear-style)

## Goals

- Modernize typography (sans-serif primary, monospace only for code/filenames)
- Add richer document interactions (multi-select, sort/filter, bulk actions)
- Improve visual hierarchy in header, tabs, and content areas
- Use semantic color tokens instead of hardcoded hex values

## Section 1: Project Header & Hero

### Current

- Breadcrumb shows raw UUID
- Flat title + stats layout
- No project metadata display (type, status, tags, deadline)

### Proposed

- **Breadcrumb**: Replace UUID with project name
- **Hero card container** with subtle background:
  - Left: Project name (larger, sans-serif), description, project type badge, status badge, tag pills
  - Right: Stats grid - 4 metric cards (documents, citations, notes, drafts) with icons
  - Deadline shown with relative date if present
- **Back button**: Clean arrow above card

## Section 2: Tab Navigation

### Current

- Flat tab bar, no counts, no visual grouping
- All tabs look identical

### Proposed

- Count badges on each tab: "Documents (5)", "Notes (3)"
- Active tab gets subtle filled background (not just bottom border)
- Larger touch targets with rounded corners
- Visual grouping: [Documents | Notes | Bibliography] gap [Drafts | Chat | Matrix]

## Section 3: Document List

### Current

- Plain identical rows with only title + date
- No sort/filter/bulk operations
- Delete button directly exposed

### Proposed

- **Toolbar**: Search input + sort dropdown (name, date added)
- **Selection**: Checkbox per card, bulk action bar when items selected (Remove, Export)
- **Richer cards**:
  - Document type icon (PDF, generic) based on filename extension
  - Title (sans-serif, medium weight)
  - Subtitle: filename, relative date ("2 hours ago"), status badge (Indexed/Processing)
  - Hover: subtle elevation, reveal three-dot menu (Remove, View)
  - Delete moved to context menu to prevent accidental clicks

## Section 4: Typography & Visual System

### Current

- Heavy monospace everywhere
- Single green accent
- Flat cards with no depth

### Proposed

- **Typography**: System sans-serif for primary text, monospace only for code/filenames/technical
- **Colors**: Keep dark + green (#00ff9f) primary, add:
  - Gray hierarchy: gray-100 titles, gray-400 body, gray-500 metadata
  - Status: green (success), amber (in-progress), red (error), cyan (info)
- **Cards**: Use `bg-card`/`ring-border` tokens instead of hardcoded values
- **Spacing**: More generous padding, consistent gaps

## Files to Modify

- `frontend/app/(dashboard)/projects/[id]/page.tsx` - Main page restructure
- Possibly extract new components for header, document list toolbar, document card

## Data Available

From `Project` interface: name, description, project_type, research_status, research_goals, deadline, tags, document_count, citation_count, note_count, draft_count, created_at, updated_at

From `ProjectDocument` interface: document_id, added_at, sort_order, document.title, document.filename, document.status, document.created_at
