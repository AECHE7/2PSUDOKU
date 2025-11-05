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
        # Create or get the game and operate using its id to keep DB work inside sync wrappers
        game_id = await self.get_or_create_game()

        # Get player info safely with async calls (by id)
        game_info = await self.get_game_player_info(game_id)

        if not game_info['player2_id'] and game_info['player1_id'] != getattr(self.user, 'id', None):
            # Add second player
            await self.add_player2(game_id, self.user.id)
            await self.start_game(game_id)
            # Refresh game info after adding player
            game_info = await self.get_game_player_info(game_id)
        elif game_info['player2_id'] and (game_info['player1_id'] == self.user.id or game_info['player2_id'] == self.user.id):
            # Rejoin existing game
            pass
        else:
            await self.send(text_data=json.dumps({'error': 'Cannot join this game'}))
            return
        
        # Send game state to client (fetch board via id)
        board_state = await self.get_board_state(game_id)
        await self.send(text_data=json.dumps({
            'type': 'game_state',
            'board': board_state,
            'player1': game_info['player1_username'],
            'player2': game_info['player2_username'],
        }))
    
    async def handle_move(self, data):
        """Handle a player placing a number."""
        row = data.get('row')
        col = data.get('col')
        value = data.get('value')
        
        if not all(isinstance(x, int) for x in [row, col, value]):
            await self.send(text_data=json.dumps({'error': 'Invalid move data'}))
            return
        
        # Resolve game id first
        game_id = await self.get_game_id()
        if not game_id:
            await self.send(text_data=json.dumps({'error': 'Game not found'}))
            return

        # Check if it's this player's turn (async-safe)
        current_turn_id = await self.get_current_turn_id(game_id)
        if current_turn_id != getattr(self.user, 'id', None):
            await self.send(text_data=json.dumps({'error': 'Not your turn'}))
            return
        
        # Validate move server-side (fetch board state via id)
        current_board = await self.get_board_state(game_id)
        puzzle = SudokuPuzzle.from_dict({'board': current_board})
        if not puzzle.is_valid_placement(row, col, value):
            await self.send(text_data=json.dumps({'error': 'Invalid move'}))
            return
        
        # Record the move
        move = await self.create_move(game_id, self.user.id, row, col, value)

        # Update board state
        new_board = [list(r) for r in current_board]
        new_board[row][col] = value
        await self.update_game_board(game_id, new_board)
        
        # Switch current turn (async-safe)
        next_player_info = await self.switch_turn(game_id)
        await self.update_game_turn(game_id, next_player_info['next_player_id'])
        
        # Broadcast the move to all players
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'move_made',
                'username': self.user.username,
                'row': row,
                'col': col,
                'value': value,
                'next_player_id': next_player_info['next_player_id'],
                'next_player_username': next_player_info['next_player_username'],
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
        
        # Send turn update
        await self.send(text_data=json.dumps({
            'type': 'current_turn_updated',
            'player_id': event['next_player_id'],
            'username': event['next_player_username'],
        }))
    
    # Database operations
    @database_sync_to_async
    def get_or_create_game(self):
        """Get or create a game session."""
        code = self.code
        # Work with primitives inside sync function to avoid passing model instances
        game, created = GameSession.objects.get_or_create(
            code=code,
            defaults={
                'player1': self.user,
                'board': {'puzzle': [], 'current': []},
            }
        )
        if created:
            # Generate a puzzle
            puzzle = SudokuPuzzle.generate_puzzle('medium')
            game.board = {
                'puzzle': [list(row) for row in puzzle.board],
                'current': [list(row) for row in puzzle.board],
            }
            game.current_turn = game.player1
            game.save()
        return game.id
    
    @database_sync_to_async
    def get_game(self):
        """Get the current game."""
        try:
            g = GameSession.objects.get(code=self.code)
            return g.id
        except GameSession.DoesNotExist:
            return None

    @database_sync_to_async
    def get_game_id(self):
        """Return the game id for current code (or None)."""
        try:
            return GameSession.objects.get(code=self.code).id
        except GameSession.DoesNotExist:
            return None
    
    @database_sync_to_async
    def add_player2(self, game_id, user_id):
        """Add second player to game and mark as in progress."""
        game = GameSession.objects.get(id=game_id)
        user = User.objects.get(id=user_id)
        game.player2 = user
        game.status = 'in_progress'
        game.save()
    
    @database_sync_to_async
    def start_game(self, game_id):
        """Mark game as started."""
        game = GameSession.objects.get(id=game_id)
        game.status = 'in_progress'
        game.save()
    
    @database_sync_to_async
    def create_move(self, game_id, player_id, row, col, value):
        """Record a move in the database."""
        game = GameSession.objects.get(id=game_id)
        player = User.objects.get(id=player_id)
        move = Move(game=game, player=player, row=row, col=col, value=value)
        move.save()
        return move.id
    
    @database_sync_to_async
    def update_game_board(self, game_id, new_board):
        """Update the game board state."""
        game = GameSession.objects.get(id=game_id)
        game.board['current'] = [list(row) for row in new_board]
        game.save()
    
    @database_sync_to_async
    def update_game_turn(self, game_id, next_player_id):
        """Update whose turn it is."""
        next_player = User.objects.get(id=next_player_id)
        game = GameSession.objects.get(id=game_id)
        game.current_turn = next_player
        game.save()
    
    @database_sync_to_async
    def get_board_state(self, game_id):
        """Get the current board state."""
        game = GameSession.objects.get(id=game_id)
        board = game.board.get('current', [])
        # Ensure it's a list of lists, not a reference issue
        return [list(row) if isinstance(row, (list, tuple)) else row for row in board]
    
    @database_sync_to_async
    def get_game_player_info(self, game_id):
        """Get player information safely for async context by game id."""
        game = GameSession.objects.get(id=game_id)
        return {
            'player1_id': game.player1.id if game.player1 else None,
            'player1_username': game.player1.username if game.player1 else None,
            'player2_id': game.player2.id if game.player2 else None,
            'player2_username': game.player2.username if game.player2 else None,
        }
    
    @database_sync_to_async
    def get_current_turn_id(self, game_id):
        """Get current turn player ID safely by game id."""
        game = GameSession.objects.get(id=game_id)
        return game.current_turn.id if game.current_turn else None
    
    @database_sync_to_async
    def switch_turn(self, game_id):
        """Compute next player (do not persist) and return info by game id."""
        game = GameSession.objects.get(id=game_id)
        if not game.player2:
            # No second player yet; keep same turn
            next_player = game.current_turn
        else:
            if game.current_turn and game.player1 and game.current_turn.id == game.player1.id:
                next_player = game.player2
            else:
                next_player = game.player1

        return {
            'next_player_id': next_player.id if next_player else None,
            'next_player_username': next_player.username if next_player else None,
        }

