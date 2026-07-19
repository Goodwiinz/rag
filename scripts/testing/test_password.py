#!/usr/bin/env python
"""Test password verification to debug login issues"""
import sys
import os

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

from sqlalchemy import create_engine, text
import bcrypt

# First, connect to DB and get the hash
db_url = "postgresql://postgres:postgres@localhost:5432/multimodal_rag_dev"
engine = create_engine(db_url)

email = "admin@multimodal-rag.com"
password = "REDACTED"

with engine.connect() as conn:
    result = conn.execute(text("SELECT password_hash FROM users WHERE email = :email"), {"email": email})
    row = result.fetchone()
    if not row:
        print(f"User {email} not found!")
        sys.exit(1)
    
    stored_hash = row[0]
    print(f"Stored hash: {stored_hash}")
    print(f"Hash length: {len(stored_hash)}")
    print(f"Hash starts with $2: {stored_hash.startswith('$2')}")
    
    # Test bcrypt verification
    try:
        pwd_bytes = password[:72].encode('utf-8')
        hash_bytes = stored_hash.encode('utf-8')
        result = bcrypt.checkpw(pwd_bytes, hash_bytes)
        print(f"bcrypt.checkpw result: {result}")
    except Exception as e:
        print(f"bcrypt.checkpw error: {e}")
    
    # Generate a new hash and compare
    new_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    print(f"New hash would be: {new_hash}")

print("Done!")
