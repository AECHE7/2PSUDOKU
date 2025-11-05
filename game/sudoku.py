"""
Sudoku puzzle generator, validator, and solver.
"""

import random
from typing import List, Tuple, Set, Optional

class SudokuPuzzle:
    """Generate and manage Sudoku puzzles."""
    
    GRID_SIZE = 9
    BOX_SIZE = 3
    EMPTY = 0
    
    def __init__(self, board: Optional[List[List[int]]] = None):
        """Initialize with an optional board (9x9 grid)."""
        if board is None:
            self.board = [[0 for _ in range(9)] for _ in range(9)]
        else:
            self.board = [row[:] for row in board]
        
        # Store the solution separately (for validation)
        self.solution = None
    
    @staticmethod
    def generate_puzzle(difficulty: str = 'medium') -> 'SudokuPuzzle':
        """Generate a random valid Sudoku puzzle and store the solution."""
        puzzle = SudokuPuzzle()
        puzzle._generate_full_solution()
        
        # Store the complete solution before removing cells
        puzzle.solution = [row[:] for row in puzzle.board]
        
        puzzle._remove_cells(difficulty)
        return puzzle
    
    def _generate_full_solution(self):
        """Generate a complete valid Sudoku solution."""
        for row in range(9):
            for col in range(9):
                if self.board[row][col] == 0:
                    numbers = list(range(1, 10))
                    random.shuffle(numbers)
                    for num in numbers:
                        if self._is_valid_move(row, col, num):
                            self.board[row][col] = num
                            if self._generate_full_solution():
                                return True
                            self.board[row][col] = 0
                    return False
        return True
    
    def _remove_cells(self, difficulty: str):
        """Remove cells based on difficulty level."""
        difficulty_map = {
            'easy': 9,      # Only 9 empty cells (72 filled) - SUPER EASY for testing/racing
            'medium': 35,   # 35 empty cells (46 filled)
            'hard': 55,     # 55 empty cells (26 filled)
        }
        cells_to_remove = difficulty_map.get(difficulty, 35)
        removed = 0
        while removed < cells_to_remove:
            row = random.randint(0, 8)
            col = random.randint(0, 8)
            if self.board[row][col] != 0:
                self.board[row][col] = 0
                removed += 1
    
    def _is_valid_move(self, row: int, col: int, num: int) -> bool:
        """Check if placing num at (row, col) is valid."""
        # Check row
        if num in self.board[row]:
            return False
        
        # Check column
        if num in [self.board[r][col] for r in range(9)]:
            return False
        
        # Check 3x3 box
        box_row = (row // 3) * 3
        box_col = (col // 3) * 3
        for r in range(box_row, box_row + 3):
            for c in range(box_col, box_col + 3):
                if self.board[r][c] == num:
                    return False
        
        return True
    
    def is_valid_placement(self, row: int, col: int, num: int) -> bool:
        """Check if a move is valid (used during gameplay)."""
        if not (0 <= row < 9 and 0 <= col < 9):
            return False
        if num < 1 or num > 9:
            return False
        return self._is_valid_move(row, col, num)
    
    def is_complete(self) -> bool:
        """Check if the puzzle is completely filled and valid."""
        # First check if all cells are filled
        for row in self.board:
            if 0 in row:
                return False
        return self._is_valid_solution()
    
    def matches_solution(self) -> bool:
        """Check if the current board matches the stored solution exactly."""
        if not self.solution:
            # If no solution stored, fall back to validation
            return self.is_complete()
        
        # Check if all cells are filled
        for row in self.board:
            if 0 in row:
                return False
        
        # Compare with solution
        for row in range(9):
            for col in range(9):
                if self.board[row][col] != self.solution[row][col]:
                    return False
        
        return True
    
    def _is_valid_solution(self) -> bool:
        """Verify the entire board is a valid solution using efficient set-based validation."""
        # Check all rows have 1-9
        for row in self.board:
            if set(row) != set(range(1, 10)):
                return False
        
        # Check all columns have 1-9
        for col in range(9):
            column = [self.board[row][col] for row in range(9)]
            if set(column) != set(range(1, 10)):
                return False
        
        # Check all 3x3 boxes have 1-9
        for box_row in range(0, 9, 3):
            for box_col in range(0, 9, 3):
                box_nums = []
                for r in range(box_row, box_row + 3):
                    for c in range(box_col, box_col + 3):
                        box_nums.append(self.board[r][c])
                if set(box_nums) != set(range(1, 10)):
                    return False
        
        return True
    
    def to_dict(self) -> dict:
        """Convert board to dictionary for JSON serialization."""
        result = {
            'board': self.board,
            'size': 9,
        }
        if self.solution:
            result['solution'] = self.solution
        return result
    
    @staticmethod
    def from_dict(data: dict) -> 'SudokuPuzzle':
        """Create puzzle from dictionary."""
        puzzle = SudokuPuzzle(data.get('board', [[0]*9]*9))
        puzzle.solution = data.get('solution')
        return puzzle
