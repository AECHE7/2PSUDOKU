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
    """Create GameResult record with fallback for missing result_type column.
    
    Note: This fallback can be removed once migration 0005_ensure_result_type
    has been applied to all environments (especially production)."""
    from django.db import transaction, IntegrityError
    from ..models import GameResult  # Fix: import from parent game module
    
    try:
        with transaction.atomic():
            # Try creating with result_type first
            try:
                return GameResult.objects.create(
                    game=game,
                    winner=winner,
                    loser=loser,
                    winner_time=winner_time,
                    difficulty=difficulty,
                    result_type=result_type
                )
            except Exception as e:
                if 'result_type' not in str(e).lower():
                    raise
                
                # Fall back to creating without result_type if column doesn't exist
                return GameResult.objects.create(
                    game=game,
                    winner=winner,
                    loser=loser,
                    winner_time=winner_time,
                    difficulty=difficulty
                )
    except IntegrityError:
        # Handle race condition - get existing result
        return GameResult.objects.get(game=game)