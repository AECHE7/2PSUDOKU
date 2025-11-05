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
        
        # Get player info safely with async calls
        game_info = await self.get_game_player_info(game)
        
        if not game_info['player2_id'] and game_info['player1_id'] != self.user.id:
            # Add second player
            await self.add_player2(game, self.user)
            await self.start_game(game)
            # Refresh game info after adding player
            game_info = await self.get_game_player_info(game)
        elif game_info['player2_id'] and (game_info['player1_id'] == self.user.id or game_info['player2_id'] == self.user.id):
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
        
        game = await self.get_game()
        if not game:
            await self.send(text_data=json.dumps({'error': 'Game not found'}))
            return
        
        # Check if it's this player's turn (async-safe)
        current_turn_id = await self.get_current_turn_id(game)
        if current_turn_id != self.user.id:
            await self.send(text_data=json.dumps({'error': 'Not your turn'}))
            return
        
        # Validate move server-side
        current_board = game.board.get('current', [])
        puzzle = SudokuPuzzle.from_dict({'board': current_board})
        if not puzzle.is_valid_placement(row, col, value):
            await self.send(text_data=json.dumps({'error': 'Invalid move'}))
            return
        
        # Record the move
        move = await self.create_move(game, self.user, row, col, value)
        
        # Update board state
        new_board = [list(row) for row in game.board.get('current', [])]
        new_board[row][col] = value
        game.board['current'] = new_board
        await self.update_game_board(game, new_board)
        
        # Switch current turn (async-safe)
        next_player_info = await self.switch_turn(game)
        await self.update_game_turn(game, next_player_info['next_player_id'])
        
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
        game.board['current'] = [list(row) for row in new_board]
        game.save()
    
    @database_sync_to_async
    def update_game_turn(self, game, next_player_id):
        """Update whose turn it is."""
        from django.contrib.auth.models import User
        next_player = User.objects.get(id=next_player_id)
        game.current_turn = next_player
        game.save()
    
    @database_sync_to_async
    def get_board_state(self, game):
        """Get the current board state."""
        board = game.board.get('current', [])
        # Ensure it's a list of lists, not a reference issue
        return [list(row) if isinstance(row, (list, tuple)) else row for row in board]
    
    @database_sync_to_async
    def get_game_player_info(self, game):
        """Get player information safely for async context."""
        return {
            'player1_id': game.player1.id if game.player1 else None,
            'player1_username': game.player1.username if game.player1 else None,
            'player2_id': game.player2.id if game.player2 else None, 
            'player2_username': game.player2.username if game.player2 else None,
        }
    
    @database_sync_to_async
    def get_current_turn_id(self, game):
        """Get current turn player ID safely."""
        return game.current_turn.id if game.current_turn else None
    
    @database_sync_to_async
    def switch_turn(self, game):
        """Switch to next player and return info."""
        if game.current_turn.id == game.player1.id:
            next_player = game.player2
        else:
            next_player = game.player1
            
        return {
            'next_player_id': next_player.id,
            'next_player_username': next_player.username,
        }

