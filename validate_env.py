"""
Environment variable validation on startup.
Ensures all required environment variables are set for production.
"""
import os
import sys


def validate_production_env():
    """Validate that all required environment variables are set for production."""
    if not os.environ.get('RENDER'):
        # Not in production, skip validation
        return
    
    print("🔍 Validating production environment variables...")
    
    required_vars = {
        'DJANGO_SECRET_KEY': 'Django secret key for cryptographic signing',
        'DATABASE_URL': 'PostgreSQL database connection string',
        'REDIS_URL': 'Redis connection string for channels and caching',
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        if not os.environ.get(var):
            missing_vars.append(f"  - {var}: {description}")
    
    if missing_vars:
        print("❌ CRITICAL: Missing required environment variables:")
        for var in missing_vars:
            print(var)
        print("\n⚠️ Application may not function correctly!")
        sys.exit(1)
    
    # Validate DEBUG is disabled in production
    if os.environ.get('DEBUG', '0') != '0':
        print("⚠️ WARNING: DEBUG should be set to 0 in production!")
    
    # Validate SECRET_KEY is not default
    if os.environ.get('DJANGO_SECRET_KEY') == 'dev-secret-change-in-production':
        print("❌ CRITICAL: DJANGO_SECRET_KEY is set to default value!")
        print("   Generate a new secret key and set it in environment variables.")
        sys.exit(1)
    
    print("✅ All required environment variables are configured")


if __name__ == '__main__':
    validate_production_env()
