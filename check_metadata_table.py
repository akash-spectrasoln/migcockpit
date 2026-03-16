"""
Check if node_cache_metadata table exists and show its contents.
"""
import psycopg2
import json

# Database connection
conn = psycopg2.connect(
    host="localhost",
    port=5433,
    database="C00008",  # Your customer database
    user="postgres",
    password="postgres"
)

cursor = conn.cursor()

print("=" * 80)
print("CHECKING CANVAS_CACHE SCHEMA AND TABLES")
print("=" * 80)

# 1. Check if CANVAS_CACHE schema exists
print("\n1. Checking if CANVAS_CACHE schema exists...")
cursor.execute("""
    SELECT schema_name 
    FROM information_schema.schemata 
    WHERE schema_name = 'CANVAS_CACHE'
""")
schema_exists = cursor.fetchone()
if schema_exists:
    print("   ✓ CANVAS_CACHE schema EXISTS")
else:
    print("   ✗ CANVAS_CACHE schema DOES NOT EXIST")
    print("\n   Creating schema...")
    cursor.execute('CREATE SCHEMA IF NOT EXISTS "CANVAS_CACHE"')
    conn.commit()
    print("   ✓ Schema created")

# 2. Check if node_cache_metadata table exists
print("\n2. Checking if node_cache_metadata table exists...")
cursor.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'CANVAS_CACHE' 
    AND table_name = 'node_cache_metadata'
""")
table_exists = cursor.fetchone()
if table_exists:
    print("   ✓ node_cache_metadata table EXISTS")
else:
    print("   ✗ node_cache_metadata table DOES NOT EXIST")
    print("\n   Creating table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS "CANVAS_CACHE".node_cache_metadata (
            id SERIAL PRIMARY KEY,
            canvas_id INTEGER NOT NULL,
            node_id VARCHAR(100) NOT NULL,
            node_name VARCHAR(255),
            node_type VARCHAR(50) NOT NULL,
            table_name VARCHAR(255) NOT NULL,
            config_hash VARCHAR(64),
            row_count INTEGER DEFAULT 0,
            column_count INTEGER DEFAULT 0,
            columns JSONB,
            source_node_ids JSONB,
            created_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_valid BOOLEAN DEFAULT TRUE,
            UNIQUE(canvas_id, node_id)
        )
    """)
    conn.commit()
    print("   ✓ Table created")

# 3. List all tables in CANVAS_CACHE schema
print("\n3. All tables in CANVAS_CACHE schema:")
cursor.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'CANVAS_CACHE'
    ORDER BY table_name
""")
tables = cursor.fetchall()
if tables:
    for table in tables:
        print(f"   - {table[0]}")
else:
    print("   (no tables found)")

# 4. Check metadata table contents
print("\n4. Contents of node_cache_metadata table:")
cursor.execute("""
    SELECT canvas_id, node_id, node_type, column_count, 
           config_hash, created_on, is_valid
    FROM "CANVAS_CACHE".node_cache_metadata
    ORDER BY created_on DESC
    LIMIT 10
""")
rows = cursor.fetchall()
if rows:
    print(f"   Found {len(rows)} cached nodes:")
    for row in rows:
        canvas_id, node_id, node_type, col_count, config_hash, created_on, is_valid = row
        print(f"   - Canvas {canvas_id}, Node {node_id[:8]}..., Type: {node_type}, "
              f"Cols: {col_count}, Hash: {config_hash}, Valid: {is_valid}")
else:
    print("   ✗ No cached nodes found (table is empty)")

# 5. Show sample metadata if exists
print("\n5. Sample column metadata (if exists):")
cursor.execute("""
    SELECT node_id, columns
    FROM "CANVAS_CACHE".node_cache_metadata
    WHERE columns IS NOT NULL
    LIMIT 1
""")
sample = cursor.fetchone()
if sample:
    node_id, columns_json = sample
    print(f"   Node: {node_id[:8]}...")
    print(f"   Columns metadata:")
    if columns_json:
        columns = json.loads(columns_json) if isinstance(columns_json, str) else columns_json
        for col in columns[:3]:  # Show first 3 columns
            print(f"     - name: {col.get('name')}")
            print(f"       technical_name: {col.get('technical_name')}")
            print(f"       db_name: {col.get('db_name')}")
            print(f"       base: {col.get('base', 'N/A')[:8]}...")
            print()
else:
    print("   (no metadata found)")

cursor.close()
conn.close()

print("\n" + "=" * 80)
print("DONE")
print("=" * 80)
