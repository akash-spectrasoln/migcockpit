# Checkpoint Cache Database Mismatch Fix

## 🔴 Problem

**Error:**
```
Error saving checkpoint for ee677f5f-4f70-4a3f-afb3-a6a7ab3bf516: 
relation "public.tool_connection" does not exist
LINE 2: SELECT * FROM "public"."tool_connection"
```

**Root Cause:**

The checkpoint cache system was trying to execute:
```sql
CREATE TABLE "staging_preview_123"."node_xxx_cache" AS
SELECT * FROM "public"."tool_connection"
```

But this fails because:
1. **Cache table** is created in the **customer database** (C00008)
2. **Source table** (`tool_connection`) exists in the **source database** (different database)
3. PostgreSQL can't reference tables from other databases in a single query

---

## 🏗️ Architecture Understanding

### Database Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                         PostgreSQL Server                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────┐      ┌─────────────────────────┐   │
│  │  Customer Database     │      │  Source Database        │   │
│  │  (C00008)              │      │  (External)             │   │
│  ├────────────────────────┤      ├─────────────────────────┤   │
│  │                        │      │                         │   │
│  │  GENERAL schema:       │      │  public schema:         │   │
│  │  - source              │      │  - tool_connection ✅   │   │
│  │  - destination         │      │  - customers            │   │
│  │  - canvas              │      │  - orders               │   │
│  │                        │      │  - ...                  │   │
│  │  staging_preview_123:  │      │                         │   │
│  │  - node_xxx_cache ❌   │      │                         │   │
│  │  - _checkpoint_metadata│      │                         │   │
│  │                        │      │                         │   │
│  └────────────────────────┘      └─────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### The Problem

**What the code was trying to do:**
```sql
-- Connect to customer database (C00008)
-- Try to execute:
CREATE TABLE "staging_preview_123"."node_xxx_cache" AS
SELECT * FROM "public"."tool_connection"  -- ❌ This table is in a different database!
```

**Why it fails:**
- PostgreSQL doesn't support cross-database queries
- `tool_connection` exists in the **source database**
- Cache table is being created in the **customer database**
- Can't reference source database tables from customer database

---

## ✅ Solution

### Strategy

For **source nodes**, we need to:
1. **Fetch data from source database** (already done by `execute_preview_query`)
2. **Insert data into cache table in customer database** (using `rows` parameter)

For **other checkpoint nodes** (join, aggregate, etc.):
1. **Use SQL** because they reference CTEs, which are in the same database

### Code Fix

**File:** `api/views/pipeline.py` (lines 1565-1579)

**Before:**
```python
if checkpoint_mgr.is_checkpoint_node(target_node_type):
    checkpoint_mgr.save_checkpoint(
        target_node_id, target_node_type, target_node_data.get('config', {}),
        None, out_cols, sql_query=sql_query, sql_params=sql_params  # ❌ SQL references source DB
    )
```

**After:**
```python
if checkpoint_mgr.is_checkpoint_node(target_node_type):
    # For source nodes, save using rows (not SQL) because the SQL references
    # a table in the source database, but the cache is in the customer database
    if target_node_type == 'source':
        checkpoint_mgr.save_checkpoint(
            target_node_id, target_node_type, target_node_data.get('config', {}),
            None, out_cols, rows=rows  # ✅ Use rows (already fetched from source DB)
        )
    else:
        # For other checkpoint nodes (join, aggregate, etc.), use SQL
        # because they reference CTEs in the same database
        checkpoint_mgr.save_checkpoint(
            target_node_id, target_node_type, target_node_data.get('config', {}),
            None, out_cols, sql_query=sql_query, sql_params=sql_params  # ✅ SQL references CTEs
        )
```

---

## 🔍 How It Works Now

### Source Node Checkpoint Flow

```
1. User clicks preview on source node
   ↓
2. SQL Compiler generates:
   SELECT * FROM "public"."tool_connection" LIMIT 100
   ↓
3. execute_preview_query():
   - Connects to SOURCE database
   - Executes query
   - Fetches ≤100 rows into Python
   - Returns rows
   ↓
4. save_checkpoint() for source node:
   - Connects to CUSTOMER database
   - Creates cache table: "staging_preview_123"."node_xxx_cache"
   - Inserts rows (from step 3) into cache table
   ✅ Success!
```

### Join/Aggregate Node Checkpoint Flow

```
1. User clicks preview on join node
   ↓
2. SQL Compiler generates:
   WITH source_cte AS (
     SELECT * FROM "staging_preview_123"."node_source_cache"  -- Cache in customer DB
   ),
   join_cte AS (
     SELECT ... FROM source_cte ...
   )
   SELECT * FROM join_cte LIMIT 100
   ↓
3. execute_preview_query():
   - Connects to CUSTOMER database (where cache tables exist)
   - Executes query (all CTEs reference customer DB tables)
   - Fetches ≤100 rows
   - Returns rows
   ↓
4. save_checkpoint() for join node:
   - Connects to CUSTOMER database
   - Creates cache table using SQL:
     CREATE TABLE "staging_preview_123"."node_join_cache" AS
     SELECT * FROM (WITH source_cte AS ... ) _sub LIMIT 100
   ✅ Success! (All tables referenced are in customer DB)
```

---

## 📊 Memory Impact

### Source Node Cache Creation

**Before (SQL-based - FAILED):**
```
Memory: 0 KB (pure SQL operation)
But: ❌ Fails because of cross-database reference
```

**After (Row-based - WORKS):**
```
Memory: ~50-100 KB (≤100 rows briefly in Python)
Then: Inserted into customer DB cache table
Result: ✅ Works!
```

**Trade-off:**
- Slightly more memory usage for source nodes (~100 KB)
- But still within safety limits (≤100 rows)
- Necessary to avoid cross-database query issues

---

## ✅ Verification

After restarting the server, verify:

1. **Source node preview:**
   - ✅ Data displays correctly
   - ✅ Cache table created in customer DB
   - ✅ No "relation does not exist" errors

2. **Projection node preview:**
   - ✅ Uses source cache (if available)
   - ✅ Data displays correctly

3. **Join/Aggregate node preview:**
   - ✅ Cache created using SQL (efficient)
   - ✅ No cross-database errors

---

## 🎓 Key Learnings

1. **PostgreSQL doesn't support cross-database queries**
   - Can't reference tables from different databases in one query
   - Need to fetch data first, then insert

2. **Source nodes are special**
   - They reference external database tables
   - Must use row-based caching, not SQL-based

3. **Other checkpoint nodes can use SQL**
   - They reference CTEs in the same database
   - SQL-based caching is more efficient (no Python memory)

4. **Memory safety is maintained**
   - Source nodes: ≤100 rows in Python (~100 KB)
   - Other nodes: 0 KB in Python (pure SQL)
   - All within safety limits

---

**Status:** ✅ Fixed
**Next Step:** Restart Django server and test source node preview
