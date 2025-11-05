import json
import uuid
import asyncio
from datetime import timedelta
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import transaction
from .models import GameSession, Move
from .sudoku import SudokuPuzzle


class GameConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time game play."""
    
    async def safe_send(self, message):
        """Safely send a message, catching closed connection errors."""
        try:
            if hasattr(self, 'channel_name') and self.channel_name:
                await self.send(text_data=json.dumps(message))
        except Exception as e:
            # Log the error but don't raise it to prevent server crashes
            print(f"WebSocket send error (connection likely closed): {e}")
    
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
            await self.safe_send({'error': 'Invalid JSON'})
            return
        
        message_type = data.get('type')

        if message_type == 'join_game':
            await self.handle_join_game(data)
        # Ready system removed - races auto-start when second player joins
        elif message_type == 'move':
            await self.handle_move(data)
        elif message_type == 'complete':
            await self.handle_puzzle_complete(data)
        elif message_type == 'get_board':
            await self.handle_get_board(data)
        elif message_type == 'play_again':
            await self.handle_play_again(data)
        elif message_type == 'leave_game':
            await self.handle_leave_game(data)
        elif message_type == 'notification':
            # Handle notification messages (these are usually just client acknowledgments)
            pass
        else:
            await self.safe_send({'error': f'Unknown message type: {message_type}'})
            return
    
    async def handle_join_game(self, data):
        """Handle player joining a game."""
        print("")
        print("="*80)
        print(f"🎮 PLAYER JOIN REQUEST")
        print(f"👤 Username: {self.user.username}")
        print(f"🆔 User ID: {self.user.id}")
        print(f"🎲 Game Code: {self.code}")
        print("="*80)
        
        # Create or get the game and operate using its id to keep DB work inside sync wrappers
        game_id = await self.get_or_create_game()
        print(f"📝 Game ID: {game_id}")

        # Get player info safely with async calls (by id)
        game_info = await self.get_game_player_info(game_id)
        print(f"👥 Current game state:")
        print(f"   - Player 1: {game_info['player1_username']} (ID: {game_info['player1_id']})")
        print(f"   - Player 2: {game_info['player2_username']} (ID: {game_info['player2_id']})")
        print(f"   - Status: {await self.get_game_status(game_id)}")

        # Fix join logic to be more permissive
        if not game_info['player1_id']:
            # No players yet, this user becomes player 1
            print(f"🥇 Adding {self.user.username} as Player 1")
            await self.add_player1(game_id, self.user.id)
            game_info = await self.get_game_player_info(game_id)
        elif not game_info['player2_id'] and game_info['player1_id'] != self.user.id:
            # Add second player and auto-start race
            print("="*60)
            print(f"🥈 Adding {self.user.username} as Player 2 - AUTO-STARTING RACE!")
            print("="*60)
            await self.add_player2(game_id, self.user.id)
            await self.start_game(game_id)
            
            # Auto-start the race when second player joins
            print("⏰ Setting start time...")
            start_iso = await self.set_start_time(game_id)
            print(f"⏰ Start time set: {start_iso}")
            
            print("🧩 Getting puzzle...")
            puzzle = await self.get_puzzle(game_id)
            print(f"🧩 Puzzle retrieved: {len(puzzle) if puzzle else 0} rows")
            
            print(f"📡 Broadcasting race_started message to group {self.group_name}")
            print(f"📅 Start time: {start_iso}")
            print("="*60)
            
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'race_started',
                    'start_time': start_iso,
                    'puzzle': puzzle,
                }
            )
            print("✅ race_started message sent to channel layer")
            print("="*60)
            
            # Refresh game info after adding player
            game_info = await self.get_game_player_info(game_id)
        elif game_info['player1_id'] == self.user.id or game_info['player2_id'] == self.user.id:
            # Player is already in this game, allow reconnection
            print(f"🔄 Player {self.user.username} reconnecting to game")
            
            # Check if race already started - if so, send race_started message
            game_status = await self.get_game_status(game_id)
            start_time_iso = await self.get_start_time_iso(game_id)
            
            print(f"📊 Current game status: {game_status}, Start time: {start_time_iso}")
            
            if game_status == 'in_progress' and start_time_iso:
                print(f"🏁 Race already in progress, sending race_started to reconnecting player")
                puzzle = await self.get_puzzle(game_id)
                await self.safe_send({
                    'type': 'race_started',
                    'start_time': start_time_iso,
                    'puzzle': puzzle,
                })
        else:
            # Game is full with other players
            await self.safe_send({'error': 'Game is full. Please create a new game.'})
            return
        
        # Send game state to client (fetch puzzle + both player boards via id)
        puzzle = await self.get_puzzle(game_id)
        player_board = await self.get_player_board(game_id, self.user.id)
        
        # Get opponent board for real-time display
        opponent_id = game_info['player2_id'] if self.user.id == game_info['player1_id'] else game_info['player1_id']
        opponent_board = await self.get_player_board(game_id, opponent_id) if opponent_id else puzzle
        
        await self.safe_send({
            'type': 'game_state',
            'puzzle': puzzle,
            'board': player_board,
            'opponent_board': opponent_board,
            'player1': game_info['player1_username'],
            'player2': game_info['player2_username'],
            'status': await self.get_game_status(game_id),
            'start_time': await self.get_start_time_iso(game_id),
        })

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
        
        print(f"🎯 Move request: Player {self.user.username} → ({row},{col}) = {value}")
        
        if not all(isinstance(x, int) for x in [row, col, value]):
            print(f"❌ Invalid move data types!")
            await self.safe_send({'error': 'Invalid move data'})
            return
        
        # Resolve game id first
        game_id = await self.get_game_id()
        if not game_id:
            print(f"❌ Game not found!")
            await self.safe_send({'error': 'Game not found'})
            return

        # Race mode: both players can play simultaneously. Fetch the player's board.
        current_board = await self.get_player_board(game_id, self.user.id)
        puzzle = SudokuPuzzle.from_dict({'board': current_board})
        
        # Validate the move
        if not puzzle.is_valid_placement(row, col, value):
            print(f"❌ Invalid move rejected: ({row},{col}) = {value}")
            print(f"   Current board state at that position: {current_board[row][col]}")
            # Check why it's invalid
            if value in current_board[row]:
                print(f"   ❌ Number {value} already in row {row}")
            if value in [current_board[r][col] for r in range(9)]:
                print(f"   ❌ Number {value} already in column {col}")
            box_row = (row // 3) * 3
            box_col = (col // 3) * 3
            box_values = [current_board[r][c] for r in range(box_row, box_row + 3) for c in range(box_col, box_col + 3)]
            if value in box_values:
                print(f"   ❌ Number {value} already in 3x3 box")
            await self.safe_send({'error': 'Invalid move - conflicts with existing numbers'})
            return
        
        print(f"✅ Move valid, updating board...")
        # Record the move
        move = await self.create_move(game_id, self.user.id, row, col, value)
        # Update player's board state
        new_board = [list(r) for r in current_board]
        new_board[row][col] = value
        await self.update_player_board(game_id, self.user.id, new_board)

        # Broadcast the move to all players with enhanced real-time data
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'move_made',
                'username': self.user.username,
                'row': row,
                'col': col,
                'value': value,
                'player_id': self.user.id,
                'timestamp': timezone.now().isoformat(),
            }
        )

        # Also broadcast updated game progress
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'game_progress_update',
                'player_id': self.user.id,
                'username': self.user.username,
                'board': new_board,
            }
        )

        # After the move, check if player's board is complete
        solution = await self.get_solution(game_id)
        puzzle_check = SudokuPuzzle.from_dict({'board': new_board, 'solution': solution})
        if puzzle_check.matches_solution():
            # Mark completion
            await self.handle_puzzle_complete({'player_id': self.user.id})
    
    async def handle_get_board(self, data):
        """Send current board state to client."""
        game_id = await self.get_game_id()
        if not game_id:
            await self.safe_send({'error': 'Game not found'})
            return

        board_state = await self.get_player_board(game_id, self.user.id)
        await self.safe_send({
            'type': 'board',
            'board': board_state,
        })
    
    # Event handlers for group messages
    async def player_connected(self, event):
        await self.safe_send({
            'type': 'notification',
            'message': f"{event['username']} connected",
        })

    async def player_joined(self, event):
        await self.safe_send({
            'type': 'notification',
            'message': f"{event['username']} joined the room",
        })

    async def race_started(self, event):
        print("="*60)
        print("📨 race_started event handler called!")
        print(f"📨 Event data: {event}")
        print("="*60)
        await self.safe_send({
            'type': 'race_started',
            'start_time': event.get('start_time'),
            'puzzle': event.get('puzzle'),
            'board': event.get('puzzle'),  # Ensure board is sent
        })
        print("✅ race_started message sent to client via WebSocket")
        print("="*60)

    async def race_finished(self, event):
        await self.safe_send({
            'type': 'race_finished',
            'winner_id': event.get('winner_id'),
            'winner_username': event.get('winner_username'),
            'winner_time': event.get('winner_time'),
            'loser_time': event.get('loser_time', 'Did not finish'),
        })
    
    async def player_disconnected(self, event):
        await self.safe_send({
            'type': 'notification',
        })
    
    async def move_made(self, event):
        await self.safe_send({
            'type': 'move',
            'username': event['username'],
            'row': event['row'],
            'col': event['col'],
            'value': event['value'],
            'player_id': event.get('player_id'),
        })

    async def notification(self, event):
        await self.safe_send({
        })

    async def game_progress_update(self, event):
        """Handle real-time game progress updates."""
        await self.send(text_data=json.dumps({
            'type': 'game_progress_update',
            'player_id': event['player_id'],
            'username': event['username'], 
            'board': event['board'],
        }))

    async def player_ready_status(self, event):
        """Handle player ready status updates."""
        await self.send(text_data=json.dumps({
            'type': 'player_ready_status',
            'player_id': event['player_id'],
            'username': event['username'],
            'both_ready': event['both_ready'],
        }))
        


    async def handle_player_ready(self, data):
        """Mark player as ready; if both ready, start the race."""
        game_id = await self.get_game_id()
        if not game_id:
            await self.send(text_data=json.dumps({'error': 'Game not found'}))
            return

        both_ready = await self.set_player_ready(game_id, self.user.id)

        # Notify group about readiness with live status update
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'player_ready_status',
                'player_id': self.user.id,
                'username': self.user.username,
                'both_ready': both_ready,
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
        print("🏁 PUZZLE COMPLETION REQUEST RECEIVED")
        print(f"👤 Player: {self.user.username} (ID: {self.user.id})")
        try:
            game_id = await self.get_game_id()
            if not game_id:
                print("❌ Game not found!")
                await self.send(text_data=json.dumps({'error': 'Game not found'}))
                return

            print(f"📝 Game ID: {game_id}")
            print("🔍 Verifying player's board against solution...")
            
            # Get both the player's board and the solution
            board = await self.get_player_board(game_id, self.user.id)
            solution = await self.get_solution(game_id)
            print(f"📋 Board retrieved: {len(board)} rows")
            print(f"✅ Solution retrieved: {len(solution) if solution else 0} rows")
            
            puzzle = SudokuPuzzle.from_dict({'board': board, 'solution': solution})
            print("🧩 Checking if puzzle matches solution...")
            
            is_complete = puzzle.matches_solution()
            print(f"✅ Puzzle matches solution: {is_complete}")
            
            if not is_complete:
                print("❌ Board does not match the correct solution!")
                await self.send(text_data=json.dumps({'error': 'Your solution is incorrect. Keep trying!'}))
                return

            print("🏆 Finalizing result...")
            # Finalize result (db-side)
            result = await self.finalize_result(game_id, self.user.id)
            print(f"🎉 Result finalized: {result}")

            print("📡 Broadcasting race_finished to all players...")
            print(f"   Winner ID: {result['winner_id']}")
            print(f"   Winner Username: {result['winner_username']}")
            print(f"   Winner Time: {result['winner_time']}")
            print(f"   Loser Time: {result.get('loser_time', 'Did not finish')}")
            print(f"   Group Name: {self.group_name}")
            
            # Send finish directly to the requester to avoid relying solely on cross-process delivery
            await self.safe_send({
                'type': 'race_finished',
                'winner_id': result['winner_id'],
                'winner_username': result['winner_username'],
                'winner_time': result['winner_time'],
                'loser_time': result.get('loser_time', 'Did not finish'),
            })

            # Broadcast finish immediately to the whole group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'race_finished',
                    'winner_id': result['winner_id'],
                    'winner_username': result['winner_username'],
                    'winner_time': result['winner_time'],
                    'loser_time': result.get('loser_time', 'Did not finish'),
                }
            )
            print("✅ race_finished broadcast completed!")
            print("="*60)
        except Exception as e:
            # Never crash the socket; report the error and keep connection alive
            import traceback
            print("❌ Error during handle_puzzle_complete:", e)
            traceback.print_exc()
            await self.safe_send({'error': 'Server error while finalizing result. Please try again.'})

    async def handle_play_again(self, data):
        """Create a new game with the same players."""
        old_game_id = await self.get_game_id()
        if not old_game_id:
            await self.send(text_data=json.dumps({'error': 'Current game not found'}))
            return

        # Get players from current game
        old_game_info = await self.get_game_player_info(old_game_id)
        if not old_game_info['player1_id'] or not old_game_info['player2_id']:
            await self.send(text_data=json.dumps({'error': 'Both players needed for rematch'}))
            return

        # Create new game
        difficulty = data.get('difficulty', 'medium')
        new_game_code = await self.create_new_game_for_rematch(
            old_game_info['player1_id'], 
            old_game_info['player2_id'], 
            difficulty
        )

        # Send new game code to both players
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'new_game_created',
                'game_code': new_game_code,
                'difficulty': difficulty,
            }
        )

    async def handle_leave_game(self, data):
        """Handle a player leaving the game session."""
        game_id = await self.get_game_id()
        if not game_id:
            await self.send(text_data=json.dumps({'error': 'Game not found'}))
            return

        reason = data.get('reason', 'user_request')
        
        # Get game info
        game_info = await self.get_game_player_info(game_id)
        leaving_player = self.user.username if self.user.is_authenticated else 'Anonymous'
        
        # Determine remaining player
        remaining_player_id = None
        remaining_player_username = None
        
        if self.user.id == game_info['player1_id']:
            remaining_player_id = game_info['player2_id']
            remaining_player_username = game_info['player2_username']
        elif self.user.id == game_info['player2_id']:
            remaining_player_id = game_info['player1_id']
            remaining_player_username = game_info['player1_username']
        
        # Update game status to reflect player leaving
        await self.mark_game_abandoned(game_id, self.user.id, reason)
        
        # Notify all players in the room
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'player_left_game',
                'leaving_player': leaving_player,
                'remaining_player': remaining_player_username,
                'reason': reason,
                'game_status': 'abandoned',
            }
        )
        
        # Send confirmation to leaving player
        await self.send(text_data=json.dumps({
            'type': 'leave_game_confirmed',
            'message': 'You have left the game successfully.',
        }))
        
        # Close connection for leaving player
        await self.close()
    
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
                'solution': [list(row) for row in puzzle.solution],
                'player1_board': [list(row) for row in puzzle.board],
                'player2_board': [list(row) for row in puzzle.board],
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
    def get_solution(self, game_id):
        """Get the correct solution for the game."""
        game = GameSession.objects.get(id=game_id)
        return game.board.get('solution', None)

    @database_sync_to_async
    def update_player_board(self, game_id, user_id, new_board):
        """Update player's board with database transaction to prevent race conditions."""
        with transaction.atomic():
            game = GameSession.objects.select_for_update().get(id=game_id)
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
            game.status = 'in_progress'  # Use valid status from STATUS_CHOICES
            game.save()
            print(f"✅ Start time set and status changed to 'in_progress': {game.start_time.isoformat()}")
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
        """Finalize game result: compute durations and store GameResult.
        Uses DB transaction + select_for_update to avoid race conditions on concurrent submissions.
        """
        from .models import GameResult
        from django.db import IntegrityError
        
        with transaction.atomic():
            # Lock the game row to serialize concurrent finishers
            game = GameSession.objects.select_for_update().get(id=game_id)
            
            # Determine winner/loser robustly
            winner = User.objects.get(id=winner_id)
            loser = None
            if game.player1 and game.player1.id == winner_id:
                loser = game.player2
            else:
                loser = game.player1

            # If a result already exists, reuse it
            existing = GameResult.objects.select_for_update().filter(game=game).select_related('winner').first()
            if existing:
                total_sec = int(existing.winner_time.total_seconds()) if existing.winner_time else 0
                wm, ws = divmod(total_sec, 60)
                return {
                    'winner_id': existing.winner.id,
                    'winner_username': existing.winner.username,
                    'winner_time': f"{wm:02d}:{ws:02d}",
                    'loser_time': 'Did not finish' if not existing.loser_time else str(existing.loser_time),
                }

            # Compute winner time
            if game.start_time:
                winner_time = timezone.now() - game.start_time
                winner_time_str = f"{int(winner_time.total_seconds() // 60):02d}:{int(winner_time.total_seconds() % 60):02d}"
            else:
                winner_time = None
                winner_time_str = "00:00"

            # Loser time reserved for future implementation
            loser_time = None
            loser_time_str = "Did not finish"

            # Try to create the result (guard against rare race IntegrityError)
            try:
                result = GameResult.objects.create(
                    game=game,
                    winner=winner,
                    loser=loser,
                    winner_time=winner_time or timedelta(0),
                    loser_time=loser_time,
                    difficulty=game.difficulty,
                )
            except IntegrityError:
                # Another process created it first; fetch and return
                existing = GameResult.objects.get(game=game)
                total_sec = int(existing.winner_time.total_seconds()) if existing.winner_time else 0
                wm, ws = divmod(total_sec, 60)
                return {
                    'winner_id': existing.winner.id,
                    'winner_username': existing.winner.username,
                    'winner_time': f"{wm:02d}:{ws:02d}",
                    'loser_time': 'Did not finish' if not existing.loser_time else str(existing.loser_time),
                }

            # Update game terminal state
            game.winner = winner
            game.status = 'finished'
            game.end_time = timezone.now()
            game.save()
            
            return {
                'winner_id': winner.id,
                'winner_username': winner.username,
                'winner_time': winner_time_str,
                'loser_time': loser_time_str,
            }

    @database_sync_to_async
    def create_new_game_for_rematch(self, player1_id, player2_id, difficulty):
        """Create a new game with both players for rematch."""
        import string
        import random
        from .sudoku import SudokuPuzzle
        
        # Generate new game code
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Create new puzzle with solution
        puzzle = SudokuPuzzle.generate_puzzle(difficulty)
        board_data = {
            'puzzle': puzzle.board,  # The puzzle with holes
            'solution': puzzle.solution,  # The complete solution
            'player1_board': [row[:] for row in puzzle.board],
            'player2_board': [row[:] for row in puzzle.board],
        }
        
        # Create new game session
        game = GameSession.objects.create(
            code=code,
            player1_id=player1_id,
            player2_id=player2_id,
            board=board_data,
            difficulty=difficulty,
            status='ready'  # Both players already known
        )
        
        return code

    async def new_game_created(self, event):
        """Handle new game creation notification."""
        await self.send(text_data=json.dumps({
            'type': 'new_game_created',
            'game_code': event['game_code'],
            'difficulty': event['difficulty'],
        }))

    async def player_left_game(self, event):
        """Handle player leaving game notification."""
        await self.send(text_data=json.dumps({
            'type': 'player_left_game',
            'leaving_player': event['leaving_player'],
            'remaining_player': event['remaining_player'],
            'reason': event['reason'],
            'game_status': event['game_status'],
            'message': f"{event['leaving_player']} has left the game.",
        }))
    
    @database_sync_to_async
    def add_player1(self, game_id, user_id):
        """Add first player to game."""
        game = GameSession.objects.get(id=game_id)
        user = User.objects.get(id=user_id)
        game.player1 = user
        game.status = 'waiting'
        game.save()
    
    @database_sync_to_async
    def add_player2(self, game_id, user_id):
        """Add second player to game and mark as racing."""
        game = GameSession.objects.get(id=game_id)
        user = User.objects.get(id=user_id)
        game.player2 = user
        # Use valid status from STATUS_CHOICES
        game.status = 'ready'
        game.save()
    
    @database_sync_to_async
    def start_game(self, game_id):
        """Mark game as in progress."""
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

    @database_sync_to_async
    def mark_game_abandoned(self, game_id, leaving_player_id, reason):
        """Mark game as abandoned when a player leaves."""
        game = GameSession.objects.get(id=game_id)
        
        # Update game status
        game.status = 'abandoned'
        game.end_time = timezone.now()
        
        # Store information about who left and why
        if not game.board:
            game.board = {}
        
        game.board['abandoned'] = {
            'leaving_player_id': leaving_player_id,
            'reason': reason,
            'timestamp': timezone.now().isoformat(),
        }
        
        # If the game was in progress, award win to remaining player
        if game.status in ['in_progress', 'ready'] and game.player1 and game.player2:
            from .models import GameResult
            
            leaving_player = None
            remaining_player = None
            
            if game.player1.id == leaving_player_id:
                leaving_player = game.player1
                remaining_player = game.player2
            else:
                leaving_player = game.player2
                remaining_player = game.player1
            
            # Create game result - remaining player wins by forfeit
            if remaining_player and leaving_player:
                GameResult.objects.create(
                    game=game,
                    winner=remaining_player,
                    loser=leaving_player,
                    winner_time=timedelta(0),  # Instant win
                    loser_time=None,
                    difficulty=game.difficulty,
                    result_type='forfeit'
                )
                game.winner = remaining_player
        
        game.save()
