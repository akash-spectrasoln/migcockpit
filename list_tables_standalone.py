
import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datamigrationapi.settings')
django.setup()

from django.db import connection
cursor = connection.cursor()
cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'GENERAL'")
print("GENERAL tables:", cursor.fetchall())
cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
print("public tables:", cursor.fetchall())
