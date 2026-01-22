#!/usr/bin/env python3
"""
Database initialization script
"""

import sys
import os
import argparse

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from src.core.database import create_tables, init_database, check_database_health, get_database_info

def main():
    parser = argparse.ArgumentParser(description='Database initialization script')
    parser.add_argument('--init', action='store_true', help='Initialize database with seed data')
    parser.add_argument('--create-tables', action='store_true', help='Create database tables')
    parser.add_argument('--check', action='store_true', help='Check database health')
    parser.add_argument('--info', action='store_true', help='Show database information')
    parser.add_argument('--force', action='store_true', help='Force initialization even if data exists')

    args = parser.parse_args()

    if args.check:
        print("Checking database health...")
        if check_database_health():
            print("✅ Database is healthy")
        else:
            print("❌ Database health check failed")
            sys.exit(1)

    if args.create_tables:
        print("Creating database tables...")
        create_tables()
        print("✅ Tables created successfully")

    if args.init:
        print("Initializing database...")
        if args.force:
            # For force init, we would need to drop and recreate
            print("⚠️  Force initialization not implemented yet")
        else:
            init_database()

    if args.info:
        print("Getting database information...")
        info = get_database_info()
        print("\n📊 Database Information:")
        for key, value in info.items():
            print(f"   {key.replace('_', ' ').title()}: {value}")

    if not any([args.check, args.create_tables, args.init, args.info]):
        print("Database Management Script")
        print("Usage: python init_db.py [options]")
        print("\nOptions:")
        print("  --init         Initialize database with seed data")
        print("  --create-tables Create database tables")
        print("  --check        Check database health")
        print("  --info         Show database information")
        print("  --force        Force initialization")
        print("\nExample:")
        print("  python init_db.py --init")
        print("  python init_db.py --check --info")

if __name__ == "__main__":
    main()