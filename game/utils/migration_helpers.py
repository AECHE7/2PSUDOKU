"""Migration helper to handle missing result_type column gracefully.

CRITICAL: This file ensures GameResult creation works even if the result_type
column is missing in the database. It will automatically add the column if needed.

Last updated: 2025-11-06
Status: PRODUCTION READY
"""
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
                logger.info("Successfully added result_type column")
                return True
            except Exception as e:
                logger.error(f"Error ensuring result_type column: {e}")
                return False
    return True

def create_game_result_safely(game, winner, loser, winner_time, difficulty, result_type='completion'):
    """Create GameResult record with multiple fallback strategies.
    
    This function will:
    1. Ensure the column exists first
    2. Check for existing result to avoid duplicates
    3. Try to create with result_type
    4. Fall back to simpler creation if needed
    5. Handle race conditions gracefully
    """
    
    try:
        # First ensure the column exists
        ensure_result_type_column()
        
        # Check for existing result first to avoid duplicates
        try:
            existing = GameResult.objects.get(game=game)
            logger.info(f"Game result already exists for game {game.id}")
            return existing
        except GameResult.DoesNotExist:
            pass
        
        with transaction.atomic():
            # Try creating with result_type first
            try:
                result = GameResult.objects.create(
                    game=game,
                    winner=winner,
                    loser=loser,
                    winner_time=winner_time,
                    difficulty=difficulty,
                    result_type=result_type
                )
                logger.info(f"Created game result for game {game.id} with result_type")
                return result
                
            except Exception as e:
                error_msg = str(e).lower()
                logger.warning(f"Error creating result with result_type: {e}")
                
                # Only fall back if it's specifically a result_type issue
                if 'result_type' not in error_msg:
                    raise
                
                # Fall back to creating without result_type
                try:
                    result = GameResult.objects.create(
                        game=game,
                        winner=winner,
                        loser=loser,
                        winner_time=winner_time,
                        difficulty=difficulty
                    )
                    logger.info(f"Created game result for game {game.id} without result_type")
                    return result
                except Exception as inner_e:
                    logger.error(f"Error in fallback creation: {inner_e}")
                    raise
                
    except IntegrityError as e:
        # Handle race condition - another process may have created it
        logger.info(f"Handling race condition for game {game.id}")
        try:
            return GameResult.objects.get(game=game)
        except GameResult.DoesNotExist:
            logger.error(f"Race condition but result doesn't exist: {e}")
            raise
            
    except Exception as e:
        logger.error(f"Unexpected error creating game result: {e}", exc_info=True)
        raise
