# Background Merge + Extraction Jobs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run entity merge and document entity extraction as durable background jobs with polling and a global job center.

**Architecture:** Reuse existing `ProcessingJob` + Celery infrastructure. Add knowledge-graph job creation endpoints, Celery handlers for merge/extract, and frontend polling UI using existing `/api/v1/processing/jobs` status endpoints.

**Tech Stack:** FastAPI, SQLAlchemy, Celery/Redis, Next.js, React, TypeScript.

---

### Task 1: Backend job API for merge/extract
- Modify `backend/src/api/search/knowledge_graph.py`
- Add `POST /knowledge-graph/merge-jobs` and `POST /knowledge-graph/extraction-jobs`
- Create `ProcessingJob` rows and enqueue Celery tasks

### Task 2: Backend worker tasks
- Modify `backend/src/tasks/processing_tasks.py`
- Add tasks to execute merge and extraction jobs with progress updates
- Reuse existing graph services and job state transitions

### Task 3: Frontend services
- Modify `frontend/src/services/entityService.ts`
- Add functions to create merge/extraction jobs and query processing jobs

### Task 4: Merge/extractor UI migration
- Modify `frontend/src/components/entities/EntityMergeTool.tsx`
- Modify `frontend/src/components/entities/DocumentEntityExtractor.tsx`
- Switch to enqueue + polling flow (non-blocking)

### Task 5: Global job center
- Create `frontend/src/components/layout/GlobalJobCenter.tsx`
- Modify `frontend/src/components/layout/SidebarLayout.tsx`
- Show active/recent jobs globally using polling

### Task 6: Tests and verification
- Add/modify tests under `frontend/src/components/entities/__tests__/`
- Run targeted Jest tests and backend syntax checks
