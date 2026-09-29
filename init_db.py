"""
Database Initialization Script for Shram setuu
Usage:
    python init_db.py          # Safely initializes schema (preserves existing data)
    python init_db.py --reset  # Resets and re-seeds clean demo data
"""
import sys
from database import init_db

if __name__ == '__main__':
    force = '--reset' in sys.argv or '-r' in sys.argv
    print(f"Initializing Shram setuu SQLite database (force_reset={force})...")
    init_db(force_reset=force)
    print("Database initialization complete!")
