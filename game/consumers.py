import json
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
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
        elif message_type == 'ready':
            await self.handle_player_ready(data)
        elif message_type == 'move':
            await self.handle_move(data)
        elif message_type == 'complete':
            await self.handle_puzzle_complete(data)
        elif message_type == 'get_board':
            await self.handle_get_board(data)
        elif message_type == 'notification':
            # Handle notification messages (these are usually just client acknowledgments)
            pass
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
        
        # Send game state to client (fetch puzzle + player board via id)
        puzzle = await self.get_puzzle(game_id)
        player_board = await self.get_player_board(game_id, self.user.id)
        await self.send(text_data=json.dumps({
            'type': 'game_state',
            'puzzle': puzzle,
            'board': player_board,
            'player1': game_info['player1_username'],
            'player2': game_info['player2_username'],
            'status': await self.get_game_status(game_id),
            'start_time': await self.get_start_time_iso(game_id),
        }))

        # Notify group that a player joined
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'player_joined',
                'username': self.user.username,
            }
        )
    
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

        # Race mode: both players can play simultaneously. Fetch the player's board.
        current_board = await self.get_player_board(game_id, self.user.id)
        puzzle = SudokuPuzzle.from_dict({'board': current_board})
        if not puzzle.is_valid_placement(row, col, value):
            await self.send(text_data=json.dumps({'error': 'Invalid move'}))
            return
        
        # Record the move
        move = await self.create_move(game_id, self.user.id, row, col, value)
        # Update player's board state
        new_board = [list(r) for r in current_board]
        new_board[row][col] = value
        await self.update_player_board(game_id, self.user.id, new_board)

        # Broadcast the move to all players so both UIs update
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'move_made',
                'username': self.user.username,
                'row': row,
                'col': col,
                'value': value,
                'player_id': self.user.id,
            }
        )

        # After the move, check if player's board is complete
        if SudokuPuzzle.from_dict({'board': new_board}).is_complete():
            # Mark completion
            await self.handle_puzzle_complete({'player_id': self.user.id})
    
    async def handle_get_board(self, data):
        """Send current board state to client."""
        game_id = await self.get_game_id()
        if not game_id:
            await self.send(text_data=json.dumps({'error': 'Game not found'}))
            return

        board_state = await self.get_player_board(game_id, self.user.id)
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

    async def player_joined(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': f"{event['username']} joined the room",
        }))

    async def race_started(self, event):
        await self.send(text_data=json.dumps({
            'type': 'race_started',
            'start_time': event.get('start_time'),
            'puzzle': event.get('puzzle'),
        }))

    async def race_finished(self, event):
        await self.send(text_data=json.dumps({
            'type': 'race_finished',
            'winner_id': event.get('winner_id'),
            'winner_username': event.get('winner_username'),
            'winner_time': event.get('winner_time'),
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
            'player_id': event.get('player_id'),
        }))

    async def notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': event['message'],
        }))
        


    async def handle_player_ready(self, data):
        """Mark player as ready; if both ready, start the race."""
        game_id = await self.get_game_id()
        if not game_id:
            await self.send(text_data=json.dumps({'error': 'Game not found'}))
            return

        both_ready = await self.set_player_ready(game_id, self.user.id)

        # Notify group about readiness
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'notification',
                'message': f"{self.user.username} is ready",
            }
        )

        if both_ready:
            # Set start time and broadcast start with puzzle
            start_iso = await self.set_start_time(game_id)
            puzzle = await self.get_puzzle(game_id)
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'race_started',
                    'start_time': start_iso,
                    'puzzle': puzzle,
                }
            )

    async def handle_puzzle_complete(self, data):
        """Handle a player's reported completion; verify and finalize result."""
        game_id = await self.get_game_id()
        if not game_id:
            await self.send(text_data=json.dumps({'error': 'Game not found'}))
            return

        # Verify player's board on server
        board = await self.get_player_board(game_id, self.user.id)
        puzzle = SudokuPuzzle.from_dict({'board': board})
        if not puzzle.is_complete():
            await self.send(text_data=json.dumps({'error': 'Board is not a valid completed solution'}))
            return

        # Finalize result (db-side)
        result = await self.finalize_result(game_id, self.user.id)

        # Broadcast finish
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'race_finished',
                'winner_id': result['winner_id'],
                'winner_username': result['winner_username'],
                'winner_time': result['winner_time'],
            }
        )
    
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
    def get_puzzle(self, game_id):
        game = GameSession.objects.get(id=game_id)
        return game.board.get('puzzle', [])

    @database_sync_to_async
    def get_player_board(self, game_id, user_id):
        game = GameSession.objects.get(id=game_id)
        if game.player1 and game.player1.id == user_id:
            return game.board.get('player1_board', game.board.get('puzzle', []))
        else:
            return game.board.get('player2_board', game.board.get('puzzle', []))

    @database_sync_to_async
    def update_player_board(self, game_id, user_id, new_board):
        game = GameSession.objects.get(id=game_id)
        if game.player1 and game.player1.id == user_id:
            game.board['player1_board'] = [list(row) for row in new_board]
        else:
            game.board['player2_board'] = [list(row) for row in new_board]
        game.save()

    @database_sync_to_async
    def set_player_ready(self, game_id, user_id):
        game = GameSession.objects.get(id=game_id)
        ready = game.board.get('ready', {})
        if game.player1 and game.player1.id == user_id:
            ready['player1'] = True
        else:
            ready['player2'] = True
        game.board['ready'] = ready
        game.save()
        return ready.get('player1', False) and ready.get('player2', False)

    @database_sync_to_async
    def set_start_time(self, game_id):
        game = GameSession.objects.get(id=game_id)
        if not game.start_time:
            game.start_time = timezone.now()
            game.status = 'in_progress'
            game.save()
        return game.start_time.isoformat() if game.start_time else None

    @database_sync_to_async
    def get_start_time_iso(self, game_id):
        game = GameSession.objects.get(id=game_id)
        return game.start_time.isoformat() if game.start_time else None

    @database_sync_to_async
    def get_game_status(self, game_id):
        game = GameSession.objects.get(id=game_id)
        return game.status

    @database_sync_to_async
    def finalize_result(self, game_id, winner_id):
        """Finalize game result: compute durations and store GameResult."""
        from .models import GameResult
        game = GameSession.objects.get(id=game_id)
        winner = User.objects.get(id=winner_id)
        loser = None
        if game.player1 and game.player1.id == winner_id:
            loser = game.player2
        else:
            loser = game.player1

        # compute times
        if game.start_time:
            winner_time = timezone.now() - game.start_time
        else:
            winner_time = None

        # Try to estimate loser time from their board completeness; if not complete, leave blank
        loser_time = None

        # Persist GameResult
        result = GameResult.objects.create(
            game=game,
            winner=winner,
            loser=loser,
            winner_time=winner_time or timezone.timedelta(0),
            loser_time=loser_time,
            difficulty=game.difficulty,
        )
        game.winner = winner
        game.status = 'finished'
        game.end_time = timezone.now()
        game.save()
        return {
            'winner_id': winner.id,
            'winner_username': winner.username,
            'winner_time': str(winner_time),
        }
    
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
    

    


