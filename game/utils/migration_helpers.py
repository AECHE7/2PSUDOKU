"""Migration helper to handle missing result_type column gracefully."""
from django.db import connection

def has_result_type_column():
    """Check if the result_type column exists in game_gameresult table."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'game_gameresult' 
                AND column_name = 'result_type'
            );
        """)
        return cursor.fetchone()[0]

def create_game_result_safely(game, winner, loser, winner_time, difficulty, result_type='completion'):
    """Migration helper to handle missing result_type column gracefully."""
import logging
from django.db import connection, transaction, IntegrityError
from django.utils import timezone
from ..models import GameResult, GameSession

logger = logging.getLogger(__name__)

def has_result_type_column():
    """Check if the result_type column exists in game_gameresult table."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'game_gameresult' 
                AND column_name = 'result_type'
            );
        """)
        return cursor.fetchone()[0]

def ensure_result_type_column():
    """Ensure the result_type column exists."""
    if not has_result_type_column():
        with connection.cursor() as cursor:
            try:
                cursor.execute("""
                    ALTER TABLE game_gameresult 
                    ADD COLUMN IF NOT EXISTS result_type varchar(20) 
                    DEFAULT 'completion' NOT NULL;
                """)
                cursor.execute("""
                    UPDATE game_gameresult 
                    SET result_type = 'completion' 
                    WHERE result_type IS NULL;
                """)
                return True
            except Exception as e:
                logger.error(f"Error ensuring result_type column: {e}")
                return False
    return True

def create_game_result_safely(game, winner, loser, winner_time, difficulty, result_type='completion'):