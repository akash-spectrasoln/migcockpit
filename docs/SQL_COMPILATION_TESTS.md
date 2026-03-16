# SQL Compilation Test Suite Documentation

## Overview

A comprehensive test suite has been created for the SQL compilation system used in preview mode. This test suite ensures that the single-query compilation architecture works correctly across all node types and pipeline combinations.

## Test Files Created

### 1. `tests/test_sql_compiler.py` (657 lines)

**Unit tests** covering:

- **TestExpressionTranslator** (11 tests)
  - Simple column references
  - Function translations (UPPER, LOWER, CONCAT, SUBSTRING)
  - Nested functions
  - Arithmetic operators
  - String concatenation
  - Numeric and string literals
  - Column reference validation
  - Complex expressions

- **TestGraphUtils** (8 tests)
  - Finding upstream nodes in simple chains
  - Finding upstream nodes for joins
  - Topological sorting
  - Cycle detection
  - DAG validation (valid and invalid)
  - Getting node dependencies
  - Finding source nodes

- **TestSQLCompiler** (12 tests)
  - Building source CTEs
  - Building filter CTEs
  - Building join CTEs
  - Building projection CTEs
  - Building projection CTEs with calculated columns
  - Building aggregate CTEs
  - Compiling complex pipelines
  - Error handling (missing nodes, invalid types)
  - LIMIT clause placement verification

### 2. `tests/test_sql_compiler_integration.py` (400+ lines)

**Integration tests** covering:

- **TestSQLCompilerIntegration** (4 tests)
  - End-to-end source → filter → projection pipeline
  - Join with projection metadata flow
  - Calculated columns in projection
  - Filter conditions preservation

- **TestPreviewModeIntegration** (2 tests)
  - PostgreSQL preview query execution
  - Unsupported database type handling

- **TestErrorHandling** (3 tests)
  - Missing source config
  - Missing input nodes
  - Invalid node types

### 3. `tests/conftest.py` (150+ lines)

**Shared fixtures** for:

- Mock customer objects
- Mock source configurations (PostgreSQL, SQL Server)
- Sample node configurations (simple, with filter, with join)
- Sample edge configurations
- Sample table metadata

### 4. `pytest.ini`

**Pytest configuration** with:

- Test discovery patterns
- Output options
- Markers (unit, integration, slow, db)
- Logging configuration
- Django settings

### 5. `tests/README.md`

**Comprehensive documentation** including:

- Test overview and structure
- Running instructions
- Test scenarios
- Mocking strategy
- Adding new tests guide
- Troubleshooting

## Test Coverage

### Expression Translation

✅ All major functions (UPPER, LOWER, CONCAT, SUBSTRING, etc.)  
✅ Arithmetic operators (+, -, *, /)  
✅ String concatenation (||)  
✅ Nested function calls  
✅ Column reference validation  
✅ Literal handling (numbers, strings, booleans)

### Graph Utilities

✅ Upstream node discovery  
✅ Topological sorting  
✅ Cycle detection  
✅ DAG validation  
✅ Dependency resolution  
✅ Source node identification

### SQL Compilation

✅ Source node CTE generation  
✅ Filter node CTE generation  
✅ Join node CTE generation (INNER, LEFT, RIGHT, FULL)  
✅ Projection node CTE generation  
✅ Projection with calculated columns  
✅ Aggregate node CTE generation  
✅ Complex multi-node pipelines  
✅ LIMIT clause placement (only in final SELECT)  
✅ Metadata propagation through pipeline

### Error Handling

✅ Missing source configurations  
✅ Missing input nodes  
✅ Invalid node types  
✅ Unsupported database types  
✅ Invalid DAGs (cycles)

## Key Test Scenarios

### 1. Simple Pipeline

```
Source → Filter → Projection
```

Tests verify:
- CTEs are generated in correct order
- Filter conditions are applied
- Projection selects correct columns
- LIMIT appears only in final SELECT

### 2. Join Pipeline

```
Source1 ──┐
          ├──→ Join → Projection
Source2 ──┘
```

Tests verify:
- Both sources are included in upstream nodes
- Join conditions are correctly formatted
- Output columns from join flow to projection
- Column aliases are handled correctly

