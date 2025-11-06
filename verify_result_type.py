#!/usr/bin/env python
"""
Quick verification script to check if result_type column exists and works.
Run this on Render shell after deployment.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection
from game.models import GameResult, GameSession, User
from datetime import timedelta

def check_column_exists():
    """Check if result_type column exists."""
    print("=" * 60)
    print("1. CHECKING IF result_type COLUMN EXISTS")
    print("=" * 60)
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns 
            WHERE table_name = 'game_gameresult' 
            AND column_name = 'result_type';
        """)
        result = cursor.fetchone()
        
        if result:
            print(f"✅ Column exists: {result[0]} ({result[1]})")
            print(f"   Default: {result[2]}")
            return True
        else:
            print("❌ Column does NOT exist!")
            return False

def test_create_result():
    """Test creating a GameResult."""
    print("\n" + "=" * 60)
    print("2. TESTING GameResult CREATION")
    print("=" * 60)
    
    try:
        # Get or create test data
        user1 = User.objects.first()
        if not user1:
            print("❌ No users in database. Create a user first.")
            return False
        
        # Create a test game session
        from game.sudoku import SudokuPuzzle
        puzzle = SudokuPuzzle.generate_puzzle('easy')
        
        test_game = GameSession.objects.create(
            code='TEST_VERIFY',
            player1=user1,
            board={'puzzle': puzzle.board, 'solution': puzzle.solution},
            difficulty='easy',
            status='finished'
        )
        
        print(f"✅ Created test game: {test_game.code}")
        
        # Try to create result
        result = GameResult.objects.create(
            game=test_game,
            winner=user1,
            winner_time=timedelta(seconds=120),
            difficulty='easy',
            result_type='completion'
        )
        
        print(f"✅ Created GameResult successfully!")
        print(f"   ID: {result.id}")
        print(f"   Result Type: {result.result_type}")
        
        # Clean up
        result.delete()
        test_game.delete()
        print("✅ Cleaned up test data")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating GameResult: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n🔍 VERIFICATION SCRIPT FOR result_type COLUMN")
    print("Database:", connection.settings_dict['NAME'])
    print("")
    
    # Check column
    column_ok = check_column_exists()
    
    if not column_ok:
        print("\n❌ FAILED: Column doesn't exist")
        print("   Run: python force_add_result_type.py")
        sys.exit(1)
    
    # Test creation
    create_ok = test_create_result()
    
    if create_ok:
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("The result_type column is working correctly.")
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ TESTS FAILED")
        print("=" * 60)
        sys.exit(1)

if __name__ == '__main__':
    main()
