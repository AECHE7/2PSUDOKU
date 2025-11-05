"""
Refactored WebSocket consumer for Sudoku Race game.
Uses structured message protocol and centralized state management.
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import transaction

from .messages import (
    MessageType, MessageFactory, MessageValidator,
    JoinGameMessage, MoveMessage, CompleteMessage,
    ErrorMessage, NotificationMessage, PlayerConnectedMessage,
    PlayerJoinedMessage, PlayerDisconnectedMessage, PlayerLeftGameMessage,
    LeaveGameMessage, LeaveGameConfirmedMessage, PingMessage, PongMessage,
    CountdownMessage, RaceCountdownMessage, RaceStartedMessage,
    GameStateMessage, PuzzleCompleteMessage
)
from .game_state import GameStateManager, GameStatus
from .models import GameSession

logger = logging.getLogger(__name__)


class GameConsumer(AsyncWebsocketConsumer):
    """
    Refactored WebSocket consumer with clean event handling and state management.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Basic attributes
        self.game_code: Optional[str] = None
        self.game_state_manager: Optional[GameStateManager] = None
        self.user: Optional[User] = None
        self.game_session: Optional[GameSession] = None
        self.group_name: Optional[str] = None
        self.is_connected: bool = False
        self.disconnecting: bool = False
        # Connection management
        self._connection_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()
        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 1  # seconds

    async def connect(self):
        """Handle WebSocket connection."""
        async with self._connection_lock:
            try:
                # Extract connection parameters
                self.game_code = self.scope['url_route']['kwargs']['code']
                self.user = self.scope['user']
                self.group_name = f'game_{self.game_code}'

                if not self.user.is_authenticated:
                    logger.warning(f"Unauthorized connection attempt for game {self.game_code}")
                    await self.close(code=4001)  # Unauthorized
                    return

                # Initialize game session with retries
                for attempt in range(self.max_retries):
                    try:
                        self.game_session = await self.get_game_session()
                        if self.game_session:
                            break
                        await asyncio.sleep(self.retry_delay)
                    except Exception as e:
                        if attempt == self.max_retries - 1:
                            raise
                        logger.warning(f"Retry {attempt + 1}/{self.max_retries} getting game session: {e}")
                        await asyncio.sleep(self.retry_delay)

                if not self.game_session:
                    logger.error(f"Game not found: {self.game_code}")
                    await self.close(code=4004)  # Game not found
                    return

                # Initialize game state manager
                self.game_state_manager = GameStateManager(self.game_session)

                # Join the game group
                await self.channel_layer.group_add(self.group_name, self.channel_name)
                
                # Accept the connection
                await self.accept()
                self.is_connected = True

                logger.info(f"Player {self.user.username} connected to game {self.game_code}")

                # Send initial state
                await self.send_state_sync()

            except Exception as e:
                logger.error(f"Failed to initialize game state: {e}", exc_info=True)
                await self.close(code=5000)  # Internal error
                return

                # Notify group of connection
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        'type': 'player_event',
                        'event_type': 'connected',
                        'username': self.user.username,
                        'user_id': self.user.id,
                    }
                )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        async with self._connection_lock:
            try:
                self.disconnecting = True
                self.is_connected = False

                # Clean up group membership
                if self.group_name:
                    try:
                        await self.channel_layer.group_discard(self.group_name, self.channel_name)
                    except Exception as e:
                        logger.error(f"Error discarding from group: {e}")

                # Notify other players if this was an established connection
                if self.user and self.game_code and not close_code in [4001, 4004]:  # Skip for auth/not found
                    try:
                        await self.channel_layer.group_send(
                            self.group_name,
                            {
                                'type': 'player_event',
                                'event_type': 'disconnected',
                                'username': self.user.username,
                                'user_id': self.user.id,
                                'code': close_code
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error sending disconnect notification: {e}")

                # Update game state if needed
                if self.game_session and self.game_session.status == GameStatus.IN_PROGRESS.value:
                    try:
                        await self.handle_player_disconnect()
                    except Exception as e:
                        logger.error(f"Error handling player disconnect state: {e}")

                logger.info(f"Player {self.user.username if self.user else 'Unknown'} disconnected from game {self.game_code} with code {close_code}")

            except Exception as e:
                logger.error(f"Error in disconnect handler: {e}", exc_info=True)
            finally:
                self.disconnecting = False

    async def receive(self, text_data=None, bytes_data=None):
        """Handle incoming WebSocket messages."""
        if not text_data:
            return

        try:
            # Parse and validate message
            raw_message = json.loads(text_data)
            msg_type = raw_message.get('type')
            if not msg_type:
                await self.send_error("Message must have a 'type' field")
                return

            # Validate message based on type
            if msg_type == MessageType.MOVE:
                if not MessageValidator.validate_move_message(raw_message):
                    await self.send_error("Invalid move message")
                    return
            elif msg_type == MessageType.JOIN_GAME:
                if not MessageValidator.validate_join_game_message(raw_message):
                    await self.send_error("Invalid join game message")
                    return
            elif msg_type == MessageType.COMPLETE:
                if not MessageValidator.validate_complete_message(raw_message):
                    await self.send_error("Invalid complete message")
                    return
            elif msg_type == MessageType.PLAY_AGAIN:
                if not MessageValidator.validate_play_again_message(raw_message):
                    await self.send_error("Invalid play again message")
                    return

            message = MessageFactory.create_message(msg_type, raw_message)

            # Route message to appropriate handler
            await self.route_message(message)

        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self.send_error("Internal server error")

    async def route_message(self, message):
        """Route message to appropriate handler based on type."""
        handlers = {
            MessageType.JOIN_GAME: self.handle_join_game,
            MessageType.MOVE: self.handle_move,
            MessageType.COMPLETE: self.handle_complete,
            MessageType.PLAY_AGAIN: self.handle_play_again,
            MessageType.LEAVE_GAME: self.handle_leave_game,
            MessageType.PING: self.handle_ping,
        }

        handler = handlers.get(message.type)
        if handler:
            await handler(message)
        else:
            await self.send_error(f"Unknown message type: {message.type}")

    # Message Handlers

    async def handle_join_game(self, message: JoinGameMessage):
        """Handle player joining game."""
        try:
            if not self.user or not self.user.is_authenticated:
                await self.send_error("Authentication required")
                return

            # Add player to game using sync_to_async
            success = await self.add_player_to_game()
            if not success:
                await self.send_error("Unable to join game")
                return

            # Refresh game session
            self.game_session = await self.get_game_session()

            # Safe async check for players
            game_data = await self.get_game_players_async()

            # Check if we need to start countdown
            if (game_data['status'] == 'ready' and
                game_data['player1_id'] and game_data['player2_id']):
                # Start countdown for both players
                await self.start_countdown()

            # Update game state manager with latest session
            self.game_state_manager = GameStateManager(self.game_session)

            # Send state synchronization
            await self.send_state_sync()

            # Notify group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'player_event',
                    'event_type': 'joined',
                    'username': self.user.username,
                    'user_id': self.user.id,
                }
            )

        except Exception as e:
            logger.error(f"Error in handle_join_game: {e}", exc_info=True)
            await self.send_error("Failed to join game")

    async def handle_move(self, message: MoveMessage):
        """Handle player move."""
        try:
            # Get move data from message
            row = message.data['row']
            col = message.data['col']
            value = message.data['value']

            # Validate move (async-safe)
            if not await self.game_state_manager.validate_move_async(
                self.user.id, row, col, value
            ):
                await self.send_error("Invalid move")
                return

            # Record move
            success = await self.game_state_manager.record_move_async(
                self.user.id, row, col, value
            )
            if not success:
                await self.send_error("Failed to record move")
                return

            # Broadcast move to group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'game_event',
                    'event_type': 'move_made',
                    'username': self.user.username,
                    'user_id': self.user.id,
                    'row': row,
                    'col': col,
                    'value': value,
                    'timestamp': timezone.now().isoformat(),
                }
            )

            # Check for auto-completion
            await self.check_auto_completion()

        except Exception as e:
            logger.error(f"Error in handle_move: {e}")
            await self.send_error("Failed to process move")

    async def handle_complete(self, message: CompleteMessage):
        """Handle puzzle completion."""
        try:
            # Get completion time from message
            completion_time = message.data['completion_time']

            success, result = await self.complete_puzzle_async(self.user.id, completion_time)
            if not success:
                await self.send_error("Failed to complete puzzle")
                return

            # Broadcast completion to group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'game_event',
                    'event_type': 'race_finished',
                    'winner_id': result['winner_id'],
                    'winner_username': result['winner_username'],
                    'winner_time': result['winner_time'],
                    'loser_time': result.get('loser_time', 'Did not finish'),
                }
            )

            # Send completion confirmation to the player
            await self.send(text_data=json.dumps({
                'type': MessageType.PUZZLE_COMPLETE,
                'player_id': self.user.id,
                'completion_time': completion_time
            }))

        except Exception as e:
            logger.error(f"Error in handle_complete: {e}")
            await self.send_error("Failed to complete puzzle")

    async def handle_play_again(self, message):
        """Handle play again request."""
        try:
            # Create new game
            new_game_code = await self.create_rematch_game(message.difficulty)

            # Broadcast new game to group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'game_event',
                    'event_type': 'new_game_created',
                    'game_code': new_game_code,
                    'difficulty': message.difficulty,
                }
            )

        except Exception as e:
            logger.error(f"Error in handle_play_again: {e}")
            await self.send_error("Failed to create new game")

    async def handle_leave_game(self, message: LeaveGameMessage):
        """Handle player leaving game."""
        try:
            # Mark game as abandoned
            await self.mark_game_abandoned()

            # Notify group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'player_event',
                    'event_type': 'left_game',
                    'username': self.user.username,
                    'user_id': self.user.id,
                }
            )

            # Send confirmation
            leave_confirmed = LeaveGameConfirmedMessage()
            await self.send(text_data=json.dumps(leave_confirmed.to_dict()))

            # Close connection
            await self.close()

        except Exception as e:
            logger.error(f"Error in handle_leave_game: {e}")
            await self.send_error("Failed to leave game")

    async def handle_ping(self, message: PingMessage):
        """Handle ping message."""
        try:
            pong = PongMessage()
            await self.send(text_data=json.dumps(pong.to_dict()))
        except Exception as e:
            logger.error(f"Error in handle_ping: {e}")

    # Group Event Handlers

    async def player_event(self, event):
        """Handle player-related events."""
        event_type = event['event_type']

        if event_type == 'joined':
            player_joined = PlayerJoinedMessage(event['user_id'], event['username'])
            await self.send(text_data=json.dumps(player_joined.to_dict()))
        elif event_type == 'connected':
            player_connected = PlayerConnectedMessage(event['user_id'], event['username'])
            await self.send(text_data=json.dumps(player_connected.to_dict()))
        elif event_type == 'disconnected':
            player_disconnected = PlayerDisconnectedMessage(event['user_id'], event['username'])
            await self.send(text_data=json.dumps(player_disconnected.to_dict()))
        elif event_type == 'left_game':
            player_left = PlayerLeftGameMessage(event['user_id'], event['username'])
            await self.send(text_data=json.dumps(player_left.to_dict()))

    async def game_event(self, event):
        """Handle game-related events."""
        event_type = event['event_type']

        if event_type == 'move_made':
            await self.send(text_data=json.dumps({
                'type': MessageType.MOVE_MADE,
                'username': event['username'],
                'row': event['row'],
                'col': event['col'],
                'value': event['value'],
                'player_id': event['user_id'],
                'timestamp': event['timestamp'],
            }))
        elif event_type == 'race_finished':
            await self.send(text_data=json.dumps({
                'type': MessageType.RACE_FINISHED,
                'winner_id': event['winner_id'],
                'winner_username': event['winner_username'],
                'winner_time': event['winner_time'],
                'loser_time': event['loser_time'],
            }))
        elif event_type == 'new_game_created':
            await self.send(text_data=json.dumps({
                'type': MessageType.NEW_GAME_CREATED,
                'game_code': event['game_code'],
                'difficulty': event['difficulty'],
            }))

    async def countdown_event(self, event):
        """Handle countdown events."""
        countdown_msg = CountdownMessage(event['seconds'])
        await self.send(text_data=json.dumps(countdown_msg.to_dict()))

    async def race_event(self, event):
        """Handle race events."""
        event_type = event['event_type']

        if event_type == 'started':
            try:
                # Send race started message
                puzzle = []
                if self.game_state_manager:
                    try:
                        state = await self.game_state_manager.get_current_state_async()
                        puzzle = getattr(state, 'puzzle', [])
                    except Exception as e:
                        logger.error(f"Error getting puzzle state: {e}", exc_info=True)
                        puzzle = []

                race_started_msg = {
                    'type': MessageType.RACE_STARTED,
                    'start_time': event.get('start_time'),
                    'puzzle': puzzle
                }
                await self.send(text_data=json.dumps(race_started_msg))
            except Exception as e:
                logger.error(f"Error in race_event: {e}", exc_info=True)
                await self.send_error("Failed to process race event")
            except Exception as e:
                logger.error(f"Error in race_event: {e}", exc_info=True)
                await self.send_error("Failed to process race event")

    # Helper Methods

    async def send_state_sync(self):
        """Send current game state to client."""
        async with self._state_lock:
            try:
                # Ensure we have a valid game session
                if not self.game_session:
                    self.game_session = await self.get_game_session()
                    if not self.game_session:
                        logger.error("No game session available")
                        await self.send_error("Game session not found")
                        return

                # Get and send state messages
                state_messages = await self.get_state_messages_async(self.user.id)

                # Send messages only if still connected
                if self.is_connected and not self.disconnecting:
                    for message in state_messages:
                        await self.send(text_data=json.dumps(message))
                        await asyncio.sleep(0.01)  # Small delay to prevent flooding

            except Exception as e:
                logger.error(f"Error sending state sync: {e}", exc_info=True)
                if not self.disconnecting:
                    await self.send_error("Failed to sync game state")

    async def check_auto_completion(self):
        """Check if player's puzzle is complete after a move."""
        try:
            # Get the current state (async-safe)
            state = await self.game_state_manager.get_current_state_async()
            if not state or not state.solution:
                logger.error("No game state or solution available")
                return

            player_state = state.players.get(self.user.id)
            if not player_state:
                logger.error("No player state found")
                return

            # Check if board is complete and correct
            board = player_state.board
            if not board:
                logger.error("No board state found")
                return

            # Check if all cells are filled with valid numbers
            if not all(0 < cell <= 9 for row in board for cell in row):
                return

            # Check against solution
            if all(board[i][j] == state.solution[i][j] for i in range(9) for j in range(9)):
                logger.info(f"Player {self.user.username} completed the puzzle correctly")
                # If not already completed, handle completion
                if not player_state.has_completed:
                    completion_time = (timezone.now() - state.start_time).total_seconds()
                    await self.handle_complete(CompleteMessage(
                        completion_time=int(completion_time)
                    ))

        except Exception as e:
            logger.error(f"Error in auto-completion check: {e}", exc_info=True)

    async def start_countdown(self):
        """Start 3-second countdown before race begins."""
        try:
            # Send countdown messages
            for i in range(3, 0, -1):
                countdown_msg = CountdownMessage(i)
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        'type': 'countdown_event',
                        'seconds': i,
                    }
                )
                await asyncio.sleep(1)

            # Start the race
            await self.start_race()

        except Exception as e:
            logger.error(f"Error in countdown: {e}")

    async def start_race(self):
        """Start the race after countdown."""
        try:
            success, start_time = await self.game_state_manager.start_race_async()
            if success:
                # Broadcast race start
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        'type': 'race_event',
                        'event_type': 'started',
                        'start_time': start_time,
                    }
                )
            else:
                await self.send_error("Failed to start race")

        except Exception as e:
            logger.error(f"Error starting race: {e}", exc_info=True)
            await self.send_error("Failed to start race")

    async def send_error(self, message: str):
        """Send error message to client."""
        error_msg = ErrorMessage(message)
        await self.send(text_data=json.dumps(error_msg.to_dict()))

    async def send_notification(self, message: str, level: str = 'info'):
        """Send notification to client."""
        notification = NotificationMessage(message, level)
        await self.send(text_data=json.dumps(notification.to_dict()))

    # Database Operations

    @database_sync_to_async
    def get_game_session(self) -> Optional[GameSession]:
        """Get game session by code."""
        try:
            return GameSession.objects.get(code=self.game_code)
        except GameSession.DoesNotExist:
            return None

    @database_sync_to_async
    def add_player_to_game(self) -> bool:
        """Add player to game if possible."""
        try:
            with transaction.atomic():
                game = GameSession.objects.select_for_update().get(code=self.game_code)

                # Check if player can join
                if game.player1_id == self.user.id or game.player2_id == self.user.id:
                    return True  # Already in game

                if not game.player1:
                    game.player1 = self.user
                    game.status = 'waiting'
                elif not game.player2:
                    game.player2 = self.user
                    if game.player1:
                        game.status = 'ready'
                        # Start countdown instead of auto-starting
                        # game.start_time = timezone.now()
                        # game.status = 'in_progress'
                else:
                    return False  # Game full

                game.save()
                return True

        except Exception as e:
            logger.error(f"Error adding player to game: {e}")
            return False

    @database_sync_to_async
    def create_rematch_game(self, difficulty: str) -> str:
        """Create new game for rematch."""
        from .sudoku import SudokuPuzzle
        import string
        import random

        # Get current players
        current_game = GameSession.objects.get(code=self.game_code)

        # Generate new game code
        new_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        # Create new puzzle
        puzzle = SudokuPuzzle.generate_puzzle(difficulty)
        board_data = {
            'puzzle': puzzle.board,
            'solution': puzzle.solution,
            'player1_board': [row[:] for row in puzzle.board],
            'player2_board': [row[:] for row in puzzle.board],
        }

        # Create new game
        new_game = GameSession.objects.create(
            code=new_code,
            player1=current_game.player1,
            player2=current_game.player2,
            board=board_data,
            difficulty=difficulty,
            status='ready'
        )

        return new_code

    @database_sync_to_async
    def complete_puzzle_async(self, player_id: int, completion_time: int):
        """Complete puzzle in database sync context."""
        try:
            with transaction.atomic():
                game = GameSession.objects.select_for_update().get(code=self.game_code)

                if game.status != GameStatus.IN_PROGRESS.value:
                    return False, None

                # Calculate completion time
                if not game.start_time:
                    return False, None

                completion_time_delta = timezone.now() - game.start_time

                # Update game result
                from .models import GameResult
                winner = None
                loser = None

                if game.player1 and game.player1.id == player_id:
                    winner = game.player1
                    loser = game.player2
                elif game.player2 and game.player2.id == player_id:
                    winner = game.player2
                    loser = game.player1
                else:
                    return False, None

                # Create result
                result = GameResult.objects.create(
                    game=game,
                    winner=winner,
                    loser=loser,
                    winner_time=completion_time_delta,
                    difficulty=game.difficulty,
                    result_type='completion'
                )

                # Update game
                game.winner = winner
                game.status = 'finished'
                game.end_time = timezone.now()
                game.save()

                result_data = {
                    'winner_id': winner.id,
                    'winner_username': winner.username,
                    'winner_time': f"{int(completion_time_delta.total_seconds() // 60):02d}:{int(completion_time_delta.total_seconds() % 60):02d}",
                    'loser_time': 'Did not finish',
                }

                return True, result_data

        except Exception as e:
            logger.error(f"Failed to complete puzzle: {e}")
            return False, None

    @database_sync_to_async
    def get_game_players_async(self):
        """Get game player data safely."""
        try:
            game = GameSession.objects.get(code=self.game_code)
            return {
                'status': game.status,
                'player1_id': game.player1_id if game.player1 else None,
                'player2_id': game.player2_id if game.player2 else None,
            }
        except GameSession.DoesNotExist:
            return {
                'status': None,
                'player1_id': None,
                'player2_id': None,
            }

    async def get_state_messages_async(self, player_id: int):
        """Get state messages using async-safe methods."""
        try:
            if not self.game_session:
                self.game_session = await self.get_game_session()

            state = await self.game_state_manager.get_current_state_async()
            messages = []

            # Game state message
            player_state = state.players.get(player_id, None)
            opponent_id = None
            opponent_board = None

            for pid, pstate in state.players.items():
                if pid != player_id:
                    opponent_id = pid
                    opponent_board = pstate.board
                    break

            # Get player usernames safely
            player1_username = None
            player2_username = None
            if self.game_session.player1_id and self.game_session.player1_id in state.players:
                player1_username = state.players[self.game_session.player1_id].username
            if self.game_session.player2_id and self.game_session.player2_id in state.players:
                player2_username = state.players[self.game_session.player2_id].username

            messages.append(GameStateMessage(
                puzzle=state.puzzle,
                board=player_state.board if player_state else state.puzzle,
                opponent_board=opponent_board,
                player1=player1_username,
                player2=player2_username,
                status=state.status.value,
                start_time=state.start_time.isoformat() if state.start_time else None
            ).to_dict())

            # If race is in progress, send race started message
            if state.status == GameStatus.IN_PROGRESS and state.start_time:
                messages.append(RaceStartedMessage(
                    start_time=state.start_time.isoformat(),
                    puzzle=state.puzzle
                ).to_dict())

            # Send puzzle complete messages for completed players
            for pid, pstate in state.players.items():
                if pstate.has_completed and pstate.completion_time:
                    messages.append(PuzzleCompleteMessage(
                        player_id=pid,
                        completion_time=int(pstate.completion_time.total_seconds())
                    ).to_dict())

            return messages

        except Exception as e:
            logger.error(f"Error getting state messages: {e}", exc_info=True)
            return []

    async def check_completion_async(self, player_id: int):
        """Check if player's puzzle is complete using async-safe methods."""
        try:
            state = await self.game_state_manager.get_current_state_async()
            player_state = state.players.get(player_id, None)

            if player_state:
                # Check if board is complete
                board = player_state.board
                if all(cell != 0 for row in board for cell in row):
                    # Check if solution matches (get solution from current state)
                    if state.solution:
                        if all(board[i][j] == state.solution[i][j]
                               for i in range(9) for j in range(9)):
                            # Mark as completed if not already
                            if not player_state.has_completed:
                                completion_time = timezone.now() - state.start_time
                                player_state.mark_completed(completion_time)
                                self.game_state_manager.update_player_board(player_id, board)
                            return player_state

            return None

        except Exception as e:
            logger.error(f"Error checking completion: {e}")
            return None

    @database_sync_to_async
    def handle_player_disconnect(self):
        """Handle player disconnection and update game state."""
        try:
            with transaction.atomic():
                # Reload game session to get latest state
                game = GameSession.objects.select_for_update().get(code=self.game_code)

                # Different handling based on game status
                if game.status == 'in_progress':
                    if game.player1 and game.player2:
                        # Mark game as abandoned and create forfeit result
                        game.status = 'abandoned'
                        game.end_time = timezone.now()

                        from .models import GameResult
                        if game.player1.id == self.user.id:
                            winner = game.player2
                            loser = game.player1
                        else:
                            winner = game.player1
                            loser = game.player2

                        GameResult.objects.create(
                            game=game,
                            winner=winner,
                            loser=loser,
                            winner_time=timezone.now() - (game.start_time or timezone.now()),
                            difficulty=game.difficulty,
                            result_type='forfeit'
                        )
                        game.winner = winner

                elif game.status == 'waiting':
                    # Remove disconnected player if they were the only one
                    if game.player1 and game.player1.id == self.user.id:
                        game.player1 = None
                    elif game.player2 and game.player2.id == self.user.id:
                        game.player2 = None
                    
                    if not game.player1 and not game.player2:
                        game.status = 'abandoned'

                game.save()
                self.game_session = game

        except Exception as e:
            logger.error(f"Error handling player disconnect: {e}", exc_info=True)
            raise
