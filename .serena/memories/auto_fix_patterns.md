# Auto-Fix Patterns

Reusable patterns for the coderabbit-auto-fixer agent. These patterns are safe to apply automatically.

## Pattern Categories

| Category | Auto-Fix Safe | Confidence |
|----------|---------------|------------|
| Security - Credentials | ✅ Yes | High |
| Bash - Return Values | ✅ Yes | High |
| Python - Defensive Checks | ⚠️ Partial | Medium |
| Python - Validation | ⚠️ Partial | Medium |
| Documentation | ✅ Yes | High |
| Error Handling | ⚠️ Partial | Medium |

---

## 1. Security: Remove Hardcoded Credentials

**Pattern ID**: `SEC-001`
**Risk Level**: Critical
**Auto-Fix Safe**: ✅ Yes

### Detection
```regex
(password|secret|api_key|token)\s*[:=]\s*[`"'][\w\-]+[`"']
```

### Fix Template
Replace hardcoded values with environment variable references:

**Before:**
```markdown
- User: `neo4j`
- Password: `password`
```

**After:**
```markdown
- User: Environment variable `NEO4J_USER` (default: `neo4j` for dev)
- Password: Environment variable `NEO4J_PASSWORD` (set in docker-compose)

> **Note**: Never commit actual credentials. Use environment variables or a secrets manager.
```

### Shell Command Pattern
**Before:**
```bash
-u neo4j -p password
```

**After:**
```bash
-u ${NEO4J_USER:-neo4j} -p ${NEO4J_PASSWORD:-password}
```

---

## 2. Bash: Separate Declaration and Assignment

**Pattern ID**: `BASH-001`
**Risk Level**: Medium
**Auto-Fix Safe**: ✅ Yes

### Detection
```regex
local\s+(\w+)=\$\(
```

### Problem
Combining `local` with command substitution masks the exit code.

### Fix Template
**Before:**
```bash
local file_type=$(detect_file_type "$FILE_PATH")
```

**After:**
```bash
local file_type
file_type=$(detect_file_type "$FILE_PATH")
```

### Serena Command
```
replace_content with regex:
  needle: local\s+(\w+)=\$\((.+)\)
  repl: local $!1\n$!1=$($!2)
```

---

## 3. Python: Defensive API Response Checks

**Pattern ID**: `PY-001`
**Risk Level**: High
**Auto-Fix Safe**: ⚠️ Partial (review context)

### Detection - OpenAI
```python
response.choices[0].message.content
```

### Fix Template - OpenAI
**Before:**
```python
title = response.choices[0].message.content.strip()
```

**After:**
```python
if not response.choices or not response.choices[0].message.content:
    logger.warning("OpenAI returned empty response")
    return None
title = response.choices[0].message.content.strip()
```

### Detection - Anthropic
```python
response.content[0].text
```

### Fix Template - Anthropic
**Before:**
```python
title = response.content[0].text.strip()
```

**After:**
```python
if not response.content or not response.content[0].text:
    logger.warning("Anthropic returned empty response")
    return None
title = response.content[0].text.strip()
```

---

## 4. Python: WebSocket Broadcast Error Handling

**Pattern ID**: `PY-002`
**Risk Level**: Medium
**Auto-Fix Safe**: ⚠️ Partial (review imports)

### Detection
```python
await.*broadcast_.*\(
```

### Problem
WebSocket broadcast failures should not fail the API endpoint.

### Fix Template
**Before:**
```python
await thread_event_service.broadcast_thread_created(
    thread_id=str(thread.id),
    conversation_id=str(thread.conversation_id),
    user_id=str(current_user.id),
    title=thread.title,
)
```

**After:**
```python
try:
    await thread_event_service.broadcast_thread_created(
        thread_id=str(thread.id),
        conversation_id=str(thread.conversation_id),
        user_id=str(current_user.id),
        title=thread.title,
    )
except Exception as e:
    logger.error(f"Failed to broadcast thread_created event: {e}")
```

---

## 5. Python: Pydantic Field/Validator Alignment

**Pattern ID**: `PY-003`
**Risk Level**: Medium
**Auto-Fix Safe**: ⚠️ Partial (check logic)

### Problem A: Inconsistent Limits
Field max_length doesn't match validator limit.

**Fix**: Align Field constraint with validator:
```python
# If validator limits to 10, Field should too
contexts: List[str] = Field(default_factory=list, max_length=10)
```

### Problem B: Required Field with None Check
Field is required but validator checks for None (unreachable).

**Fix**: Make field optional for auto-calculation:
```python
# Before
overall_score: float = Field(..., ge=0.0, le=1.0)

# After
overall_score: Optional[float] = Field(None, ge=0.0, le=1.0)
```

---

## 6. Documentation: Docstring/Export Alignment

**Pattern ID**: `DOC-001`
**Risk Level**: Low
**Auto-Fix Safe**: ✅ Yes

### Problem
Docstring usage examples reference symbols not in `__all__`.

### Fix Options
1. Update docstring to match actual exports
2. Add missing symbols to `__all__`

### Example Fix
```python
"""
Usage:
    from src.core.ai import AIClient, EmbeddingClient, CompletionResponse
"""
```

---

## 7. Python: Config Field Validators

**Pattern ID**: `PY-004`
**Risk Level**: Low
**Auto-Fix Safe**: ✅ Yes

### Pattern
Add validators for numeric/float config fields.

### Template
```python
@field_validator("FIELD_NAME")
@classmethod
def validate_field_name(cls, v):
    if v < MIN or v > MAX:
        raise ValueError(f"FIELD_NAME must be between {MIN} and {MAX}")
    return v
```

### Common Validations
| Field Type | Min | Max |
|------------|-----|-----|
| max_messages | 1 | 1000 |
| max_tokens | 1 | 200000 |
| threshold (float) | 0.0 | 1.0 |

---

## Usage Guide

### Applying a Pattern

1. **Identify pattern** from CodeRabbit finding type
2. **Check auto-fix safety** in the table above
3. **Use Serena tools**:
   - `replace_content` with regex for simple patterns
   - `replace_symbol_body` for function/method changes
   - `insert_before_symbol` / `insert_after_symbol` for adding code

### Example Workflow

```
1. Read issue from Linear: mcp__plugin_linear_linear__get_issue
2. Read affected file: mcp__serena__read_file
3. Find pattern match in this file
4. Apply fix using appropriate Serena tool
5. Verify with: mcp__serena__read_file (check changes)
6. Update Linear: mcp__plugin_linear_linear__update_issue
```

---

## Fix History

| Date | Pattern | Issue | File | Status |
|------|---------|-------|------|--------|
| 2026-01-11 | SEC-001 | GOO-68 | .serena/memories/database_fixes_and_indexing.md | ✅ Fixed |
| 2026-01-11 | BASH-001 | GOO-69 | scripts/verify-fix.sh | ✅ Fixed |
| 2026-01-11 | PY-001 | GOO-70 | backend/src/services/thread_title_generator.py | ✅ Fixed |
| 2026-01-11 | PY-003 | GOO-71 | backend/src/core/ai/schemas.py | ✅ Fixed |
| 2026-01-11 | PY-002 | GOO-72 | backend/src/api/threads.py | ✅ Fixed |
| 2026-01-11 | DOC-001 | GOO-73 | backend/src/core/ai/__init__.py | ✅ Fixed |
| 2026-01-11 | PY-004 | GOO-74 | backend/src/core/config.py | ✅ Fixed |

---

*Last updated: 2026-01-11*
