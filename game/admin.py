from django.contrib import admin
from .models import GameSession, Move

@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ('code', 'player1', 'player2', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('code', 'player1__username', 'player2__username')

@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ('game', 'player', 'row', 'col', 'value', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('game__code', 'player__username')
