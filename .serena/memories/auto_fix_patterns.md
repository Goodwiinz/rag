# Auto-Fix Patterns for CodeRabbit Findings

This memory contains reusable fix patterns for common CodeRabbit findings.

## Purpose
- Provide templates for consistent fixes
- Enable automated fixing of common issues
- Document Serena tool usage for each pattern

---

## Security Patterns

### Pattern: Hardcoded API Key
**Finding Type**: critical_security
**Detection**: `search_for_pattern` with regex for API key formats

```python
# Before
"API_KEY": "sk_live_xxxxx"

# After  
"API_KEY": "${API_KEY_ENV_VAR}"
```

**Serena Tools**:
1. `search_for_pattern(substring_pattern="['\"]\\w+_KEY['\"]:\\s*['\"][^$]")` - Find hardcoded keys
2. `read_file` - Get context
3. `replace_content` - Apply fix

---

### Pattern: Missing Authentication
**Finding Type**: critical_security
**Detection**: Endpoint without `Depends(get_current_user)`

```python
# Before
@router.post("/endpoint")
async def my_endpoint(request: Request):

# After
@router.post("/endpoint")
async def my_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user)
):
```

**Serena Tools**:
1. `find_symbol(name_path_pattern="my_endpoint")` - Locate function
2. `get_symbols_overview` - Check file imports
3. `replace_symbol_body` - Add auth parameter

---

### Pattern: PII in Logs
**Finding Type**: critical_security
**Detection**: Logging with `email`, `password`, `ssn`, etc.

```python
# Before
logger.info("User action", extra={"user_email": user.email})

# After
logger.info("User action", extra={"user_id": str(user.id)})
```

**Serena Tools**:
1. `search_for_pattern(substring_pattern="user_email|user\\.email")` - Find PII logging
2. `replace_content` - Remove PII fields

---

## Code Quality Patterns

### Pattern: Thread Safety for Shared State
**Finding Type**: potential_issue
**Detection**: Mutable class attributes without locks

```python
# Before
class Cache:
    def __init__(self):
        self._data = {}
    
    async def set(self, key, value):
        self._data[key] = value

# After
class Cache:
    def __init__(self):
        self._data = {}
        self._lock = asyncio.Lock()
    
    async def set(self, key, value):
        async with self._lock:
            self._data[key] = value
```

**Serena Tools**:
1. `find_symbol(name_path_pattern="Cache")` - Locate class
2. `get_symbols_overview(depth=1)` - List methods
3. `replace_symbol_body` - Add lock to __init__ and methods

---

### Pattern: Timezone-Naive Datetime
**Finding Type**: potential_issue
**Detection**: `datetime.fromisoformat()` without timezone check

```python
# Before
created_at = datetime.fromisoformat(data["created_at"])

# After
created_at = datetime.fromisoformat(data["created_at"])
if created_at.tzinfo is None:
    created_at = created_at.replace(tzinfo=timezone.utc)
```

**Serena Tools**:
1. `search_for_pattern(substring_pattern="fromisoformat")` - Find datetime parsing
2. `replace_content` - Add timezone check

---

### Pattern: Missing Pydantic Validators
**Finding Type**: refactor_suggestion
**Detection**: Numeric config fields without validation

```python
# Before
class Settings(BaseSettings):
    CACHE_TTL: int = 3600

# After
class Settings(BaseSettings):
    CACHE_TTL: int = 3600
    
    @field_validator("CACHE_TTL")
    @classmethod
    def validate_cache_ttl(cls, v):
        if v <= 0:
            raise ValueError("CACHE_TTL must be positive")
        return v
```

**Serena Tools**:
1. `find_symbol(name_path_pattern="Settings")` - Locate settings class
2. `insert_after_symbol` - Add validator after field

---

## TypeScript/Frontend Patterns

### Pattern: Comment-Code Inconsistency
**Finding Type**: refactor_suggestion
**Detection**: Comments that don't match implementation

```typescript
// Before
// Fallback: use first 100 chars
if (text.length <= 200) {

// After
// Fallback: use first 200 chars
if (text.length <= 200) {
```

**Serena Tools**:
1. `search_for_pattern` - Find inconsistent comments
2. `replace_content` - Update comment

---

### Pattern: Build Artifacts in Git
**Finding Type**: refactor_suggestion
**Detection**: `.tsbuildinfo`, `.cache`, etc. tracked in git

**Fix Steps**:
1. Add to `.gitignore`
2. Run `git rm --cached <file>`

**Serena Tools**:
1. `read_file(".gitignore")` - Check current ignores
2. `replace_content` - Add new ignore pattern
3. `execute_shell_command("git rm --cached ...")` - Remove from tracking

---

## Usage Guide

### When to Use These Patterns
1. CodeRabbit identifies an issue
2. Check this memory for matching pattern
3. Apply the fix using documented Serena tools
4. Update `coderabbit_findings.md` with resolution

### Adding New Patterns
When you discover a new fixable pattern:
1. Document the before/after code
2. List the Serena tools needed
3. Add to appropriate category
4. Test on sample code before adding

---

## Pattern Statistics

| Category | Patterns | Auto-Fixable |
|----------|----------|--------------|
| Security | 3 | 3 |
| Code Quality | 3 | 3 |
| Frontend | 2 | 2 |
| **Total** | **8** | **8** |
