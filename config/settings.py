import os
import dj_database_url
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file only if it exists (for local development)
env_file = BASE_DIR / '.env'
if env_file.exists():
    load_dotenv(env_file)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-secret-change-in-production')
DEBUG = os.environ.get('DEBUG', '1') == '1'

# Enforce production security: DEBUG should NEVER be True in production
if os.environ.get('RENDER') and DEBUG:
    print("⚠️ WARNING: DEBUG is enabled on Render. Set DEBUG=0 in environment variables!")
    # Force DEBUG off in production for security
    DEBUG = False

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '0.0.0.0',
    'twopsudoku.onrender.com',
    '.onrender.com',  # Allow any Render subdomain
    '*' if DEBUG else None  # Only allow all hosts in DEBUG mode
]
ALLOWED_HOSTS = [host for host in ALLOWED_HOSTS if host is not None]

# CSRF trusted origins for Render deployment
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'https://twopsudoku.onrender.com',
    'https://*.onrender.com',  # Allow any Render subdomain
]

# Add additional trusted origins from environment if specified
additional_origins = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if additional_origins:
    CSRF_TRUSTED_ORIGINS.extend(additional_origins.split(','))

# Additional CSRF settings for production
if not DEBUG:
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    CSRF_USE_SESSIONS = False
    CSRF_COOKIE_SAMESITE = 'Lax'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'game.apps.GameConfig',  # Use our custom AppConfig with auto-migration
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'game.middleware.EmergencyMigrationMiddleware',  # Emergency migration safety net
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Content Security Policy settings to allow Bootstrap CDN
CSP_DEFAULT_SRC = ("'self'",)
CSP_STYLE_SRC = (
    "'self'", 
    "'unsafe-inline'",  # Allow inline styles
    "https://cdn.jsdelivr.net",  # Bootstrap CSS
)
CSP_SCRIPT_SRC = (
    "'self'", 
    "'unsafe-inline'",  # Allow inline scripts
    "https://cdn.jsdelivr.net",  # Bootstrap JS
)
CSP_FONT_SRC = ("'self'", "https://cdn.jsdelivr.net")
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_CONNECT_SRC = ("'self'", "ws:", "wss:")  # Allow WebSocket connections

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    print(f"Using PostgreSQL database: {DATABASE_URL[:50]}...")  # Debug log
    try:
        DATABASES = {
            'default': dj_database_url.parse(
                DATABASE_URL, 
                conn_max_age=600,  # Keep connections alive for 10 minutes
                ssl_require=True,
                conn_health_checks=True,  # Enable connection health checks
            )
        }
        # Add connection pooling configuration
        DATABASES['default']['OPTIONS'] = {
            'connect_timeout': 10,
            'options': '-c statement_timeout=30000',  # 30 second query timeout
        }
    except Exception as e:
        print(f"Database configuration error: {e}")
        raise
else:
    print("Using SQLite database for development")
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Only add STATICFILES_DIRS if the static directory exists
static_dir = BASE_DIR / 'static'
if static_dir.exists():
    STATICFILES_DIRS = [static_dir]

# Static file storage for production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Logging configuration for debugging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Channels / Redis
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')
print(f"Using Redis URL: {REDIS_URL}")  # Debug log

# Cache configuration using Redis
# Use django-redis in production for better performance and features
# Falls back to in-memory cache in development if django-redis is not available
try:
    import django_redis
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
                'RETRY_ON_TIMEOUT': True,
                'MAX_CONNECTIONS': 50,
            },
            'KEY_PREFIX': '2psudoku',
            'TIMEOUT': 300,  # 5 minutes default
        }
    }
    print("✅ Using django-redis cache backend")
except ImportError:
    # Fallback to dummy cache in development if django-redis not installed
    print("⚠️ django-redis not found, using dummy cache (development only)")
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        }
    }

# Parse Redis URL for Channels
import urllib.parse
redis_url = urllib.parse.urlparse(REDIS_URL)

try:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [{
                    'address': (redis_url.hostname, redis_url.port),
                    'password': redis_url.password,
                }] if redis_url.password else [REDIS_URL],
            },
        },
    }
    print("Redis channel layers configured successfully")
except Exception as e:
    print(f"Redis configuration error: {e}")
    # Fallback to in-memory channel layer for debugging
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# Production security settings
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    
    # Render handles SSL termination, so we don't need these redirect settings
    # SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # SECURE_HSTS_SECONDS = 31536000
    # SECURE_SSL_REDIRECT = True  # This was causing the redirect loop!
    
    # Only secure cookies if we're definitely on HTTPS (Render handles this)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = 'DENY'
    
    # Additional security headers
    SECURE_REFERRER_POLICY = 'same-origin'
    SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
    
    # Trust Render's proxy headers
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
