from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import uuid
from .models import GameSession
from .sudoku import SudokuPuzzle

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        if password != password_confirm:
            return render(request, 'game/register.html', {'error': 'Passwords do not match'})
        if User.objects.filter(username=username).exists():
            return render(request, 'game/register.html', {'error': 'Username already exists'})
        user = User.objects.create_user(username=username, password=password)
        login(request, user)
        return redirect('index')
    return render(request, 'game/register.html', {})

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('index')
        return render(request, 'game/login.html', {'error': 'Invalid credentials'})
    return render(request, 'game/login.html', {})

def logout_view(request):
    logout(request)
    return redirect('index')

@login_required(login_url='login')
def index(request):
    games = GameSession.objects.filter(status='waiting')
    return render(request, 'game/index.html', {'games': games})

@login_required(login_url='login')
def create_game(request):
    """Create a new game session."""
    code = str(uuid.uuid4())[:8].upper()
    puzzle = SudokuPuzzle.generate_puzzle('medium')
    
    game = GameSession.objects.create(
        code=code,
        player1=request.user,
        board={
            'puzzle': puzzle.board,
            'current': [row[:] for row in puzzle.board],
        },
        current_turn=request.user,
        status='waiting',
    )
    
    return redirect('game_detail', code=code)

@login_required(login_url='login')
def game_detail(request, code):
    """Display a game board."""
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
            game.status = 'in_progress'
            game.save()
            is_player2 = True
        else:
            return render(request, 'game/cannot_join.html', {'game': game})
    
    return render(request, 'game/game_board.html', {
        'game': game,
        'board': game.board.get('current', []),
        'is_player1': is_player1,
        'is_player2': is_player2,
    })
