from django.contrib import admin
from .models import GameSession, Move

# Register your models here.

@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ['session_code', 'player1', 'player2', 'status', 'winner', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['session_code', 'player1__username', 'player2__username']
    readonly_fields = ['session_code', 'created_at', 'started_at', 'completed_at']

@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ['game', 'player', 'row', 'col', 'value', 'is_valid', 'timestamp']
    list_filter = ['is_valid', 'timestamp']
    search_fields = ['game__session_code', 'player__username']
    readonly_fields = ['timestamp']

