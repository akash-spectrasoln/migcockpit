# Projection Calculated Columns - Architectural Refactor

## Overview
This refactor implements a complete architectural redesign of calculated column handling in the Projection node, transitioning from a **list-driven** model to an **expression-driven metadata model**.

## Problem Statement
The previous implementation treated calculated columns as physical columns, leading to:
- NULL values in calculated column outputs
- Incorrect SQL generation (column names instead of expressions)
- Schema inference from SQL results instead of metadata
- Calculated columns defaulting to TEXT datatype

## Solution Architecture

### 1. Metadata as Single Source of Truth
**Before:** Schema was built from `selected_columns` + `calculated_columns` lists  
**After:** Schema is built from `output_metadata.columns` with explicit `source` markers

```python
output_metadata_columns = [
    {
        'name': 'table_name',
        'datatype': 'STRING',
        'source': 'base',  # Physical column
        'nullable': True
    },
    {
        'name': 'upper_table_name',
        'datatype': 'STRING',
        'source': 'calculated',  # Virtual column
        'expression': 'UPPER(table_name)',
        'nullable': True
    }
]
```

### 2. Expression-Driven SQL Generation
**Before:**
```sql
SELECT "table_name", "upper_table_name"  -- Treats calculated as physical
FROM source_table
```

**After:**
```sql
SELECT "table_name", UPPER("table_name") AS "upper_table_name"  -- Executes expression
FROM source_table
```

### 3. Unified Processing Pipeline

#### Step 1: Build Output Metadata
```python
# Iterate through selected_columns
for col in selected_columns:
    calc_col = next((cc for cc in valid_calculated_columns if cc['name'] == col), None)
    if calc_col:
        # Add calculated column metadata with expression
        output_metadata_columns.append({
            'name': calc_col['name'],
            'datatype': calc_col.get('dataType', 'STRING'),
            'source': 'calculated',
            'expression': calc_col['expression'],
            'nullable': True
        })
    else:
        # Add base column metadata
        output_metadata_columns.append({
            'name': col,
            'datatype': input_col_meta.get('datatype', 'TEXT'),
            'source': 'base',
            'nullable': True
        })
```

#### Step 2: Generate SQL from Metadata
```python
for col_meta in output_metadata_columns:
    if col_meta.get('source') == 'calculated':
        # Use expression
        expression = col_meta.get('expression')
        normalized = self._normalize_calculated_expression(expression, all_available_columns)
        select_parts.append(f'({normalized}) AS "{col_meta["name"]}"')
    else:
        # Use column name
        select_parts.append(f'"{col_meta["name"]}"')
```

#### Step 3: Build Schema from Metadata
```python
for col_meta in output_metadata_columns:
    projected_columns.append({
        'name': col_meta.get('name'),
        'datatype': col_meta.get('datatype', 'TEXT'),
        'nullable': col_meta.get('nullable', True),
        'source': col_meta.get('source', 'base')
    })
```

#### Step 4: Process Rows from Metadata
```python
for row in rows:
    projected_row = {}
    for col_meta in output_metadata_columns:
        col_name = col_meta.get('name')
        col_value = row.get(col_name)
        projected_row[col_name] = col_value
    projected_rows.append(projected_row)
```

## Key Changes

### File: `api/views.py`

#### 1. SELECT Clause Construction (Lines 10204-10316)
- **Removed:** Separate loops for base columns and calculated columns
- **Added:** Unified loop over `output_metadata_columns`
- **Logic:** Check `source` field to determine SQL generation strategy

#### 2. Payload Construction (Lines 10318-10349)
- **Removed:** `columns` field with column name list
- **Removed:** `calculated_columns` field as separate list
- **Changed:** Always send `select_clause` (expression-driven)

#### 3. Row Processing (Lines 10550-10590)
- **Removed:** Separate loops for base columns and calculated columns
- **Added:** Single loop over `output_metadata_columns`
- **Logic:** Preserve NULL values to maintain schema consistency

#### 4. Schema Construction (Lines 10633-10668)
- **Removed:** `column_metadata_map` building from input node
- **Removed:** Separate loops for base and calculated columns
- **Added:** Direct iteration over `output_metadata_columns`

## Mandatory Rules Compliance

✅ **Calculated columns are NOT physical columns**  
✅ **Calculated columns are expressions**  
✅ **Node cache stores calculated column metadata, NOT values**  
✅ **Execution driven ONLY by node cache metadata**  
✅ **Schema NEVER inferred from SQL result rows**  
✅ **SELECT clause built from metadata expressions**  
✅ **Output schema matches metadata exactly**  
✅ **Calculated columns preserve correct datatypes**  
✅ **No NULL outputs unless input values are NULL**  
✅ **No TODOs, placeholders, or mock logic**

## Testing Instructions

1. **Create Projection Node** with calculated column:
   ```json
   {
     "name": "upper_table_name",
     "expression": "UPPER(table_name)",
     "dataType": "STRING"
   }
   ```

2. **Execute Pipeline** and verify logs show:
   ```
   [SQL] Final SELECT clause: "table_name", (UPPER("table_name")) AS "upper_table_name"
   [Schema] Built output schema with 2 columns from metadata
   [Schema] Calculated columns: ['upper_table_name']
   ```

3. **Verify Output**:
   - Calculated column has non-NULL values
   - Datatype is STRING, not TEXT
   - Values match expected transformation

## Migration Notes

- **Frontend:** No changes required - frontend already sends `calculatedColumns` in config
- **Cache:** Existing cache entries remain valid - metadata is rebuilt on execution
- **Downstream Nodes:** Will receive correct schema with proper datatypes

## Performance Impact

- **Neutral:** Same number of database queries
- **Improved:** Reduced Python-side processing (no column list reconciliation)
- **Improved:** Cleaner code path (single loop instead of multiple)

## Rollback Plan

If issues arise, revert commits in this order:
1. Schema construction refactor
2. Row processing refactor  
3. Payload construction refactor
4. SELECT clause refactor

Each step is independently revertible.
