#!/usr/bin/env python3
"""
Comprehensive migration script for 2PSUDOKU race mode deployment.
Ensures all database migrations are applied before starting the server.
"""

import os
import sys
import django
from pathlib import Path

# Add the project directory to Python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Setup Django
django.setup()

def run_migrations():
    """Run all pending migrations and verify critical tables."""
    from django.core.management import execute_from_command_line
    from django.db import connection
    
    print("🔄 Running comprehensive database migrations...")
    
    try:
        # Run all migrations
        print("📋 Applying all pending migrations...")
        execute_from_command_line(['manage.py', 'migrate', '--verbosity=2'])
        
        # Verify critical tables exist using Django ORM (database-agnostic)
        print("🔍 Verifying database schema...")
        from django.contrib.auth.models import User
        from game.models import GameSession, GameResult
        
        try:
            # Test if we can query basic models
            User.objects.count()
            print("✅ auth_user table: EXISTS")
            auth_exists = True
        except Exception:
            print("❌ auth_user table: MISSING")
            auth_exists = False
        
        try:
            # Test if GameSession has difficulty field
            game = GameSession.objects.first()
            if game:
                _ = game.difficulty  # This will fail if column doesn't exist
            print("✅ difficulty column: EXISTS")
            difficulty_exists = True
        except Exception:
            print("❌ difficulty column: MISSING")
            difficulty_exists = False
            
        try:
            # Test if GameResult table exists
            GameResult.objects.count()
            print("✅ game_gameresult table: EXISTS")
            result_table_exists = True
        except Exception:
            print("❌ game_gameresult table: MISSING")
            result_table_exists = False
            
        if not (auth_exists and difficulty_exists and result_table_exists):
            print("❌ Some required schema elements are missing!")
            return False
                
        print("🎉 All migrations completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == '__main__':
    success = run_migrations()
    sys.exit(0 if success else 1)