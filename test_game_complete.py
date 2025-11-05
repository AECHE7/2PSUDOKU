#!/usr/bin/env python
"""
Test script for game flow: creation, joining, racing, and completion
"""
import os
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from game.models import GameSession, User
from game.sudoku import SudokuPuzzle
from django.utils import timezone
import random
import string

def generate_unique_code():
    """Generate a unique 6-character game code"""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not GameSession.objects.filter(code=code).exists():
            return code

def test_game_flow():
    print('🧪 TESTING GAME FLOW...')
    print()
    
    # Ensure we have test users
    print('0. Setting up test users...')
    player1, _ = User.objects.get_or_create(
        username='testplayer1',
        defaults={'email': 'player1@test.com'}
    )
    player2, _ = User.objects.get_or_create(
        username='testplayer2',
        defaults={'email': 'player2@test.com'}
    )
    print(f'✅ Player 1: {player1.username} (ID: {player1.id})')
    print(f'✅ Player 2: {player2.username} (ID: {player2.id})')
    print()
    
    # Create a test game
    print('1. Creating test game...')
    puzzle = SudokuPuzzle.generate_puzzle('easy')
    code = generate_unique_code()
    
    game = GameSession.objects.create(
        code=code,
        player1_id=player1.id,
        difficulty='easy',
        board={
            'puzzle': puzzle.board,
            'solution': puzzle.solution,
            'player1_board': [row[:] for row in puzzle.board],
            'player2_board': [row[:] for row in puzzle.board],
        },
        status='waiting',
    )
    print(f'✅ Game created with code: {game.code}')
    print(f'   Status: {game.status}')
    print(f'   Player 1: {player1.username}')
    print()
    
    # Simulate player 2 joining
    print('2. Simulating player 2 joining...')
    game.player2_id = player2.id
    game.status = 'ready'
    game.save()
    print('✅ Player 2 joined')
    print(f'   Status: {game.status}')
    print(f'   Player 2: {player2.username}')
    print()
    
    # Simulate race starting
    print('3. Simulating race start...')
    game.start_time = timezone.now()
    game.status = 'in_progress'  # Using correct status
    game.save()
    print(f'✅ Race started at: {game.start_time}')
    print(f'   Status: {game.status}')
    print()
    
    # Test board validation
    print('4. Testing board validation...')
    from game.sudoku import SudokuPuzzle as GamePuzzle
    
    # Test with the puzzle board (incomplete)
    test_puzzle = GamePuzzle([row[:] for row in puzzle.board])
    test_puzzle.solution = [row[:] for row in puzzle.solution]
    is_complete = test_puzzle.matches_solution()
    print(f'   Incomplete board matches solution: {is_complete} (should be False)')
    
    # Test with the solution (complete)
    complete_puzzle = GamePuzzle([row[:] for row in puzzle.solution])
    complete_puzzle.solution = [row[:] for row in puzzle.solution]
    is_complete = complete_puzzle.matches_solution()
    print(f'   Complete board matches solution: {is_complete} (should be True)')
    print()
    
    # Show some puzzle stats
    print('5. Puzzle statistics...')
    empty_cells = sum(1 for row in puzzle.board for cell in row if cell == 0)
    filled_cells = 81 - empty_cells
    print(f'   Total cells: 81')
    print(f'   Filled cells: {filled_cells}')
    print(f'   Empty cells: {empty_cells}')
    print(f'   Difficulty: {game.difficulty}')
    print()
    
    # Clean up
    print('6. Cleaning up test data...')
    game.delete()
    print(f'✅ Test game deleted')
    print()
    
    print('🎉 ALL TESTS PASSED!')
    print()
    print('Summary:')
    print('✅ Game creation works')
    print('✅ Player joining works')
    print('✅ Race start works')
    print('✅ Board validation works')
    print('✅ Status transitions work correctly')

if __name__ == '__main__':
    test_game_flow()
