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
    
    # Redis can be optional for single-instance deployments; require it only when explicitly requested
    require_redis = os.environ.get('REQUIRE_REDIS', '0') == '1'

    required_vars = {
        'DJANGO_SECRET_KEY': 'Django secret key for cryptographic signing',
        'DATABASE_URL': 'PostgreSQL database connection string',
    }
    if require_redis:
        required_vars['REDIS_URL'] = 'Redis connection string for channels and caching'
    
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
    
    # Informational note when Redis is not required and not provided
    if not require_redis and not os.environ.get('REDIS_URL'):
        print("ℹ️ No REDIS_URL set — app will use in-memory channels/cache (okay for single-instance)")

    print("✅ All required environment variables are configured")


if __name__ == '__main__':
    validate_production_env()
