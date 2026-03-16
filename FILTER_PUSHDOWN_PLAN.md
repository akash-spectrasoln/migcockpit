# Filter Pushdown Implementation Plan

## Problem
Currently, filters are applied AFTER joins, which is inefficient:

```sql
-- CURRENT (INEFFICIENT)
SELECT * FROM (
  SELECT * FROM staging.join_node  -- Join of 1M x 1M rows
) filt
WHERE "_L_cmp_id" = 1  -- Filter reduces to 1K rows
```

This processes 1M x 1M = 1 trillion row combinations, then filters.

## Special Case: Calculated Columns
Filters on calculated columns require **expression substitution** instead of column name pushdown.

### Scenario 1: Simple Expression (CAN PUSH)
```sql
-- Pipeline: Source → Projection (total = qty * price) → Filter (total > 1000)

-- WITHOUT PUSHDOWN (inefficient)
SELECT * FROM (
  SELECT *, quantity * unit_price AS total_price FROM orders
) calc
WHERE total_price > 1000

-- WITH PUSHDOWN (efficient)
SELECT *, quantity * unit_price AS total_price 
FROM orders 
WHERE (quantity * unit_price) > 1000  -- Expression pushed, not column
```

### Scenario 2: Cross-Table Calculation (CANNOT PUSH TO SOURCE)
```sql
-- Pipeline: Join → Projection (profit = revenue - cost) → Filter (profit > 100)

-- CANNOT push to source (uses columns from both tables)
-- CAN push to immediately after JOIN
SELECT * FROM (
  SELECT *, l.revenue - r.cost AS profit
  FROM orders l JOIN products r ON ...
) calc
WHERE (l.revenue - r.cost) > 100  -- Push expression after JOIN
```

### Scenario 3: Aggregate Calculation (CANNOT PUSH - USE HAVING)
```sql
-- Pipeline: Source → Group By (total = SUM(amount)) → Filter (total > 10000)

-- WRONG: Cannot push WHERE on aggregate
SELECT customer_id, SUM(amount) AS total_sales
FROM orders
WHERE SUM(amount) > 10000  -- ❌ INVALID SQL

-- CORRECT: Use HAVING clause
SELECT customer_id, SUM(amount) AS total_sales
FROM orders
GROUP BY customer_id
HAVING SUM(amount) > 10000  -- ✅ CORRECT
```

### Decision Matrix for Calculated Columns

| Calculation Type | Can Push? | Strategy |
|-----------------|-----------|----------|
| Simple expression (col1 + col2) | ✅ Yes | Substitute expression in WHERE |
| Expression after JOIN | ⚠️ Partial | Push to after JOIN, not source |
| Aggregate (SUM, AVG, etc.) | ❌ No | Use HAVING clause |
| Window function (ROW_NUMBER) | ❌ No | Must filter after window |
| Nested calculation | ⚠️ Depends | Analyze dependency chain |

## Desired Behavior
```sql
-- OPTIMIZED (FILTER PUSHDOWN)
SELECT * FROM (
  SELECT * FROM tool_log WHERE "cmp_id" = 1  -- Only 1K rows
) l
INNER JOIN (
  SELECT * FROM tool_connection  -- 1M rows
) r
ON l."connection_id" = r."connection_id"  -- Join 1K x 1M = 1M combinations
```

This processes only 1K x 1M = 1 million combinations.

## Implementation Strategy

### Phase 1: Column Lineage Tracking
Track which columns come from which source tables through transformations.

```python
class ColumnLineage:
    """Tracks column provenance through the pipeline."""
    
    def __init__(self):
        self.lineage = {}  # {node_id: {column_name: source_info}}
    
    def track_source(self, node_id: str, columns: List[str], source_table: str):
        """Track columns from a source node."""
        self.lineage[node_id] = {
            col: {"source_node": node_id, "source_table": source_table, "original_name": col}
            for col in columns
        }
    
    def track_join(self, join_node_id: str, left_node_id: str, right_node_id: str, column_mapping: Dict):
        """Track columns through a JOIN with renaming."""
        self.lineage[join_node_id] = {}
        
        # Track left columns (may be renamed with _L_ prefix)
        for col, info in self.lineage.get(left_node_id, {}).items():
            new_name = column_mapping.get(f"left.{col}", col)
            self.lineage[join_node_id][new_name] = {
                **info,
                "renamed_from": col,
                "join_side": "left"
            }
        
        # Track right columns (may be renamed with _R_ prefix)
        for col, info in self.lineage.get(right_node_id, {}).items():
            new_name = column_mapping.get(f"right.{col}", col)
            self.lineage[join_node_id][new_name] = {
                **info,
                "renamed_from": col,
                "join_side": "right"
            }
    
    def get_source_column(self, node_id: str, column_name: str) -> Optional[Dict]:
        """Get the original source info for a column."""
        return self.lineage.get(node_id, {}).get(column_name)
```

### Phase 2: Filter Analysis
Analyze filter predicates to determine if they can be pushed down.

