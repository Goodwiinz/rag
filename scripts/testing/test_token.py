#!/usr/bin/env python
"""Test token verification.

The JWT to verify is read from the TEST_JWT_TOKEN environment variable or the
first CLI argument so that no signed admin token lives in source control
(issue #379).
"""
import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))
os.chdir(os.path.join(os.getcwd(), "backend"))

from src.core.config import settings
from src.core.security import verify_token

token = os.environ.get("TEST_JWT_TOKEN") or (sys.argv[1] if len(sys.argv) > 1 else None)
if not token:
    sys.exit(
        "Usage: TEST_JWT_TOKEN=<jwt> python test_token.py  (or pass the token as the first argument)"
    )

print(f"JWT_SECRET_KEY from settings: {settings.JWT_SECRET_KEY[:20]}...")
print(f"JWT_ALGORITHM: {settings.JWT_ALGORITHM}")

# Try to verify
result = verify_token(token)
print(f"\nverify_token result: {result}")

if result:
    print(f"  user_id: {result.user_id}")
    print(f"  email: {result.email}")
    print(f"  role: {result.role}")
else:
    print("  Token verification FAILED")
    
    # Try manual decode to see the error
    from jose import jwt, JWTError
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        print(f"  Manual decode worked: {payload}")
    except JWTError as e:
        print(f"  Manual decode error: {e}")
