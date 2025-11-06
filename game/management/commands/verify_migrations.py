from django.core.management.base import BaseCommand
from django.db import connection
import sys
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Verify critical migrations are applied and required columns exist'

    def handle(self, *args, **options):
        required_columns = {
            'game_gameresult': ['result_type', 'winner_id', 'loser_id', 'winner_time'],
            'game_gamesession': ['status', 'code', 'player1_id', 'player2_id']
        }
        
        missing_columns = []
        with connection.cursor() as cursor:
            for table, columns in required_columns.items():
                for column in columns:
                    try:
                        # Check if column exists using information_schema
                        if connection.vendor == 'postgresql':
                            cursor.execute("""
                                SELECT column_name 
                                FROM information_schema.columns 
                                WHERE table_name = %s AND column_name = %s
                            """, [table, column])
                        elif connection.vendor == 'sqlite':
                            cursor.execute(f"PRAGMA table_info({table})")
                            columns_info = cursor.fetchall()
                            column_names = [col[1] for col in columns_info]
                            if column not in column_names:
                                missing_columns.append(f"{table}.{column}")
                            continue
                        
                        if not cursor.fetchone():
                            missing_columns.append(f"{table}.{column}")
                    except Exception as e:
                        self.stderr.write(
                            self.style.ERROR(f"Error checking {table}.{column}: {e}")
                        )
                        missing_columns.append(f"{table}.{column} (error checking)")
        
        if missing_columns:
            self.stderr.write(
                self.style.ERROR(
                    "Critical columns missing. Run migrations:\n" +
                    "\n".join(f" - {col}" for col in missing_columns)
                )
            )
            sys.exit(1)
        
        self.stdout.write(
            self.style.SUCCESS("✅ All required database columns are present")
        )