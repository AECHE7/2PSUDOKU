#!/usr/bin/env python
"""
Demo script to test the 2P Sudoku game functionality
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sudoku_project.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth.models import User
from game.models import GameSession, Move
from game.sudoku_logic import generate_sudoku_puzzle


def create_demo_users():
    """Create demo users"""
    print("Creating demo users...")
    
    # Create or get users
    user1, created1 = User.objects.get_or_create(
        username='demo_player1',
        defaults={'email': 'player1@demo.com'}
    )
    if created1:
        user1.set_password('demo123')
        user1.save()
        print("✓ Created user: demo_player1")
    else:
        print("✓ User already exists: demo_player1")
    
    user2, created2 = User.objects.get_or_create(
        username='demo_player2',
        defaults={'email': 'player2@demo.com'}
    )
    if created2:
        user2.set_password('demo123')
        user2.save()
        print("✓ Created user: demo_player2")
    else:
        print("✓ User already exists: demo_player2")
    
    return user1, user2


def create_demo_game(user1, user2):
    """Create a demo game"""
    print("\nCreating demo game...")
    
    # Generate puzzle
    puzzle, solution = generate_sudoku_puzzle(difficulty=40)
    print("✓ Generated Sudoku puzzle")
    
    # Create game session
    game = GameSession.objects.create(
        session_code=GameSession.generate_session_code(),
        player1=user1,
        player2=user2,
        status='active',
        current_turn=user1
    )
    
    game.set_initial_board(puzzle)
    game.set_current_board(puzzle)
    game.set_solution(solution)
    game.save()
    
    print(f"✓ Created game with session code: {game.session_code}")
    return game


def display_board(board):
    """Display Sudoku board"""
    print("\n" + "="*37)
    for i, row in enumerate(board):
        if i % 3 == 0 and i != 0:
            print("  " + "-"*33)
        row_str = "  "
        for j, val in enumerate(row):
            if j % 3 == 0 and j != 0:
                row_str += "| "
            row_str += (str(val) if val != 0 else ".") + " "
        print(row_str)
    print("="*37 + "\n")


def simulate_moves(game):
    """Simulate some game moves"""
    print("\nSimulating game moves...")
    
    board = game.get_current_board()
    solution = game.get_solution()
    
    # Find first 5 empty cells and fill them
    moves_made = 0
    current_player = game.player1
    
    for i in range(9):
        for j in range(9):
            if board[i][j] == 0 and moves_made < 5:
                correct_value = solution[i][j]
                
                # Create move
                Move.objects.create(
                    game=game,
                    player=current_player,
                    row=i,
                    col=j,
                    value=correct_value,
                    is_valid=True
                )
                
                # Update board
                board[i][j] = correct_value
                game.set_current_board(board)
                
                # Update score
                if current_player == game.player1:
                    game.player1_score += 10
                    current_player = game.player2
                else:
                    game.player2_score += 10
                    current_player = game.player1
                
                game.save()
                
                print(f"✓ {current_player.username if current_player == game.player2 else game.player1.username} placed {correct_value} at ({i}, {j})")
                moves_made += 1
            
            if moves_made >= 5:
                break
        if moves_made >= 5:
            break
    
    print(f"\n✓ Made {moves_made} moves")
    return game


def display_game_info(game):
    """Display game information"""
    print("\nGame Information:")
    print("="*50)
    print(f"Session Code: {game.session_code}")
    print(f"Status: {game.get_status_display()}")
    print(f"Player 1: {game.player1.username} (Score: {game.player1_score})")
    print(f"Player 2: {game.player2.username} (Score: {game.player2_score})")
    print(f"Current Turn: {game.current_turn.username if game.current_turn else 'N/A'}")
    print(f"Total Moves: {game.moves.count()}")
    print("="*50)
    
    print("\nCurrent Board:")
    display_board(game.get_current_board())


def main():
    """Main demo function"""
    print("\n" + "="*50)
    print("  2-Player Sudoku Game - Functionality Demo")
    print("="*50 + "\n")
    
    try:
        # Create demo users
        user1, user2 = create_demo_users()
        
        # Create demo game
        game = create_demo_game(user1, user2)
        
        # Display initial board
        print("\nInitial Board:")
        display_board(game.get_initial_board())
        
        # Simulate moves
        game = simulate_moves(game)
        
        # Refresh game from database
        game.refresh_from_db()
        
        # Display game info
        display_game_info(game)
        
        print("\n✓ Demo completed successfully!")
        print(f"\nDemo credentials:")
        print(f"  Username: demo_player1 | Password: demo123")
        print(f"  Username: demo_player2 | Password: demo123")
        print(f"\nYou can now run the server and login with these credentials:")
        print(f"  python manage.py runserver")
        print(f"  Then visit: http://127.0.0.1:8000/")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
