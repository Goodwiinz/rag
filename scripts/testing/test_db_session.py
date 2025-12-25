#!/usr/bin/env python
"""Debug SQLAlchemy session"""
import sys
import os

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))
os.chdir(os.path.join(os.getcwd(), "backend"))

from src.core.config import settings
from src.core.database import SessionLocal
from src.models.user import User

print(f"DATABASE_URL: {settings.DATABASE_URL}")

db = SessionLocal()

# Simple query without filters
print("\nAll users in database:")
all_users = db.query(User).all()
for u in all_users:
    print(f"  {u.email} | is_active={u.is_active} | is_deleted={u.is_deleted}")

print(f"\nTotal users: {len(all_users)}")

# Try specific email lookup
email = "admin@multimodal-rag.com"
print(f"\nLooking up: {email}")
user = db.query(User).filter(User.email == email).first()
print(f"Result: {user}")

if user:
    print(f"  Found: {user.email}")
else:
    print("  NOT FOUND")

db.close()
