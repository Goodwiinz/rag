# Supabase Migration Phase 2: Auth Migration

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace custom JWT auth (python-jose, bcrypt, custom token creation) with Supabase Auth while keeping the existing RBAC system and API key auth intact.

**Architecture:** Supabase Auth handles user identity, login, registration, and JWT issuance. Our backend validates Supabase JWTs and maps them to existing User records. Frontend uses `@supabase/supabase-js` for auth flows. Dual-JWT support during transition.

**Tech Stack:** Supabase Auth, @supabase/supabase-js, python-jose (for Supabase JWT validation), FastAPI

---

### Task 1: Install Frontend Supabase Client

**Files:**

- Modify: `frontend/package.json`
- Create: `frontend/src/lib/supabase.ts`

**Step 1: Install @supabase/supabase-js**

Run:

```bash
cd /Users/goodwiinz/development/RAG_system/frontend
npm install @supabase/supabase-js
```

**Step 2: Create Supabase client utility**

Create `frontend/src/lib/supabase.ts`:

```typescript
import { createClient } from "@supabase/supabase-js";

const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL || "http://localhost:54321";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
```

**Step 3: Add env vars to frontend**

Add to `frontend/.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<from supabase status output>
```

**Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/supabase.ts
git commit -m "feat: add Supabase JS client for frontend auth"
```

---

### Task 2: Migrate Users to Supabase Auth

**Files:**

- Create: `supabase/migrations/<timestamp>_sync_users_to_auth.sql`

**Step 1: Create migration to sync existing users into Supabase Auth**

Supabase Auth stores users in `auth.users`. We need to insert our existing users there while keeping our `public.users` table as a profiles table linked by UUID.

Create SQL migration:

```sql
-- Sync existing users from public.users to auth.users
-- This creates Supabase Auth identities for existing users
-- Password hashes are compatible (both use bcrypt)

INSERT INTO auth.users (
  id,
  instance_id,
  email,
  encrypted_password,
  email_confirmed_at,
  raw_app_meta_data,
  raw_user_meta_data,
  role,
  created_at,
  updated_at,
  confirmation_token,
  aud
)
SELECT
  u.id,
  '00000000-0000-0000-0000-000000000000'::uuid,
  u.email,
  u.password_hash,
  now(),
  jsonb_build_object('provider', 'email', 'providers', ARRAY['email'], 'role', u.role),
  jsonb_build_object('first_name', u.first_name, 'last_name', u.last_name),
  'authenticated',
  u.created_at,
  u.updated_at,
  '',
  'authenticated'
FROM public.users u
WHERE NOT EXISTS (
  SELECT 1 FROM auth.users au WHERE au.id = u.id
);

-- Create identities for each user
INSERT INTO auth.identities (
  id,
  user_id,
  identity_data,
  provider,
  provider_id,
  last_sign_in_at,
  created_at,
  updated_at
)
SELECT
  u.id,
  u.id,
  jsonb_build_object('sub', u.id::text, 'email', u.email),
  'email',
  u.id::text,
  u.last_login,
  u.created_at,
  u.updated_at
FROM public.users u
WHERE NOT EXISTS (
  SELECT 1 FROM auth.identities ai WHERE ai.user_id = u.id
);
```

**Step 2: Apply migration**

Run:

```bash
npx supabase db reset
```

**Step 3: Verify users exist in auth.users**

```bash
psql postgresql://postgres:postgres@127.0.0.1:54322/postgres \
  -c "SELECT id, email, raw_app_meta_data->>'role' as role FROM auth.users;"
```

**Step 4: Test Supabase Auth login**

```bash
curl -X POST http://localhost:54321/auth/v1/token?grant_type=password \
  -H "apikey: <ANON_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@multimodal-rag.com","password":"REDACTED"}'
