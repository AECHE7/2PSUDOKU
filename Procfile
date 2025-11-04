release: python migrate_comprehensive.py
web: python migrate_comprehensive.py && daphne -p $PORT -b 0.0.0.0 config.asgi:application
worker: python manage.py runworker channels