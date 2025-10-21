"""
Tests for Sudoku puzzle generation and validation.
"""

from django.test import TestCase
from game.sudoku import SudokuPuzzle


class SudokuPuzzleTestCase(TestCase):
    """Test Sudoku puzzle generation and validation."""
    
    def test_puzzle_generation(self):
        """Test that a puzzle can be generated without errors."""
        puzzle = SudokuPuzzle.generate_puzzle('medium')
        self.assertIsNotNone(puzzle)
        self.assertEqual(len(puzzle.board), 9)
        for row in puzzle.board:
            self.assertEqual(len(row), 9)
    
    def test_puzzle_has_empty_cells(self):
        """Test that generated puzzle has some empty cells."""
        puzzle = SudokuPuzzle.generate_puzzle('medium')
        empty_count = sum(row.count(0) for row in puzzle.board)
        self.assertGreater(empty_count, 0)
    
    def test_is_valid_move(self):
        """Test move validation."""
        puzzle = SudokuPuzzle()
        puzzle.board = [
            [5, 3, 0, 0, 7, 0, 0, 0, 0],
            [6, 0, 0, 1, 9, 5, 0, 0, 0],
            [0, 9, 8, 0, 0, 0, 0, 6, 0],
            [8, 0, 0, 0, 6, 0, 0, 0, 3],
            [4, 0, 0, 8, 0, 3, 0, 0, 1],
            [7, 0, 0, 0, 2, 0, 0, 0, 6],
            [0, 6, 0, 0, 0, 0, 2, 8, 0],
            [0, 0, 0, 4, 1, 9, 0, 0, 5],
            [0, 0, 0, 0, 8, 0, 0, 7, 9],
        ]
        
        # Valid move
        self.assertTrue(puzzle.is_valid_placement(0, 2, 4))
        
        # Invalid: number already in row
        self.assertFalse(puzzle.is_valid_placement(0, 2, 5))
        
        # Invalid: number already in column
        self.assertFalse(puzzle.is_valid_placement(1, 0, 6))
        
        # Invalid: number already in box
        self.assertFalse(puzzle.is_valid_placement(0, 2, 3))
    
    def test_is_complete(self):
        """Test completion check."""
        puzzle = SudokuPuzzle()
        
        # Empty puzzle is not complete
        self.assertFalse(puzzle.is_complete())
        
        # Fill with valid solution
        puzzle.board = [
            [5, 3, 4, 6, 7, 8, 9, 1, 2],
            [6, 7, 2, 1, 9, 5, 3, 4, 8],
            [1, 9, 8, 3, 4, 2, 5, 6, 7],
            [8, 5, 9, 7, 6, 1, 4, 2, 3],
            [4, 2, 6, 8, 5, 3, 7, 9, 1],
            [7, 1, 3, 9, 2, 4, 8, 5, 6],
            [9, 6, 1, 5, 3, 7, 2, 8, 4],
            [2, 8, 7, 4, 1, 9, 6, 3, 5],
            [3, 4, 5, 2, 8, 6, 1, 7, 9],
        ]
        
        # Valid complete puzzle should be recognized
        self.assertTrue(puzzle.is_complete())
    
    def test_to_and_from_dict(self):
        """Test serialization/deserialization."""
        puzzle1 = SudokuPuzzle()
        puzzle1.board[0][0] = 5
        
        data = puzzle1.to_dict()
        puzzle2 = SudokuPuzzle.from_dict(data)
        
        self.assertEqual(puzzle1.board, puzzle2.board)