### 3. Calculated Columns

```
Source → Projection (with calculated columns)
```

Tests verify:
- Calculated columns are translated to SQL expressions
- Base columns are selected separately
- Metadata includes calculated columns with correct source type
- Expressions reference available columns correctly

### 4. Complex Pipeline

```
Source1 ──┐
          ├──→ Join → Filter → Projection
Source2 ──┘
```

Tests verify:
- All nodes are compiled in correct order
- Metadata flows correctly through all nodes
- Final SQL query structure is correct

## Running Tests

### Prerequisites

```bash
pip install pytest pytest-django pytest-mock
```

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/test_sql_compiler.py

# Integration tests only
pytest tests/test_sql_compiler_integration.py

# Expression translator tests
pytest tests/test_sql_compiler.py::TestExpressionTranslator

# Graph utils tests
pytest tests/test_sql_compiler.py::TestGraphUtils

# SQL compiler tests
pytest tests/test_sql_compiler.py::TestSQLCompiler
```

### With Coverage

```bash
pytest tests/ --cov=api.utils.sql_compiler --cov=api.utils.expression_translator --cov=api.utils.graph_utils --cov-report=html
```

## Mocking Strategy

Tests use extensive mocking to avoid requiring actual database connections:

1. **Database Connections**: Mocked using `unittest.mock.patch`
2. **Source Config Retrieval**: Mocked `decrypt_source_data` function
3. **Table Metadata**: Mocked `_get_table_metadata` method
4. **Query Execution**: Mocked in integration tests

This allows tests to:
- Run quickly without database setup
- Test logic without external dependencies
- Verify SQL generation without executing queries
- Test error conditions safely

## Critical Test: LIMIT Placement

One of the most important tests verifies that `LIMIT` appears **only** in the final SELECT statement, not in any CTEs:

```python
def test_limit_only_in_final_query(self, mock_customer):
    """Test that LIMIT is only added to final SELECT, not CTEs."""
    # ... setup ...
    sql_query, params, metadata = compiler.compile()
    
    # Count LIMIT occurrences - should only be in final SELECT
    limit_count = sql_query.upper().count('LIMIT')
    assert limit_count == 1
```

This ensures that:
- CTEs don't limit intermediate results (which would break joins/aggregates)
- Only the final result set is limited
- Pagination works correctly

## Integration with CI/CD

These tests should be integrated into your CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
- name: Run SQL Compilation Tests
  run: |
    pip install pytest pytest-django pytest-mock
    pytest tests/test_sql_compiler.py tests/test_sql_compiler_integration.py -v
```

## Future Enhancements

Potential additions to the test suite:

1. **Performance Tests**: Measure compilation time for large pipelines
2. **SQL Validation**: Verify generated SQL is syntactically correct (using SQL parser)
3. **Database-Specific Tests**: Test SQL generation differences for MySQL, SQL Server, Oracle
4. **Edge Cases**: 
   - Empty pipelines
   - Single-node pipelines
   - Very deep pipelines (10+ nodes)
   - Multiple joins in sequence
5. **Regression Tests**: Capture known-good SQL outputs and verify they don't change

## Related Files

- `api/utils/sql_compiler.py` - SQL compiler implementation
- `api/utils/expression_translator.py` - Expression translator implementation
- `api/utils/graph_utils.py` - Graph utilities implementation
- `api/utils/db_executor.py` - Database query executor
- `api/views/pipeline.py` - Pipeline execution view (uses SQL compiler in preview mode)

## Maintenance

When modifying SQL compilation logic:

1. **Run tests first**: `pytest tests/test_sql_compiler.py -v`
2. **Update tests** if behavior changes intentionally
3. **Add new tests** for new features or edge cases
4. **Verify coverage** remains high (>90%)
5. **Document** any breaking changes in test behavior

## Summary

The test suite provides comprehensive coverage of the SQL compilation system, ensuring:

✅ Correct SQL generation for all node types  
✅ Proper metadata flow through pipelines  
✅ Error handling for invalid configurations  
✅ LIMIT clause placement correctness  
✅ Expression translation accuracy  
✅ DAG validation and traversal  

This test suite is essential for maintaining the reliability and correctness of the preview mode SQL compilation feature.
