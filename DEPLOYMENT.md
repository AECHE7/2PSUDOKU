# Deployment Guide for 2P Sudoku

This guide provides detailed instructions for deploying the 2-Player Sudoku game in various environments.

## Prerequisites

- Python 3.8 or higher
- Redis server 5.0 or higher
- PostgreSQL (for production, optional for development)
- pip and virtualenv

## Development Setup

### 1. Environment Setup

```bash
# Clone the repository
git clone https://github.com/AECHE7/2PSUDOKU.git
cd 2PSUDOKU

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Setup

```bash
# Apply migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser
```

### 3. Static Files

```bash
# Collect static files (for production)
python manage.py collectstatic --noinput
```

### 4. Start Redis

Redis is required for WebSocket functionality:

```bash
# On Linux/Mac
redis-server

# On Windows (if installed via Chocolatey or MSI)
redis-server

# Using Docker
docker run -d -p 6379:6379 redis:latest
```

### 5. Run Development Server

```bash
# Start Django development server with Daphne (ASGI)
daphne -b 0.0.0.0 -p 8000 sudoku_project.asgi:application

# Or use Django's runserver (HTTP only, WebSockets won't work)
python manage.py runserver
```

### 6. Access the Application

Open your browser and navigate to:
- Main app: http://127.0.0.1:8000/
- Admin panel: http://127.0.0.1:8000/admin/

## Production Deployment

### Option 1: Heroku

1. Create a Heroku app:
```bash
heroku create your-app-name
```

2. Add PostgreSQL and Redis add-ons:
```bash
heroku addons:create heroku-postgresql:mini
heroku addons:create heroku-redis:mini
```

3. Set environment variables:
```bash
heroku config:set DJANGO_SECRET_KEY='your-secret-key'
heroku config:set DEBUG=False
```

4. Create Procfile:
```
web: daphne -b 0.0.0.0 -p $PORT sudoku_project.asgi:application
```

5. Deploy:
```bash
git push heroku main
heroku run python manage.py migrate
```

### Option 2: Docker

1. Create `Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Run migrations and start server
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "sudoku_project.asgi:application"]
```

2. Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  web:
    build: .
    command: daphne -b 0.0.0.0 -p 8000 sudoku_project.asgi:application
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    depends_on:
      - redis
    environment:
      - DEBUG=False
      - REDIS_HOST=redis

volumes:
  redis_data:
```

3. Deploy:
```bash
docker-compose up -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

### Option 3: VPS (Ubuntu/Debian)

1. Install system dependencies:
```bash
sudo apt update
sudo apt install python3-pip python3-venv nginx redis-server postgresql
```

2. Setup PostgreSQL:
```bash
sudo -u postgres psql
CREATE DATABASE sudoku_db;
CREATE USER sudoku_user WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE sudoku_db TO sudoku_user;
\q
```

3. Update Django settings for production:
```python
# In settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'sudoku_db',
        'USER': 'sudoku_user',
        'PASSWORD': 'your-password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

ALLOWED_HOSTS = ['your-domain.com', 'www.your-domain.com']
DEBUG = False
```

4. Setup Gunicorn/Daphne with systemd:

Create `/etc/systemd/system/sudoku.service`:
```ini
[Unit]
Description=2P Sudoku Daphne Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/2PSUDOKU
ExecStart=/var/www/2PSUDOKU/venv/bin/daphne -b 0.0.0.0 -p 8000 sudoku_project.asgi:application

[Install]
WantedBy=multi-user.target
```

5. Configure Nginx:

Create `/etc/nginx/sites-available/sudoku`:
```nginx
upstream django {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    location /static/ {
        alias /var/www/2PSUDOKU/staticfiles/;
    }

    location / {
        proxy_pass http://django;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

6. Enable and start services:
```bash
sudo ln -s /etc/nginx/sites-available/sudoku /etc/nginx/sites-enabled/
sudo systemctl enable sudoku
sudo systemctl start sudoku
sudo systemctl restart nginx
```

## Environment Variables

For production, use environment variables:

```bash
# Required
export DJANGO_SECRET_KEY='your-secret-key-here'
export DEBUG=False
export ALLOWED_HOSTS='your-domain.com,www.your-domain.com'

# Database (if using PostgreSQL)
export DB_NAME='sudoku_db'
export DB_USER='sudoku_user'
export DB_PASSWORD='your-db-password'
export DB_HOST='localhost'
export DB_PORT='5432'

# Redis
export REDIS_HOST='localhost'
export REDIS_PORT='6379'
```

## Security Checklist

Before deploying to production:

- [ ] Set `DEBUG = False` in settings.py
- [ ] Generate a strong `SECRET_KEY`
- [ ] Configure `ALLOWED_HOSTS` properly
- [ ] Set up HTTPS with SSL certificate
- [ ] Enable `CSRF_COOKIE_SECURE = True`
- [ ] Enable `SESSION_COOKIE_SECURE = True`
- [ ] Enable `SECURE_SSL_REDIRECT = True`
- [ ] Set up proper database backups
- [ ] Configure Redis password
- [ ] Use environment variables for sensitive data
- [ ] Set up logging and monitoring
- [ ] Review and test all security settings

## Monitoring & Maintenance

### Logs
```bash
# View Django logs
tail -f /var/log/sudoku/django.log

# View Nginx logs
tail -f /var/nginx/access.log
tail -f /var/nginx/error.log
```

### Database Backups
```bash
# PostgreSQL backup
pg_dump sudoku_db > backup_$(date +%Y%m%d).sql

# Restore
psql sudoku_db < backup_20250101.sql
```

### Updates
```bash
# Pull latest code
git pull origin main

# Install new dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Restart service
sudo systemctl restart sudoku
```

## Troubleshooting

### WebSockets not working
- Ensure Redis is running: `redis-cli ping`
- Check channel layer configuration in settings.py
- Verify Nginx proxy settings include WebSocket upgrade headers

### Static files not loading
- Run `python manage.py collectstatic`
- Check Nginx static files configuration
- Verify STATIC_ROOT and STATIC_URL settings

### Database connection issues
- Check PostgreSQL is running: `sudo systemctl status postgresql`
- Verify database credentials in settings
- Check database user permissions

### Performance issues
- Enable database connection pooling
- Configure Redis max memory
- Set up caching with Django's cache framework
- Use a CDN for static files
- Monitor server resources

## Scaling

For high traffic:

1. **Use multiple Daphne workers**:
   - Run multiple Daphne instances behind a load balancer
   - Use Redis for session storage

2. **Database optimization**:
   - Add database indexes
   - Use read replicas
   - Configure connection pooling

3. **Caching**:
   - Use Django's caching framework
   - Cache game sessions and moves
   - Use Redis for caching

4. **Load Balancing**:
   - Use Nginx or HAProxy for load balancing
   - Distribute WebSocket connections across multiple servers

## Support

For issues or questions:
- GitHub Issues: https://github.com/AECHE7/2PSUDOKU/issues
- Documentation: See README.md

## License

MIT License - See LICENSE file for details
