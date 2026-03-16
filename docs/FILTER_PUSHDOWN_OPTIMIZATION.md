# Filter Pushdown Optimization

## Overview

Filter pushdown optimization pushes filter conditions directly into source queries at the database level, reducing data transfer and improving query performance.

## Implementation

### Core Concept

Instead of:
```sql
WITH source AS (SELECT * FROM table),
     filter AS (SELECT * FROM source WHERE column > 100)
SELECT * FROM filter
```

We generate:
```sql
WITH source AS (SELECT * FROM table WHERE column > 100)
SELECT * FROM source
```

### Rules for Pushdown

Filters can be pushed down to a source if:
1. ✅ Filter directly follows source (no intermediate transformations)
2. ✅ Filter only references source columns (no calculated columns from projections)
3. ✅ No joins, aggregates, or compute nodes between source and filter
4. ✅ Projection nodes without calculated columns are allowed

Filters CANNOT be pushed down if:
- ❌ Join node exists between source and filter
- ❌ Aggregate node exists between source and filter
- ❌ Compute node exists between source and filter
- ❌ Projection with calculated columns exists between source and filter

### Code Implementation

**File**: `api/utils/sql_compiler.py`

**Key Functions:**
1. `_find_pushable_filters(source_node_id)` - Identifies filters that can be pushed down
2. `_build_source_cte(node)` - Includes pushed-down filters in source WHERE clause
3. `_build_filter_cte(node)` - Skips filters that were pushed down

**Process:**
1. Identify SQL-compilable nodes (stops at compute boundaries)
2. For each source node, find pushable filters downstream
3. Mark pushable filters in `pushed_down_filters` set
4. Build source CTE with WHERE clause from pushed-down filters
5. Skip building separate CTE for pushed-down filters

## Benefits

- ✅ Reduced data transfer from database
- ✅ Better query performance (database can use indexes)
- ✅ Simpler SQL queries (fewer CTEs)
- ✅ Lower memory usage

## Example

### Before Optimization
```sql
WITH node_source AS (
    SELECT * FROM "public"."users"
),
node_filter AS (
    SELECT * FROM node_source WHERE "age" > 18
)
SELECT * FROM node_filter LIMIT 50
```

### After Optimization
```sql
WITH node_source AS (
    SELECT * FROM "public"."users" WHERE "age" > 18
)
SELECT * FROM node_source LIMIT 50
```

## Limitations

- Only applies to filters directly following sources
- Cannot push filters past joins, aggregates, or compute nodes
- Cannot push filters past projections with calculated columns
- Multiple filters on same source are combined with AND logic

## Future Enhancements

1. **Multi-level pushdown**: Push filters through projections without calculated columns
2. **Join filter pushdown**: Push filters to individual tables before join
3. **Aggregate filter pushdown**: Push filters before aggregation (HAVING vs WHERE)
