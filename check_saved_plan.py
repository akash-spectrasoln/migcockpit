
import psycopg2
import json
import os
from dotenv import load_dotenv

load_dotenv()

def check_plan(job_id):
    conn = psycopg2.connect(
        host=os.getenv('DATABASE_HOST', 'localhost'),
        port=os.getenv('DATABASE_PORT', '5433'),
        user=os.getenv('DATABASE_USER', 'postgres'),
        password=os.getenv('DATABASE_PASSWORD', 'SecurePassword123!'),
        dbname='C00008'  # Assuming this from earlier context or common pattern
    )
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT plan_data FROM "CANVAS_CACHE".execution_plans LIMIT 1')
        row = cursor.fetchone()
        if not row:
            print("No plans found in CANVAS_CACHE.execution_plans")
            return

        plan_data = row[0]
        if isinstance(plan_data, str):
            plan_data = json.loads(plan_data)
        
        print(f"Total Levels: {len(plan_data.get('levels', []))}")
        if plan_data.get('levels'):
            level = plan_data.get('levels')[0]
            print(f"\n--- Level {level.get('level_num')} ---")
            if level.get('queries'):
                query = level.get('queries')[0]
                sql = query.get('sql', '')
                print("SQL Query:")
                print(sql)
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    check_plan("72b33140-4df7-4132-ada2-e6922bfb1ed2")
