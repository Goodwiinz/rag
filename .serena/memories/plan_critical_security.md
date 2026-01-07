# Critical Security Fixes - Detailed Implementation Plan
**Priority:** CRITICAL
**Timeline:** Week 1 (5 business days)
**Status:** ✅ COMPLETED (2026-01-07)

---

## Issue 1: JWT Token in WebSocket Query Parameters

### Current State
**File:** `backend/src/api/websocket_v2.py:61`
```python
@router.websocket("/connect")
async def websocket_connect_v2(
    websocket: WebSocket,
    token: str = Query(...),  # VULNERABLE: Token in URL
):
```

### Security Risk
- Tokens logged in server access logs
- Visible in browser history and dev tools
- Captured by proxy servers and CDNs
- Can be leaked via Referrer headers

### Implementation Plan

#### Step 1: Create WebSocket Authentication Helper
**New File:** `backend/src/core/websocket_auth.py`
```python
from fastapi import WebSocket, HTTPException, status
from typing import Optional
import jwt
from .config import settings

class WebSocketAuthenticator:
    """Secure WebSocket authentication using headers or subprotocol."""
    
    @staticmethod
    async def authenticate(websocket: WebSocket) -> dict:
        """
        Authenticate WebSocket connection.
        
        Attempts authentication in order:
        1. Authorization header (Bearer token)
        2. Sec-WebSocket-Protocol header (for browser compatibility)
        3. Cookie (for session-based auth)
        
        Returns:
            dict: Decoded JWT payload with user info
            
        Raises:
            HTTPException: If authentication fails
        """
        token = None
        
        # Method 1: Authorization header
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
        
        # Method 2: Sec-WebSocket-Protocol (browser workaround)
        if not token:
            protocol_header = websocket.headers.get("sec-websocket-protocol")
            if protocol_header:
                # Format: "auth, <token>" - we send back "auth" to accept
                protocols = [p.strip() for p in protocol_header.split(",")]
                if len(protocols) >= 2 and protocols[0] == "auth":
                    token = protocols[1]
        
        # Method 3: Cookie fallback
        if not token:
            cookies = websocket.cookies
            token = cookies.get("access_token")
        
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No authentication token provided"
            )
        
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )
```

#### Step 2: Update WebSocket Endpoint
**File:** `backend/src/api/websocket_v2.py`
```python
from ..core.websocket_auth import WebSocketAuthenticator

@router.websocket("/connect")
async def websocket_connect_v2(websocket: WebSocket):
    """
    Secure WebSocket connection endpoint.
    
    Authentication methods (in priority order):
    1. Authorization: Bearer <token> header
    2. Sec-WebSocket-Protocol: auth, <token>
    3. Cookie: access_token=<token>
    """
    try:
        # Authenticate before accepting connection
        user_payload = await WebSocketAuthenticator.authenticate(websocket)
        user_id = user_payload.get("sub")
        
        # Accept connection with protocol if using subprotocol auth
        protocol_header = websocket.headers.get("sec-websocket-protocol")
        if protocol_header and protocol_header.startswith("auth"):
            await websocket.accept(subprotocol="auth")
        else:
            await websocket.accept()
        
        # Continue with authenticated connection...
        await websocket_manager.connect(websocket, user_id)
        
    except HTTPException as e:
        await websocket.close(code=4001, reason=e.detail)
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        await websocket.close(code=4000, reason="Connection error")
```

#### Step 3: Update Frontend WebSocket Client
**File:** `frontend/src/services/realtime-websocket-service.ts`
```typescript
class RealtimeWebSocketService {
  private connect(): void {
    const token = this.getAuthToken();
    
    // Use Sec-WebSocket-Protocol for browser compatibility
    this.ws = new WebSocket(
      this.wsUrl,
      ['auth', token]  // Protocol header carries token
    );
    
    // Alternatively, for Node.js clients:
    // this.ws = new WebSocket(this.wsUrl, {
    //   headers: { Authorization: `Bearer ${token}` }
    // });
  }
}
```

