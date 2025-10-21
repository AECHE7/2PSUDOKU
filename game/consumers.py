import json
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import GameSession, Move
from .sudoku import SudokuPuzzle


class GameConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time game play."""
    
    async def connect(self):
        self.code = self.scope['url_route']['kwargs']['code']
        self.group_name = f'game_{self.code}'
        self.user = self.scope['user']
        
        # Join the game channel group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        # Notify other players that someone connected
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'player_connected',
                'username': self.user.username if self.user.is_authenticated else 'Anonymous',
            }
        )
    
    async def disconnect(self, close_code):
        # Leave the group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        
        # Notify other players
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'player_disconnected',
                'username': self.user.username if self.user.is_authenticated else 'Anonymous',
            }
        )
    
    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None:
            return
        
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({'error': 'Invalid JSON'}))
            return
        
        message_type = data.get('type')
        
        if message_type == 'join_game':
            await self.handle_join_game(data)
        elif message_type == 'move':
            await self.handle_move(data)
        elif message_type == 'get_board':
            await self.handle_get_board(data)
        else:
            await self.send(text_data=json.dumps({'error': f'Unknown message type: {message_type}'}))
    
    async def handle_join_game(self, data):
        """Handle player joining a game."""
        game = await self.get_or_create_game()
        
        if game.player2 is None and game.player1.id != self.user.id:
            # Add second player
            await self.add_player2(game, self.user)
            await self.start_game(game)
        elif game.player2 and (game.player1.id == self.user.id or game.player2.id == self.user.id):
            # Rejoin existing game
            pass
        else:
            await self.send(text_data=json.dumps({'error': 'Cannot join this game'}))
            return
        
        # Send game state to client
        board_state = await self.get_board_state(game)
        await self.send(text_data=json.dumps({
            'type': 'game_state',
            'board': board_state,
            'player1': game.player1.username,
            'player2': game.player2.username if game.player2 else None,
        }))
    
    async def handle_move(self, data):
        """Handle a player placing a number."""
        row = data.get('row')
        col = data.get('col')
        value = data.get('value')
        
        if not all(isinstance(x, int) for x in [row, col, value]):
            await self.send(text_data=json.dumps({'error': 'Invalid move data'}))
            return
        
        game = await self.get_game()
        if not game:
            await self.send(text_data=json.dumps({'error': 'Game not found'}))
            return
        
        # Validate move server-side
        puzzle = SudokuPuzzle(json.loads(json.dumps(game.board.get('current', [[0]*9]*9))))
        if not puzzle.is_valid_placement(row, col, value):
            await self.send(text_data=json.dumps({'error': 'Invalid move'}))
            return
        
        # Record the move
        move = await self.create_move(game, self.user, row, col, value)
        
        # Update board state
        new_board = game.board.get('current', [[0]*9]*9)
        new_board[row][col] = value
        game.board['current'] = new_board
        await self.update_game_board(game, new_board)
        
        # Broadcast the move to all players
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'move_made',
                'username': self.user.username,
                'row': row,
                'col': col,
                'value': value,
            }
        )
    
    async def handle_get_board(self, data):
        """Send current board state to client."""
        game = await self.get_game()
        if not game:
            await self.send(text_data=json.dumps({'error': 'Game not found'}))
            return
        
        board_state = await self.get_board_state(game)
        await self.send(text_data=json.dumps({
            'type': 'board',
            'board': board_state,
        }))
    
    # Event handlers for group messages
    async def player_connected(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': f"{event['username']} connected",
        }))
    
    async def player_disconnected(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': f"{event['username']} disconnected",
        }))
    
    async def move_made(self, event):
        await self.send(text_data=json.dumps({
            'type': 'move',
            'username': event['username'],
            'row': event['row'],
            'col': event['col'],
            'value': event['value'],
        }))
    
    # Database operations
    @database_sync_to_async
    def get_or_create_game(self):
        """Get or create a game session."""
        code = self.code
        game, created = GameSession.objects.get_or_create(
            code=code,
            defaults={
                'player1': self.user,
                'board': {'puzzle': [[0]*9]*9, 'current': [[0]*9]*9},
            }
        )
        if created:
            # Generate a puzzle
            puzzle = SudokuPuzzle.generate_puzzle('medium')
            game.board = {
                'puzzle': puzzle.board,
                'current': [row[:] for row in puzzle.board],
            }
            game.current_turn = game.player1
            game.save()
        return game
    
    @database_sync_to_async
    def get_game(self):
        """Get the current game."""
        try:
            return GameSession.objects.get(code=self.code)
        except GameSession.DoesNotExist:
            return None
    
    @database_sync_to_async
    def add_player2(self, game, user):
        """Add second player to game and mark as in progress."""
        game.player2 = user
        game.status = 'in_progress'
        game.save()
    
    @database_sync_to_async
    def start_game(self, game):
        """Mark game as started."""
        game.status = 'in_progress'
        game.save()
    
    @database_sync_to_async
    def create_move(self, game, player, row, col, value):
        """Record a move in the database."""
        move = Move(game=game, player=player, row=row, col=col, value=value)
        move.save()
        return move
    
    @database_sync_to_async
    def update_game_board(self, game, new_board):
        """Update the game board state."""
        game.board['current'] = new_board
        game.save()
    
    @database_sync_to_async
    def get_board_state(self, game):
        """Get the current board state."""
        return game.board.get('current', [[0]*9]*9)

