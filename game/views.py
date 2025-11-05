from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.html import escape
from django.views.decorators.cache import cache_page
import uuid
import re
from .models import GameSession
from .sudoku import SudokuPuzzle
from .decorators import rate_limit

def sanitize_username(username):
    """Sanitize username to prevent XSS and ensure valid characters."""
    if not username:
        return None
    # Allow only alphanumeric, underscore, and hyphen
    username = re.sub(r'[^\w\-]', '', username)
    return escape(username.strip())[:150]  # Django's max username length

@rate_limit(max_requests=5, window_seconds=300)  # 5 attempts per 5 minutes
def register(request):
    if request.method == 'POST':
        username = sanitize_username(request.POST.get('username', ''))
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        # Validate inputs
        errors = {}
        if not username:
            errors['username'] = ['Username is required']
        elif len(username) < 3:
            errors['username'] = ['Username must be at least 3 characters long']
        elif User.objects.filter(username=username).exists():
            errors['username'] = ['Username already exists']
            
        if not password:
            errors['password'] = ['Password is required']
        elif len(password) < 6:
            errors['password'] = ['Password must be at least 6 characters long']
            
        if not password_confirm:
            errors['password_confirm'] = ['Please confirm your password']
        elif password != password_confirm:
            errors['password_confirm'] = ['Passwords do not match']
            
        if errors:
            # Create a form-like object for template compatibility
            form = type('MockForm', (), {
                'errors': errors,
                'username': type('Field', (), {'errors': errors.get('username', []), 'value': username or ''})(),
                'password': type('Field', (), {'errors': errors.get('password', []), 'value': ''})(),
                'password_confirm': type('Field', (), {'errors': errors.get('password_confirm', []), 'value': ''})(),
            })()
            return render(request, 'game/register.html', {'form': form})
        
        # Create user and login
        user = User.objects.create_user(username=username, password=password)
        login(request, user)
        return redirect('index')
    
    # Create empty form for GET request
    form = type('MockForm', (), {
        'errors': {},
        'username': type('Field', (), {'errors': [], 'value': ''})(),
        'password': type('Field', (), {'errors': [], 'value': ''})(),
        'password_confirm': type('Field', (), {'errors': [], 'value': ''})(),
    })()
    return render(request, 'game/register.html', {'form': form})

@rate_limit(max_requests=10, window_seconds=300)  # 10 attempts per 5 minutes
def login_view(request):
    if request.method == 'POST':
        username = sanitize_username(request.POST.get('username', ''))
        password = request.POST.get('password')
        
        # Validate inputs
        errors = {}
        if not username:
            errors['username'] = ['Username is required']
        if not password:
            errors['password'] = ['Password is required']
            
        if errors:
            # Create a form-like object for template compatibility
            form = type('MockForm', (), {
                'errors': errors,
                'username': type('Field', (), {'errors': errors.get('username', []), 'value': username})(),
                'password': type('Field', (), {'errors': errors.get('password', []), 'value': ''})(),
            })()
            return render(request, 'game/login.html', {'form': form})
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            # Create error for invalid credentials
            form = type('MockForm', (), {
                'errors': {'__all__': ['Invalid username or password']},
                'username': type('Field', (), {'errors': [], 'value': username})(),
                'password': type('Field', (), {'errors': [], 'value': ''})(),
            })()
            return render(request, 'game/login.html', {'form': form})
    
    # Create empty form for GET request
    form = type('MockForm', (), {
        'errors': {},
        'username': type('Field', (), {'errors': [], 'value': ''})(),
        'password': type('Field', (), {'errors': [], 'value': ''})(),
    })()
    return render(request, 'game/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('index')

@login_required(login_url='login')
def index(request):
    games = GameSession.objects.filter(status='waiting')
    return render(request, 'game/index.html', {'games': games})

@login_required(login_url='login')
def create_game(request):
    """Create a new game session with difficulty selection."""
    if request.method == 'POST':
        difficulty = request.POST.get('difficulty', 'medium')
        if difficulty not in ['easy', 'medium', 'hard']:
            difficulty = 'medium'
            
        code = str(uuid.uuid4())[:8].upper()
        puzzle = SudokuPuzzle.generate_puzzle(difficulty)
        
        game = GameSession.objects.create(
            code=code,
            player1=request.user,
            difficulty=difficulty,
            board={
                'puzzle': puzzle.board,  # The puzzle with holes
                'solution': puzzle.solution,  # The complete solution
                'player1_board': [row[:] for row in puzzle.board],  # Each player has own board state
                'player2_board': [row[:] for row in puzzle.board],
            },
            status='waiting',
        )
        
        return redirect('game_detail', code=code)
    
    # Show difficulty selection form
    return render(request, 'game/create_game.html')

@login_required(login_url='login')
def game_detail(request, code):
    """Display a game board for competitive solving."""
    try:
        game = GameSession.objects.get(code=code)
    except GameSession.DoesNotExist:
        return render(request, 'game/game_not_found.html', {'code': code})
    
    # Check if user is a player
    is_player1 = game.player1 == request.user
    is_player2 = game.player2 == request.user if game.player2 else False
    
    if not (is_player1 or is_player2):
        # Allow joining if game is waiting
        if game.status == 'waiting' and game.player2 is None:
            game.player2 = request.user
            game.status = 'ready'  # Both players joined, ready to start
            game.save()
            is_player2 = True
        else:
            return render(request, 'game/cannot_join.html', {'game': game})
    
    # Get the correct board state for this player
    player_key = 'player1_board' if is_player1 else 'player2_board'
    board = game.board.get(player_key, game.board.get('puzzle', []))
    
    return render(request, 'game/game_board.html', {
        'game': game,
        'board': board,
        'puzzle': game.board.get('puzzle', []),
        'is_player1': is_player1,
        'is_player2': is_player2,
        'difficulty': game.difficulty,
    })
