#!/usr/bin/env python
"""
Simple script to run Django migrations manually.
Useful for debugging migration issues.
"""
import os
import django
from django.core.management import execute_from_command_line
from django.conf import settings

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    
    print("🔍 Current database configuration:")
    db_config = settings.DATABASES['default']
    print(f"Engine: {db_config['ENGINE']}")
    print(f"Name: {db_config.get('NAME', 'N/A')}")
    print(f"Host: {db_config.get('HOST', 'N/A')}")
    
    print("\n📋 Current migration status:")
    execute_from_command_line(['manage.py', 'showmigrations'])
    
    print("\n🗃️ Running migrations...")
    execute_from_command_line(['manage.py', 'migrate', '--verbosity=2'])
    
    print("\n✅ Migration script completed!")