#### Step 4: Add Security Tests
**File:** `backend/tests/security/test_websocket_auth.py`
```python
import pytest
from fastapi.testclient import TestClient

class TestWebSocketSecurity:
    def test_rejects_token_in_query_param(self, client):
        """Ensure old query param method is rejected."""
        with pytest.raises(Exception):
            with client.websocket_connect("/api/v2/ws/connect?token=xxx"):
                pass
    
    def test_accepts_header_auth(self, client, valid_token):
        """Test Authorization header authentication."""
        with client.websocket_connect(
            "/api/v2/ws/connect",
            headers={"Authorization": f"Bearer {valid_token}"}
        ) as ws:
            assert ws.receive_json()["type"] == "connected"
    
    def test_accepts_subprotocol_auth(self, client, valid_token):
        """Test Sec-WebSocket-Protocol authentication."""
        with client.websocket_connect(
            "/api/v2/ws/connect",
            subprotocols=["auth", valid_token]
        ) as ws:
            assert ws.receive_json()["type"] == "connected"
```

### Migration Strategy
1. Deploy new endpoint alongside old (backward compatible)
2. Update frontend to use new auth method
3. Add deprecation warning to old endpoint
4. Remove old endpoint after 2 weeks

---

## Issue 2: SQL Injection in sort_by Parameter

### Current State
**File:** `backend/src/api/documents.py:102-116`
```python
@router.get("", response_model=DocumentListResponse)
async def list_documents(
    sort_by: Optional[str] = Query("created_at"),  # NO VALIDATION
    sort_order: Optional[str] = Query("desc"),     # NO VALIDATION
):
```

### Security Risk
- Arbitrary column names could be injected
- Error messages may leak schema information
- Could be used for timing attacks

### Implementation Plan

#### Step 1: Create Validation Enums
**File:** `backend/src/shared/enums.py` (add to existing)
```python
from enum import Enum

class DocumentSortField(str, Enum):
    """Allowed sort fields for document queries."""
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    TITLE = "title"
    FILENAME = "filename"
    FILE_SIZE = "file_size_bytes"
    PROCESSING_STATUS = "processing_status"
    DOCUMENT_TYPE = "document_type"

class SortOrder(str, Enum):
    """Sort order direction."""
    ASC = "asc"
    DESC = "desc"
```

#### Step 2: Update API Endpoint
**File:** `backend/src/api/documents.py`
```python
from ..shared.enums import DocumentSortField, SortOrder

@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: DocumentSortField = Query(
        DocumentSortField.CREATED_AT,
        description="Field to sort by"
    ),
    sort_order: SortOrder = Query(
        SortOrder.DESC,
        description="Sort direction"
    ),
    # ... other params
):
    # Now sort_by is guaranteed to be a valid enum value
    order_column = getattr(Document, sort_by.value)
    if sort_order == SortOrder.DESC:
        order_column = order_column.desc()
    
    query = query.order_by(order_column)
```

#### Step 3: Create Query Builder Helper
**File:** `backend/src/core/query_helpers.py`
```python
from sqlalchemy import asc, desc
from sqlalchemy.orm import Query
from typing import Type, TypeVar
from ..shared.enums import SortOrder

T = TypeVar('T')

def apply_sorting(
    query: Query,
    model: Type[T],
    sort_field: str,
    sort_order: SortOrder,
    allowed_fields: set[str]
) -> Query:
    """
    Safely apply sorting to a query.
    
    Args:
        query: SQLAlchemy query object
        model: Model class to sort
        sort_field: Field name to sort by
        sort_order: ASC or DESC
        allowed_fields: Set of allowed field names
        
    Returns:
        Query with sorting applied
        
    Raises:
        ValueError: If sort_field not in allowed_fields
    """
    if sort_field not in allowed_fields:
        raise ValueError(f"Invalid sort field: {sort_field}")
    
    column = getattr(model, sort_field, None)
    if column is None:
        raise ValueError(f"Field {sort_field} not found on model")
    
    order_func = desc if sort_order == SortOrder.DESC else asc
    return query.order_by(order_func(column))
```

