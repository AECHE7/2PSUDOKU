# Quick Start Guide - 2PSUDOKU

## 5-Minute Setup

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start Redis
docker run -p 6379:6379 -d redis:7

# 4. Run migrations
python manage.py migrate

# 5. Start server
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` and register!

## Test User Setup

```bash
python manage.py createsuperuser  # Create admin user
python manage.py shell
# In shell:
from django.contrib.auth.models import User
User.objects.create_user('player1', password='pass123')
User.objects.create_user('player2', password='pass123')
```

## Development Workflow

### Run Tests
```bash
python manage.py test game.tests -v 2
```

### Check System
```bash
python manage.py check
```

### Make Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Access Admin
```
http://127.0.0.1:8000/admin/
```

## Game URLs

| Endpoint | Purpose |
|----------|---------|
| `/` | Lobby (requires login) |
| `/register/` | User registration |
| `/login/` | User login |
| `/logout/` | User logout |
| `/create/` | Create new game |
| `/game/<code>/` | Play game with code |
| `/admin/` | Django admin panel |
| `ws://localhost:8000/ws/game/<code>/` | WebSocket connection |

## Troubleshooting

### Redis Error
```
Error: Cannot connect to Redis
→ docker run -p 6379:6379 -d redis:7
```

### WebSocket Connection Failed
```
Check Redis is running and ASGI_APPLICATION is set in settings.py
```

### Database Error
```
Run: python manage.py migrate
```

### Port Already in Use
```
python manage.py runserver 8001  # Use different port
```

## File Locations

- Models: `game/models.py`
- Views: `game/views.py`
- WebSocket: `game/consumers.py`
- Sudoku Logic: `game/sudoku.py`
- Templates: `templates/game/`
- Static Files: `static/game/`
- Tests: `game/tests.py`
- Config: `config/settings.py`, `config/asgi.py`

## Project Features

- ✅ Real-time two-player Sudoku
- ✅ User authentication
- ✅ WebSocket synchronization
- ✅ Server-side validation
- ✅ Puzzle generation
- ✅ Move logging
- ✅ Admin panel
- ✅ CI/CD workflow

## Deploy Checklist

- [ ] Set `DEBUG=0` in `.env`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Use PostgreSQL instead of SQLite
- [ ] Deploy Redis separately
- [ ] Use Daphne/Uvicorn for ASGI
- [ ] Collect static files: `python manage.py collectstatic`
- [ ] Enable HTTPS
- [ ] Configure CSRF settings

## Testing

```bash
# Run all tests
python manage.py test

# Run specific test
python manage.py test game.tests.SudokuPuzzleTestCase

# With coverage
pip install coverage
coverage run --source='game' manage.py test
coverage report
```

---

**Everything is ready to play!** 🎮
