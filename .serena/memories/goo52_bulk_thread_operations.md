# GOO-52: Bulk Thread Operations - Implementation Guide

## Overview
Enable bulk resolve, archive, and delete operations for threads with multi-select UI.

## Phase 1: Backend Schemas (backend/src/schemas/chat.py)

Add after ThreadListResponse (~line 215):

```python
class BulkThreadRequest(BaseModel):
    """Bulk thread operation request"""
    thread_ids: List[UUID] = Field(..., min_length=1, max_length=100)

class BulkThreadResult(BaseModel):
    """Result for single thread in bulk op"""
    thread_id: UUID
    success: bool
    error: Optional[str] = None
    thread: Optional[ThreadResponse] = None

class BulkThreadResponse(BaseModel):
    """Bulk operation response"""
    total: int
    succeeded: int
    failed: int
    results: List[BulkThreadResult]
```

## Phase 2: ChatService Methods (backend/src/services/chat_service.py)

Add after delete_thread (~line 515):

```python
def bulk_update_threads(
    self, thread_ids: List[UUID], data: ThreadUpdate, user_id: UUID
) -> List[Tuple[UUID, bool, Optional[str], Optional[Thread]]]:
    """Bulk update threads. Returns (thread_id, success, error, thread) tuples."""
    results = []
    for tid in thread_ids:
        try:
            thread = self.update_thread(tid, data, user_id)
            results.append((tid, bool(thread), None if thread else "Not found", thread))
        except Exception as e:
            results.append((tid, False, str(e), None))
    return results

def bulk_delete_threads(
    self, thread_ids: List[UUID], user_id: UUID
) -> List[Tuple[UUID, bool, Optional[str]]]:
    """Bulk delete threads. Returns (thread_id, success, error) tuples."""
    results = []
    for tid in thread_ids:
        try:
            success = self.delete_thread(tid, user_id)
            results.append((tid, success, None if success else "Not found"))
        except Exception as e:
            results.append((tid, False, str(e)))
    return results
```

## Phase 3: API Endpoints (backend/src/api/threads.py)

Add after archive_thread (~line 315):

```python
@router.post("/bulk/resolve", response_model=BulkThreadResponse)
async def bulk_resolve_threads(
    request: BulkThreadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = get_chat_service(db)
    results = service.bulk_update_threads(
        request.thread_ids, ThreadUpdate(status=ThreadStatus.RESOLVED), current_user.id
    )
    return _build_bulk_response(results, "resolved", current_user.id)

@router.post("/bulk/archive", response_model=BulkThreadResponse)
async def bulk_archive_threads(request: BulkThreadRequest, ...):
    # Same pattern with ThreadStatus.ARCHIVED

@router.delete("/bulk", response_model=BulkThreadResponse)
async def bulk_delete_threads(request: BulkThreadRequest, ...):
    results = service.bulk_delete_threads(request.thread_ids, current_user.id)
    # Build response from (tid, success, error) tuples
```

## Phase 4: WebSocket Events (backend/src/services/thread_event_service.py)

Add MessageType.THREADS_BULK_UPDATED and method:

```python
async def broadcast_threads_bulk_updated(
    self, thread_ids: List[str], action: str, user_id: str
) -> None:
    message = WebSocketMessage(
        type=MessageType.THREADS_BULK_UPDATED,
        data={"thread_ids": thread_ids, "action": action, "count": len(thread_ids)},
        timestamp=datetime.now(timezone.utc),
    )
    await self._broadcast_to_channels([f"thread:{tid}" for tid in thread_ids], message)
```

## Phase 5: Frontend Types (frontend/src/types/workspace.ts)

```typescript
export interface BulkThreadRequest { thread_ids: string[]; }
export interface BulkThreadResult {
  thread_id: string; success: boolean; error?: string; thread?: Thread;
}
export interface BulkThreadResponse {
  total: number; succeeded: number; failed: number; results: BulkThreadResult[];
}
```

## Phase 6: Frontend API (frontend/src/services/workspaceService.ts)

```typescript
async bulkResolveThreads(threadIds: string[]): Promise<BulkThreadResponse> {
  return (await v2Client.post(`${API_PREFIX}/threads/bulk/resolve`, { thread_ids: threadIds })).data;
},
async bulkArchiveThreads(threadIds: string[]): Promise<BulkThreadResponse> { ... },
async bulkDeleteThreads(threadIds: string[]): Promise<BulkThreadResponse> {
  return (await v2Client.delete(`${API_PREFIX}/threads/bulk`, { data: { thread_ids: threadIds } })).data;
},
```

## Phase 7: Frontend Store (frontend/src/store/chat-store.ts)

State additions:
- `selectedThreadIds: Set<string>` - currently selected thread IDs
- `isSelectMode: boolean` - whether multi-select mode is active

Actions:
- `toggleSelectMode()` - enter/exit select mode, clears selection on exit
- `toggleThreadSelection(id)` - add/remove thread from selection
- `selectAllThreads()` - select all threads in current conversation
- `clearSelection()` - deselect all
- `bulkResolveThreads()` - call API, update local state, clear selection
- `bulkArchiveThreads()` - same pattern
- `bulkDeleteThreads()` - same pattern, also clear currentThreadId if deleted

## Phase 8: UI Components (ConversationSidebar.tsx)

1. **Select mode toggle** in header toolbar (CheckSquare icon)
2. **Bulk action toolbar** when items selected:
   - Selection count badge
   - Select All / Clear buttons
   - Resolve / Archive / Delete buttons
3. **Checkbox per thread** when isSelectMode=true
4. **Confirmation dialog** for bulk delete

Props to add:
```typescript
isSelectMode?: boolean;
selectedIds?: Set<string>;
onToggleSelectMode?: () => void;
onToggleSelection?: (id: string) => void;
onBulkResolve?: () => void;
onBulkArchive?: () => void;
onBulkDelete?: () => void;
```

## Acceptance Criteria
- [ ] Select multiple threads with checkboxes
- [ ] Bulk resolve selected threads
- [ ] Bulk archive selected threads  
- [ ] Bulk delete with confirmation
- [ ] Undo option for bulk operations (toast with undo)
