# SQL Compilation Test Suite

Comprehensive test suite for the SQL compilation system used in preview mode.

## Overview

This test suite covers:

1. **Expression Translation** (`test_sql_compiler.py::TestExpressionTranslator`)
   - Python-style expression to SQL translation
   - Function calls (UPPER, LOWER, CONCAT, etc.)
   - Arithmetic operators
   - Column reference validation

2. **Graph Utilities** (`test_sql_compiler.py::TestGraphUtils`)
   - DAG traversal and topological sorting
   - Cycle detection
   - Upstream node discovery
   - Source node identification

3. **SQL Compiler** (`test_sql_compiler.py::TestSQLCompiler`)
   - Source node CTE generation
   - Filter node CTE generation
   - Join node CTE generation
   - Projection node CTE generation (with calculated columns)
   - Aggregate node CTE generation
   - Complex pipeline compilation
   - LIMIT clause placement (only in final SELECT)

4. **Integration Tests** (`test_sql_compiler_integration.py`)
   - End-to-end pipeline compilation
   - Metadata flow between nodes
   - Preview query execution
   - Error handling

## Running Tests

### Prerequisites

```bash
pip install pytest pytest-django pytest-mock
```

### Run All Tests

```bash
# From project root
pytest tests/

# With verbose output
pytest tests/ -v

# With coverage (if pytest-cov installed)
pytest tests/ --cov=api --cov-report=html
```

### Run Specific Test Files

```bash
# Unit tests only
pytest tests/test_sql_compiler.py

# Integration tests only
pytest tests/test_sql_compiler_integration.py

# Specific test class
pytest tests/test_sql_compiler.py::TestExpressionTranslator

# Specific test method
pytest tests/test_sql_compiler.py::TestExpressionTranslator::test_upper_function
```

### Run Tests by Marker

```bash
# Unit tests (fast, no external dependencies)
pytest -m unit

# Integration tests
pytest -m integration
```

## Test Structure

```
tests/
├── conftest.py                          # Shared fixtures
├── test_sql_compiler.py                  # Unit tests
│   ├── TestExpressionTranslator         # Expression translation tests
│   ├── TestGraphUtils                   # Graph utility tests
│   └── TestSQLCompiler                  # SQL compiler tests
├── test_sql_compiler_integration.py     # Integration tests
│   ├── TestSQLCompilerIntegration       # End-to-end tests
│   ├── TestPreviewModeIntegration       # Preview execution tests
│   └── TestErrorHandling                # Error handling tests
└── README.md                            # This file
```

## Key Test Scenarios

### 1. Expression Translation

Tests verify that Python-style expressions are correctly translated to SQL:

- `UPPER(name)` → `UPPER("name")`
- `CONCAT(first, last)` → `CONCAT("first", "last")`
- `a + b` → `"a" + "b"`
- Column reference validation

### 2. DAG Validation

Tests ensure pipeline graphs are valid DAGs:

- Valid linear chains (source → filter → projection)
- Valid joins (two sources → join)
- Cycle detection
- Topological ordering

### 3. SQL Compilation

Tests verify correct SQL generation for each node type:

- **Source**: `SELECT * FROM "schema"."table"`
- **Filter**: `SELECT * FROM cte WHERE conditions`
- **Join**: `SELECT columns FROM left_cte JOIN right_cte ON conditions`
- **Projection**: `SELECT selected_columns, calculated_expressions FROM cte`
- **Aggregate**: `SELECT aggregates FROM cte GROUP BY columns`

### 4. LIMIT Placement

Critical test: LIMIT must only appear in the final SELECT, not in CTEs:

```sql
WITH node_source1 AS (SELECT * FROM users),
     node_filter1 AS (SELECT * FROM node_source1 WHERE age > 18)
SELECT id, name FROM node_filter1 LIMIT 50
```

### 5. Metadata Flow

Tests verify that column metadata flows correctly through the pipeline:

- Source metadata → Filter metadata (unchanged)
- Join metadata combines left + right columns
- Projection metadata includes calculated columns
- Output metadata matches final SELECT columns

## Mocking Strategy

Tests use extensive mocking to avoid requiring actual database connections:

- **Database connections**: Mocked using `unittest.mock.patch`
- **Source config retrieval**: Mocked `decrypt_source_data`
- **Table metadata**: Mocked `_get_table_metadata`
- **Query execution**: Mocked in integration tests

## Adding New Tests

When adding new functionality:

1. **Add unit tests** in `test_sql_compiler.py` for isolated functionality
2. **Add integration tests** in `test_sql_compiler_integration.py` for end-to-end scenarios
3. **Update fixtures** in `conftest.py` if new test data is needed
4. **Document** new test scenarios in this README

### Example Test Template

```python
def test_new_feature(self, mock_customer):
    """Test description."""
    nodes = [
        {
            'id': 'node1',
            'data': {
                'type': 'source',
                'config': {'sourceId': 1, 'tableName': 'test'}
            }
        }
    ]
    edges = []
    
    compiler = SQLCompiler(nodes, edges, 'node1', mock_customer, 'postgresql')
    
    with patch.object(compiler, '_build_source_cte', return_value=(...)):
        sql_query, params, metadata = compiler.compile()
        
        # Assertions
        assert 'expected_sql_pattern' in sql_query
```

## Continuous Integration

These tests should be run:

- Before committing code changes
- In CI/CD pipeline
- Before deploying to staging/production

## Troubleshooting

### Import Errors

If you see import errors:

```bash
# Ensure you're in the project root
cd /path/to/migcockpit-qoder/migcockpit/datamigration-migcockpit

# Install dependencies
pip install -r requirements.txt

# Run tests with Python path
PYTHONPATH=. pytest tests/
```

### Database Connection Errors

Most tests mock database connections. If you see connection errors:

1. Check that mocks are properly set up
2. Verify `@patch` decorators are correct
3. Ensure `conftest.py` fixtures are loaded

### Test Failures

If tests fail:

1. Check test output for specific error messages
2. Verify mock return values match expected structure
3. Ensure SQL query patterns match actual implementation
4. Check that metadata structures match expected format

## Coverage Goals

- **Unit tests**: 90%+ coverage for `sql_compiler.py`, `expression_translator.py`, `graph_utils.py`
- **Integration tests**: Cover all major pipeline combinations
- **Error handling**: Test all error paths

## Related Documentation

- `docs/CALCULATED_COLUMNS_ARCHITECTURE.md` - Calculated columns architecture
- `api/utils/sql_compiler.py` - SQL compiler implementation
- `api/utils/expression_translator.py` - Expression translator implementation
- `api/utils/graph_utils.py` - Graph utilities implementation