```python
def analyze_filter_pushdown(filter_node_id: str, filter_conditions: List[Dict], lineage: ColumnLineage, reverse_adj: Dict) -> Dict:
    """
    Determine which filters can be pushed to which upstream nodes.
    
    Returns:
        {
            "pushable": {
                "source_node_1": [condition1, condition2],
                "source_node_2": [condition3]
            },
            "non_pushable": [condition4]  # Must stay at filter node
        }
    """
    pushable = defaultdict(list)
    non_pushable = []
    
    for cond in filter_conditions:
        column = cond.get("column")
        
        # Get column lineage
        source_info = lineage.get_source_column(filter_node_id, column)
        
        if source_info and source_info.get("source_node"):
            # Can push down - rewrite condition with original column name
            source_node = source_info["source_node"]
            original_col = source_info["original_name"]
            
            pushable[source_node].append({
                **cond,
                "column": original_col  # Use original column name
            })
        else:
            # Cannot push down (computed column, aggregate, etc.)
            non_pushable.append(cond)
    
    return {"pushable": dict(pushable), "non_pushable": non_pushable}
```

### Phase 3: SQL Rewriting
Modify SQL compilation to inject pushed-down filters.

```python
def compile_nested_sql_with_pushdown(
    node_id: str,
    nodes: Dict[str, Any],
    edges: List[Dict[str, Any]],
    materialization_points: Dict[str, Any],
    config: Dict[str, Any],
    pushed_filters: Optional[Dict[str, List[Dict]]] = None  # {node_id: [conditions]}
) -> CompiledSQL:
    """
    Compile nested SQL with filter pushdown support.
    
    Args:
        pushed_filters: Filters to inject at specific nodes
    """
    # ... existing logic ...
    
    # When compiling a source node:
    if node_type == "source":
        base_sql = _compile_source_node(node, nodes, edges, config)
        
        # Inject pushed-down filters
        if pushed_filters and node_id in pushed_filters:
            conditions = pushed_filters[node_id]
            where_clause = _build_where_clause(conditions)
            base_sql = f"SELECT * FROM ({base_sql}) src WHERE {where_clause}"
        
        return base_sql
```

### Phase 4: Integration with Planner
Update the execution plan builder to perform filter pushdown analysis.

```python
def build_execution_plan_with_pushdown(...):
    # 1. Build column lineage
    lineage = ColumnLineage()
    for node in topological_order:
        if node_type == "source":
            lineage.track_source(node_id, columns, source_table)
        elif node_type == "join":
            lineage.track_join(node_id, left_id, right_id, column_mapping)
        # ... other transformations ...
    
    # 2. Analyze filters for pushdown
    pushed_filters = {}
    for node in nodes:
        if node_type == "filter":
            analysis = analyze_filter_pushdown(node_id, conditions, lineage, reverse_adj)
            pushed_filters.update(analysis["pushable"])
            # Keep non-pushable filters at the filter node
    
    # 3. Compile SQL with pushed filters
    for level in execution_levels:
        for node_id in level:
            sql = compile_nested_sql_with_pushdown(
                node_id, nodes, edges, materialization_points, config,
                pushed_filters=pushed_filters
            )
```

## Example Transformation

### Input Pipeline
```
Source(tool_log) → Join(tool_connection) → Filter(cmp_id = 1) → Destination
```

### Without Pushdown
```sql
-- Level 1: Source nodes
CREATE TABLE staging.node_source_1 AS SELECT * FROM tool_log;
CREATE TABLE staging.node_source_2 AS SELECT * FROM tool_connection;

-- Level 2: Join
CREATE TABLE staging.node_join AS
SELECT l.*, r.* FROM staging.node_source_1 l
INNER JOIN staging.node_source_2 r ON l.connection_id = r.connection_id;

-- Level 3: Filter
CREATE TABLE staging.node_filter AS
SELECT * FROM staging.node_join WHERE "_L_cmp_id" = 1;
```

### With Pushdown
```sql
-- Level 1: Source nodes WITH PUSHED FILTER
CREATE TABLE staging.node_source_1 AS 
SELECT * FROM tool_log WHERE "cmp_id" = 1;  -- ← FILTER PUSHED HERE

CREATE TABLE staging.node_source_2 AS 
SELECT * FROM tool_connection;

-- Level 2: Join (now operates on filtered data)
CREATE TABLE staging.node_join AS
SELECT l.*, r.* FROM staging.node_source_1 l
INNER JOIN staging.node_source_2 r ON l.connection_id = r.connection_id;

-- Level 3: Filter node becomes a no-op (all filters pushed down)
-- Can be eliminated entirely
```

## Complexity Estimate
- **Column Lineage Tracking**: Medium (2-3 days)
- **Filter Analysis**: Medium (2-3 days)
- **SQL Rewriting**: High (3-5 days)
- **Testing & Edge Cases**: High (3-5 days)

**Total**: ~2 weeks of focused development

## Edge Cases to Handle
1. **Computed columns**: Cannot push filters on calculated fields
2. **Aggregates**: Cannot push filters through GROUP BY
3. **Window functions**: Cannot push filters through OVER clauses
4. **Multiple filters**: Must merge conditions with AND
5. **OR conditions**: May prevent pushdown
6. **Subquery correlation**: Complex dependencies

## Recommendation
Implement in phases:
1. ✅ **Phase 0** (Current): Document the issue
2. **Phase 1**: Implement column lineage tracking
3. **Phase 2**: Add simple filter pushdown (single-table filters only)
4. **Phase 3**: Handle JOIN column renaming
5. **Phase 4**: Optimize complex cases

This is a **significant optimization** but requires careful implementation to avoid breaking existing functionality.
