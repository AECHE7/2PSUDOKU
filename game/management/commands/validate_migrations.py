from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
import sys

class Command(BaseCommand):
    help = 'Validates that required migrations are applied'

    def handle(self, *args, **options):
        self.stdout.write('Checking required migrations...')
        
        # Check if game_gameresult table exists and has result_type column
        with connection.cursor() as cursor:
            # Check table existence
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'game_gameresult'
                );
            """)
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                self.stderr.write(self.style.ERROR(
                    'Critical error: game_gameresult table does not exist! '
                    'Migrations must be run before starting the application.'
                ))
                sys.exit(1)
            
            # Check result_type column
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'game_gameresult' 
                    AND column_name = 'result_type'
                );
            """)
            column_exists = cursor.fetchone()[0]
            
            if not column_exists:
                self.stderr.write(self.style.ERROR(
                    'Critical error: result_type column missing from game_gameresult! '
                    'Migration 0003_gameresult_result_type must be applied.'
                ))
                sys.exit(1)

        # Check migration history
        recorder = MigrationRecorder(connection)
        applied = recorder.applied_migrations()
        
        required_migrations = {
            ('game', '0001_initial'),
            ('game', '0002_remove_gamesession_current_turn_and_more'),
            ('game', '0003_gameresult_result_type_alter_gamesession_status'),
            ('game', '0004_alter_gameresult_loser'),
        }
        
        missing = required_migrations - set(applied)
        if missing:
            self.stderr.write(self.style.ERROR(
                f'Critical error: Missing required migrations: {missing}. '
                'Run python manage.py migrate before starting the application.'
            ))
            sys.exit(1)
            
        self.stdout.write(self.style.SUCCESS('✅ All required migrations are applied'))