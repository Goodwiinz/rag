#!/usr/bin/env python
"""Simulate full auth_service login to debug"""
import sys
import os

# Add paths
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))
os.chdir(os.path.join(os.getcwd(), "backend"))

# Import like the app does
from src.core.config import settings
from src.core.database import SessionLocal
from src.core.security import verify_password
from src.models.user import User
from sqlalchemy import and_

print(f"DATABASE_URL from settings: {settings.DATABASE_URL}")

# Open database session
db = SessionLocal()

email = "admin@multimodal-rag.com"
password = "admin123"

print(f"\nLooking for user: {email}")

# Query exactly like auth_service.py line 51-59
from sqlalchemy.orm import joinedload
user = db.query(User).options(
    joinedload(User.organization)
).filter(
    and_(
        User.email == email.lower(),
        User.is_active == True,
        User.is_deleted == False
    )
).first()

if not user:
    print(f"User not found!")
    db.close()
    sys.exit(1)

print(f"User found: {user.email}")
print(f"User is_active: {user.is_active}")
print(f"User is_deleted: {user.is_deleted}")
print(f"Password hash prefix: {user.password_hash[:20]}")

# Verify password exactly like auth_service.py line 61
print(f"\nTesting verify_password('{password}', hash)...")
result = verify_password(password, user.password_hash)
print(f"verify_password result: {result}")

if not result:
    print("\nPassword verification FAILED!")
    print("This explains the 401 error.")
else:
    print("\nPassword verification PASSED!")
    print("The login should work - something else is wrong.")

db.close()
