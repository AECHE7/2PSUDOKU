"""
Sudoku puzzle generation and validation logic
"""
import random
import copy


def is_valid_move(board, row, col, num):
    """Check if placing num at (row, col) is valid"""
    # Check row
    for j in range(9):
        if board[row][j] == num:
            return False
    
    # Check column
    for i in range(9):
        if board[i][col] == num:
            return False
    
    # Check 3x3 box
    box_row, box_col = 3 * (row // 3), 3 * (col // 3)
    for i in range(box_row, box_row + 3):
        for j in range(box_col, box_col + 3):
            if board[i][j] == num:
                return False
    
    return True


def solve_sudoku(board):
    """Solve sudoku using backtracking. Returns True if solved."""
    for i in range(9):
        for j in range(9):
            if board[i][j] == 0:
                for num in range(1, 10):
                    if is_valid_move(board, i, j, num):
                        board[i][j] = num
                        if solve_sudoku(board):
                            return True
                        board[i][j] = 0
                return False
    return True


def generate_full_board():
    """Generate a complete valid Sudoku board"""
    board = [[0 for _ in range(9)] for _ in range(9)]
    
    # Fill diagonal 3x3 boxes first (they're independent)
    for box in range(0, 9, 3):
        nums = list(range(1, 10))
        random.shuffle(nums)
        idx = 0
        for i in range(box, box + 3):
            for j in range(box, box + 3):
                board[i][j] = nums[idx]
                idx += 1
    
    # Solve the rest
    solve_sudoku(board)
    return board


def remove_numbers(board, difficulty=40):
    """Remove numbers from a complete board to create a puzzle.
    difficulty: number of cells to remove (40-50 for medium difficulty)
    """
    puzzle = copy.deepcopy(board)
    positions = [(i, j) for i in range(9) for j in range(9)]
    random.shuffle(positions)
    
    for i in range(min(difficulty, len(positions))):
        row, col = positions[i]
        puzzle[row][col] = 0
    
    return puzzle


def generate_sudoku_puzzle(difficulty=40):
    """Generate a Sudoku puzzle with solution.
    Returns: (puzzle, solution)
    """
    solution = generate_full_board()
    puzzle = remove_numbers(solution, difficulty)
    return puzzle, solution


def is_board_complete(board):
    """Check if board is completely filled (no zeros)"""
    for row in board:
        if 0 in row:
            return False
    return True


def check_board_correct(board, solution):
    """Check if the current board matches the solution"""
    for i in range(9):
        for j in range(9):
            if board[i][j] != 0 and board[i][j] != solution[i][j]:
                return False
    return True


def validate_move(board, solution, row, col, value):
    """Validate a move against the solution"""
    if row < 0 or row >= 9 or col < 0 or col >= 9:
        return False
    if value < 1 or value > 9:
        return False
    if board[row][col] != 0:  # Cell already filled
        return False
    return solution[row][col] == value