```

Expected: Returns Supabase JWT with access_token and refresh_token.

**Step 5: Commit**

```bash
git add supabase/migrations/
git commit -m "feat: sync existing users to Supabase Auth"
```

---

### Task 3: Backend — Dual JWT Validation

**Files:**

- Modify: `backend/src/core/security.py`

**Step 1: Add Supabase JWT validation alongside existing**

Update `verify_token()` to try Supabase JWT first, fall back to custom JWT:

```python
def verify_token(token: str) -> Optional[TokenData]:
    """Verify JWT token — supports both Supabase and custom JWTs."""
    # Try Supabase JWT first (signed with JWT_SECRET from Supabase)
    supabase_secret = os.getenv("SUPABASE_JWT_SECRET", "")
    if supabase_secret:
        try:
            payload = jwt.decode(token, supabase_secret, algorithms=["HS256"],
                                 audience="authenticated")
            user_id = payload.get("sub")
            email = payload.get("email")
            app_metadata = payload.get("app_metadata", {})
            role = app_metadata.get("role", "USER")
            # Supabase doesn't include org_id in JWT, we'll look it up
            return TokenData(
                user_id=user_id,
                email=email,
                organization_id=None,  # Resolved in get_current_user
                role=role,
                exp=datetime.utcfromtimestamp(payload.get("exp")) if payload.get("exp") else None,
            )
        except JWTError:
            pass  # Fall through to custom JWT

    # Fallback: custom JWT (existing logic)
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY,
                             algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        email = payload.get("email")
        organization_id = payload.get("organization_id")
        role = payload.get("role")
        exp = payload.get("exp")
        if user_id is None:
            return None
        return TokenData(
            user_id=user_id, email=email,
            organization_id=organization_id, role=role,
            exp=datetime.utcfromtimestamp(exp) if exp else None,
        )
    except JWTError:
        return None
```

**Step 2: Update get_current_user to resolve org_id for Supabase tokens**

In `backend/src/core/dependencies.py`, update `get_current_user()` to handle `organization_id=None` (Supabase tokens don't include it):

```python
async def get_current_user(
    token_data: dict = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db),
) -> User:
    stmt = (
        select(User)
        .options(selectinload(User.organization))
        .where(
            User.id == token_data.user_id,
            User.is_active == True,
            User.is_deleted == False,
        )
    )
    result = await db.execute(stmt)
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user
```

This already works — it queries by user_id regardless of org_id in token.

**Step 3: Add SUPABASE_JWT_SECRET to config**

In `backend/src/core/config.py`:

```python
SUPABASE_JWT_SECRET: str = ""  # From supabase status output
```

**Step 4: Test dual validation**

- Test with existing custom JWT (should still work)
- Test with Supabase JWT (should also work)

**Step 5: Commit**

```bash
git add backend/src/core/security.py backend/src/core/config.py
git commit -m "feat: dual JWT validation — supports both Supabase and custom tokens"
```

---

### Task 4: Frontend — Migrate Auth Store to Supabase

**Files:**

- Modify: `frontend/src/stores/authStore.ts`

**Step 1: Update authStore to use Supabase Auth**

Replace the `login`, `register`, `logout`, `refreshToken` methods to use the Supabase client:

```typescript
login: async (email: string, password: string, rememberMe?: boolean) => {
  set({ isLoading: true, error: null });
  try {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;

    const session = data.session;
    const supabaseUser = data.user;

    // Fetch our full user profile from the backend using the Supabase token
    const response = await apiClient.get('/auth/me', {
      headers: { Authorization: `Bearer ${session.access_token}` },
    });

    set({
      user: response.data,
      token: session.access_token,
      refreshTokenValue: session.refresh_token,
      isAuthenticated: true,
      isLoading: false,
      rememberMe: rememberMe || false,
      tokenExpiresAt: session.expires_at ? session.expires_at * 1000 : null,
    });
  } catch (error: any) {
    set({ error: error.message, isLoading: false });
    throw error;
  }
},
```

Similar changes for `register`, `logout`, `refreshToken`.

**Step 2: Set up Supabase auth state listener**

Add `onAuthStateChange` listener to handle token refresh automatically:

```typescript
// In store initialization
supabase.auth.onAuthStateChange((event, session) => {
  if (event === "TOKEN_REFRESHED" && session) {
    set({
      token: session.access_token,
      refreshTokenValue: session.refresh_token,
    });
  }
  if (event === "SIGNED_OUT") {
    set({ user: null, token: null, isAuthenticated: false });
  }
});
```

**Step 3: Update apiClient to use Supabase session token**

In `frontend/src/services/apiClient.ts`, update the Authorization header interceptor to get the token from Supabase session.

**Step 4: Commit**

```bash
git add frontend/src/stores/authStore.ts frontend/src/lib/supabase.ts frontend/src/services/apiClient.ts
git commit -m "feat: migrate frontend auth to Supabase Auth"
```

---

### Task 5: Backend — Add Supabase Auth Endpoints

**Files:**

- Modify: `backend/src/api/auth/auth.py`

**Step 1: Update login endpoint to accept Supabase flow**

The login endpoint needs to support two modes during transition:

1. Direct password login (existing — calls bcrypt)
2. Token exchange (new — frontend logs in via Supabase, sends token to backend)

Add a `/auth/supabase-callback` endpoint:

```python
@router.post("/auth/supabase-callback")
async def supabase_auth_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Exchange Supabase JWT for our session (profile lookup)."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = auth_header.split(" ", 1)[1]
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Look up user profile
    user = await db.execute(
        select(User).options(selectinload(User.organization))
        .where(User.id == token_data.user_id, User.is_active == True)
    )
    user = user.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found")

    return {"user": user.to_dict(), "organization": user.organization.to_dict() if user.organization else None}
