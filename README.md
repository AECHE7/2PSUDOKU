# 2PSUDOKU

A real-time, two-player Sudoku web game built with Django, Django Channels, and WebSockets.

## Features

- **User Authentication**: Secure registration and login system
- **Real-Time Multiplayer**: Live game updates via WebSockets
- **Turn-Based Gameplay**: Players alternate making moves
- **Move Validation**: Server-side validation ensures fair play
- **Scoring System**: Points awarded for correct moves
- **Game Lobby**: Create or join games with session codes
- **Game History**: Track your completed games and stats

## Technical Stack

- **Backend**: Python 3.x, Django 4.2
- **Real-Time**: Django Channels, WebSockets, Redis
- **Frontend**: HTML, CSS, JavaScript
- **Database**: SQLite (development), PostgreSQL ready (production)

## Installation & Setup

### Prerequisites

- Python 3.8 or higher
- Redis server (for WebSocket support)
- pip (Python package manager)

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/AECHE7/2PSUDOKU.git
   cd 2PSUDOKU
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Apply database migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create a superuser** (optional, for admin access)
   ```bash
   python manage.py createsuperuser
   ```

6. **Start Redis server**
   ```bash
   redis-server
   ```
   
   Note: Redis must be running for WebSocket functionality to work.

7. **Run the development server**
   ```bash
   python manage.py runserver
   ```

8. **Access the application**
   - Open your browser and navigate to `http://127.0.0.1:8000/`
   - Register a new account or login
   - Create or join a game!

## How to Play

1. **Register/Login**: Create an account or login to access the game lobby
2. **Create a Game**: Click "Create New Game" to start a new Sudoku session
3. **Share the Code**: Share your game's session code with a friend
4. **Join a Game**: Enter a session code or select from available games
5. **Play**: Take turns filling in the Sudoku grid
   - Select an empty cell
   - Choose a number from the number pad
   - Valid moves earn 10 points
   - Invalid moves pass the turn to your opponent
6. **Win**: Complete the puzzle with the highest score!

## Game Rules

- Players take turns filling in empty cells
- Each correct move awards 10 points
- Invalid moves pass the turn but don't update the board
- The player with the highest score when the puzzle is complete wins
- If scores are equal, the game is a draw

## Architecture

### Models
- **GameSession**: Stores game state, players, scores, and board data
- **Move**: Records all moves made during games

### WebSocket Communication
- Real-time updates using Django Channels
- Redis as the channel layer backend
- Synchronous game state across all clients

### Frontend
- Responsive design with modern CSS
- JavaScript handles WebSocket connections and UI updates
- Interactive Sudoku board with visual feedback

## Development

### Project Structure
```
2PSUDOKU/
├── game/                  # Main game app
│   ├── migrations/        # Database migrations
│   ├── templates/         # HTML templates
│   ├── admin.py          # Admin interface config
│   ├── consumers.py      # WebSocket consumers
│   ├── models.py         # Database models
│   ├── routing.py        # WebSocket routing
│   ├── sudoku_logic.py   # Sudoku generation & validation
│   ├── urls.py           # URL patterns
│   └── views.py          # View functions
├── sudoku_project/       # Project settings
│   ├── asgi.py          # ASGI configuration
│   ├── settings.py      # Django settings
│   └── urls.py          # Main URL config
├── static/              # Static files (CSS, JS)
├── manage.py           # Django management script
└── requirements.txt    # Python dependencies
```

### Running Tests
```bash
python manage.py test game
```

### Admin Interface
Access the admin panel at `http://127.0.0.1:8000/admin/` to:
- View all game sessions
- Monitor player moves
- Manage users

## Production Deployment

For production deployment:

1. Set `DEBUG = False` in settings.py
2. Configure a production database (PostgreSQL recommended)
3. Set up proper SECRET_KEY management
4. Use a production-grade Redis server
5. Serve static files with a web server (nginx, Apache)
6. Use a production ASGI server (Daphne, Uvicorn)

## Contributing

Contributions are welcome! Please feel free to submit pull requests.

## License

This project is open source and available under the MIT License.

## Future Enhancements

- [ ] Matchmaking system
- [ ] Chat functionality during games
- [ ] Leaderboards and statistics
- [ ] Different difficulty levels
- [ ] Mobile app version
- [ ] Tournament mode
- [ ] Spectator mode
- [ ] Replay saved games
