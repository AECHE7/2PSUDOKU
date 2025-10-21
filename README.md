# 2PSUDOKU

Real-time two-player Sudoku built with Django, Django Channels, and WebSockets.

## Features

- **User Authentication**: Secure registration and login system
- **Game Sessions**: Create game lobbies or join existing ones by code
- **Real-Time Play**: Powered by Django Channels and WebSockets for instant updates
- **Sudoku Logic**: Automatic puzzle generation, move validation, and board state tracking
- **Turn-Based Mechanics**: Players alternate filling numbers with server-side validation
- **Live Board Updates**: Both players see all moves instantly without page refresh

## Tech Stack

- **Backend**: Python 3.x, Django 5.2+, Django Channels
- **Database**: SQLite (development), PostgreSQL (production)
- **Real-Time Layer**: Redis + Django Channels
- **Frontend**: Django templates + vanilla JavaScript + WebSockets

## Quick Start (Development)

### 1. Create and activate virtual environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Setup environment

```bash
cp .env.example .env
# Edit .env if needed (defaults work for development)
```

### 4. Start Redis (required for WebSockets)

```bash
# Using Docker (recommended):
docker run -p 6379:6379 -d redis:7

# Or run Redis locally if installed:
redis-server
```

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Create a superuser (optional, for admin panel)

```bash
python manage.py createsuperuser
```

### 7. Start development server

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` in your browser.

## Usage

1. **Register**: Create a new account at `/register/`
2. **Login**: Log in with your credentials
3. **Create Game**: Click "Create Game" to start a new puzzle
4. **Join Game**: Click on a waiting game in the lobby to join
5. **Play**: Click on cells to enter numbers (1-9)
6. **Real-Time Sync**: Your opponent's moves appear instantly

## Project Structure

```
2PSUDOKU/
├── config/              # Django project configuration
│   ├── settings.py      # Settings with Channels config
│   ├── asgi.py          # ASGI app for Channels
│   ├── wsgi.py          # WSGI for regular views
│   └── urls.py          # URL routing
├── game/                # Main app
│   ├── models.py        # GameSession, Move models
│   ├── views.py         # Auth and game views
│   ├── consumers.py     # WebSocket consumers
│   ├── sudoku.py        # Sudoku puzzle logic
│   ├── routing.py       # WebSocket URL routing
│   ├── urls.py          # URL patterns
│   ├── admin.py         # Django admin
│   └── tests.py         # Unit tests
├── templates/           # HTML templates
│   ├── base.html        # Base template with nav
│   └── game/
│       ├── index.html           # Lobby page
│       ├── login.html           # Login page
│       ├── register.html        # Registration page
│       └── game_board.html      # Game board
├── static/game/         # Static files
│   ├── game_board.js    # Game board JavaScript
│   ├── game.js          # Lobby JavaScript
│   └── styles.css       # CSS styles
├── db.sqlite3           # SQLite database (created after migrations)
├── manage.py            # Django management script
└── requirements.txt     # Python dependencies
```

## Testing

Run unit tests:

```bash
python manage.py test game.tests
```

## Admin Panel

Access Django admin at `/admin/` with superuser credentials to:
- View and manage game sessions
- View player moves
- Monitor user accounts

## Production Deployment Notes

For production deployment:

1. **Database**: Switch from SQLite to PostgreSQL
2. **Redis**: Use a managed Redis service or deploy a Redis instance
3. **ASGI Server**: Use Daphne or Uvicorn instead of Django's runserver
4. **Environment**: Set `DEBUG=0` in `.env` and configure `ALLOWED_HOSTS`
5. **Static Files**: Collect static files with `python manage.py collectstatic`
6. **Security**: Enable HTTPS and configure CSRF settings

Example production settings in `.env`:
```
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=0
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
REDIS_URL=redis://your-redis-host:6379
```

## API Endpoints

### HTTP Endpoints

- `GET /` - Lobby (requires login)
- `GET /register/` - Registration page
- `POST /register/` - Register new user
- `GET /login/` - Login page
- `POST /login/` - Log in user
- `GET /logout/` - Log out user
- `GET /create/` - Create new game
- `GET /game/<code>/` - Play game

### WebSocket Endpoint

- `ws://localhost:8000/ws/game/<code>/` - Game WebSocket connection

### WebSocket Messages

**Client to Server:**
```json
{
  "type": "join_game",
  "playerId": 123
}
```

```json
{
  "type": "move",
  "row": 0,
  "col": 0,
  "value": 5
}
```

```json
{
  "type": "get_board"
}
```

**Server to Client:**
```json
{
  "type": "game_state",
  "board": [[...9x9 board...]],
  "player1": "username1",
  "player2": "username2"
}
```

```json
{
  "type": "move",
  "username": "player",
  "row": 0,
  "col": 0,
  "value": 5
}
```

```json
{
  "type": "notification",
  "message": "Player connected"
}
```

## Troubleshooting

### Redis Connection Error
Ensure Redis is running on `localhost:6379` or update `REDIS_URL` in `.env`.

### WebSocket Connection Issues
- Check that Redis is running
- Ensure `ASGI_APPLICATION = 'config.asgi.application'` is set in settings
- Verify WebSocket URL matches your server URL

### Database Errors
Run migrations: `python manage.py migrate`

## Future Enhancements

- [ ] Game timer and scoring system
- [ ] Elo rating system and leaderboard
- [ ] Spectator mode
- [ ] Undo/hint functionality
- [ ] Difficulty selection before game
- [ ] Game history and statistics
- [ ] Chat during games
- [ ] Mobile app

## Contributing

Contributions are welcome! Please submit pull requests to improve the project.

## License

MIT License - See LICENSE file for details

# 2PSUDOKU