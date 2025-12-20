#!/usr/bin/env python
"""Test token verification"""
import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))
os.chdir(os.path.join(os.getcwd(), "backend"))

from src.core.config import settings
from src.core.security import verify_token

# Token from successful login
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhNWU1YjJhYy0yMzQwLTQwYjgtYjIwOS1kYmQ3OWJkMTk2MDciLCJlbWFpbCI6ImFkbWluQG11bHRpbW9kYWwtcmFnLmNvbSIsIm9yZ2FuaXphdGlvbl9pZCI6IjFmNjA1M2JjLTk0NmYtNDY2MC1iYzdjLWNkM2MyODkwMTgwNiIsInJvbGUiOiJhZG1pbiIsImV4cCI6MTc2NjA4NDUwNX0.QUowR2SFF1G5Pt0izzfcnrA9rwVmIWPnAROKXX1WRMU"

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
