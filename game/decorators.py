"""
Simple rate limiting decorator for Django views.
Protects against brute force attacks on login and registration.
"""
from functools import wraps
from django.core.cache import cache
from django.http import HttpResponse
from django.utils import timezone
import hashlib


def rate_limit(max_requests=5, window_seconds=300):
    """
    Rate limiting decorator.
    
    Args:
        max_requests: Maximum number of requests allowed in the time window
        window_seconds: Time window in seconds (default: 5 minutes)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Get client IP
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            
            # Create cache key
            cache_key = f'rate_limit:{view_func.__name__}:{ip}'
            
            # Get current request count
            requests = cache.get(cache_key, 0)
            
            if requests >= max_requests:
                # Rate limit exceeded
                retry_after = cache.ttl(cache_key)
                return HttpResponse(
                    f'Rate limit exceeded. Please try again in {retry_after} seconds.',
                    status=429,
                    headers={'Retry-After': str(retry_after)}
                )
            
            # Increment request count
            cache.set(cache_key, requests + 1, window_seconds)
            
            return view_func(request, *args, **kwargs)
        
        return wrapped_view
    return decorator
