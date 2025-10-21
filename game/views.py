from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from .models import GameSession, Move
from .sudoku_logic import generate_sudoku_puzzle
import json

# Create your views here.

def home(request):
    """Home page view"""
    return render(request, 'game/home.html')


def register(request):
    """User registration view"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        if not username or not password:
            messages.error(request, 'Username and password are required.')
            return render(request, 'game/register.html')
        
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'game/register.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'game/register.html')
        
        user = User.objects.create_user(username=username, password=password)
        login(request, user)
        messages.success(request, f'Welcome, {username}! Your account has been created.')
        return redirect('lobby')
    
    return render(request, 'game/register.html')


def login_view(request):
    """User login view"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {username}!')
            return redirect('lobby')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'game/login.html')


def logout_view(request):
    """User logout view"""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')


@login_required
def lobby(request):
    """Game lobby view - create or join games"""
    from django.db import models
    
    # Get active games waiting for players
    waiting_games = GameSession.objects.filter(status='waiting').exclude(player1=request.user)
    
    # Get user's active games
    user_games = GameSession.objects.filter(
        status__in=['waiting', 'active']
    ).filter(
        models.Q(player1=request.user) | models.Q(player2=request.user)
    )
    
    return render(request, 'game/lobby.html', {
        'waiting_games': waiting_games,
        'user_games': user_games
    })


@login_required
def create_game(request):
    """Create a new game session"""
    # Generate puzzle
    puzzle, solution = generate_sudoku_puzzle(difficulty=40)
    
    # Create game session
    game = GameSession.objects.create(
        session_code=GameSession.generate_session_code(),
        player1=request.user,
        status='waiting'
    )
    
    game.set_initial_board(puzzle)
    game.set_current_board(puzzle)
    game.set_solution(solution)
    game.save()
    
    messages.success(request, f'Game created! Share code: {game.session_code}')
    return redirect('game_room', session_code=game.session_code)


@login_required
def join_game(request, session_code):
    """Join an existing game session"""
    game = get_object_or_404(GameSession, session_code=session_code)
    
    if game.status != 'waiting':
        messages.error(request, 'This game is no longer available.')
        return redirect('lobby')
    
    if game.player1 == request.user:
        # Player 1 rejoining their own game
        return redirect('game_room', session_code=session_code)
    
    if game.player2 is not None:
        messages.error(request, 'This game is already full.')
        return redirect('lobby')
    
    # Join as player 2
    game.player2 = request.user
    game.status = 'active'
    game.current_turn = game.player1  # Player 1 starts
    game.started_at = timezone.now()
    game.save()
    
    messages.success(request, f'Joined game {session_code}!')
    return redirect('game_room', session_code=session_code)


@login_required
def game_room(request, session_code):
    """Game room view - actual gameplay"""
    game = get_object_or_404(GameSession, session_code=session_code)
    
    # Check if user is part of this game
    if request.user not in [game.player1, game.player2]:
        messages.error(request, 'You are not part of this game.')
        return redirect('lobby')
    
    return render(request, 'game/game_room.html', {
        'game': game,
        'initial_board': game.get_initial_board(),
        'current_board': game.get_current_board(),
    })


@login_required
def game_history(request):
    """View user's game history"""
    from django.db import models
    
    completed_games = GameSession.objects.filter(
        status='completed'
    ).filter(
        models.Q(player1=request.user) | models.Q(player2=request.user)
    ).order_by('-completed_at')
    
    return render(request, 'game/history.html', {
        'games': completed_games
    })