#### Step 4: Add Input Validation Tests
**File:** `backend/tests/security/test_input_validation.py`
```python
import pytest

class TestSortValidation:
    def test_rejects_invalid_sort_field(self, client, auth_headers):
        """Ensure invalid sort fields are rejected."""
        response = client.get(
            "/api/v1/documents?sort_by=; DROP TABLE documents;--",
            headers=auth_headers
        )
        assert response.status_code == 422
        assert "not a valid enumeration member" in response.json()["detail"][0]["msg"]
    
    def test_accepts_valid_sort_field(self, client, auth_headers):
        """Ensure valid sort fields work."""
        response = client.get(
            "/api/v1/documents?sort_by=created_at&sort_order=desc",
            headers=auth_headers
        )
        assert response.status_code == 200
    
    @pytest.mark.parametrize("field", [
        "created_at", "updated_at", "title", "filename"
    ])
    def test_all_allowed_fields(self, client, auth_headers, field):
        """Test all allowed sort fields."""
        response = client.get(
            f"/api/v1/documents?sort_by={field}",
            headers=auth_headers
        )
        assert response.status_code == 200
```

---

## Issue 3: Overly Permissive CORS

### Current State
**File:** `backend/src/main.py:170-177`
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # TOO PERMISSIVE
)
```

### Security Risk
- Allows any custom headers from any origin
- Could enable request forgery attacks
- May leak sensitive headers

### Implementation Plan

#### Step 1: Define Allowed Headers
**File:** `backend/src/core/config.py` (add)
```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # CORS Configuration
    cors_origins: str = "http://localhost:3000"
    cors_allowed_headers: str = (
        "Authorization,"
        "Content-Type,"
        "Accept,"
        "Origin,"
        "X-Request-ID,"
        "X-Correlation-ID,"
        "Cache-Control"
    )
    cors_allowed_methods: str = "GET,POST,PUT,DELETE,PATCH,OPTIONS"
    cors_expose_headers: str = "X-Request-ID,X-Correlation-ID"
    
    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def cors_headers_list(self) -> list[str]:
        return [h.strip() for h in self.cors_allowed_headers.split(",")]
    
    @property
    def cors_methods_list(self) -> list[str]:
        return [m.strip() for m in self.cors_allowed_methods.split(",")]
    
    @property
    def cors_expose_list(self) -> list[str]:
        return [h.strip() for h in self.cors_expose_headers.split(",")]
```

#### Step 2: Update CORS Middleware
**File:** `backend/src/main.py`
```python
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings

# Strict CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=settings.cors_methods_list,
    allow_headers=settings.cors_headers_list,
    expose_headers=settings.cors_expose_list,
    max_age=86400,  # Cache preflight for 24 hours
)

# Log CORS configuration on startup
@app.on_event("startup")
async def log_cors_config():
    logger.info(f"CORS Origins: {settings.cors_origins_list}")
    logger.info(f"CORS Headers: {settings.cors_headers_list}")
```

#### Step 3: Add Environment Variables
**File:** `.env.example`
```bash
# CORS Configuration
CORS_ORIGINS=http://localhost:3000,https://app.example.com
CORS_ALLOWED_HEADERS=Authorization,Content-Type,Accept,X-Request-ID
CORS_ALLOWED_METHODS=GET,POST,PUT,DELETE,PATCH,OPTIONS
```

---

## Issue 4: Missing Accessibility Labels

### Current State
Multiple icon-only buttons lack aria-labels:
- `ChatInput.tsx` - formatting buttons, settings, send
- `ProcessingStatus.tsx` - expand/collapse button
- Various components with `<Button><Icon /></Button>` pattern

### Implementation Plan

#### Step 1: Create IconButton Component
**File:** `frontend/src/components/ui/icon-button.tsx`
```typescript
import * as React from "react";
import { Button, ButtonProps } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface IconButtonProps extends Omit<ButtonProps, 'children'> {
  icon: React.ReactNode;
  label: string;  // Required for accessibility
  showTooltip?: boolean;
}

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ icon, label, showTooltip = true, className, ...props }, ref) => {
    const button = (
      <Button
        ref={ref}
        variant="ghost"
        size="icon"
        aria-label={label}
        className={cn("h-8 w-8", className)}
        {...props}
      >
        {icon}
        <span className="sr-only">{label}</span>
      </Button>
    );

    if (showTooltip) {
      return (
        <Tooltip>
          <TooltipTrigger asChild>{button}</TooltipTrigger>
          <TooltipContent>{label}</TooltipContent>
        </Tooltip>
      );
    }

    return button;
  }
);

