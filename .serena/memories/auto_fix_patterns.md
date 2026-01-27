# Auto-Fix Patterns

Reusable patterns for fixing common security vulnerabilities and code issues.

## Security Fixes

### 1. Jinja2 XSS Vulnerability (CWE-94)

**Issue**: Jinja2 templates without autoescape enabled allow XSS attacks through user-controlled content.

**Bandit Code**: B701  
**Fixed In**: GOO-152  
**Date**: 2026-01-27

**Pattern**:
```python
# ❌ VULNERABLE
from jinja2 import Environment, BaseLoader
self._env = Environment(loader=BaseLoader())

# ✅ FIXED - HTML/XML templates
from jinja2 import Environment, BaseLoader, select_autoescape
self._env = Environment(
    loader=BaseLoader(),
    autoescape=select_autoescape(['html', 'xml'])
)

# ✅ FIXED - All templates (defense-in-depth)
self._env = Environment(
    loader=BaseLoader(),
    autoescape=True
)
```

**Files Fixed**:
- `backend/src/services/research/export_service.py:213` (MarkdownFormatter)
- `backend/src/services/research/export_service.py:238` (HTMLFormatter)

**Verification**:
```bash
bandit -ll -ii <file.py>
# Should show: No issues identified
```

**Test Case**:
```python
# Malicious input that should be escaped
malicious_input = "<script>alert('XSS')</script>"
# After fix, renders as: &lt;script&gt;alert('XSS')&lt;/script&gt;
```

---

## Pattern Template

When adding new patterns, use this format:

```markdown
### N. Vulnerability Name (CWE-XXX)

**Issue**: Brief description of the vulnerability

**Bandit Code**: BXXX  
**Fixed In**: GOO-XXX  
**Date**: YYYY-MM-DD

**Pattern**:
```python
# ❌ VULNERABLE
<vulnerable code>

# ✅ FIXED
<fixed code>
```

**Files Fixed**:
- `path/to/file.py:line` (description)

**Verification**:
```bash
<verification command>
```

**Test Case**:
```python
<test case showing the fix works>
```
```

---

## Usage

1. **Before fixing**: Search this file for similar patterns
2. **During fix**: Follow the established pattern
3. **After fixing**: Add new pattern if not already documented
4. **Testing**: Always verify fix with bandit or appropriate tool
