# SQL Compilation Visual Guide: Multiple Nodes

## Simple Example: 3 Nodes

### Pipeline Structure

```
┌──────────┐
│  Source  │  (users table)
└────┬─────┘
     │
     │ Edge: source → filter
     │
┌────▼─────┐
│  Filter  │  (age > 18)
└────┬─────┘
     │
     │ Edge: filter → projection
     │
┌────▼─────────┐
│  Projection  │  (select: id, name)
└──────────────┘
```

### Compilation Process

#### Step 1: Find Upstream Nodes

```
Target: projection
Upstream: [source, filter, projection]
```

#### Step 2: Build CTEs

```
CTE 1: node_source
┌─────────────────────────────┐
│ SELECT * FROM "users"       │
└─────────────────────────────┘
         │
         │ Referenced by
         ▼
CTE 2: node_filter
┌─────────────────────────────┐
│ SELECT *                    │
│ FROM node_source             │
│ WHERE "age" > %s            │
└─────────────────────────────┘
         │
         │ Referenced by
         ▼
CTE 3: node_projection
┌─────────────────────────────┐
│ SELECT "id", "name"         │
│ FROM node_filter            │
└─────────────────────────────┘
```

#### Step 3: Final Query

```sql
WITH 
    node_source AS (
        SELECT * FROM "users"
    ),
    node_filter AS (
        SELECT * FROM node_source WHERE "age" > %s
    ),
    node_projection AS (
        SELECT "id", "name" FROM node_filter
    )
SELECT "id", "name" 
FROM node_projection 
LIMIT %s
```

---

## Complex Example: Join Pipeline

### Pipeline Structure

```
┌──────────┐
│ Source1  │  (users)
└────┬─────┘
     │
     │ Left input
     │
┌────▼─────┐      ┌──────────┐
│   Join   │◄─────│ Source2  │  (orders)
└────┬─────┘      └──────────┘
     │ Right input
     │
┌────▼─────┐
│Projection│
└──────────┘
```

### Compilation Process

#### Step 1: Upstream Discovery

```
Target: projection
Upstream: [source1, source2, join, projection]
```

**Note:** Both sources must be built before the join!

#### Step 2: CTE Building Order

```
┌─────────────────┐
│ CTE: node_source1│  ← Built first (no dependencies)
└─────────────────┘
         │
         │
┌─────────────────┐
│ CTE: node_source2│  ← Built second (no dependencies)
└─────────────────┘
         │
         │ Both referenced by
         ▼
┌─────────────────────────────────────────────┐
│ CTE: node_join                              │
│ SELECT ...                                  │
│ FROM node_source1 AS __L__                  │
│ INNER JOIN node_source2 AS __R__           │
│ ON __L__."id" = __R__."user_id"            │
└─────────────────────────────────────────────┘
         │
         │ Referenced by
         ▼
┌─────────────────────────────────────────────┐
│ CTE: node_projection                       │
│ SELECT "user_id", "order_id"               │
│ FROM node_join                             │
└─────────────────────────────────────────────┘
```

#### Step 3: Final SQL

```sql
WITH 
    node_source1 AS (
        SELECT * FROM "users"
    ),
    node_source2 AS (
        SELECT * FROM "orders"
    ),
    node_join AS (
        SELECT 
            __L__."id" AS "user_id",
            __R__."order_id" AS "order_id"
        FROM node_source1 AS __L__
        INNER JOIN node_source2 AS __R__
        ON __L__."id" = __R__."user_id"
    ),
    node_projection AS (
        SELECT "user_id", "order_id" FROM node_join
    )
SELECT "user_id", "order_id" 
FROM node_projection 
LIMIT %s
```

---

## Very Complex Example: 6 Nodes

### Pipeline Structure

```
        ┌──────────┐
        │ Source1  │
        └────┬─────┘
             │
        ┌────▼─────┐
        │ Filter1  │
        └────┬─────┘
             │
             │ Left input
        ┌────▼─────┐      ┌──────────┐
        │   Join   │◄─────│ Source2  │
        └────┬─────┘      └──────────┘
             │ Right input
             │
        ┌────▼─────┐
        │ Filter2  │
        └────┬─────┘
             │
        ┌────▼─────────┐
        │  Projection │
        └─────────────┘
```

