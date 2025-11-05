"""
Django management command to create a test game ready for browser testing
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from game.models import GameSession, User
from game.sudoku import SudokuPuzzle
import random
import string


class Command(BaseCommand):
    help = 'Create a test game with two players ready to start racing in browser'

    def add_arguments(self, parser):
        parser.add_argument(
            '--difficulty',
            type=str,
            default='easy',
            choices=['easy', 'medium', 'hard'],
            help='Puzzle difficulty level'
        )
        parser.add_argument(
            '--auto-start',
            action='store_true',
            help='Automatically start the race (set status to in_progress)'
        )

    def generate_unique_code(self):
        """Generate a unique 6-character game code"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not GameSession.objects.filter(code=code).exists():
                return code

    def handle(self, *args, **options):
        difficulty = options['difficulty']
        auto_start = options['auto_start']
        
        self.stdout.write(self.style.SUCCESS('🎮 Creating Test Game for Browser Testing'))
        self.stdout.write('=' * 60)
        self.stdout.write('')
        
        # Ensure we have test users
        self.stdout.write('1. Setting up test users...')
        player1, created1 = User.objects.get_or_create(
            username='testplayer1',
            defaults={'email': 'player1@test.com'}
        )
        if created1:
            player1.set_password('testpass123')
            player1.save()
            self.stdout.write('   ✅ Created testplayer1')
        else:
            self.stdout.write('   ✅ Using existing testplayer1')
        
        player2, created2 = User.objects.get_or_create(
            username='testplayer2',
            defaults={'email': 'player2@test.com'}
        )
        if created2:
            player2.set_password('testpass123')
            player2.save()
            self.stdout.write('   ✅ Created testplayer2')
        else:
            self.stdout.write('   ✅ Using existing testplayer2')
        
        self.stdout.write('')
        
        # Create the game
        self.stdout.write(f'2. Creating game (difficulty: {difficulty})...')
        code = self.generate_unique_code()
        puzzle = SudokuPuzzle.generate_puzzle(difficulty)
        
        # Determine initial status
        if auto_start:
            status = 'in_progress'
            start_time = timezone.now()
        else:
            status = 'ready'
            start_time = None
        
        game = GameSession.objects.create(
            code=code,
            player1_id=player1.id,
            player2_id=player2.id,
            difficulty=difficulty,
            board={
                'puzzle': puzzle.board,
                'solution': puzzle.solution,
                'player1_board': [row[:] for row in puzzle.board],
                'player2_board': [row[:] for row in puzzle.board],
            },
            status=status,
            start_time=start_time,
        )
        
        self.stdout.write(self.style.SUCCESS('   ✅ Game created!'))
        self.stdout.write('')
        
        # Show game details
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('🎉 TEST GAME READY!'))
        self.stdout.write('=' * 60)
        self.stdout.write('')
        self.stdout.write(f'Game Code: {self.style.WARNING(code)}')
        self.stdout.write(f'Difficulty: {difficulty}')
        self.stdout.write(f'Status: {status}')
        if start_time:
            self.stdout.write(f'Started: {start_time}')
        self.stdout.write('')
        
        # Show puzzle stats
        empty_cells = sum(1 for row in puzzle.board for cell in row if cell == 0)
        filled_cells = 81 - empty_cells
        self.stdout.write('Puzzle Info:')
        self.stdout.write(f'  - Empty cells: {empty_cells}')
        self.stdout.write(f'  - Filled cells: {filled_cells}')
        self.stdout.write('')
        
        # Show browser testing instructions
        self.stdout.write(self.style.SUCCESS('📋 BROWSER TESTING INSTRUCTIONS:'))
        self.stdout.write('')
        self.stdout.write('1. Open TWO browser windows (or use incognito for second)')
        self.stdout.write('')
        self.stdout.write('   Window 1 (Player 1):')
        self.stdout.write(f'   - Go to: http://localhost:8000/login/')
        self.stdout.write(f'   - Login: testplayer1 / testpass123')
        self.stdout.write(f'   - Navigate to: http://localhost:8000/game/{code}/')
        self.stdout.write('')
        self.stdout.write('   Window 2 (Player 2):')
        self.stdout.write(f'   - Go to: http://localhost:8000/login/')
        self.stdout.write(f'   - Login: testplayer2 / testpass123')
        self.stdout.write(f'   - Navigate to: http://localhost:8000/game/{code}/')
        self.stdout.write('')
        
        if auto_start:
            self.stdout.write('2. Game will START IMMEDIATELY (auto-start enabled)')
            self.stdout.write('   - Timers should start counting')
            self.stdout.write('   - Both boards should be editable')
        else:
            self.stdout.write('2. Game is READY but not started')
            self.stdout.write('   - Wait for both players to connect')
            self.stdout.write('   - Race will start automatically when both are ready')
        
        self.stdout.write('')
        self.stdout.write('3. Test the complete flow:')
        self.stdout.write('   ✓ Timer synchronization')
        self.stdout.write('   ✓ Real-time move updates')
        self.stdout.write('   ✓ Board validation')
        self.stdout.write('   ✓ Auto-submit on completion')
        self.stdout.write('   ✓ Winner modal display')
        self.stdout.write('   ✓ Play again functionality')
        self.stdout.write('')
        
        # Quick access URLs
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('🔗 QUICK ACCESS URLS:'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'Game URL: http://localhost:8000/game/{code}/')
        self.stdout.write(f'Login: http://localhost:8000/login/')
        self.stdout.write(f'Lobby: http://localhost:8000/')
        self.stdout.write('')
        
        # Show a tip
        self.stdout.write(self.style.WARNING('💡 TIP: Open browser DevTools (F12) to see:'))
        self.stdout.write('   - WebSocket messages in Console')
        self.stdout.write('   - Network tab for WS connection')
        self.stdout.write('   - Detailed game flow logging')
        self.stdout.write('')
