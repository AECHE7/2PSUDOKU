"""
Structured WebSocket message protocol for Sudoku Race game.
Defines message types, schemas, and validation for clean real-time communication.
"""

import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime


class MessageType:
    """WebSocket message types for structured communication."""

    # Connection & Game Setup
    JOIN_GAME = "join_game"
    GAME_STATE = "game_state"
    PLAYER_CONNECTED = "player_connected"
    PLAYER_JOINED = "player_joined"
    PLAYER_DISCONNECTED = "player_disconnected"

    # Game Flow
    RACE_STARTED = "race_started"
    RACE_FINISHED = "race_finished"

    # Gameplay
    MOVE = "move"
    MOVE_MADE = "move_made"
    GAME_PROGRESS_UPDATE = "game_progress_update"

    # Completion & Results
    PUZZLE_COMPLETE = "puzzle_complete"
    COMPLETE = "complete"

    # Game Management
    PLAY_AGAIN = "play_again"
    NEW_GAME_CREATED = "new_game_created"
    LEAVE_GAME = "leave_game"
    PLAYER_LEFT_GAME = "player_left_game"
    LEAVE_GAME_CONFIRMED = "leave_game_confirmed"

    # System
    NOTIFICATION = "notification"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


@dataclass
class WebSocketMessage:
    """Base class for all WebSocket messages."""
    type: str
    data: Dict[str, Any]
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for JSON serialization."""
        return {
            'type': self.type,
            'timestamp': self.timestamp,
            **self.data
        }

    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'WebSocketMessage':
        """Create message from JSON string."""
        data = json.loads(json_str)
        msg_type = data.pop('type')
        timestamp = data.pop('timestamp', None)
        return cls(type=msg_type, data=data, timestamp=timestamp)


# Specific Message Classes

@dataclass
class JoinGameMessage(WebSocketMessage):
    """Player joining a game."""
    def __init__(self, player_id: int):
        super().__init__(
            type=MessageType.JOIN_GAME,
            data={'player_id': player_id}
        )


@dataclass
class GameStateMessage(WebSocketMessage):
    """Current game state broadcast."""
    def __init__(self, puzzle: List[List[int]], board: List[List[int]],
                 opponent_board: Optional[List[List[int]]], player1: str,
                 player2: Optional[str], status: str,
                 start_time: Optional[str]):
        super().__init__(
            type=MessageType.GAME_STATE,
            data={
                'puzzle': puzzle,
                'board': board,
                'opponent_board': opponent_board,
                'player1': player1,
                'player2': player2,
                'status': status,
                'start_time': start_time
            }
        )


@dataclass
class RaceStartedMessage(WebSocketMessage):
    """Race has begun."""
    def __init__(self, start_time: str, puzzle: List[List[int]]):
        super().__init__(
            type=MessageType.RACE_STARTED,
            data={
                'start_time': start_time,
                'puzzle': puzzle
            }
        )


@dataclass
class MoveMessage(WebSocketMessage):
    """Player makes a move."""
    def __init__(self, row: int, col: int, value: int):
        super().__init__(
            type=MessageType.MOVE,
            data={
                'row': row,
                'col': col,
                'value': value
            }
        )


@dataclass
class MoveMadeMessage(WebSocketMessage):
    """Move broadcast to all players."""
    def __init__(self, username: str, row: int, col: int, value: int,
                 player_id: int, timestamp: str):
        super().__init__(
            type=MessageType.MOVE_MADE,
            data={
                'username': username,
                'row': row,
                'col': col,
                'value': value,
                'player_id': player_id,
                'timestamp': timestamp
            }
        )


@dataclass
class CompleteMessage(WebSocketMessage):
    """Player submits completed puzzle."""
    def __init__(self, completion_time: int):
        super().__init__(
            type=MessageType.COMPLETE,
            data={'completion_time': completion_time}
        )


@dataclass
class RaceFinishedMessage(WebSocketMessage):
    """Race completion results."""
    def __init__(self, winner_id: int, winner_username: str,
                 winner_time: str, loser_time: Optional[str]):
        super().__init__(
            type=MessageType.RACE_FINISHED,
            data={
                'winner_id': winner_id,
                'winner_username': winner_username,
                'winner_time': winner_time,
                'loser_time': loser_time
            }
        )


@dataclass
class PlayAgainMessage(WebSocketMessage):
    """Request to play again."""
    def __init__(self, difficulty: str):
        super().__init__(
            type=MessageType.PLAY_AGAIN,
            data={'difficulty': difficulty}
        )


@dataclass
class NewGameCreatedMessage(WebSocketMessage):
    """New game created for rematch."""
    def __init__(self, game_code: str, difficulty: str):
        super().__init__(
            type=MessageType.NEW_GAME_CREATED,
            data={
                'game_code': game_code,
                'difficulty': difficulty
            }
        )


@dataclass
class ErrorMessage(WebSocketMessage):
    """Error message."""
    def __init__(self, message: str, code: Optional[str] = None):
        data = {'error': message}
        if code:
            data['code'] = code
        super().__init__(
            type=MessageType.ERROR,
            data=data
        )


@dataclass
class NotificationMessage(WebSocketMessage):
    """General notification."""
    def __init__(self, message: str, level: str = 'info'):
        super().__init__(
            type=MessageType.NOTIFICATION,
            data={
                'message': message,
                'level': level
            }
        )


class MessageFactory:
    """Factory for creating message instances."""

    @staticmethod
    def create_message(msg_type: str, data: Dict[str, Any]) -> WebSocketMessage:
        """Create a message instance based on type."""
        message_classes = {
            MessageType.JOIN_GAME: JoinGameMessage,
            MessageType.GAME_STATE: GameStateMessage,
            MessageType.MOVE: MoveMessage,
            MessageType.MOVE_MADE: MoveMadeMessage,
            MessageType.COMPLETE: CompleteMessage,
            MessageType.RACE_FINISHED: RaceFinishedMessage,
            MessageType.PLAY_AGAIN: PlayAgainMessage,
            MessageType.NEW_GAME_CREATED: NewGameCreatedMessage,
            MessageType.ERROR: ErrorMessage,
            MessageType.NOTIFICATION: NotificationMessage,
        }

        if msg_type not in message_classes:
            raise ValueError(f"Unknown message type: {msg_type}")

        # Extract required fields based on message class
        if msg_type == MessageType.JOIN_GAME:
            return message_classes[msg_type](data.get('player_id'))
        elif msg_type == MessageType.GAME_STATE:
            return message_classes[msg_type](
                data.get('puzzle'), data.get('board'),
                data.get('opponent_board'), data.get('player1'),
                data.get('player2'), data.get('status'),
                data.get('start_time')
            )
        elif msg_type == MessageType.MOVE:
            return message_classes[msg_type](
                data.get('row'), data.get('col'), data.get('value')
            )
        elif msg_type == MessageType.MOVE_MADE:
            return message_classes[msg_type](
                data.get('username'), data.get('row'),
                data.get('col'), data.get('value'),
                data.get('player_id'), data.get('timestamp')
            )
        elif msg_type == MessageType.COMPLETE:
            return message_classes[msg_type](data.get('completion_time'))
        elif msg_type == MessageType.RACE_FINISHED:
            return message_classes[msg_type](
                data.get('winner_id'), data.get('winner_username'),
                data.get('winner_time'), data.get('loser_time')
            )
        elif msg_type == MessageType.PLAY_AGAIN:
            return message_classes[msg_type](data.get('difficulty'))
        elif msg_type == MessageType.NEW_GAME_CREATED:
            return message_classes[msg_type](
                data.get('game_code'), data.get('difficulty')
            )
        elif msg_type == MessageType.ERROR:
            return message_classes[msg_type](
                data.get('message'), data.get('code')
            )
        elif msg_type == MessageType.NOTIFICATION:
            return message_classes[msg_type](
                data.get('message'), data.get('level')
            )

        # Default case - pass all data to constructor
        return message_classes[msg_type](**data)


class MessageValidator:
    """Validates WebSocket messages against schemas."""

    @staticmethod
    def validate_move_message(data: Dict[str, Any]) -> bool:
        """Validate move message data."""
        required_fields = ['row', 'col', 'value']
        if not all(field in data for field in required_fields):
            return False

        # Validate types and ranges
        try:
            row = int(data['row'])
            col = int(data['col'])
            value = int(data['value'])
            
            # Check ranges
            if not (0 <= row < 9 and 0 <= col < 9):
                return False
            if not (0 <= value <= 9):  # 0 is allowed for clearing a cell
                return False
                
            return True
        except (ValueError, TypeError):
            return False
