from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import GameSession, Move
from .sudoku_logic import (
    generate_sudoku_puzzle,
    is_valid_move,
    validate_move,
    is_board_complete,
    check_board_correct
)

# Create your tests here.

class SudokuLogicTests(TestCase):
    """Test Sudoku puzzle generation and validation logic"""
    
    def test_generate_puzzle(self):
        """Test that puzzle generation works"""
        puzzle, solution = generate_sudoku_puzzle(difficulty=40)
        
        # Check dimensions
        self.assertEqual(len(puzzle), 9)
        self.assertEqual(len(solution), 9)
        for row in puzzle:
            self.assertEqual(len(row), 9)
        for row in solution:
            self.assertEqual(len(row), 9)
        
        # Check that puzzle has empty cells
        empty_count = sum(1 for row in puzzle for cell in row if cell == 0)
        self.assertGreater(empty_count, 0)
        
        # Check that solution has no empty cells
        empty_in_solution = sum(1 for row in solution for cell in row if cell == 0)
        self.assertEqual(empty_in_solution, 0)
    
    def test_validate_move(self):
        """Test move validation"""
        puzzle, solution = generate_sudoku_puzzle(difficulty=40)
        
        # Find first empty cell
        row, col = None, None
        for i in range(9):
            for j in range(9):
                if puzzle[i][j] == 0:
                    row, col = i, j
                    break
            if row is not None:
                break
        
        self.assertIsNotNone(row)
        correct_value = solution[row][col]
        wrong_value = (correct_value % 9) + 1
        
        # Test correct move
        self.assertTrue(validate_move(puzzle, solution, row, col, correct_value))
        
        # Test incorrect move
        self.assertFalse(validate_move(puzzle, solution, row, col, wrong_value))
        
        # Test already filled cell
        for i in range(9):
            for j in range(9):
                if puzzle[i][j] != 0:
                    self.assertFalse(validate_move(puzzle, solution, i, j, puzzle[i][j]))
                    break
    
    def test_is_board_complete(self):
        """Test board completion check"""
        puzzle, solution = generate_sudoku_puzzle()
        
        # Puzzle should not be complete
        self.assertFalse(is_board_complete(puzzle))
        
        # Solution should be complete
        self.assertTrue(is_board_complete(solution))


class GameSessionModelTests(TestCase):
    """Test GameSession model"""
    
    def setUp(self):
        self.user1 = User.objects.create_user(username='player1', password='pass123')
        self.user2 = User.objects.create_user(username='player2', password='pass123')
    
    def test_create_game_session(self):
        """Test creating a game session"""
        puzzle, solution = generate_sudoku_puzzle()
        game = GameSession.objects.create(
            session_code=GameSession.generate_session_code(),
            player1=self.user1,
            status='waiting'
        )
        game.set_initial_board(puzzle)
        game.set_current_board(puzzle)
        game.set_solution(solution)
        game.save()
        
        self.assertEqual(game.status, 'waiting')
        self.assertEqual(game.player1, self.user1)
        self.assertIsNone(game.player2)
        self.assertEqual(len(game.session_code), 8)
    
    def test_session_code_generation(self):
        """Test unique session code generation"""
        code1 = GameSession.generate_session_code()
        code2 = GameSession.generate_session_code()
        
        self.assertEqual(len(code1), 8)
        self.assertEqual(len(code2), 8)
        # Codes should be different (with very high probability)
        self.assertNotEqual(code1, code2)


class AuthenticationTests(TestCase):
    """Test user authentication views"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
    
    def test_home_page(self):
        """Test home page loads"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
    
    def test_register_page(self):
        """Test registration page loads"""
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
    
    def test_login_page(self):
        """Test login page loads"""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
    
    def test_register_user(self):
        """Test user registration"""
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'password': 'newpass123',
            'password_confirm': 'newpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after success
        self.assertTrue(User.objects.filter(username='newuser').exists())
    
    def test_login_user(self):
        """Test user login"""
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after success
    
    def test_lobby_requires_login(self):
        """Test that lobby requires authentication"""
        response = self.client.get(reverse('lobby'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
        # Login and try again
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('lobby'))
        self.assertEqual(response.status_code, 200)


class GameFlowTests(TestCase):
    """Test game creation and joining flow"""
    
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='player1', password='pass123')
        self.user2 = User.objects.create_user(username='player2', password='pass123')
    
    def test_create_game(self):
        """Test game creation"""
        self.client.login(username='player1', password='pass123')
        response = self.client.get(reverse('create_game'))
        
        # Should redirect to game room
        self.assertEqual(response.status_code, 302)
        
        # Game should exist
        game = GameSession.objects.filter(player1=self.user1).first()
        self.assertIsNotNone(game)
        self.assertEqual(game.status, 'waiting')
    
    def test_join_game(self):
        """Test joining a game"""
        # Create a game as player1
        self.client.login(username='player1', password='pass123')
        self.client.get(reverse('create_game'))
        game = GameSession.objects.filter(player1=self.user1).first()
        
        # Join as player2
        self.client.logout()
        self.client.login(username='player2', password='pass123')
        response = self.client.get(reverse('join_game', args=[game.session_code]))
        
        # Should redirect to game room
        self.assertEqual(response.status_code, 302)
        
        # Game should be active
        game.refresh_from_db()
        self.assertEqual(game.status, 'active')
        self.assertEqual(game.player2, self.user2)

