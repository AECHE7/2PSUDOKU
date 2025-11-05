"""
Centralized game state management for Sudoku Race.
Handles state synchronization, validation, and consistency checks.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

from django.utils import timezone
from django.db import transaction
from channels.db import database_sync_to_async

from .models import GameSession, Move
from .sudoku import SudokuPuzzle
from .messages import MessageType, GameStateMessage, RaceStartedMessage, PuzzleCompleteMessage

logger = logging.getLogger(__name__)


class GameStatus(Enum):
    """Game status enumeration."""
    WAITING = "waiting"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"
    ABANDONED = "abandoned"


class PlayerState:
    """Represents a player's current state in the game."""

    def __init__(self, player_id: int, username: str):
        self.player_id = player_id
        self.username = username
        self.board: List[List[int]] = []
        self.is_ready = False
        self.completion_time: Optional[timedelta] = None
        self.has_completed = False
        self.last_activity = timezone.now()

    def update_board(self, board: List[List[int]]):
        """Update player's board state."""
        self.board = [row[:] for row in board]  # Deep copy
        self.last_activity = timezone.now()

    def mark_completed(self, completion_time: timedelta):
        """Mark player as completed."""
        self.has_completed = True
        self.completion_time = completion_time
        self.last_activity = timezone.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'player_id': self.player_id,
            'username': self.username,
            'board': self.board,
            'is_ready': self.is_ready,
            'completion_time': self.completion_time.total_seconds() if self.completion_time else None,
            'has_completed': self.has_completed,
            'last_activity': self.last_activity.isoformat(),
        }


@dataclass
class GameStateSnapshot:
    """Snapshot of complete game state for synchronization."""

    game_id: int
    status: GameStatus
    puzzle: List[List[int]]
    solution: List[List[int]]
    players: Dict[int, PlayerState]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    winner_id: Optional[int]
    created_at: datetime
    last_updated: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'game_id': self.game_id,
            'status': self.status.value,
            'puzzle': self.puzzle,
            'solution': self.solution,
            'players': {pid: player.to_dict() for pid, player in self.players.items()},
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'winner_id': self.winner_id,
            'created_at': self.created_at.isoformat(),
            'last_updated': self.last_updated.isoformat(),
        }


