from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

User = get_user_model()

class GameSession(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting for player 2'),
        ('in_progress', 'In progress'),
        ('finished', 'Finished'),
    ]
    code = models.CharField(max_length=12, unique=True)
    player1 = models.ForeignKey(User, related_name='games_as_p1', on_delete=models.CASCADE)
    player2 = models.ForeignKey(User, related_name='games_as_p2', on_delete=models.CASCADE, null=True, blank=True)
    board = models.JSONField(default=dict)  # store initial puzzle and current state
    current_turn = models.ForeignKey(User, related_name='current_turn_games', on_delete=models.SET_NULL, null=True, blank=True)
    winner = models.ForeignKey(User, related_name='won_games', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
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
