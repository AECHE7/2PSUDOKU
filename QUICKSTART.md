# Quick Start Guide

Get the 2-Player Sudoku game running in 5 minutes!

## Prerequisites

- Python 3.8+ installed
- Git installed
- Redis server (optional for testing, required for production)

## Installation

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/AECHE7/2PSUDOKU.git
cd 2PSUDOKU

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Initialize Database

```bash
# Run migrations
python manage.py migrate

# Create demo users and game (optional)
python demo.py
```

### 3. Run the Server

```bash
# Start the development server
python manage.py runserver
```

### 4. Access the Application

Open your browser and go to: **http://127.0.0.1:8000/**

## Demo Accounts

If you ran `demo.py`, you can login with:
- **Username:** `demo_player1` | **Password:** `demo123`
- **Username:** `demo_player2` | **Password:** `demo123`

Or create your own account by clicking "Register" on the home page.

## How to Play

### Creating a Game

1. Login to your account
2. Click "Go to Lobby" or "Create New Game"
3. Share your game's session code with a friend
4. Wait for them to join

### Joining a Game

1. Login to your account
2. Go to the lobby
3. Enter the session code in "Join with Code"
   - OR select from available games
4. Click "Join Game"

### Playing the Game

1. Wait for your turn (indicated by the green dot)
2. Click on an empty cell in the Sudoku grid
3. Select a number from the number pad
4. Valid moves earn you 10 points
5. Invalid moves pass your turn to the opponent
6. Complete the puzzle with the highest score to win!

## Testing WebSocket Functionality

For real-time gameplay, you need Redis:

```bash
# Install Redis
# Ubuntu/Debian:
sudo apt install redis-server

# Mac:
brew install redis

# Start Redis
redis-server

# In another terminal, start the Django server with ASGI
daphne -b 0.0.0.0 -p 8000 sudoku_project.asgi:application
```

## Troubleshooting

### "No module named django"
```bash
# Make sure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### WebSocket connection fails
- Make sure Redis is running: `redis-cli ping` (should return "PONG")
- Use Daphne instead of runserver: `daphne sudoku_project.asgi:application`

### Database errors
```bash
# Reset database (WARNING: deletes all data)
rm db.sqlite3
python manage.py migrate
python demo.py
```

## Next Steps

- See [README.md](README.md) for full documentation
- See [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment
- Run tests: `python manage.py test game`
- Create superuser: `python manage.py createsuperuser`
- Access admin: http://127.0.0.1:8000/admin/

## Development

### Running Tests
```bash
python manage.py test game
```

### Making Changes
```bash
# After modifying models
python manage.py makemigrations
python manage.py migrate

# After modifying static files
python manage.py collectstatic
```

### Code Quality
```bash
# Check for issues
python manage.py check

# Run deployment checks
python manage.py check --deploy
```

## Getting Help

- **Issues:** https://github.com/AECHE7/2PSUDOKU/issues
- **Documentation:** [README.md](README.md)
- **Deployment:** [DEPLOYMENT.md](DEPLOYMENT.md)

Enjoy playing 2-Player Sudoku! 🎮🎉
