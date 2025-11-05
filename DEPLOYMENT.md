# 🚀 Deployment Guide - 2PSUDOKU

This guide will help you deploy the 2PSUDOKU real-time multiplayer Sudoku game to production platforms.

## 🎯 Platform Recommendations

### **🟢 Render (Recommended for Django + WebSockets)**
- ✅ Native WebSocket support
- ✅ Built-in Redis instances
- ✅ PostgreSQL databases included
- ✅ Easy environment management
- ✅ Auto-deployments from GitHub

### **🟡 Railway (Alternative)**
- ✅ Great for Django apps
- ✅ PostgreSQL and Redis support
- ✅ Simple deployment process

### **🔴 Vercel (Not Recommended)**
- ❌ No native WebSocket support
- ❌ Serverless functions not ideal for real-time apps
- ❌ No built-in Redis/PostgreSQL

---

# 📋 Pre-Deployment Checklist

- [ ] Repository pushed to GitHub
- [ ] All deployment files created (✅ Done!)
- [ ] Production environment variables ready
- [ ] Domain name ready (optional)

---

# 🎯 Render Deployment (Recommended)

## Step 1: Create Accounts & Services

### 1.1 Create Render Account
1. Go to [render.com](https://render.com)
2. Sign up with GitHub (connects to your repo)
3. Verify your email

### 1.2 Create Redis Instance
1. In Render dashboard → **"Create New"** → **"Redis"**
2. **Name**: `2psudoku-redis`
3. **Region**: Choose closest to users
4. **Plan**: Free tier (25MB, fine for testing)
5. Click **"Create Redis"**
6. ⏳ Wait for deployment (~2 minutes)
7. 📝 **Copy the Redis URL** (Internal Redis URL)

### 1.3 Create PostgreSQL Database
1. **"Create New"** → **"PostgreSQL"**
2. **Name**: `2psudoku-db`
3. **Database**: `2psudoku`
4. **User**: `2psudoku_user`
5. **Region**: Same as Redis
6. **Plan**: Free tier
7. Click **"Create Database"**
8. ⏳ Wait for deployment (~3 minutes)
9. 📝 **Copy the Database URL** (External Database URL)

## Step 2: Create Web Service

### 2.1 Create Web Service
1. **"Create New"** → **"Web Service"**
2. **Connect Repository**: Select your `2PSUDOKU` GitHub repo
3. **Name**: `2psudoku-app`
4. **Region**: Same as database/Redis
5. **Branch**: `main`
6. **Runtime**: `Python 3`
7. **Build Command**: `./build.sh`
8. **Start Command**: `daphne -p $PORT -b 0.0.0.0 config.asgi:application`

### 2.2 Environment Variables
In the **Environment** tab, add:

```bash
DJANGO_SECRET_KEY=your-super-secret-50-character-key-here-random
DEBUG=0
ALLOWED_HOSTS=your-app-name.onrender.com
DATABASE_URL=postgresql://user:pass@host:5432/dbname
# Optional: Use Redis for channels/cache (recommended for multi-instance)
# If omitted, app will fall back to in-memory channels/cache suitable for a single instance
# REDIS_URL=redis://host:port/db

# Optional: Force Redis requirement (set to 1 to fail startup if REDIS_URL is missing)
# REQUIRE_REDIS=1
```

**🔑 Generate Secret Key:**
```python
# Run this in Python to generate a secret key:
import secrets
print(secrets.token_urlsafe(50))
```

### 2.3 Deploy
1. Click **"Create Web Service"**
2. ⏳ Wait for build (~5-10 minutes)
3. Check logs for any errors
4. Visit your app URL: `https://your-app-name.onrender.com`

---

# 🚂 Railway Deployment (Alternative)

## Step 1: Setup Railway

### 1.1 Create Account
1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub
3. Create new project

### 1.2 Deploy from GitHub
1. **"Deploy from GitHub repo"**
2. Select your `2PSUDOKU` repository
3. Railway auto-detects Python

### 1.3 Add Services
1. **Add PostgreSQL**: Click **"+ New"** → **"Database"** → **"PostgreSQL"**
2. **Add Redis**: Click **"+ New"** → **"Database"** → **"Redis"**

### 1.4 Environment Variables
In your service settings, add:

```bash
DJANGO_SECRET_KEY=your-secret-key
DEBUG=0
ALLOWED_HOSTS=$RAILWAY_STATIC_URL
DATABASE_URL=$DATABASE_URL
REDIS_URL=$REDIS_URL
```

### 1.5 Deploy
Railway will automatically build and deploy from your GitHub repo.

---

# 🔧 Post-Deployment Setup

## Step 1: Run Migrations
Most platforms run this automatically via `build.sh`, but if needed:

```bash
# In platform terminal/console:
python manage.py migrate
```

## Step 2: Create Superuser (Optional)
```bash
# In platform terminal:
python manage.py createsuperuser
```

## Step 3: Test the Application

### 3.1 Basic Functionality Test
1. Visit your deployed URL
2. Register two test accounts
3. Create a game with one account
4. Join with the second account
5. Verify real-time moves work

### 3.2 Check Admin Panel
1. Go to `https://your-app.com/admin/`
2. Login with superuser
3. Verify data is being saved

---

# 🎮 Testing Your Deployment

## Quick Deployment Test

1. **Open 2 browser windows**
2. **Window 1**: Register as `alice` / `testpass123`
3. **Window 2**: Register as `bob` / `testpass123`
4. **Alice**: Create new game → Note game code
5. **Bob**: Join game using code or click waiting game
6. **Alice**: Make a move (click cell, enter number)
7. **Bob**: Should see move instantly
8. **Bob**: Make your move
9. **Alice**: Should see Bob's move instantly

✅ **If moves update in real-time = SUCCESS!**

---

# 🔍 Troubleshooting

## Common Issues

### 🚨 "DisallowedHost" Error
**Solution**: Add your domain to `ALLOWED_HOSTS` in environment variables:
```bash
ALLOWED_HOSTS=yourdomain.onrender.com,www.yourdomain.com
```

### 🚨 Redis Connection Error
**Solution**: Check Redis URL format:
```bash
REDIS_URL=redis://host:port/db
# OR for Render internal:
REDIS_URL=redis://red-xxx:6379
```

### 🚨 Database Connection Error
**Solution**: Verify DATABASE_URL:
```bash
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

### 🚨 Static Files Not Loading
**Solution**: Run collect static:
```bash
python manage.py collectstatic --noinput
```

### 🚨 WebSocket Connection Failed
1. Check that Daphne is running (not Gunicorn)
2. If running multiple instances, ensure `REDIS_URL` is set and reachable; otherwise run a single instance or set up Redis
3. Check ASGI configuration in `config/asgi.py`

## Debugging Steps

### 1. Check Logs
- **Render**: Dashboard → Service → Logs tab
- **Railway**: Service → Deployments → View logs

### 2. Check Environment Variables
Verify all required environment variables are set correctly.

### 3. Test Components
```bash
# Test Redis connection:
python -c "import redis; r=redis.from_url('YOUR_REDIS_URL'); print(r.ping())"

# Test database:
python manage.py dbshell
```

---

# 🎉 Success!

Once deployed successfully, your real-time two-player Sudoku game will be live at:
- `https://your-app-name.onrender.com` (Render)
- `https://your-app-name.up.railway.app` (Railway)

Share the URL with friends to play real-time Sudoku together! 🎮

---

# 📈 Next Steps

## Performance Optimization
- [ ] Set up CDN for static files
- [ ] Configure caching
- [ ] Monitor performance with APM tools

## Feature Enhancements
- [ ] Add game timers and scoring
- [ ] Implement leaderboards
- [ ] Add spectator mode
- [ ] Mobile app development

## Scaling
- [ ] Horizontal scaling for high traffic
- [ ] Redis clustering
- [ ] Database optimization

---

# 💡 Tips

1. **Always test in production** after deployment
2. **Monitor logs** during first few days
3. **Set up alerts** for downtime
4. **Regular backups** of database
5. **Keep secrets secure** - never commit to Git

Happy deploying! 🚀