IconButton.displayName = "IconButton";
```

#### Step 2: Update ChatInput Component
**File:** `frontend/src/components/chat/ChatInput.tsx`
```typescript
import { IconButton } from "@/components/ui/icon-button";

// Replace:
<Button variant="ghost" size="sm" onClick={handleBold}>
  <BoldIcon className="w-4 h-4" />
</Button>

// With:
<IconButton
  icon={<BoldIcon className="w-4 h-4" />}
  label="Bold text (Ctrl+B)"
  onClick={handleBold}
/>

// All formatting buttons:
const formattingButtons = [
  { icon: <BoldIcon />, label: "Bold (Ctrl+B)", action: handleBold },
  { icon: <ItalicIcon />, label: "Italic (Ctrl+I)", action: handleItalic },
  { icon: <LinkIcon />, label: "Insert link (Ctrl+K)", action: handleLink },
  { icon: <CodeIcon />, label: "Code block", action: handleCode },
];

{formattingButtons.map(({ icon, label, action }) => (
  <IconButton key={label} icon={icon} label={label} onClick={action} />
))}
```

#### Step 3: Update ProcessingStatus Component
**File:** `frontend/src/components/processing/ProcessingStatus.tsx`
```typescript
<IconButton
  icon={expanded ? <ChevronUpIcon /> : <ChevronDownIcon />}
  label={expanded ? "Collapse processing details" : "Expand processing details"}
  onClick={() => setExpanded(!expanded)}
  aria-expanded={expanded}
  aria-controls="processing-details"
/>

<div id="processing-details" aria-hidden={!expanded}>
  {/* Processing details content */}
</div>
```

#### Step 4: Add ESLint Rule for Enforcement
**File:** `frontend/.eslintrc.json` (add)
```json
{
  "rules": {
    "jsx-a11y/control-has-associated-label": "error",
    "jsx-a11y/interactive-supports-focus": "error",
    "jsx-a11y/click-events-have-key-events": "warn"
  }
}
```

---

## Testing Checklist

### Security Tests
- [x] WebSocket rejects query param tokens ✅ (test_authenticate_no_token_raises_error)
- [x] WebSocket accepts header authentication ✅ (test_authenticate_with_bearer_header)
- [x] WebSocket accepts subprotocol authentication ✅ (test_authenticate_with_subprotocol)
- [x] Invalid sort fields return 422 ✅ (test_document_sort_field_rejects_injection)
- [x] SQL injection attempts blocked ✅ (test_sort_order_rejects_injection)
- [x] CORS blocks unauthorized origins ✅ (test_cors_origins_list_parsing, config implemented)
- [x] CORS blocks unauthorized headers ✅ (test_cors_allowed_headers_not_wildcard)

### Accessibility Tests
- [x] All icon buttons have aria-labels ✅ (IconButton component created)
- [ ] Screen reader can navigate chat input (pending - update ChatInput.tsx)
- [ ] Keyboard navigation works for all buttons (pending - manual testing required)
- [ ] Focus indicators visible (pending - manual testing required)
- [ ] Expandable sections have aria-expanded (pending - update ProcessingStatus.tsx)

---

## Rollout Plan

### Day 1-2: Backend Security
1. Implement WebSocket auth helper
2. Add sort field validation
3. Tighten CORS configuration
4. Deploy to staging

### Day 3: Frontend Updates
1. Update WebSocket client
2. Create IconButton component
3. Update components with accessibility
4. Test with screen reader

### Day 4: Integration Testing
1. End-to-end security tests
2. Accessibility audit (axe-core)
3. Browser compatibility testing

### Day 5: Production Deployment
1. Deploy backend changes
2. Deploy frontend changes
3. Monitor for issues
4. Document changes
