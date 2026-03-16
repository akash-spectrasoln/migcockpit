
import os
import django
import json
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datamigrationapi.settings')
django.setup()

from api.models import Customer
from api.utils.sql_compiler import SQLCompiler

def test_compile():
    customer = Customer.objects.first()
    if not customer:
        print("No customer found")
        return

    # Mock nodes and edges
    nodes = [
        {
            'id': 'node_1',
            'data': {
                'type': 'source',
                'config': {
                    'sourceId': 1,
                    'tableName': 'users',
                    'schema': 'public'
                }
            }
        },
        {
            'id': 'node_2',
            'data': {
                'type': 'filter',
                'config': {
                    'conditions': [
                        {'column': 'id', 'operator': '>', 'value': 0}
                    ]
                }
            }
        }
    ]
    edges = [
        {'id': 'e1-2', 'source': 'node_1', 'target': 'node_2'}
    ]

    try:
        compiler = SQLCompiler(nodes, edges, 'node_2', customer, 'postgresql')
        sql, params, metadata = compiler.compile()
        print("SQL Compiled Successfully:")
        print(sql)
        print("Params:", params)
    except Exception as e:
        print("Error during compilation:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_compile()
