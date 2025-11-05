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
    CountdownMessage, RaceCountdownMessage
)
from .game_state import GameStateManager
from .models import GameSession

logger = logging.getLogger(__name__)


class GameConsumer(AsyncWebsocketConsumer):
    """
    Refactored WebSocket consumer with clean event handling and state management.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.game_code: Optional[str] = None
        self.game_state_manager: Optional[GameStateManager] = None
        self.user: Optional[User] = None
        self.is_connected = False

    async def connect(self):
        """Handle WebSocket connection."""
        self.game_code = self.scope['url_route']['kwargs']['code']
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close(code=4001)  # Unauthorized
            return

        # Initialize game state manager
        try:
            game_session = await self.get_game_session()
            if not game_session:
                await self.close(code=4004)  # Game not found
                return

            self.game_state_manager = GameStateManager(game_session)
        except Exception as e:
            logger.error(f"Failed to initialize game state: {e}")
            await self.close(code=5000)  # Internal error
            return

        # Join game group
        self.group_name = f'game_{self.game_code}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()
        self.is_connected = True

        logger.info(f"Player {self.user.username} connected to game {self.game_code}")

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

        # Send initial state synchronization
        await self.send_state_sync()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        self.is_connected = False

        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        # Notify other players
        if self.user and self.game_code:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'player_event',
                    'event_type': 'disconnected',
                    'username': self.user.username,
                    'user_id': self.user.id,
                }
            )

        logger.info(f"Player {self.user.username} disconnected from game {self.game_code}")

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
            # Add player to game
            success = await self.add_player_to_game()
            if not success:
                await self.send_error("Unable to join game")
                return

            # Check if we need to start countdown
            game = await self.get_game_session()
            if game and game.status == 'ready' and game.player1 and game.player2:
                # Start countdown for both players
                await self.start_countdown()

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
            logger.error(f"Error in handle_join_game: {e}")
            await self.send_error("Failed to join game")

    async def handle_move(self, message: MoveMessage):
        """Handle player move."""
        try:
            # Validate move
            if not self.game_state_manager.validate_move(
                self.user.id, message.row, message.col, message.value
            ):
                await self.send_error("Invalid move")
                return

            # Record move
            success = self.game_state_manager.record_move(
                self.user.id, message.row, message.col, message.value
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
                    'row': message.row,
                    'col': message.col,
                    'value': message.value,
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
            success, result = self.game_state_manager.complete_puzzle(self.user.id)
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
            # Send race started message
            race_started_msg = {
                'type': MessageType.RACE_STARTED,
                'start_time': event['start_time'],
                'puzzle': self.game_state_manager.get_current_state().puzzle if self.game_state_manager else []
            }
            await self.send(text_data=json.dumps(race_started_msg))

    # Helper Methods

    async def send_state_sync(self):
        """Send current game state to client."""
        try:
            state_messages = self.game_state_manager.get_state_messages(self.user.id)

            for message in state_messages:
                await self.send(text_data=json.dumps(message))

        except Exception as e:
            logger.error(f"Error sending state sync: {e}")

    async def check_auto_completion(self):
        """Check if player's puzzle is complete after a move."""
        try:
            state = self.game_state_manager.get_current_state()
            player_state = state.players.get(self.user.id)

            if player_state and player_state.has_completed:
                # Auto-submit completion
                await self.handle_complete(CompleteMessage(
                    completion_time=int(player_state.completion_time.total_seconds())
                ))

        except Exception as e:
            logger.error(f"Error in auto-completion check: {e}")

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
            success, start_time = self.game_state_manager.start_race()
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
            logger.error(f"Error starting race: {e}")
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
    def mark_game_abandoned(self):
        """Mark game as abandoned."""
        try:
            with transaction.atomic():
                game = GameSession.objects.select_for_update().get(code=self.game_code)

                game.status = 'abandoned'
                game.end_time = timezone.now()

                # Create forfeit result if game was in progress
                if game.status == 'in_progress' and game.player1 and game.player2:
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

                game.save()

        except Exception as e:
            logger.error(f"Error marking game abandoned: {e}")
