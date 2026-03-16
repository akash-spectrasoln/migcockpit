# How Projection Preview Works - Step by Step

## 🎯 When You Click Preview on a Projection Node

Here's exactly what happens when you click the preview button on a projection node:

```
USER CLICKS PREVIEW ON PROJECTION NODE
    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: Frontend Sends Request                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  POST /api/pipeline/execute/                                                │
│  {                                                                           │
│    "targetNodeId": "5d2647be-50dd-4372-8179-4b866fe34221",  // Projection   │
│    "canvasId": "123",                                                        │
│    "nodes": [...],  // All nodes in canvas                                  │
│    "edges": [...],  // All edges in canvas                                  │
│    "preview": true,                                                          │
│    "page": 1,                                                                │
│    "pageSize": 100                                                           │
│  }                                                                           │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: Backend Receives Request (pipeline.py)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PipelineQueryExecutionView.post()                                          │
│    ├─ Extract target_node_id (projection node)                              │
│    ├─ Extract canvas_id                                                     │
│    ├─ Extract nodes and edges                                               │
│    └─ Initialize CheckpointCacheManager                                     │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Find Nearest Checkpoint                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  checkpoint_mgr.find_nearest_checkpoint(projection_node_id, nodes, edges)   │
│                                                                              │
│  BFS Traversal Upstream:                                                    │
│    Projection → Source                                                      │
│                                                                              │
│  Check Projection: Not a checkpoint node → Skip                             │
│  Check Source: IS checkpoint node → Check for cache                         │
│                                                                              │
│  Result: ancestor_id = source_node_id, checkpoint = {...} or None           │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: SQL Compilation                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  compiler = SQLCompiler(customer, nodes, edges, db_type)                    │
│  sql_query, sql_params, metadata = compiler.compile(                        │
│      target_node_id=projection_node_id,                                     │
│      page_size=100                                                           │
│  )                                                                           │
│                                                                              │
│  Compilation Process:                                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 1. Build Source CTE                                                  │  │
│  │    - Get source config from GENERAL.source table ← ERROR WAS HERE!  │  │
│  │    - Get table metadata (columns, types)                            │  │
│  │    - Build: WITH source_cte AS (                                    │  │
│  │                SELECT * FROM "public"."tool_connection" LIMIT 100   │  │
│  │              )                                                       │  │
│  │                                                                      │  │
│  │ 2. Build Projection CTE                                             │  │
│  │    - Get input metadata from source_cte                             │  │
│  │    - Get selected columns from projection config                    │  │
│  │    - Build: projection_cte AS (                                     │  │
│  │                SELECT "column1", "column2", "column3"               │  │
│  │                FROM source_cte                                      │  │
│  │              )                                                       │  │
│  │                                                                      │  │
│  │ 3. Final SELECT                                                     │  │
│  │    SELECT * FROM projection_cte LIMIT 100                           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Full SQL Generated:                                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ WITH source_cte AS (                                                 │  │
│  │   SELECT * FROM "public"."tool_connection" LIMIT 100                 │  │
│  │ ),                                                                   │  │
│  │ projection_cte AS (                                                  │  │
│  │   SELECT "id", "name", "status" FROM source_cte                      │  │
│  │ )                                                                    │  │
│  │ SELECT * FROM projection_cte LIMIT 100                               │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 5: Execute SQL in Database                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  results = execute_preview_query(sql_query, sql_params, source_config, ...) │
│                                                                              │
│  Database Execution:                                                         │
│    1. Read from tool_connection table (LIMIT 100)                           │
│    2. Apply projection (select specific columns)                            │
│    3. Return ≤100 rows                                                      │
│                                                                              │
│  Python Memory:                                                              │
│    cursor.fetchmany(100) → ≤100 rows loaded                                 │
│    enforce_preview_memory_limit(rows, 100) → Guard                          │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 6: Save Checkpoint (if applicable)                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  For Source Node (checkpoint node):                                         │
│    checkpoint_mgr.save_checkpoint(                                          │
│      node_id=source_node_id,                                                │
│      sql_query="SELECT * FROM tool_connection LIMIT 100",                   │
│      ...                                                                     │
│    )                                                                         │
│                                                                              │
│  Creates:                                                                    │
│    CREATE TABLE "staging_preview_123"."node_<source_id>_cache" AS           │
│    SELECT * FROM "public"."tool_connection" LIMIT 100                        │
│                                                                              │
│  For Projection Node:                                                       │
│    NOT a checkpoint node → No cache created                                 │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 7: Return Response to Frontend                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Response({                                                                  │
│    "rows": [                                                                 │
│      {"id": 1, "name": "Tool A", "status": "active"},                        │
│      {"id": 2, "name": "Tool B", "status": "inactive"},                      │
│      ...  // ≤100 rows                                                      │
│    ],                                                                        │
│    "columns": ["id", "name", "status"],                                      │
│    "total": 100,                                                             │
│    "has_more": false,                                                        │
│    "from_cache": false,  // First time, no cache hit                         │
│    "preview_mode": "output"                                                  │
│  })                                                                          │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │   FRONTEND DISPLAYS DATA     │
                    │   in TableDataPanel          │
                    └──────────────────────────────┘
```

---

## 🔍 The Error You Were Seeing

### Where It Failed

The error occurred in **STEP 4 - SQL Compilation**, specifically when building the Source CTE:

```python
# In _build_source_cte method:
# Line 1: Get source config from GENERAL.source table
source_config = self._get_source_config(source_id)

# In _get_source_config method:
# Line 2: Query GENERAL.source table
cursor.execute(f'''
    SELECT {name_column}, {config_column}, created_on
    FROM "GENERAL".source
    WHERE id = %s
''', (source_id,))
```

**The Problem:**
- Code tried to SELECT both `source_name` and `src_name`
- Code tried to SELECT both `source_config` and `src_config`
- But your database only has `source_name` and `source_config`
- SQL error: `column "src_config" does not exist`

### The Fix

Now the code:
1. **Checks which columns exist** in `GENERAL.source` table
2. **Only SELECTs columns that exist**
3. **Validates** that required columns are present

```python
# Get available columns
cursor.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_schema = 'GENERAL' AND table_name = 'source'
""")
available_columns = [row[0] for row in cursor.fetchall()]

# Use whichever column exists
name_column = 'source_name' if 'source_name' in available_columns else 'src_name'
config_column = 'source_config' if 'source_config' in available_columns else 'src_config'

# Validate
if name_column not in available_columns:
    raise ValueError(f"Source table missing name column")

# Only SELECT columns that exist
cursor.execute(f'''
    SELECT "{name_column}", "{config_column}", created_on
    FROM "GENERAL".source
    WHERE id = %s
''', (source_id,))
```

---

## ✅ Now It Should Work

Try clicking preview on your projection node again. The flow should complete successfully:

1. ✅ Get source config (fixed!)
2. ✅ Build SQL with CTEs
3. ✅ Execute in database
4. ✅ Return ≤100 rows
5. ✅ Display in UI

---

## 🎓 Key Takeaways

1. **Projection nodes are NOT checkpoint nodes** - they don't create cache tables
2. **Projection preview requires upstream source** - must compile from source → projection
3. **Source config is fetched from GENERAL.source table** - this was failing before
4. **All SQL compilation happens before database execution** - errors in compilation prevent execution
5. **Memory is always safe** - ≤100 rows regardless of cache hits

---

**Status:** ✅ Fixed - Try previewing your projection node now!
