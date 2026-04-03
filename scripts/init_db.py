#!/usr/bin/env python3
"""
Database Initialization Script.

Usage:
    python init_db.py           # Initialize database if missing
    python init_db.py --reset   # Delete existing database and recreate
"""
import sys
import argparse
from modules.config import Config
from modules.db.session_store import SessionStore

def init_db(reset: bool = False):
    db_path = Config.DB_PATH
    print(f"Target Database: {db_path}")

    if db_path.exists():
        if reset:
            print("⚠️  --reset flag provided. Deleting existing database...")
            db_path.unlink()
            print("✅ Database file deleted.")
        else:
            print("ℹ️  Database already exists. Run with --reset to recreate.")
            return

    # Initialize store (this triggers schema creation)
    print("Initializing SessionStore...")
    store = SessionStore()
    
    # Verify
    if db_path.exists():
        tables = store.get_session_count()
        print(f"✅ Database initialized successfully at {db_path}.")
        print(f"   Current session count: {tables}")
    else:
        print("❌ Failed to create database file.")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize Tri_Dashboard Database")
    parser.add_argument("--reset", action="store_true", help="Delete existing database and recreate")
    args = parser.parse_args()
    
    init_db(args.reset)
