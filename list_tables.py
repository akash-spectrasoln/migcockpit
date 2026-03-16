
from django.db import connection
cursor = connection.cursor()
cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'GENERAL'")
print(cursor.fetchall())
cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
print(cursor.fetchall())
