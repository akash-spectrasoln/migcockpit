# Checkpoint Cache System - Complete Flow Explanation

## 🎯 Overview

The checkpoint cache system creates **physical SQL tables** to store intermediate results at specific "checkpoint nodes". These tables are **NOT loaded into memory** - they are used as **starting points for nested SQL queries**.

---

## 📋 Table of Contents

1. [Which Nodes Get Cache Tables](#which-nodes-get-cache-tables)
2. [Cache Creation Flow](#cache-creation-flow)
3. [Cache Fetch & Usage Flow](#cache-fetch--usage-flow)
4. [Memory vs SQL: How Data Flows](#memory-vs-sql-how-data-flows)
5. [Complete Example Scenarios](#complete-example-scenarios)

---

## 1️⃣ Which Nodes Get Cache Tables?

### Checkpoint Node Types

**File:** `api/services/checkpoint_cache.py` Line 19

```python
CHECKPOINT_NODE_TYPES = {'join', 'aggregate', 'compute', 'window', 'sort', 'source'}
```

### Why These Nodes?

| Node Type | Why Checkpoint? | Complexity |
|-----------|----------------|------------|
| **source** | Starting point of data | Low (but always cached) |
| **join** | Combines multiple datasets | HIGH |
| **aggregate** | GROUP BY operations | HIGH |
| **compute** | Python execution boundary | HIGH |
| **window** | Window functions (OVER) | MEDIUM |
| **sort** | ORDER BY operations | MEDIUM |

### Nodes That DON'T Get Cache Tables

| Node Type | Why No Cache? | How Handled? |
|-----------|---------------|--------------|
| **filter** | Simple WHERE clause | Pushed into SQL |
| **projection** | Simple SELECT columns | Pushed into SQL |
| **union** | Simple UNION ALL | Pushed into SQL |

---

## 2️⃣ Cache Creation Flow

### Flow Diagram

```
User previews a node
    ↓
Is this a checkpoint node? (join/aggregate/compute/etc.)
    ↓
    YES → Create cache table
    ↓
┌─────────────────────────────────────────────────────────────┐
│ CACHE CREATION PROCESS                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 1. Compute node hash                                        │
│    hash = SHA256(node_id + node_config)                    │
│                                                             │
│ 2. Create table name                                        │
│    table = "staging_preview_{canvas_id}.node_{node_id}_cache" │
│                                                             │
│ 3. Materialize data (TWO METHODS)                          │
│                                                             │
│    METHOD A: SQL-based (for join/aggregate/window/sort)    │
│    ┌─────────────────────────────────────────────────┐    │
│    │ CREATE TABLE cache_table AS                     │    │
│    │ SELECT * FROM (                                 │    │
│    │   -- Complex SQL with CTEs                      │    │
│    │ ) _sub                                          │    │
│    │ LIMIT 100  -- ✅ Hard limit                     │    │
│    └─────────────────────────────────────────────────┘    │
│                                                             │
│    METHOD B: Memory-based (for compute nodes ONLY)         │
│    ┌─────────────────────────────────────────────────┐    │
│    │ 1. Fetch input (≤100 rows)                      │    │
│    │ 2. Run Python code                              │    │
│    │ 3. Truncate output to 100 rows                  │    │
│    │ 4. CREATE TABLE + INSERT rows                   │    │
│    └─────────────────────────────────────────────────┘    │
│                                                             │
│ 4. Save metadata                                            │
│    INSERT INTO _checkpoint_metadata (                      │
│      node_id,                                              │
│      node_version_hash,                                    │
│      upstream_version_hash,                                │
│      expires_at,  -- TTL = 20 minutes                      │
│      column_metadata                                       │
│    )                                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Detailed Steps

#### Step 1: Hash Computation

**File:** `checkpoint_cache.py` Lines 69-71

```python
def _compute_node_hash(self, node_id: str, node_config: Dict[str, Any]) -> str:
    config_str = json.dumps(node_config, sort_keys=True)
    return hashlib.sha256(f"{node_id}:{config_str}".encode()).hexdigest()
```

**Purpose:** Detect if node configuration changed (invalidates cache)

#### Step 2: Table Creation

**Schema:** `staging_preview_{canvas_id}`  
**Table:** `node_{node_id}_cache`

**Example:**
- Canvas ID: `123`
- Node ID: `abc-def-456`
- Table: `"staging_preview_123"."node_abc_def_456_cache"`

#### Step 3A: SQL-Based Materialization

**File:** `checkpoint_cache.py` Lines 137-141

```python
if sql_query:
    # Materialize via SQL
    # Use subquery to enforce limit
    ctas_sql = f'CREATE TABLE {full_table_name} AS SELECT * FROM ({sql_query}) _sub LIMIT {MAX_CACHE_ROWS}'
    cursor.execute(ctas_sql, sql_params or [])
```

**What Happens:**
1. SQL compiler builds a query from source → target node
2. Entire query executes **in the database**
3. Result materialized as physical table
4. **NO DATA ENTERS PYTHON** (pure SQL operation)
5. Limited to 100 rows

**Example SQL:**
```sql
CREATE TABLE "staging_preview_123"."node_join1_cache" AS
SELECT * FROM (
  WITH source_cte AS (
    SELECT * FROM "public"."customers" LIMIT 100
  ),
  join_cte AS (
    SELECT s.*, o.order_id, o.amount
    FROM source_cte s
    LEFT JOIN "public"."orders" o ON s.customer_id = o.customer_id
  )
  SELECT * FROM join_cte
) _sub
LIMIT 100
```

#### Step 3B: Memory-Based Materialization (Compute Nodes Only)

**File:** `checkpoint_cache.py` Lines 142-158

```python
elif rows:
    # Materialize from memory (Compute result)
    if not rows: return False
    
    rows = rows[:MAX_CACHE_ROWS]  # ✅ Truncate to 100
    col_names = list(rows[0].keys())
    
    # Create table
    col_defs = [f'"{col}" TEXT' for col in col_names]
    cursor.execute(f'CREATE TABLE {full_table_name} ({", ".join(col_defs)})')
    
    # Insert rows
    placeholders = ", ".join(["%s"] * len(col_names))
    cols_str = ", ".join([f'"{c}"' for c in col_names])
    insert_sql = f'INSERT INTO {full_table_name} ({cols_str}) VALUES ({placeholders})'
    cursor.executemany(insert_sql, [tuple(r.get(c) for c in col_names) for r in rows])
```

**What Happens:**
1. Compute node runs Python code (input ≤100 rows)
2. Output DataFrame truncated to 100 rows
3. Rows converted to list of dicts
4. Table created in database
5. Rows inserted via `executemany()`
6. **Data briefly in Python, then moved to database**

#### Step 4: Metadata Storage

**File:** `checkpoint_cache.py` Lines 161-170

```python
cursor.execute(f'''
    INSERT INTO "{self.schema_name}"."_checkpoint_metadata" 
    (node_id, node_version_hash, upstream_version_hash, expires_at, column_metadata)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (node_id) DO UPDATE SET
        node_version_hash = EXCLUDED.node_version_hash,
        upstream_version_hash = EXCLUDED.upstream_version_hash,
        expires_at = EXCLUDED.expires_at,
        column_metadata = EXCLUDED.column_metadata
''', (node_id, node_version_hash, upstream_version_hash or "", expires_at, json.dumps(columns)))
```

**Metadata Table Schema:**
```sql
CREATE TABLE "_checkpoint_metadata" (
    node_id VARCHAR(255) PRIMARY KEY,
    node_version_hash VARCHAR(64) NOT NULL,      -- Detects config changes
    upstream_version_hash VARCHAR(64),           -- Detects upstream changes
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,               -- TTL = 20 minutes
    column_metadata JSONB                        -- Column names & types
)
```

---

## 3️⃣ Cache Fetch & Usage Flow

### Discovery Process

**File:** `checkpoint_cache.py` Lines 217-257

```
User previews Node F
    ↓
find_nearest_checkpoint(F, nodes, edges)
    ↓
BFS traversal upstream: F → E → D → C → B → A
    ↓
For each node, check:
  1. Is it a checkpoint node type?
  2. Does cache table exist?
  3. Is cache still valid (not expired)?
  4. Do hashes match (config unchanged)?
    ↓
First match found = CHECKPOINT HIT
    ↓
Return (checkpoint_node_id, checkpoint_metadata)
```

### BFS Traversal Example

**Pipeline:**
```
Source A → Filter B → Join C → Projection D → Aggregate E → Filter F
```

**Checkpoint Nodes:** A (source), C (join), E (aggregate)

**Preview Node F:**
```
BFS Queue: [F]
  Check F: filter → NOT checkpoint → continue
  Add upstream: [E]

BFS Queue: [E]
  Check E: aggregate → IS checkpoint
    Check cache table exists? YES
    Check expired? NO (still valid)
    Check hash matches? YES
    → CHECKPOINT HIT! Return (E, cache_metadata)
```

**Result:** Start SQL compilation from E's cache table

### Cache Hit Response

**File:** `pipeline.py` Lines 1393-1408

```python
if ancestor_id == target_node_id and checkpoint:
    logger.info(f"[CHECKPOINT HIT] Target node {target_node_id} has valid table cache")
    
    # Just select from the checkpoint table
    sql = f'SELECT * FROM {checkpoint["table_ref"]} LIMIT %s'
    results = execute_preview_query(sql, [page_size], {}, page, page_size, skip_db_type=True)
    
    return Response({
        "rows": results.get('rows', []),
        "columns": [c.get('name') for c in checkpoint['columns']],
        "has_more": False,
        "total": len(results.get('rows', [])),
        "page": page,
        "page_size": page_size,
        "from_cache": True,  # ✅ Indicates cache hit
        "preview_mode": True
    })
```

**What Happens:**
1. **Direct SELECT** from cache table
2. **NO SQL compilation** needed
3. **NO upstream traversal** needed
4. **O(1) latency** - instant response
5. **NO data in Python** (except final ≤100 rows for response)

---

## 4️⃣ Memory vs SQL: How Data Flows

### ❌ WRONG Understanding: "Cache Loaded into Memory"

**MYTH:** Cache tables are loaded into Python memory for processing

**REALITY:** Cache tables are used as **SQL starting points**

### ✅ CORRECT Understanding: "Cache as SQL Table Reference"

#### Scenario 1: Cache Hit (Target Node Has Cache)

```
User previews Node E (aggregate)
    ↓
find_nearest_checkpoint(E) → Found E's cache
    ↓
SQL: SELECT * FROM "staging_preview_123"."node_E_cache" LIMIT 100
    ↓
Database returns ≤100 rows
    ↓
cursor.fetchmany(100) → Python gets ≤100 rows
    ↓
Response to frontend
```

**Memory Usage:** ~10-100 KB (only final result)

#### Scenario 2: Cache Miss, Nearest Checkpoint Upstream

```
User previews Node F (filter)
    ↓
find_nearest_checkpoint(F) → Found E's cache (upstream)
    ↓
SQL Compiler builds:
    WITH checkpoint_cte AS (
      SELECT * FROM "staging_preview_123"."node_E_cache"  -- ✅ Reference cache table
    ),
    filter_cte AS (
      SELECT * FROM checkpoint_cte
      WHERE age > 25  -- Apply F's filter
    )
    SELECT * FROM filter_cte
    LIMIT 100
    ↓
Database executes entire query
    ↓
cursor.fetchmany(100) → Python gets ≤100 rows
    ↓
Response to frontend
```

**Memory Usage:** ~10-100 KB (only final result)

**Key Point:** Cache table is **referenced in SQL**, not loaded into memory!

#### Scenario 3: No Cache Found (Start from Source)

```
User previews Node F
    ↓
find_nearest_checkpoint(F) → No cache found
    ↓
SQL Compiler builds from source:
    WITH source_cte AS (
      SELECT * FROM "public"."customers" LIMIT 100  -- ✅ Source with LIMIT
    ),
    filter_b_cte AS (
      SELECT * FROM source_cte WHERE status = 'active'
    ),
    join_c_cte AS (
      SELECT s.*, o.order_id
      FROM filter_b_cte s
      LEFT JOIN "public"."orders" o ON s.id = o.customer_id
    ),
    projection_d_cte AS (
      SELECT id, name, order_id FROM join_c_cte
    ),
    aggregate_e_cte AS (
      SELECT id, COUNT(order_id) as order_count
      FROM projection_d_cte
      GROUP BY id
    ),
    filter_f_cte AS (
      SELECT * FROM aggregate_e_cte WHERE order_count > 5
    )
    SELECT * FROM filter_f_cte
    LIMIT 100
    ↓
Database executes entire query
    ↓
cursor.fetchmany(100) → Python gets ≤100 rows
    ↓
Save checkpoint for E (aggregate node)
    ↓
Response to frontend
```

**Memory Usage:** ~10-100 KB (only final result)

**Key Point:** Entire pipeline executes **in database**, not in Python!

---

## 5️⃣ Complete Example Scenarios

### Example 1: Simple Pipeline with Checkpoints

**Pipeline:**
```
Source A (customers)
  ↓
Filter B (status='active')
  ↓
Join C (with orders)
  ↓
Projection D (select columns)
  ↓
Aggregate E (count orders)
  ↓
Filter F (order_count > 5)
```

**Checkpoint Nodes:** A (source), C (join), E (aggregate)

#### First Preview of Node F

**Step 1:** Find nearest checkpoint
- Check F: filter → no cache
- Check E: aggregate → no cache
- Check D: projection → not checkpoint type
- Check C: join → no cache
- Check B: filter → not checkpoint type
- Check A: source → no cache
- **Result:** No checkpoint found, start from source

**Step 2:** SQL Compilation (source → F)
```sql
WITH source_cte AS (
  SELECT * FROM "public"."customers" LIMIT 100
),
filter_b_cte AS (
  SELECT * FROM source_cte WHERE status = 'active'
),
join_c_cte AS (
  SELECT s.*, o.order_id, o.amount
  FROM filter_b_cte s
  LEFT JOIN "public"."orders" o ON s.customer_id = o.customer_id
),
projection_d_cte AS (
  SELECT customer_id, name, order_id, amount FROM join_c_cte
),
aggregate_e_cte AS (
  SELECT customer_id, name, COUNT(order_id) as order_count, SUM(amount) as total_amount
  FROM projection_d_cte
  GROUP BY customer_id, name
),
filter_f_cte AS (
  SELECT * FROM aggregate_e_cte WHERE order_count > 5
)
SELECT * FROM filter_f_cte LIMIT 100
```

**Step 3:** Execute in database
- Database processes entire query
- Returns ≤100 rows
- **Memory:** ~10-100 KB

**Step 4:** Save checkpoints
- **Source A:** `CREATE TABLE node_A_cache AS SELECT * FROM customers LIMIT 100`
- **Join C:** `CREATE TABLE node_C_cache AS SELECT * FROM (join_c_cte) LIMIT 100`
- **Aggregate E:** `CREATE TABLE node_E_cache AS SELECT * FROM (aggregate_e_cte) LIMIT 100`

**Cache Tables Created:** 3 tables (A, C, E)

#### Second Preview of Node F (Cache Hit!)

**Step 1:** Find nearest checkpoint
- Check F: filter → no cache
- Check E: aggregate → **CACHE HIT!** ✅

**Step 2:** Direct SELECT
```sql
SELECT * FROM "staging_preview_123"."node_E_cache" 
WHERE order_count > 5  -- Apply F's filter
LIMIT 100
```

**Step 3:** Return cached result
- **Latency:** ~50ms (vs ~500ms first time)
- **Memory:** ~10-100 KB
- **No recomputation!**

#### Preview of Node C (Intermediate Checkpoint)

**Step 1:** Find nearest checkpoint
- Check C: join → **CACHE HIT!** ✅

**Step 2:** Direct SELECT
```sql
SELECT * FROM "staging_preview_123"."node_C_cache" LIMIT 100
```

**Step 3:** Return cached result
- **Instant response!**

---

### Example 2: Pipeline with Compute Node

**Pipeline:**
```
Source A (sales_data)
  ↓
Filter B (year=2024)
  ↓
Compute C (Python: calculate moving average)
  ↓
Projection D (select columns)
  ↓
Aggregate E (sum by region)
```

**Checkpoint Nodes:** A (source), C (compute), E (aggregate)

#### Preview of Node C (Compute)

**Step 1:** Find nearest checkpoint
- Check C: compute → no cache
- Check B: filter → not checkpoint
- Check A: source → **CACHE HIT!** ✅

**Step 2:** SQL Compilation (A → B)
```sql
WITH checkpoint_cte AS (
  SELECT * FROM "staging_preview_123"."node_A_cache"  -- Use A's cache
),
filter_b_cte AS (
  SELECT * FROM checkpoint_cte WHERE year = 2024
)
SELECT * FROM filter_b_cte LIMIT 100
```

**Step 3:** Execute SQL → Get input rows (≤100)
- **Memory:** ~10-100 KB for input

**Step 4:** Python Execution
```python
import pandas as pd
input_df = pd.DataFrame(input_rows)  # ≤100 rows

# User code
_output_df = input_df.copy()
_output_df['moving_avg'] = input_df['sales'].rolling(window=7).mean()

# Truncate output
if len(_output_df) > 100:
    _output_df = _output_df.head(100)

output_rows = _output_df.to_dict('records')
```

**Step 5:** Save Compute Cache
```sql
CREATE TABLE "staging_preview_123"."node_C_cache" (
  date TEXT,
  sales TEXT,
  moving_avg TEXT
);

INSERT INTO "staging_preview_123"."node_C_cache" VALUES
  ('2024-01-01', '1000', '950.5'),
  ('2024-01-02', '1100', '975.2'),
  ...  -- ≤100 rows
```

**Step 6:** Return result
- **Memory Peak:** ~100-200 KB (input + output briefly)
- **Final Memory:** ~10-100 KB (response only)

#### Preview of Node E (After Compute)

**Step 1:** Find nearest checkpoint
- Check E: aggregate → no cache
- Check D: projection → not checkpoint
- Check C: compute → **CACHE HIT!** ✅

**Step 2:** SQL Compilation (C → E)
```sql
WITH checkpoint_cte AS (
  SELECT * FROM "staging_preview_123"."node_C_cache"  -- Use C's cache
),
projection_d_cte AS (
  SELECT date, region, moving_avg FROM checkpoint_cte
),
aggregate_e_cte AS (
  SELECT region, AVG(moving_avg::numeric) as avg_moving_avg
  FROM projection_d_cte
  GROUP BY region
)
SELECT * FROM aggregate_e_cte LIMIT 100
```

**Step 3:** Execute in database
- **No Python execution!**
- **Pure SQL from C's cache table**
- **Memory:** ~10-100 KB

---

## 📊 Summary Table

### Cache Creation Rules

| Node Type | Cache Created? | Method | Data in Memory? |
|-----------|---------------|--------|-----------------|
| source | ✅ YES | SQL (CTAS) | ❌ NO |
| filter | ❌ NO | - | ❌ NO |
| projection | ❌ NO | - | ❌ NO |
| join | ✅ YES | SQL (CTAS) | ❌ NO |
| aggregate | ✅ YES | SQL (CTAS) | ❌ NO |
| compute | ✅ YES | Memory → INSERT | ✅ YES (≤100 rows) |
| window | ✅ YES | SQL (CTAS) | ❌ NO |
| sort | ✅ YES | SQL (CTAS) | ❌ NO |
| union | ❌ NO | - | ❌ NO |

### Cache Usage Rules

| Scenario | SQL Pattern | Memory Usage |
|----------|-------------|--------------|
| Cache hit (target node) | `SELECT * FROM cache_table` | ≤100 KB |
| Cache hit (upstream) | `WITH cte AS (SELECT * FROM cache_table) ...` | ≤100 KB |
| No cache | `WITH source_cte AS (SELECT * FROM source LIMIT 100) ...` | ≤100 KB |
| Compute node | Python execution + INSERT | ≤200 KB (peak) |

### How Many Nodes After Cache Table?

**Answer:** Cache tables are created **AT** checkpoint nodes, not after them.

**Example Pipeline:**
```
A (source) → B (filter) → C (join) → D (projection) → E (aggregate) → F (filter)
```

**Cache Tables:**
- **At A:** `node_A_cache` (created when previewing A or any downstream node)
- **At C:** `node_C_cache` (created when previewing C or downstream)
- **At E:** `node_E_cache` (created when previewing E or downstream)

**Nodes Between Caches:**
- A → C: 1 node (B - filter)
- C → E: 1 node (D - projection)
- E → F: 0 nodes (F is filter, not checkpoint)

**Rule:** Non-checkpoint nodes (filter, projection) are compiled into SQL CTEs, not cached.

---

## 🔑 Key Takeaways

1. **Cache tables are SQL tables**, not in-memory data structures
2. **Only checkpoint nodes** get cache tables (join, aggregate, compute, etc.)
3. **SQL-based caching** = pure database operation (no Python memory)
4. **Memory-based caching** = only for compute nodes (≤100 rows)
5. **Cache reuse** = SQL references cache table in CTE
6. **No data in Python** except final ≤100 rows for response
7. **TTL = 20 minutes** - caches expire automatically
8. **Hash-based invalidation** - config changes invalidate cache

---

## 🎓 Mental Model

Think of cache tables as **SQL bookmarks**:

```
Without cache:
  Read entire book from page 1 → page 500

With cache at page 300:
  Start reading from page 300 → page 500
  (Skip pages 1-299)

Cache table = "Bookmark at page 300"
```

**NOT:** "Copy pages 1-300 into memory"  
**YES:** "Start SQL query from cached table"

---

**Last Updated:** 2026-02-13
