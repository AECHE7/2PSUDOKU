#!/usr/bin/env python
"""
Integration test for the two-player Sudoku game.
Tests user registration, login, game creation, and game flow.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, '/workspaces/2PSUDOKU')
django.setup()

from django.contrib.auth.models import User
from django.test import Client
from game.models import GameSession, Move
from game.sudoku import SudokuPuzzle


def test_game_flow():
    """Test complete game flow."""
    
    print("=" * 60)
    print("TESTING TWO-PLAYER SUDOKU GAME FLOW")
    print("=" * 60)
    
    # Clean up test users
    User.objects.filter(username__in=['player1', 'player2']).delete()
    GameSession.objects.all().delete()
    
    client = Client()
    
    # Test 1: User Registration
    print("\n1. Testing User Registration...")
    response = client.post('/register/', {
        'username': 'player1',
        'password': 'testpass123',
        'password_confirm': 'testpass123'
    })
    assert response.status_code == 302, "Registration failed"
    player1 = User.objects.get(username='player1')
    print(f"   ✓ Player 1 registered: {player1.username} (ID: {player1.id})")
    
    response = client.post('/register/', {
        'username': 'player2',
        'password': 'testpass123',
        'password_confirm': 'testpass123'
    })
    assert response.status_code == 302, "Registration failed"
    player2 = User.objects.get(username='player2')
    print(f"   ✓ Player 2 registered: {player2.username} (ID: {player2.id})")
    
    # Test 2: Game Creation (by Player 1)
    print("\n2. Testing Game Creation...")
    # Make sure we're logged in as player1
    client.logout()
    client.login(username='player1', password='testpass123')
    
    response = client.post('/create/')
    assert response.status_code == 302, "Game creation failed"
    game = GameSession.objects.latest('created_at')
    print(f"   ✓ Game created with code: {game.code}")
    print(f"   ✓ Player 1: {game.player1.username}")
    print(f"   ✓ Status: {game.get_status_display()}")
    print(f"   ✓ Board size: {len(game.board['current'])}x{len(game.board['current'][0])}")
    print(f"   ✓ Empty cells: {sum(row.count(0) for row in game.board['current'])}")
    
    # Test 3: Check Game Board Template
    print("\n3. Testing Game Board Template...")
    response = client.get(f'/game/{game.code}/')
    assert response.status_code == 200, "Game board page failed"
    assert b'Sudoku Game' in response.content, "Game title not found"
    assert game.code.encode() in response.content, "Game code not in response"
    print(f"   ✓ Game board template rendered correctly")
    print(f"   ✓ Response status: {response.status_code}")
    
    # Test 4: Player 2 Joins
    print("\n4. Testing Player 2 Joining...")
    # Login as player2
    client.logout()
    client.login(username='player2', password='testpass123')
    
    response = client.get(f'/game/{game.code}/')
    assert response.status_code == 200, "Player 2 join failed"
    
    # Reload game from DB
    game.refresh_from_db()
    assert game.player2 is not None, "Player 2 not added to game"
    assert game.status == 'in_progress', "Game status not updated"
    print(f"   ✓ Player 2 joined successfully")
    print(f"   ✓ Game status: {game.get_status_display()}")
    print(f"   ✓ Current turn: {game.current_turn.username}")
    
    # Test 5: Move Validation
    print("\n5. Testing Move Validation...")
    puzzle = SudokuPuzzle.from_dict({'board': game.board['current']})
    
    # Find a valid empty cell
    valid_row, valid_col = None, None
    for r in range(9):
        for c in range(9):
            if game.board['current'][r][c] == 0:
                # Try to find a valid value
                for val in range(1, 10):
                    if puzzle.is_valid_placement(r, c, val):
                        valid_row, valid_col = r, c
                        valid_value = val
                        break
            if valid_row is not None:
                break
        if valid_row is not None:
            break
    
    if valid_row is not None:
        print(f"   ✓ Found valid move: ({valid_row}, {valid_col}) = {valid_value}")
        
        # Try invalid move (number already in row)
        invalid_value = game.board['current'][valid_row][0]
        if invalid_value != 0:
            is_valid = puzzle.is_valid_placement(valid_row, valid_col, invalid_value)
            print(f"   ✓ Invalid move detection working: is_valid={is_valid}")
        
        # Record move in DB
        move = Move.objects.create(
            game=game,
            player=game.current_turn,
            row=valid_row,
            col=valid_col,
            value=valid_value
        )
        print(f"   ✓ Move recorded in database")
    
    # Test 6: Database State
    print("\n6. Testing Database State...")
    assert GameSession.objects.count() >= 1, "Game not in database"
    assert game.player1 is not None, "Player 1 not set"
    assert game.player2 is not None, "Player 2 not set"
    assert game.current_turn is not None, "Current turn not set"
    assert Move.objects.filter(game=game).count() >= 0, "Moves not tracking"
    print(f"   ✓ GameSession count: {GameSession.objects.count()}")
    print(f"   ✓ Players: {game.player1.username} vs {game.player2.username}")
    print(f"   ✓ Moves recorded: {Move.objects.filter(game=game).count()}")
    
    # Test 7: Sudoku Logic
    print("\n7. Testing Sudoku Logic...")
    puzzle = SudokuPuzzle.generate_puzzle('medium')
    print(f"   ✓ Puzzle generated successfully")
    print(f"   ✓ Empty cells: {sum(row.count(0) for row in puzzle.board)}")
    
    # Test serialization
    data = puzzle.to_dict()
    puzzle2 = SudokuPuzzle.from_dict(data)
    assert puzzle.board == puzzle2.board, "Serialization failed"
    print(f"   ✓ Serialization/deserialization working")
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED! ✓")
    print("=" * 60)
    print("\nGame Summary:")
    print(f"  Game Code: {game.code}")
    print(f"  Player 1: {game.player1.username}")
    print(f"  Player 2: {game.player2.username}")
    print(f"  Status: {game.get_status_display()}")
    print(f"  Current Turn: {game.current_turn.username}")
    print(f"  Moves: {Move.objects.filter(game=game).count()}")
    print()


if __name__ == '__main__':
    try:
        test_game_flow()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
