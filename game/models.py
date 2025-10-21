from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json
import secrets

# Create your models here.

class GameSession(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting for Player'),
        ('active', 'Active'),
        ('completed', 'Completed'),
    ]
    
    session_code = models.CharField(max_length=8, unique=True, db_index=True)
    player1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='games_as_player1')
    player2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='games_as_player2', null=True, blank=True)
    
    initial_board = models.TextField()  # JSON string of initial puzzle
    current_board = models.TextField()  # JSON string of current state
    solution = models.TextField()  # JSON string of solution
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    current_turn = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='games_current_turn', null=True, blank=True)
    
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='games_won', null=True, blank=True)
    player1_score = models.IntegerField(default=0)
    player2_score = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Game {self.session_code} - {self.status}"
    
    @staticmethod
    def generate_session_code():
        """Generate a unique 8-character session code"""
        while True:
            code = secrets.token_urlsafe(6)[:8].upper()
            if not GameSession.objects.filter(session_code=code).exists():
                return code
    
    def get_initial_board(self):
        """Return the initial board as a 2D list"""
        return json.loads(self.initial_board)
    
    def get_current_board(self):
        """Return the current board as a 2D list"""
        return json.loads(self.current_board)
    
    def get_solution(self):
        """Return the solution as a 2D list"""
        return json.loads(self.solution)
    
    def set_initial_board(self, board):
        """Set the initial board from a 2D list"""
        self.initial_board = json.dumps(board)
    
    def set_current_board(self, board):
        """Set the current board from a 2D list"""
        self.current_board = json.dumps(board)
    
    def set_solution(self, solution):
        """Set the solution from a 2D list"""
        self.solution = json.dumps(solution)


class Move(models.Model):
    game = models.ForeignKey(GameSession, on_delete=models.CASCADE, related_name='moves')
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    
    row = models.IntegerField()
    col = models.IntegerField()
    value = models.IntegerField()
    
    is_valid = models.BooleanField(default=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"Move by {self.player.username} at ({self.row}, {self.col}) = {self.value}"