class GameStateManager:
    """Centralized manager for game state operations."""

    def __init__(self, game_session: GameSession):
        self.game_session = game_session
        self._state_cache: Optional[GameStateSnapshot] = None
        self._last_sync = None

    def get_current_state(self) -> GameStateSnapshot:
        """Get current game state, using cache if recent."""
        if self._should_refresh_cache():
            self._state_cache = self._load_state_from_db()
            self._last_sync = timezone.now()

        return self._state_cache

    def _should_refresh_cache(self) -> bool:
        """Check if cache should be refreshed."""
        if self._state_cache is None:
            return True

        # Refresh if cache is older than 5 seconds
        return (timezone.now() - self._last_sync).total_seconds() > 5

    def _load_state_from_db(self) -> GameStateSnapshot:
        """Load complete state from database."""
        game = self.game_session

        # Load players
        players = {}
        if game.player1:
            players[game.player1.id] = PlayerState(
                game.player1.id, game.player1.username
            )
        if game.player2:
            players[game.player2.id] = PlayerState(
                game.player2.id, game.player2.username
            )

        # Load board data
        board_data = game.board or {}
        puzzle = board_data.get('puzzle', [])
        solution = board_data.get('solution', [])

        # Load player boards
        for player_id, player_state in players.items():
            if player_id == game.player1_id:
                player_state.board = board_data.get('player1_board', puzzle)
            elif player_id == game.player2_id:
                player_state.board = board_data.get('player2_board', puzzle)

        return GameStateSnapshot(
            game_id=game.id,
            status=GameStatus(game.status),
            puzzle=puzzle,
            solution=solution,
            players=players,
            start_time=game.start_time,
            end_time=game.end_time,
            winner_id=game.winner.id if game.winner else None,
            created_at=game.created_at,
            last_updated=timezone.now(),
        )

    def update_player_board(self, player_id: int, board: List[List[int]]) -> bool:
        """Update a player's board state."""
        try:
            with transaction.atomic():
                game = GameSession.objects.select_for_update().get(id=self.game_session.id)

                # Update board data
                board_data = game.board or {}
                if player_id == game.player1_id:
                    board_data['player1_board'] = [row[:] for row in board]
                elif player_id == game.player2_id:
                    board_data['player2_board'] = [row[:] for row in board]
                else:
                    return False

                game.board = board_data
                game.save()

                # Update cache
                if self._state_cache and player_id in self._state_cache.players:
                    self._state_cache.players[player_id].update_board(board)
                    self._state_cache.last_updated = timezone.now()

                return True

        except Exception as e:
            logger.error(f"Failed to update player board: {e}")
            return False

    def start_race(self) -> Tuple[bool, Optional[str]]:
        """Start the race if conditions are met."""
        try:
            with transaction.atomic():
                game = GameSession.objects.select_for_update().get(id=self.game_session.id)

                # Check conditions
                if game.status != 'ready':
                    return False, "Game not ready to start"

                if not game.player1 or not game.player2:
                    return False, "Need two players to start"

                # Set start time and status
                game.start_time = timezone.now()
                game.status = GameStatus.IN_PROGRESS.value
                game.save()

                # Update cache
                if self._state_cache:
                    self._state_cache.start_time = game.start_time
                    self._state_cache.status = GameStatus.IN_PROGRESS
                    self._state_cache.last_updated = timezone.now()

                return True, game.start_time.isoformat()

        except Exception as e:
            logger.error(f"Failed to start race: {e}")
            return False, str(e)

    def complete_puzzle(self, player_id: int) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Mark a player's puzzle as completed."""
        try:
            with transaction.atomic():
                game = GameSession.objects.select_for_update().get(id=self.game_session.id)

                # Verify game state
                if game.status != GameStatus.IN_PROGRESS.value:
                    logger.error(f"Cannot complete puzzle: game status is {game.status}")
                    return False, None

                # Verify start time
                if not game.start_time:
                    logger.error("Cannot complete puzzle: no start time")
                    return False, None

                # Verify board data
                board_data = game.board or {}
                player_board = None
                if player_id == game.player1_id:
                    player_board = board_data.get('player1_board')
                elif player_id == game.player2_id:
                    player_board = board_data.get('player2_board')
                
                solution = board_data.get('solution')
                
                if not player_board or not solution:
                    logger.error("Cannot complete puzzle: missing board data")
                    return False, None

                # Verify solution is correct
                is_correct = all(
                    player_board[i][j] == solution[i][j]
                    for i in range(9)
                    for j in range(9)
                )

                if not is_correct:
                    logger.error("Cannot complete puzzle: solution is incorrect")
                    return False, None

                completion_time = timezone.now() - game.start_time

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
                    logger.error(f"Cannot complete puzzle: player {player_id} not in game")
                    return False, None

                # Create result
                result = GameResult.objects.create(
                    game=game,
                    winner=winner,
                    loser=loser,
                    winner_time=completion_time,
                    difficulty=game.difficulty,
                    result_type='completion'
                )

                # Update game
                game.winner = winner
                game.status = GameStatus.FINISHED.value
                game.end_time = timezone.now()
                game.save()

                # Update cache
                if self._state_cache:
                    if player_id in self._state_cache.players:
                        self._state_cache.players[player_id].mark_completed(completion_time)
                    self._state_cache.status = GameStatus.FINISHED
                    self._state_cache.winner_id = player_id
                    self._state_cache.end_time = game.end_time
                    self._state_cache.last_updated = timezone.now()

                result_data = {
                    'winner_id': winner.id,
                    'winner_username': winner.username,
                    'winner_time': f"{int(completion_time.total_seconds() // 60):02d}:{int(completion_time.total_seconds() % 60):02d}",
                    'loser_time': 'Did not finish',
                }

                return True, result_data

        except Exception as e:
            logger.error(f"Failed to complete puzzle: {e}")
            return False, None

    def add_player(self, player_id: int, username: str, is_player1: bool = False) -> bool:
        """Add a player to the game."""
        try:
            with transaction.atomic():
                game = GameSession.objects.select_for_update().get(id=self.game_session.id)

                from django.contrib.auth.models import User
                user = User.objects.get(id=player_id)

                if is_player1 and not game.player1:
                    game.player1 = user
                    game.status = 'waiting'
                elif not is_player1 and not game.player2:
                    game.player2 = user
                    if game.player1:
                        game.status = 'ready'
                else:
                    return False

                game.save()

                # Update cache
                if self._state_cache:
                    self._state_cache.players[player_id] = PlayerState(player_id, username)
                    self._state_cache.last_updated = timezone.now()

                return True

        except Exception as e:
            logger.error(f"Failed to add player: {e}")
            return False

    def validate_move(self, player_id: int, row: int, col: int, value: int) -> bool:
        """Validate a move against the current game state."""
        state = self.get_current_state()

        # Check if game is in progress
        if state.status != GameStatus.IN_PROGRESS:
            return False

        # Check if player is in game
        if player_id not in state.players:
            return False

        player_state = state.players[player_id]

        # Check bounds
        if not (0 <= row < 9 and 0 <= col < 9 and 1 <= value <= 9):
            return False

        # Check if cell is already filled in puzzle (immutable)
        if state.puzzle[row][col] != 0:
            return False

        # Check Sudoku rules against player's current board
        board = player_state.board

        # Check row - exclude current cell
        for c in range(9):
            if c != col and board[row][c] == value:
                return False

        # Check column - exclude current cell
        for r in range(9):
            if r != row and board[r][col] == value:
                return False

        # Check 3x3 box - exclude current cell
        box_row = (row // 3) * 3
        box_col = (col // 3) * 3
        for r in range(box_row, box_row + 3):
            for c in range(box_col, box_col + 3):
                if (r != row or c != col) and board[r][c] == value:
                    return False

        return True

    def record_move(self, player_id: int, row: int, col: int, value: int) -> bool:
        """Record a validated move."""
        try:
            # Create move record
            Move.objects.create(
                game=self.game_session,
                player_id=player_id,
                row=row,
                col=col,
                value=value
            )

            # Update player board
            state = self.get_current_state()
            if player_id in state.players:
                board = state.players[player_id].board
                board[row][col] = value
                self.update_player_board(player_id, board)

            return True

        except Exception as e:
            logger.error(f"Failed to record move: {e}")
            return False

    def get_state_messages(self, player_id: int) -> List[Dict[str, Any]]:
        """Get state synchronization messages for a player."""
        state = self.get_current_state()
        messages = []

        # Game state message
        player_state = state.players.get(player_id)
        opponent_id = None
        opponent_board = None

        for pid, pstate in state.players.items():
            if pid != player_id:
                opponent_id = pid
                opponent_board = pstate.board
                break

        messages.append(GameStateMessage(
            puzzle=state.puzzle,
            board=player_state.board if player_state else state.puzzle,
            opponent_board=opponent_board,
            player1=state.players.get(self.game_session.player1_id).username if self.game_session.player1 else None,
            player2=state.players.get(self.game_session.player2_id).username if self.game_session.player2 else None,
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

    @database_sync_to_async
    def get_current_state_async(self) -> GameStateSnapshot:
        """Async-safe version of get_current_state."""
        return self.get_current_state()

    @database_sync_to_async
    def validate_move_async(self, player_id: int, row: int, col: int, value: int) -> bool:
        """Async-safe move validation."""
        return self.validate_move(player_id, row, col, value)

    @database_sync_to_async
    def record_move_async(self, player_id: int, row: int, col: int, value: int) -> bool:
        """Async-safe move recording."""
        return self.record_move(player_id, row, col, value)

    @database_sync_to_async
    def start_race_async(self) -> Tuple[bool, Optional[str]]:
        """Async-safe race start."""
        return self.start_race()

    @database_sync_to_async
    def complete_puzzle_async(self, player_id: int) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Async-safe puzzle completion."""
        return self.complete_puzzle(player_id)

    @database_sync_to_async
    def get_state_messages_async(self, player_id: int) -> List[Dict[str, Any]]:
        """Async-safe state messages retrieval."""
        return self.get_state_messages(player_id)
