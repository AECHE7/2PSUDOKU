# 🚀 Quick Reference - Production Deployment

## Essential Commands

### Development
```bash
# Start development server
python manage.py runserver

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Check for issues
python manage.py check
```

### Production Deployment
```bash
# Validate environment
python validate_env.py

# Run migrations
python migrate_race_mode.py

# Collect static files
python manage.py collectstatic --noinput

# Start production server
./start_server.sh
```

## Environment Variables

### Required (Production)
```bash
DJANGO_SECRET_KEY=<50+ character random string>
DATABASE_URL=postgresql://user:pass@host:port/db
REDIS_URL=redis://host:port
DEBUG=0
RENDER=1
```

### Optional
```bash
PORT=8000
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com
```

## Security Checklist

- [ ] `DEBUG=0` in production
- [ ] Unique `SECRET_KEY` (50+ chars)
- [ ] Database backups configured
- [ ] SSL/TLS enabled
- [ ] Rate limiting active
- [ ] Input sanitization enabled
- [ ] Error tracking configured

## Troubleshooting

### WebSocket Issues
```javascript
// Enable debug mode temporarily
localStorage.setItem('debug', 'true');
location.reload();
```

### Database Issues
```bash
# Check connection
python manage.py dbshell

# Reset migrations (dangerous!)
python manage.py migrate game zero
python manage.py migrate
```

### Redis Issues
```bash
# Test Redis connection
redis-cli -u $REDIS_URL ping
```

## Monitoring

### Key Metrics to Watch
- Response time < 200ms
- Error rate < 0.1%
- WebSocket latency < 100ms
- Active games count
- Database connection pool usage

### Health Check Endpoints
- `/` - Main page (should load)
- `/admin/` - Admin panel (should require login)

## Support Contacts

**Documentation:** See `SECURITY_ANALYSIS.md` and `IMPLEMENTATION_CHANGES.md`  
**Issues:** Check GitHub Issues  
**Updates:** Follow deployment guide in `DEPLOY_NOW.md`
