#!/usr/bin/env python
"""
Force add result_type column to game_gameresult table.
This script directly manipulates the database schema.
Run this ONCE on production after deployment.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

def add_result_type_column():
    """Add result_type column if it doesn't exist."""
    
    print("=" * 70)
    print("FORCE ADDING result_type COLUMN TO game_gameresult")
    print("=" * 70)
    
    with connection.cursor() as cursor:
        # Check if column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'game_gameresult' 
            AND column_name = 'result_type';
        """)
        
        result = cursor.fetchone()
        
        if result:
            print("✅ Column 'result_type' already exists in game_gameresult")
            print("   No action needed.")
            return True
        
        print("⚠️  Column 'result_type' does NOT exist")
        print("   Adding column now...")
        
        try:
            # Add the column with default value
            cursor.execute("""
                ALTER TABLE game_gameresult 
                ADD COLUMN result_type VARCHAR(20) 
                DEFAULT 'completion' NOT NULL;
            """)
            
            print("✅ Successfully added 'result_type' column")
            
            # Update existing rows (if any)
            cursor.execute("""
                UPDATE game_gameresult 
                SET result_type = 'completion' 
                WHERE result_type IS NULL OR result_type = '';
            """)
            
            print("✅ Updated existing records with default value")
            
            # Verify the column was added
            cursor.execute("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns 
                WHERE table_name = 'game_gameresult' 
                AND column_name = 'result_type';
            """)
            
            verify = cursor.fetchone()
            if verify:
                print(f"✅ Verified: {verify[0]} ({verify[1]}) DEFAULT {verify[2]}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error adding column: {e}")
            import traceback
            traceback.print_exc()
            return False

def verify_table_structure():
    """Display current table structure."""
    print("\n" + "=" * 70)
    print("CURRENT game_gameresult TABLE STRUCTURE")
    print("=" * 70)
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'game_gameresult'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        
        if columns:
            print(f"\n{'Column':<20} {'Type':<15} {'Nullable':<10} {'Default':<20}")
            print("-" * 70)
            for col in columns:
                print(f"{col[0]:<20} {col[1]:<15} {col[2]:<10} {str(col[3]):<20}")
        else:
            print("❌ Table 'game_gameresult' not found!")
            return False
    
    return True

def main():
    """Main execution."""
    try:
        print("\n🔧 DATABASE SCHEMA FIX UTILITY")
        print(f"Database: {connection.settings_dict['NAME']}")
        print(f"Host: {connection.settings_dict['HOST']}\n")
        
        # Verify table exists
        if not verify_table_structure():
            print("\n❌ Please run migrations first: python manage.py migrate")
            sys.exit(1)
        
        # Add the column
        if add_result_type_column():
            print("\n" + "=" * 70)
            print("✅ SUCCESS - result_type column is ready!")
            print("=" * 70)
            
            # Show final structure
            verify_table_structure()
            
            print("\n✅ You can now restart your application.")
            sys.exit(0)
        else:
            print("\n❌ Failed to add result_type column")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