### Execution Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    PREVIEW REQUEST                           │
│  Target Node: projection                                     │
└──────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              STEP 1: DAG TRAVERSAL                           │
│                                                              │
│  Starting from: projection                                  │
│  Following edges backwards:                                 │
│    projection ← filter2 ← join ← filter1 ← source1         │
│    projection ← filter2 ← join ← source2                  │
│                                                              │
│  Upstream nodes (topological order):                        │
│  [source1, filter1, source2, join, filter2, projection]     │
└──────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              STEP 2: CTE GENERATION                          │
│                                                              │
│  Iteration 1: Build CTE for source1                         │
│    ┌────────────────────────────┐                           │
│    │ node_source1 = SELECT *    │                           │
│    │ FROM "users"               │                           │
│    └────────────────────────────┘                           │
│                                                              │
│  Iteration 2: Build CTE for filter1                        │
│    ┌────────────────────────────┐                           │
│    │ node_filter1 = SELECT *    │                           │
│    │ FROM node_source1          │                           │
│    │ WHERE "age" > %s           │                           │
│    └────────────────────────────┘                           │
│                                                              │
│  Iteration 3: Build CTE for source2                        │
│    ┌────────────────────────────┐                           │
│    │ node_source2 = SELECT *    │                           │
│    │ FROM "orders"              │                           │
│    └────────────────────────────┘                           │
│                                                              │
│  Iteration 4: Build CTE for join                            │
│    ┌────────────────────────────┐                           │
│    │ node_join = SELECT ...     │                           │
│    │ FROM node_filter1 AS __L__ │                           │
│    │ JOIN node_source2 AS __R__│                           │
│    │ ON __L__."id" = __R__."id"│                           │
│    └────────────────────────────┘                           │
│                                                              │
│  Iteration 5: Build CTE for filter2                        │
│    ┌────────────────────────────┐                           │
│    │ node_filter2 = SELECT *    │                           │
│    │ FROM node_join             │                           │
│    │ WHERE "total" > %s         │                           │
│    └────────────────────────────┘                           │
│                                                              │
│  Iteration 6: Build CTE for projection                     │
│    ┌────────────────────────────┐                           │
│    │ node_projection = SELECT   │                           │
│    │ "id", "name"               │                           │
│    │ FROM node_filter2          │                           │
│    └────────────────────────────┘                           │
└──────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              STEP 3: QUERY ASSEMBLY                          │
│                                                              │
│  Combine all CTEs with WITH clause:                        │
│                                                              │
│  WITH                                                       │
│    node_source1 AS (...),                                  │
│    node_filter1 AS (...),                                   │
│    node_source2 AS (...),                                   │
│    node_join AS (...),                                      │
│    node_filter2 AS (...),                                    │
│    node_projection AS (...)                                 │
│  SELECT columns FROM node_projection LIMIT %s               │
└──────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              STEP 4: EXECUTION                               │
│                                                              │
│  • Connect to source database                               │
│  • Execute single SQL query                                │
│  • Parameters: [18, 100, 50]                               │
│  • Return: rows, columns, metadata                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Concepts Visualized

### 1. Topological Order

Nodes must be built in dependency order:

```
Dependency Graph:
    source1 ──┐
              ├──► join ──► filter2 ──► projection
    source2 ──┘

Build Order (Topological):
    1. source1  (no dependencies)
    2. source2  (no dependencies)
    3. join     (depends on source1, source2)
    4. filter2  (depends on join)
    5. projection (depends on filter2)
```

### 2. CTE Reference Chain

Each CTE references previous CTEs:

```
node_source1
    │
    └──► node_filter1
            │
            ├──► node_join ──► node_filter2 ──► node_projection
            │
    node_source2 ──┘
```

### 3. Metadata Flow

```
Source1 Metadata
    │
    ├─► Filter1 Metadata (same columns)
    │       │
    │       └─► Join Metadata (combines columns)
    │               │
Source2 Metadata ────┘
    │
    └─► Join Metadata (combines columns)
            │
            ├─► Filter2 Metadata (same columns)
            │       │
            │       └─► Projection Metadata (selected columns)
```

### 4. Parameter Accumulation

```
Filter1: WHERE age > %s
    Parameters: [18]

Filter2: WHERE total > %s
    Parameters: [18, 100]  ← Accumulated

Final Query: LIMIT %s
    Parameters: [18, 100, 50]  ← Page size added
```

---

## Comparison: Sequential vs Single Query

### Sequential Execution (Old Way)

```
┌─────────┐
│ Source1 │──► Execute ──► Cache ──┐
└─────────┘                        │
                                   │
┌─────────┐                        │
│ Filter1 │──► Execute on cache ──► Cache ──┐
└─────────┘                                  │
                                             │
┌─────────┐                                  │
│ Source2 │──► Execute ──► Cache ────────────┼──┐
└─────────┘                                  │  │
                                             │  │
┌─────────┐                                  │  │
│  Join   │──► Execute on caches ────────────┼──┼──► Cache ──┐
└─────────┘                                  │  │            │
                                             │  │            │
┌─────────┐                                  │  │            │
│ Filter2 │──► Execute on cache ─────────────┼──┼────────────┼──► Cache ──┐
└─────────┘                                  │  │            │            │
                                             │  │            │            │
┌─────────────┐                              │  │            │            │
│ Projection │──► Execute on cache ──────────┼──┼────────────┼────────────┼──► Result
└─────────────┘                              │  │            │            │
                                             │  │            │            │
Total: 6 database queries                    │  │            │            │
```

### Single Query (New Way)

```
┌─────────┐
│ Source1 │──┐
└─────────┘  │
             │
┌─────────┐  │  ┌─────────┐
│ Filter1 │──┼──│ Source2 │
└─────────┘  │  └─────────┘
             │
┌─────────┐  │
│  Join   │──┘
└─────────┘
    │
┌─────────┐
│ Filter2 │
└─────────┘
    │
┌─────────────┐
│ Projection │──► Compile to Single SQL ──► Execute ──► Result
└─────────────┘

Total: 1 database query
```

---

## Summary

**The SQL compilation system:**

1. ✅ **Finds** all upstream nodes in topological order
2. ✅ **Builds** CTEs for each node (bottom-up)
3. ✅ **Combines** CTEs into single SQL query
4. ✅ **Executes** one query and returns results

**Result:** Previewing any node shows the exact result of executing the entire pipeline up to that node, using a single optimized SQL query.
