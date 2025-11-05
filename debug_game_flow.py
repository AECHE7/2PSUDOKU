#!/usr/bin/env python3
"""
Debug script to test the complete Sudoku racing game flow.
This script simulates the game flow to identify issues.
"""

import os
import sys
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from game.models import GameSession, GameResult
from game.sudoku import SudokuPuzzle
from django.contrib.auth.models import User

def test_game_creation():
    """Test game creation flow."""
    print("🧪 Testing game creation...")

    # Create test users
    user1, created1 = User.objects.get_or_create(
        username='test_player1',
        defaults={'email': 'test1@example.com'}
    )
    user2, created2 = User.objects.get_or_create(
        username='test_player2',
        defaults={'email': 'test2@example.com'}
    )

    print(f"👤 User 1: {user1.username} (ID: {user1.id})")
    print(f"👤 User 2: {user2.username} (ID: {user2.id})")

    # Create game
    puzzle = SudokuPuzzle.generate_puzzle('easy')
    game = GameSession.objects.create(
        code='DEBUG123',
        player1=user1,
        difficulty='easy',
        board={
            'puzzle': puzzle.board,
            'solution': puzzle.solution,
            'player1_board': [row[:] for row in puzzle.board],
            'player2_board': [row[:] for row in puzzle.board],
        },
        status='waiting',
    )

    print(f"🎮 Game created: {game.code} (ID: {game.id})")
    print(f"📊 Initial status: {game.status}")
    print(f"🧩 Puzzle has {sum(row.count(0) for row in puzzle.board)} empty cells")

    return game, user1, user2

def test_player_joining(game, user2):
    """Test second player joining."""
    print("\n🧪 Testing player joining...")

    # Simulate player 2 joining
    game.player2 = user2
    game.status = 'ready'
    game.save()

    print(f"👥 Player 2 joined: {user2.username}")
    print(f"📊 Status changed to: {game.status}")

    return game

def test_race_start(game):
    """Test race starting."""
    print("\n🧪 Testing race start...")

    # Simulate race start
    game.start_time = datetime.now()
    game.status = 'in_progress'
    game.save()

    print(f"🏁 Race started at: {game.start_time}")
    print(f"📊 Status: {game.status}")

    return game

def test_completion_flow(game, winner, loser):
    """Test completion and winner announcement."""
    print("\n🧪 Testing completion flow...")

    # Simulate winner completing puzzle
    completion_time = datetime.now() - game.start_time

    # Create game result
    result = GameResult.objects.create(
        game=game,
        winner=winner,
        loser=loser,
        winner_time=completion_time,
        difficulty=game.difficulty,
        result_type='completion'
    )

    game.winner = winner
    game.status = 'finished'
    game.end_time = datetime.now()
    game.save()

    print(f"🏆 Winner: {winner.username}")
    print(f"⏱️ Completion time: {completion_time}")
    print(f"📊 Game status: {game.status}")

    return result

def test_rematch_flow(game, user1, user2):
    """Test rematch creation."""
    print("\n🧪 Testing rematch flow...")

    # Create new game for rematch
    puzzle = SudokuPuzzle.generate_puzzle('easy')
    new_game = GameSession.objects.create(
        code='REMATCH456',
        player1=user1,
        player2=user2,
        difficulty='easy',
        board={
            'puzzle': puzzle.board,
            'solution': puzzle.solution,
            'player1_board': [row[:] for row in puzzle.board],
            'player2_board': [row[:] for row in puzzle.board],
        },
        status='ready',
    )

    print(f"🔄 New game created: {new_game.code}")
    print(f"👥 Same players: {user1.username} vs {user2.username}")

    return new_game

def main():
    """Run the complete game flow test."""
    print("🎯 Starting Sudoku Racing Game Flow Debug")
    print("=" * 50)

    try:
        # Clean up any existing test data
        GameSession.objects.filter(code__in=['DEBUG123', 'REMATCH456']).delete()
        GameResult.objects.filter(game__code__in=['DEBUG123', 'REMATCH456']).delete()

        # Test complete flow
        game, user1, user2 = test_game_creation()
        game = test_player_joining(game, user2)
        game = test_race_start(game)
        result = test_completion_flow(game, user1, user2)
        new_game = test_rematch_flow(game, user1, user2)

        print("\n✅ All tests completed successfully!")
        print("🎮 Game flow appears to work at database level")

        # Summary
        print("\n📋 Summary:")
        print(f"   - Original game: {game.code} ({game.status})")
        print(f"   - Winner: {result.winner.username}")
        print(f"   - Rematch: {new_game.code} ({new_game.status})")

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
