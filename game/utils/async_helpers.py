"""Async helper utilities for safe database and state access."""
import logging
from functools import wraps
from asgiref.sync import sync_to_async
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)

def safe_async_state(default=None):
    """Decorator for safely accessing state attributes in async context."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                return default
        return wrapper
    return decorator

class AsyncStateManager:
    """Helper for safely accessing state attributes in async context."""
    
    @staticmethod
    def get_attr_safe(obj, attr, default=None):
        """Safely get attribute from object."""
        try:
            return getattr(obj, attr, default)
        except Exception as e:
            logger.error(f"Error accessing {attr}: {e}")
            return default
            
    @staticmethod
    async def get_model_instance(model_class, **kwargs):
        """Safely get model instance in async context."""
        try:
            return await sync_to_async(model_class.objects.get)(**kwargs)
        except ObjectDoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting {model_class.__name__}: {e}")
            return None
            
    @staticmethod
    @sync_to_async
    def update_with_transaction(func, *args, **kwargs):
        """Run function in transaction context."""
        try:
            with transaction.atomic():
                return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Transaction error in {func.__name__}: {e}")
            return None