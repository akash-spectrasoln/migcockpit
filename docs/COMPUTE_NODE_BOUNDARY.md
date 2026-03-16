# Compute Node Execution Boundary Implementation

## Core Rule

**Compute nodes are HARD execution boundaries that do NOT participate in SQL compilation.**

## Implementation Summary

### 1. SQL Compiler Behavior (`api/utils/sql_compiler.py`)

- **Stops at Compute Boundaries**: SQL compilation automatically stops before any compute node
- **No Compute in SQL**: Compute nodes never appear in SQL CTEs or subqueries
- **Helper Function**: `find_sql_compilable_nodes()` finds all SQL-compilable nodes, stopping at compute boundaries

**Key Changes:**
- Added `find_sql_compilable_nodes()` function in `graph_utils.py`
- Updated `SQLCompiler.compile()` to use `find_sql_compilable_nodes()` instead of `find_upstream_nodes()`
- SQL compilation stops before compute nodes and raises error if target is compute

### 2. Execution Flow

#### Preview Mode (Compute Node as Target)

1. **Detect Compute Target**: Check if target node is compute
2. **Find Input Node**: Get the node immediately before compute
3. **Compile SQL Upstream**: Compile SQL only up to input node (stops at compute boundary)
4. **Execute SQL**: Run SQL query to get DataFrame
5. **Execute Compute**: Pass DataFrame as `_input_df`, execute Python code
6. **Return Output**: Return `_output_df` as preview result

#### Preview Mode (Non-Compute Target)

1. **Compile SQL**: Use `find_sql_compilable_nodes()` to find SQL-compilable nodes
2. **Stop at Boundaries**: Automatically stops before any compute nodes in upstream chain
3. **Execute SQL**: Run compiled SQL query
4. **Return Results**: Return SQL query results

### 3. Compute Node Contract

**Input Variables:**
- `_input_df` - Primary input DataFrame (read-only)
- `input_df` - Alias for convenience
- `df` - Common alias
- `pd` / `pandas` - Pandas library
- `np` / `numpy` - NumPy library (if available)

**Output Variables:**
- `_output_df` - Primary output DataFrame (required)
- `output_df` - Alias for convenience

**Default Code:**
```python
_output_df = _input_df
```

### 4. Metadata Flow

- Compute nodes emit `output_metadata` from their `_output_df`
- Downstream nodes rely on compute metadata, not DB introspection
- Types are preserved unless explicitly changed by compute logic

### 5. Prohibited Behavior

✅ **Enforced:**
- Compute nodes cannot be compiled to SQL
- SQL compilation stops before compute nodes
- Compute nodes never appear in CTEs

❌ **Prevented:**
- No dummy SQL generation for compute nodes
- No AST → SQL translation attempts
- No mixing SQL and Python in same node

## Code Locations

### SQL Compiler
- **File**: `api/utils/sql_compiler.py`
- **Function**: `compile()` (lines ~51-155)
- **Behavior**: Stops at compute boundaries using `find_sql_compilable_nodes()`

### Graph Utilities
- **File**: `api/utils/graph_utils.py`
- **Function**: `find_sql_compilable_nodes()` (lines ~176-250)
- **Behavior**: DFS traversal that stops at compute nodes

### Pipeline Execution
- **File**: `api/views/pipeline.py`
- **Section**: Preview mode compute handling (lines ~1335-1655)
- **Behavior**: Executes SQL up to compute, then executes compute Python code

## Example Pipeline Flows

### Flow 1: Source → Filter → Compute
```
1. Compile SQL: Source + Filter
2. Execute SQL → DataFrame
3. Execute Compute: DataFrame → _output_df
4. Return: _output_df
```

### Flow 2: Source → Compute → Projection (Future)
```
1. Compile SQL: Source (stops before Compute)
2. Execute SQL → DataFrame
3. Execute Compute: DataFrame → _output_df
4. [Future] Continue SQL compilation using compute metadata
5. [Future] Execute Projection on compute output
```

## Testing

### Test Case 1: Compute Node Preview
- **Setup**: Source → Filter → Compute
- **Expected**: SQL compiles Source+Filter, Compute executes Python
- **Verify**: No compute node in SQL, Python code executes correctly

### Test Case 2: Compute Node in Middle
- **Setup**: Source → Compute → Projection
- **Expected**: SQL compiles Source only, stops at Compute
- **Verify**: Compute boundary detected, SQL stops correctly

### Test Case 3: Multiple Compute Nodes
- **Setup**: Source → Compute1 → Filter → Compute2
- **Expected**: SQL compiles Source, stops at Compute1
- **Verify**: First compute boundary stops SQL compilation

## Future Enhancements

1. **Downstream SQL Compilation**: Support SQL compilation after compute nodes using compute output metadata
2. **Compute Output Metadata**: Use compute `output_metadata` for downstream node column resolution
3. **Hybrid Execution**: Execute compute, then continue SQL compilation for downstream nodes

## Notes

- Compute nodes preserve all whitespace (no trimming)
- Compute nodes support syntax highlighting in frontend
- Compute nodes have save button in editor
- Error handling provides helpful tips for DataFrame boolean checks
