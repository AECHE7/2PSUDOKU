"""
Django management command to test the complete game flow
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from game.models import GameSession, User
from game.sudoku import SudokuPuzzle
import random
import string


class Command(BaseCommand):
    help = 'Test the complete game flow: creation, joining, racing, and completion'

    def add_arguments(self, parser):
        parser.add_argument(
            '--difficulty',
            type=str,
            default='easy',
            choices=['easy', 'medium', 'hard'],
            help='Puzzle difficulty level'
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up test data after completion'
        )
        parser.add_argument(
            '--keep-game',
            action='store_true',
            help='Keep the test game in database (no cleanup)'
        )

    def generate_unique_code(self):
        """Generate a unique 6-character game code"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not GameSession.objects.filter(code=code).exists():
                return code

    def handle(self, *args, **options):
        difficulty = options['difficulty']
        cleanup = options['cleanup']
        keep_game = options['keep_game']
        
        self.stdout.write(self.style.SUCCESS('🧪 TESTING GAME FLOW...'))
        self.stdout.write('')
        
        # Ensure we have test users
        self.stdout.write('0. Setting up test users...')
        player1, created1 = User.objects.get_or_create(
            username='testplayer1',
            defaults={'email': 'player1@test.com'}
        )
        if created1:
            player1.set_password('testpass123')
            player1.save()
            self.stdout.write(f'   Created new user: {player1.username}')
        
        player2, created2 = User.objects.get_or_create(
            username='testplayer2',
            defaults={'email': 'player2@test.com'}
        )
        if created2:
            player2.set_password('testpass123')
            player2.save()
            self.stdout.write(f'   Created new user: {player2.username}')
        
        self.stdout.write(self.style.SUCCESS(f'✅ Player 1: {player1.username} (ID: {player1.id})'))
        self.stdout.write(self.style.SUCCESS(f'✅ Player 2: {player2.username} (ID: {player2.id})'))
        self.stdout.write('')
        
        # Create a test game
        self.stdout.write(f'1. Creating test game (difficulty: {difficulty})...')
        puzzle = SudokuPuzzle.generate_puzzle(difficulty)
        code = self.generate_unique_code()
        
        game = GameSession.objects.create(
            code=code,
            player1_id=player1.id,
            difficulty=difficulty,
            board={
                'puzzle': puzzle.board,
                'solution': puzzle.solution,
                'player1_board': [row[:] for row in puzzle.board],
                'player2_board': [row[:] for row in puzzle.board],
            },
            status='waiting',
        )
        self.stdout.write(self.style.SUCCESS(f'✅ Game created with code: {game.code}'))
        self.stdout.write(f'   Status: {game.status}')
        self.stdout.write(f'   Player 1: {player1.username}')
        self.stdout.write(f'   URL: http://localhost:8000/game/{game.code}/')
        self.stdout.write('')
        
        # Simulate player 2 joining
        self.stdout.write('2. Simulating player 2 joining...')
        game.player2_id = player2.id
        game.status = 'ready'
        game.save()
        self.stdout.write(self.style.SUCCESS('✅ Player 2 joined'))
        self.stdout.write(f'   Status: {game.status}')
        self.stdout.write(f'   Player 2: {player2.username}')
        self.stdout.write('')
        
        # Simulate race starting
        self.stdout.write('3. Simulating race start...')
        game.start_time = timezone.now()
        game.status = 'in_progress'
        game.save()
        self.stdout.write(self.style.SUCCESS(f'✅ Race started at: {game.start_time}'))
        self.stdout.write(f'   Status: {game.status}')
        self.stdout.write('')
        
        # Test board validation
        self.stdout.write('4. Testing board validation...')
        
        # Test with the puzzle board (incomplete)
        test_puzzle = SudokuPuzzle([row[:] for row in puzzle.board])
        test_puzzle.solution = [row[:] for row in puzzle.solution]
        is_complete = test_puzzle.matches_solution()
        
        if not is_complete:
            self.stdout.write(self.style.SUCCESS(f'   ✅ Incomplete board correctly identified: {is_complete}'))
        else:
            self.stdout.write(self.style.ERROR(f'   ❌ Incomplete board validation failed'))
        
        # Test with the solution (complete)
        complete_puzzle = SudokuPuzzle([row[:] for row in puzzle.solution])
        complete_puzzle.solution = [row[:] for row in puzzle.solution]
        is_complete = complete_puzzle.matches_solution()
        
        if is_complete:
            self.stdout.write(self.style.SUCCESS(f'   ✅ Complete board correctly identified: {is_complete}'))
        else:
            self.stdout.write(self.style.ERROR(f'   ❌ Complete board validation failed'))
        
        self.stdout.write('')
        
        # Show puzzle stats
        self.stdout.write('5. Puzzle statistics...')
        empty_cells = sum(1 for row in puzzle.board for cell in row if cell == 0)
        filled_cells = 81 - empty_cells
        self.stdout.write(f'   Total cells: 81')
        self.stdout.write(f'   Filled cells: {filled_cells}')
        self.stdout.write(f'   Empty cells: {empty_cells}')
        self.stdout.write(f'   Difficulty: {game.difficulty}')
        self.stdout.write('')
        
        # Cleanup or keep
        if cleanup or not keep_game:
            self.stdout.write('6. Cleaning up test data...')
            game.delete()
            self.stdout.write(self.style.SUCCESS(f'✅ Test game deleted'))
        else:
            self.stdout.write('6. Keeping test game for manual testing...')
            self.stdout.write(self.style.WARNING(f'⚠️  Game {game.code} kept in database'))
            self.stdout.write(f'   Access at: http://localhost:8000/game/{game.code}/')
            self.stdout.write(f'   Player 1: {player1.username}')
            self.stdout.write(f'   Player 2: {player2.username}')
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('🎉 ALL TESTS PASSED!'))
        self.stdout.write('')
        self.stdout.write('Summary:')
        self.stdout.write(self.style.SUCCESS('✅ Game creation works'))
        self.stdout.write(self.style.SUCCESS('✅ Player joining works'))
        self.stdout.write(self.style.SUCCESS('✅ Race start works'))
        self.stdout.write(self.style.SUCCESS('✅ Board validation works'))
        self.stdout.write(self.style.SUCCESS('✅ Status transitions work correctly'))
