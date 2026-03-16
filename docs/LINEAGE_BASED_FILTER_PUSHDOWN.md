# Lineage-Based Filter Pushdown Optimization

## Core Principle

**Filter pushdown is decided by column lineage, NOT by node type.**

Compute and Aggregate nodes are not blockers by themselves. They block pushdown only for columns they create.

## Column Lineage Tracking

For every column, we track:
- `origin_node_id`: Node where column was created
- `origin_type`: `SOURCE`, `JOIN`, `PROJECTION`, `COMPUTE`, `AGGREGATE`
- `expression`: Expression if calculated (None for base columns)

### Lineage Rules

1. **SOURCE columns**: Tracked when source CTE is built
2. **JOIN columns**: Inherit lineage from input tables (marked as JOIN if new)
3. **PROJECTION columns**: 
   - Base columns: Keep existing lineage
   - Calculated columns: Tracked with expression
4. **AGGREGATE columns**: Tracked with aggregation expression
5. **COMPUTE columns**: Tracked in execution phase (not SQL compilation)

## Filter Pushdown Rules

### Step 1: Identify Column Origin

For each filter condition, determine where the column was created using `_get_column_origin()`.

### Step 2: Decide Pushdown Eligibility

| Column Origin | Pushdown Allowed? | Reason |
|--------------|-------------------|--------|
| SOURCE / JOIN / PROJECTION | ✅ YES | Column exists upstream |
| COMPUTE | ❌ NO | Column created in Compute, doesn't exist upstream |
| AGGREGATE | ❌ NO | Column created in Aggregate, doesn't exist upstream |

**Key Point**: Node type alone is NOT a blocker. A Compute node doesn't block pushdown for columns it doesn't create.

### Step 3: Find Earliest Valid Pushdown Position

- Push filter to the earliest source node upstream from column origin
- Never push past column creation point
- Never push past Compute/Aggregate if column is created there

### Step 4: Apply Pushdown Decision

**CRITICAL RULE**: All columns in filter must be pushdown-safe. If ANY column is unsafe, entire filter stays local.

**NO PARTIAL PUSHDOWN** - prevents inconsistent previews.

## Implementation Flow

### Three-Pass Compilation

1. **First Pass**: Build all CTEs to establish column lineage
   - Track column origins as CTEs are built
   - Build filters locally (no pushdown analysis yet)

2. **Second Pass**: Analyze filter pushdown
   - For each filter, check column origins
   - Determine if filter can be pushed down
   - Mark filters for pushdown if all columns are safe

3. **Third Pass**: Rebuild CTEs with pushed-down filters
   - Rebuild source CTEs to include pushed-down filters in WHERE clause
   - Rebuild downstream CTEs that depend on sources with pushed-down filters
   - Skip building separate CTEs for pushed-down filters

## Examples

### Example 1: Pushdown Allowed

```
Source(id, status)
  ↓
Compute(score = id * 2)
  ↓
Filter(status = 'ACTIVE')
```

- `status` originates from Source ✅
- Compute does not modify `status` ✅
- **Result**: Push filter to Source SQL

### Example 2: Pushdown Blocked

```
Source(marks)
  ↓
Compute(score = marks * 2)
  ↓
Filter(score > 80)
```

- `score` created in Compute ❌
- **Result**: Filter must execute after Compute

### Example 3: Mixed Conditions (No Pushdown)

```
Filter:
  status = 'ACTIVE' AND score > 80
```

- `status` → pushdown-safe ✅
- `score` → not pushdown-safe ❌
- **Result**: Entire filter executes locally (no partial pushdown)

### Example 4: Pre-Aggregate Filter (Required Pushdown)

```
Source(amount)
  ↓
Aggregate(sum_amount = SUM(amount))
  ↓
Filter(amount > 100)
```

- `amount` exists upstream ✅
- Filter must apply before aggregation ✅
- **Result**: Push filter before Aggregate

SQL:
```sql
SELECT SUM(amount)
FROM source
WHERE amount > 100
```

### Example 5: Post-Aggregate Filter (No Pushdown)

```
Source(amount)
  ↓
Aggregate(sum_amount = SUM(amount))
  ↓
Filter(sum_amount > 1000)
```

- `sum_amount` created in Aggregate ❌
- **Result**: Apply filter after Aggregate (HAVING-style)

## Code Structure

### Key Functions

1. `_track_column_lineage()`: Track column origin
2. `_get_column_origin()`: Get column origin information
3. `_can_pushdown_filter_column()`: Check if column can be pushed down
4. `_analyze_filter_pushdown()`: Analyze entire filter for pushdown eligibility
5. `_find_earliest_source_node()`: Find earliest source node upstream
6. `_is_downstream()`: Check if node is downstream of another

### Key Data Structures

- `column_lineage`: Dict mapping column names to origin info
- `pushed_down_filters`: Set of filter node IDs that were pushed down
- `filter_pushdown_info`: Dict mapping filter node IDs to pushdown info

## Benefits

✅ Correct preview results based on column existence
✅ No false blocking by Compute/Aggregate nodes
✅ Predictable behavior (lineage-based, not heuristic)
✅ Minimal DB usage (pushdown when safe)
✅ Scales with pipeline size

## Limitations

- Only pushes filters when ALL columns are pushdown-safe
- Requires complete column lineage tracking
- May require rebuilding CTEs when filters are pushed down

## Future Enhancements

1. **Multi-level pushdown**: Push filters through projections without calculated columns
2. **Join filter pushdown**: Push filters to individual tables before join
3. **Aggregate filter pushdown**: Distinguish between pre-aggregate (WHERE) and post-aggregate (HAVING) filters
