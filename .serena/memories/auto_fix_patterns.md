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
bandit -ll -ii backend/src/services/research/export_service.py
# Result: No issues identified
```

**Test Case**:
```python
# Malicious input that should be escaped
malicious_input = "<script>alert('XSS')</script>"
# After fix, renders as: &lt;script&gt;alert('XSS')&lt;/script&gt;
```

---

### 2. XXE Vulnerability (CWE-20)

**Issue**: XML External Entity vulnerability allows file disclosure, SSRF, and DoS attacks via malicious XML.

**Bandit Code**: B314  
**Fixed In**: GOO-153  
**Date**: 2026-01-27

**Pattern**:
```python
# ❌ VULNERABLE
import xml.etree.ElementTree as ET
root = ET.fromstring(xml_data)

# ✅ FIXED - Use defusedxml
from defusedxml import ElementTree as ET
root = ET.fromstring(xml_data)  # Prevents XXE, DTD, entity expansion
```

**Files Fixed**:
- `backend/src/services/arxiv/arxiv_service.py:10` (import)
- `backend/requirements.txt:21` (added defusedxml==0.7.1)

**Verification**:
```bash
bandit -ll -ii backend/src/services/arxiv/arxiv_service.py
# Result: No high-severity issues (was 1)
```

**Test Case**:
```python
# Malicious XXE payload
malicious_xml = """<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<feed>&xxe;</feed>
"""
# Should raise DefusedXmlException instead of reading file
```

---

### 3. Pickle Deserialization Vulnerability (CWE-502)

**Issue**: Unsafe pickle deserialization allows remote code execution via malicious serialized objects.

**Bandit Code**: B301  
**Fixed In**: GOO-154  
**Date**: 2026-01-27

**Pattern**:
```python
# ❌ VULNERABLE
import pickle
data = pickle.loads(untrusted_data)  # RCE risk!

# ✅ FIXED - HMAC-signed pickle
import hmac
import hashlib
import pickle

def secure_pickle_dumps(obj: Any) -> bytes:
    """Serialize with HMAC-SHA256 signature."""
    pickled_data = pickle.dumps(obj)
    signature = hmac.new(SECRET_KEY, pickled_data, hashlib.sha256).digest()
    return signature + pickled_data  # [32-byte sig][data]

def secure_pickle_loads(data: bytes) -> Any:
    """Deserialize after signature validation."""
    signature = data[:32]
    pickled_data = data[32:]
    
    # Verify HMAC
    expected = hmac.new(SECRET_KEY, pickled_data, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Invalid HMAC - tampering detected")
    
    return pickle.loads(pickled_data)  # Safe after validation
```

**Files Fixed**:
- `backend/src/core/caching.py:147-205` (added HMAC functions)

**Verification**:
```bash
bandit -ll -ii backend/src/core/caching.py
# Result: No high/medium severity issues (was 2 medium)
```

**Test Case**:
```python
# Attack: Malicious pickle payload
class Exploit:
    def __reduce__(self):
        return (os.system, ('rm -rf /',))

malicious = pickle.dumps(Exploit())
# ❌ Without HMAC: Would execute rm -rf /
# ✅ With HMAC: Raises ValueError("Invalid HMAC - tampering detected")
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
