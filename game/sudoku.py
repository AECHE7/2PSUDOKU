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
    
    @staticmethod
    def generate_puzzle(difficulty: str = 'medium') -> 'SudokuPuzzle':
        """Generate a random valid Sudoku puzzle."""
        puzzle = SudokuPuzzle()
        puzzle._generate_full_solution()
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
            'easy': 30,
            'medium': 40,
            'hard': 50,
        }
        cells_to_remove = difficulty_map.get(difficulty, 40)
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
        """Check if the puzzle is completely filled."""
        for row in self.board:
            if 0 in row:
                return False
        return self._is_valid_solution()
    
    def _is_valid_solution(self) -> bool:
        """Verify the entire board is a valid solution."""
        for row in range(9):
            for col in range(9):
                num = self.board[row][col]
                if num == 0:
                    return False
                # Temporarily remove to check if it's valid
                self.board[row][col] = 0
                if not self._is_valid_move(row, col, num):
                    self.board[row][col] = num
                    return False
                self.board[row][col] = num
        return True
    
    def to_dict(self) -> dict:
        """Convert board to dictionary for JSON serialization."""
        return {
            'board': self.board,
            'size': 9,
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'SudokuPuzzle':
        """Create puzzle from dictionary."""
        return SudokuPuzzle(data.get('board', [[0]*9]*9))
