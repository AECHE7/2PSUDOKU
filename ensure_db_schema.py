#!/usr/bin/env python
"""
Emergency database schema fixer.
Ensures critical columns exist before the server starts.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

def ensure_result_type_column():
    """Ensure result_type column exists in game_gameresult table."""
    print("🔍 Checking if result_type column exists...")
    
    with connection.cursor() as cursor:
        # Check if column exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'game_gameresult' 
                AND column_name = 'result_type'
            );
        """)
        exists = cursor.fetchone()[0]
        
        if exists:
            print("✅ result_type column already exists")
            return True
        
        print("⚠️  result_type column does not exist. Creating it now...")
        
        try:
            # Create the column with default value
            cursor.execute("""
                ALTER TABLE game_gameresult 
                ADD COLUMN result_type varchar(20) 
                DEFAULT 'completion' NOT NULL;
            """)
            
            # Update any NULL values (shouldn't be any with NOT NULL, but just in case)
            cursor.execute("""
                UPDATE game_gameresult 
                SET result_type = 'completion' 
                WHERE result_type IS NULL OR result_type = '';
            """)
            
            print("✅ Successfully created result_type column")
            return True
            
        except Exception as e:
            print(f"❌ Error creating result_type column: {e}")
            return False

def verify_all_tables():
    """Verify all required tables exist."""
    print("🔍 Verifying database tables...")
    
    required_tables = [
        'game_gamesession',
        'game_gameresult',
        'game_move',
        'auth_user'
    ]
    
    with connection.cursor() as cursor:
        for table in required_tables:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                );
            """, [table])
            exists = cursor.fetchone()[0]
            
            if exists:
                print(f"  ✅ Table {table} exists")
            else:
                print(f"  ❌ Table {table} MISSING!")
                return False
    
    return True

def main():
    """Main execution function."""
    print("=" * 60)
    print("🔧 Emergency Database Schema Fixer")
    print("=" * 60)
    
    try:
        # Verify tables exist
        if not verify_all_tables():
            print("❌ Some required tables are missing. Run migrations first!")
            sys.exit(1)
        
        # Ensure result_type column
        if not ensure_result_type_column():
            print("❌ Failed to ensure result_type column exists")
            sys.exit(1)
        
        print("=" * 60)
        print("✅ Database schema is ready!")
        print("=" * 60)
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
