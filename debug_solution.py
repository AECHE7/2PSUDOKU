#!/usr/bin/env python3
"""
Quick test to debug solution validation.
"""

from game.sudoku import SudokuPuzzle

# Generate one puzzle
puzzle = SudokuPuzzle.generate_puzzle('easy')

print("Puzzle board:")
for row in puzzle.board:
    print(row)

print("\nSolution:")
for row in puzzle.solution:
    print(row)

print("\nTesting _is_valid_solution():")
test_puzzle = SudokuPuzzle(puzzle.solution)
result = test_puzzle._is_valid_solution()
print(f"Result: {result}")

# Manual validation
print("\nManual validation:")
print("Checking rows...")
for i, row in enumerate(puzzle.solution):
    row_set = set(row)
    expected = set(range(1, 10))
    if row_set != expected:
        print(f"Row {i} FAILED: {row_set} vs {expected}")
    else:
        print(f"Row {i} OK: {row}")

print("\nChecking columns...")
for col in range(9):
    column = [puzzle.solution[row][col] for row in range(9)]
    col_set = set(column)
    expected = set(range(1, 10))
    if col_set != expected:
        print(f"Column {col} FAILED: {col_set} vs {expected}")
        print(f"  Values: {column}")
    else:
        print(f"Column {col} OK")

print("\nChecking boxes...")
for box_row in range(0, 9, 3):
    for box_col in range(0, 9, 3):
        box_nums = []
        for r in range(box_row, box_row + 3):
            for c in range(box_col, box_col + 3):
                box_nums.append(puzzle.solution[r][c])
        box_set = set(box_nums)
        expected = set(range(1, 10))
        if box_set != expected:
            print(f"Box ({box_row},{box_col}) FAILED: {box_set} vs {expected}")
            print(f"  Values: {box_nums}")
        else:
            print(f"Box ({box_row},{box_col}) OK")
