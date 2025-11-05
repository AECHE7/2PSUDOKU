from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

User = get_user_model()

class GameSession(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting for player 2'),
        ('ready', 'Both players joined, ready to start'),
        ('in_progress', 'Game in progress'),
        ('finished', 'Game finished'),
        ('abandoned', 'Game abandoned by player'),
    ]
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    code = models.CharField(max_length=12, unique=True)
    player1 = models.ForeignKey(User, related_name='games_as_p1', on_delete=models.CASCADE)
    player2 = models.ForeignKey(User, related_name='games_as_p2', on_delete=models.CASCADE, null=True, blank=True)
    board = models.JSONField(default=dict)  # store initial puzzle and player states
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    winner = models.ForeignKey(User, related_name='won_games', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    
    class Meta:
        ordering = ['-created_at']

class Move(models.Model):
    game = models.ForeignKey(GameSession, related_name='moves', on_delete=models.CASCADE)
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    row = models.IntegerField()
    col = models.IntegerField()
    value = models.IntegerField()
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['timestamp']


class GameResult(models.Model):
    """Store game results and records for competitive play."""
    RESULT_TYPE_CHOICES = [
        ('completion', 'Won by completing puzzle first'),
        ('forfeit', 'Won by opponent forfeit/abandonment'),
        ('timeout', 'Won by opponent timeout'),
    ]
    
    game = models.OneToOneField(GameSession, on_delete=models.CASCADE, related_name='result')
    winner = models.ForeignKey(User, related_name='won_results', on_delete=models.CASCADE)
    loser = models.ForeignKey(User, related_name='lost_results', on_delete=models.CASCADE)
    winner_time = models.DurationField()  # Time taken by winner to solve
    loser_time = models.DurationField(null=True, blank=True)  # Time taken by loser (if they finished)
    difficulty = models.CharField(max_length=10, choices=GameSession.DIFFICULTY_CHOICES)
    result_type = models.CharField(max_length=20, choices=RESULT_TYPE_CHOICES, default='completion')
    completed_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-completed_at']
        
    def __str__(self):
        if self.result_type == 'forfeit':
            return f"{self.winner.username} won by forfeit vs {self.loser.username} ({self.difficulty})"
        return f"{self.winner.username} beat {self.loser.username} in {self.winner_time} ({self.difficulty})"
