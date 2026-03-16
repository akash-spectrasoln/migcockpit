import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datamigration.settings')
django.setup()

from django.db import connection

cursor = connection.cursor()
cursor.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_schema = 'GENERAL' AND table_name = 'source' 
    ORDER BY ordinal_position
""")

columns = [row[0] for row in cursor.fetchall()]
print("Columns in GENERAL.source table:")
for col in columns:
    print(f"  - {col}")

cursor.close()