```

**Step 2: Keep existing login/register endpoints working**

Don't remove them — they serve as fallback during transition and for API key users.

**Step 3: Commit**

```bash
git add backend/src/api/auth/auth.py
git commit -m "feat: add Supabase auth callback endpoint for token exchange"
```

---

### Task 6: Update WebSocket Auth

**Files:**

- Modify: `backend/src/core/websocket_auth.py`

**Step 1: Update WebSocket auth to validate Supabase JWTs**

The existing WebSocket auth already calls `verify_token()` which now supports Supabase JWTs (from Task 3). Verify it works.

Read `websocket_auth.py` to confirm it uses the same `verify_token` function. If it has its own JWT validation, update it.

**Step 2: Test WebSocket connection with Supabase token**

**Step 3: Commit (if changes needed)**

---

### Task 7: Add .env Configuration

**Files:**

- Modify: `backend/.env.example`
- Modify: `frontend/.env.example` (create if doesn't exist)

**Step 1: Add Supabase JWT secret to backend .env.example**

```env
# Supabase Auth
SUPABASE_JWT_SECRET=""  # From: npx supabase status (secret key)
```

**Step 2: Add frontend env vars**

```env
NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=  # From: npx supabase status
```

**Step 3: Commit**

```bash
git add backend/.env.example
git commit -m "docs: add Supabase Auth env vars to examples"
```

---

### Task 8: Integration Test

**Files:**

- No file changes — verification only

**Step 1: Test Supabase Auth login flow end-to-end**

1. Sign in via Supabase Auth API
2. Use the returned token to call backend `/auth/me`
3. Use the token to call `/api/v1/documents/`
4. Verify all return 200

**Step 2: Test legacy login still works**

1. POST to `/api/v1/auth/login` with email/password
2. Verify custom JWT is returned
3. Use custom JWT to call protected endpoints

**Step 3: Run type-check and lint**

```bash
cd frontend && npm run type-check && npm run lint
```

**Step 4: Final commit**

```bash
git commit -m "chore: Phase 2 complete — Supabase Auth with dual JWT support"
```

---

## Summary

| Task | Description                      | Risk   |
| ---- | -------------------------------- | ------ |
| 1    | Install frontend Supabase client | Low    |
| 2    | Sync users to Supabase Auth      | Medium |
| 3    | Dual JWT validation in backend   | Medium |
| 4    | Migrate frontend auth store      | Medium |
| 5    | Supabase auth callback endpoint  | Low    |
| 6    | Update WebSocket auth            | Low    |
| 7    | Add env configuration            | Low    |
| 8    | Integration test                 | Low    |
