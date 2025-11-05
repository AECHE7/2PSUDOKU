#!/usr/bin/env python3
"""
Test puzzle generation to ensure no invalid initial boards.
"""

from game.sudoku import SudokuPuzzle

def validate_puzzle(puzzle):
    """Validate that a puzzle has no conflicts in initial state."""
    board = puzzle.board
    errors = []
    
    # Check each filled cell doesn't conflict
    for row in range(9):
        for col in range(9):
            if board[row][col] != 0:
                num = board[row][col]
                
                # Check row conflicts (excluding current cell)
                row_values = [board[row][c] for c in range(9) if c != col and board[row][c] != 0]
                if num in row_values:
                    errors.append(f"Row conflict at ({row},{col}): {num} appears multiple times in row {row}")
                
                # Check column conflicts (excluding current cell)
                col_values = [board[r][col] for r in range(9) if r != row and board[r][col] != 0]
                if num in col_values:
                    errors.append(f"Column conflict at ({row},{col}): {num} appears multiple times in column {col}")
                
                # Check box conflicts (excluding current cell)
                box_row = (row // 3) * 3
                box_col = (col // 3) * 3
                box_values = []
                for r in range(box_row, box_row + 3):
                    for c in range(box_col, box_col + 3):
                        if (r != row or c != col) and board[r][c] != 0:
                            box_values.append(board[r][c])
                if num in box_values:
                    errors.append(f"Box conflict at ({row},{col}): {num} appears multiple times in box starting at ({box_row},{box_col})")
    
    return errors

def print_board(board):
    """Pretty print a Sudoku board."""
    for i, row in enumerate(board):
        if i % 3 == 0 and i != 0:
            print("------+-------+------")
        row_str = ""
        for j, val in enumerate(row):
            if j % 3 == 0 and j != 0:
                row_str += "| "
            row_str += str(val if val != 0 else '.') + " "
        print(row_str)

def test_generation(difficulty, count=5):
    """Test puzzle generation for a given difficulty."""
    print(f"\n{'='*60}")
    print(f"Testing {difficulty.upper()} difficulty ({count} puzzles)")
    print('='*60)
    
    for i in range(count):
        print(f"\n--- Puzzle #{i+1} ---")
        puzzle = SudokuPuzzle.generate_puzzle(difficulty)
        
        # Count empty cells
        empty_cells = sum(1 for row in puzzle.board for cell in row if cell == 0)
        filled_cells = 81 - empty_cells
        
        print(f"Empty cells: {empty_cells}, Filled cells: {filled_cells}")
        
        # Validate the puzzle
        errors = validate_puzzle(puzzle)
        
        if errors:
            print(f"\n❌ ERRORS FOUND IN PUZZLE #{i+1}:")
            for error in errors:
                print(f"  - {error}")
            print("\nPuzzle board:")
            print_board(puzzle.board)
            print("\nSolution:")
            print_board(puzzle.solution)
            return False
        else:
            print(f"✅ Puzzle #{i+1} is valid")
        
        # Verify solution is actually complete
        if puzzle.solution:
            # Create a puzzle object with the solution to validate it
            solution_puzzle = SudokuPuzzle(puzzle.solution)
            solution_errors = validate_puzzle(solution_puzzle)
            if solution_errors:
                print(f"❌ SOLUTION HAS ERRORS:")
                for error in solution_errors:
                    print(f"  - {error}")
                return False
            
            # Check solution is actually complete (all cells 1-9)
            if not solution_puzzle._is_valid_solution():
                print(f"❌ Solution validation failed!")
                print_board(puzzle.solution)
                return False
            else:
                print(f"✅ Solution is valid and complete")
    
    print(f"\n✅ All {count} {difficulty} puzzles passed validation!")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("SUDOKU PUZZLE GENERATION VALIDATION TEST")
    print("=" * 60)
    
    all_passed = True
    
    # Test each difficulty
    for difficulty in ['easy', 'medium', 'hard']:
        if not test_generation(difficulty, count=10):
            all_passed = False
            break
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED - Puzzle generation is working correctly!")
    else:
        print("❌ TESTS FAILED - There are issues with puzzle generation!")
    print("=" * 60)
