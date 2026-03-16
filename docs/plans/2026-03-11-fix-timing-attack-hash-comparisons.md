# Fix Timing Attack in Hash Comparisons — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace unsafe `==` string comparisons with `secrets.compare_digest()` in two hash verification functions, close PRs #204, #183, and #131 (all duplicates of the same fix).

**Architecture:** Two functions use `==` to compare hash strings, enabling timing attacks. Fix is surgical — swap `==` for `secrets.compare_digest()` in both locations. Add unit tests. Rebase onto develop, drop out-of-scope file changes from the Jules bot, squash-merge.

**Tech Stack:** Python stdlib `secrets.compare_digest()`, pytest

---

## Context

Three open PRs target the same vulnerability:

- **#204** — fixes `security.py` + `encryption.py` (most complete)
- **#183** — fixes `security.py` only (subset of #204)
- **#131** — fixes `security.py` only (subset of #204)

We'll use #204 as the base (it covers both files), fix its out-of-scope changes, merge it, then close #183 and #131 as superseded.

### Vulnerable Code

1. **`backend/src/core/security.py:415`** — `verify_sensitive_data_hash()`

   ```python
   return hashlib.sha256(data.encode()).hexdigest() == hashed
   ```

2. **`backend/src/core/encryption.py:559`** — `HashUtils.verify_password()`
   ```python
   return test_hash == hashed_password
   ```

### Already Safe (no changes needed)

- `api_key_auth.py:103` — uses `secrets.compare_digest()` ✅
- `encryption.py:614` — uses `secrets.compare_digest()` for HMAC ✅
- `caching.py:179` — uses `hmac.compare_digest()` ✅
- `security.py:61` — uses `bcrypt.checkpw()` (constant-time) ✅

---

### Task 1: Fix `verify_sensitive_data_hash()` in security.py

**Files:**

- Modify: `backend/src/core/security.py:411-415`

**Step 1: Apply the fix**

Replace:

```python
def verify_sensitive_data_hash(data: str, hashed: str) -> bool:
    """Verify sensitive data against its hash"""
    import hashlib

    return hashlib.sha256(data.encode()).hexdigest() == hashed
```

With:

```python
def verify_sensitive_data_hash(data: str, hashed: str) -> bool:
    """Verify sensitive data against its hash using constant-time comparison"""
    import hashlib
    import secrets

    return secrets.compare_digest(hashlib.sha256(data.encode()).hexdigest(), hashed)
```

---

### Task 2: Fix `HashUtils.verify_password()` in encryption.py

**Files:**

- Modify: `backend/src/core/encryption.py:558-559`

**Step 1: Apply the fix**

Replace:

```python
test_hash, _ = HashUtils.hash_password(password, salt)
return test_hash == hashed_password
```

With:

```python
import secrets
test_hash, _ = HashUtils.hash_password(password, salt)
return secrets.compare_digest(test_hash, hashed_password)
```

---

### Task 3: Add unit tests

**Files:**

- Create: `backend/tests/unit/test_timing_safe_comparisons.py`

**Step 1: Write tests**

```python
import hashlib
import pytest
from src.core.security import verify_sensitive_data_hash
from src.core.encryption import HashUtils


class TestVerifySensitiveDataHash:
    def test_valid_hash_returns_true(self):
        data = "my-secret-data"
        hashed = hashlib.sha256(data.encode()).hexdigest()
        assert verify_sensitive_data_hash(data, hashed) is True

    def test_invalid_hash_returns_false(self):
        data = "my-secret-data"
        assert verify_sensitive_data_hash(data, "wrong_hash") is False

    def test_wrong_data_returns_false(self):
        hashed = hashlib.sha256(b"original").hexdigest()
        assert verify_sensitive_data_hash("tampered", hashed) is False


class TestHashUtilsVerifyPassword:
    def test_correct_password_returns_true(self):
        password = "password123"
        hashed, salt = HashUtils.hash_password(password)
        assert HashUtils.verify_password(password, hashed, salt) is True

    def test_wrong_password_returns_false(self):
        password = "password123"
        hashed, salt = HashUtils.hash_password(password)
        assert HashUtils.verify_password("wrong", hashed, salt) is False

    def test_wrong_salt_returns_false(self):
        password = "password123"
        hashed, salt = HashUtils.hash_password(password)
        assert HashUtils.verify_password(password, hashed, b"wrong_salt") is False
```

**Step 2: Run tests**

```bash
pytest backend/tests/unit/test_timing_safe_comparisons.py -v
```

Expected: 6 passed

---

### Task 4: Rebase PR #204, drop out-of-scope changes, push, merge

**Step 1: Checkout and rebase**

```bash
git checkout sentinel/fix-timing-attacks-14983909776090055932
git rebase origin/develop
```

**Step 2: Revert out-of-scope files** (if not auto-dropped by rebase)

```bash
git checkout origin/develop -- frontend/src/lib/supabase.ts backend/requirements.txt backend/requirements-minimal.txt
```

**Step 3: Verify only in-scope files remain**

```bash
git diff origin/develop --name-only
```

Expected files:

- `backend/src/core/security.py`
- `backend/src/core/encryption.py`
- `backend/src/tests/test_encryption_security.py` (PR's test file)
- `backend/tests/unit/test_timing_safe_comparisons.py` (our test file)

**Step 4: Run tests**

```bash
pytest backend/tests/unit/test_timing_safe_comparisons.py backend/src/tests/test_encryption_security.py -v
```

Expected: all pass

**Step 5: Force push and squash merge**

```bash
git push --force-with-lease origin sentinel/fix-timing-attacks-14983909776090055932
gh pr merge 204 --squash --subject "fix: timing attack in hash comparisons (#204)"
```

---

### Task 5: Close duplicate PRs

**Step 1: Close #183 and #131 as superseded**

```bash
gh pr close 183 --comment "Superseded by #204 which covers both security.py and encryption.py."
gh pr close 131 --comment "Superseded by #204 which covers both security.py and encryption.py."
```

---

## Files Modified

| File                                                 | Change                                                              |
| ---------------------------------------------------- | ------------------------------------------------------------------- |
| `backend/src/core/security.py`                       | `==` → `secrets.compare_digest()` in `verify_sensitive_data_hash()` |
| `backend/src/core/encryption.py`                     | `==` → `secrets.compare_digest()` in `HashUtils.verify_password()`  |
| `backend/tests/unit/test_timing_safe_comparisons.py` | New: 6 unit tests                                                   |
| `backend/src/tests/test_encryption_security.py`      | From PR: 4 unit tests                                               |

## Verification

```bash
pytest backend/tests/unit/test_timing_safe_comparisons.py backend/src/tests/test_encryption_security.py -v
```
