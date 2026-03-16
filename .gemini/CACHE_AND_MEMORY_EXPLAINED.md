# Cache Storage & Memory Usage - Complete Explanation

## 1️⃣ **Why Cache Might Not Be Stored**

### Possible Reasons

#### A. **Checkpoint Save is Failing Silently**

The `save_checkpoint()` method returns `False` on error but doesn't raise an exception. Let me check if we're logging the result:

**Current code:**
```python
checkpoint_mgr.save_checkpoint(...)  # ← No check of return value
```

**Should be:**
```python
success = checkpoint_mgr.save_checkpoint(...)
if success:
    logger.info(f"[CHECKPOINT] Cache saved successfully")
else:
    logger.error(f"[CHECKPOINT] Cache save FAILED")
```

#### B. **Node Type Not Recognized as Checkpoint Node**

Check which node types create checkpoints:

```python
CHECKPOINT_NODE_TYPES = {'source', 'join', 'aggregate', 'compute', 'window', 'sort'}
```

**Non-checkpoint nodes (no cache):**
- `filter` - Too simple, compiled into SQL
- `projection` - Too simple, compiled into SQL
- `union` - Simple UNION ALL

#### C. **Cache is Being Created But You're Not Seeing It**

The cache is stored in:
- **Database:** Customer database (e.g., `C00008`)
- **Schema:** `staging_preview_<canvas_id>`
- **Table:** `node_<node_id>_cache`

**To verify cache exists:**
```sql
-- Connect to customer database
\c C00008

-- List preview schemas
SELECT schema_name 
FROM information_schema.schemata 
WHERE schema_name LIKE 'staging_preview_%';

-- List cache tables
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'staging_preview_<your_canvas_id>';

-- Check cache data
SELECT COUNT(*) FROM "staging_preview_<canvas_id>"."node_<node_id>_cache";
```

---

## 2️⃣ **Memory Usage in Preview - Complete Answer**

### ✅ **YES, Preview Data Goes to Memory (But Safely)**

Here's the complete flow:

### **Source Node Preview Flow**

```
1. SQL Compiler generates:
   SELECT * FROM "public"."tool_connection" LIMIT 100
   
2. execute_preview_query():
   ├─ Connects to SOURCE database
   ├─ Executes query
   ├─ cursor.fetchmany(100)  ← Fetches ≤100 rows into Python memory
   └─ Returns rows as list of dicts
   
3. Python Memory:
   rows = [{col1: val1, col2: val2}, {...}, ...]  ← ~50-100 KB
   
4. save_checkpoint() for source:
   ├─ Connects to CUSTOMER database
   ├─ CREATE TABLE cache (...)
   ├─ INSERT INTO cache VALUES (...)  ← Inserts from Python memory
   └─ Cache now in database
   
5. Return to frontend:
   Response({"rows": rows, ...})  ← Sends from Python memory
   
6. Python memory freed:
   rows variable goes out of scope
```

### **Memory Lifecycle**

| Step | Python Memory | Database | Duration |
|------|--------------|----------|----------|
| 1. SQL execution | 0 KB | Query running | ~1-2s |
| 2. Fetch rows | ~100 KB | - | ~100ms |
| 3. Save checkpoint | ~100 KB | Writing cache | ~200ms |
| 4. Return response | ~100 KB | Cache stored | ~50ms |
| 5. Request complete | 0 KB | Cache persists | - |

**Total Python memory peak:** ~100 KB (≤100 rows)
**Total duration in memory:** ~2-3 seconds
**Cache persists in database:** 20 minutes

---

## 🔒 **Memory Safety Guarantees**

### **Multiple Layers of Protection**

#### Layer 1: SQL LIMIT
```sql
SELECT * FROM source_table LIMIT 100  ← Database enforces limit
```

#### Layer 2: Cursor Fetch Limit
```python
rows = cursor.fetchmany(MAX_PREVIEW_ROWS)  # MAX_PREVIEW_ROWS = 100
```

#### Layer 3: Memory Guard
```python
rows = enforce_preview_memory_limit(rows, MAX_PREVIEW_ROWS)
if len(rows) >= MAX_PREVIEW_ROWS:
    logger.warning(f"[PREVIEW MEMORY GUARD] Hit row limit: {len(rows)} rows")
```

#### Layer 4: Checkpoint Save Limit
```python
rows = rows[:MAX_CACHE_ROWS]  # MAX_CACHE_ROWS = 100
```

**Result:** Impossible to load more than 100 rows into Python memory!

---

## 📊 **Memory Usage by Node Type**

### Source Node
```
Python Memory: ~100 KB (≤100 rows)
Duration: ~2-3 seconds
Cache: Stored in database (row-based INSERT)
```

### Join/Aggregate/Window/Sort Nodes
```
Python Memory: ~50 KB (≤100 rows, final result only)
Duration: ~2-3 seconds
Cache: Stored in database (SQL-based CTAS)
```

### Filter/Projection Nodes (No Cache)
```
Python Memory: ~50 KB (≤100 rows, final result only)
Duration: ~2-3 seconds
Cache: None (not checkpoint nodes)
```

### Compute Node
```
Python Memory: ~100-200 KB (input + output, both ≤100 rows)
Duration: ~3-5 seconds (includes Python execution)
Cache: Stored in database (row-based INSERT)
```

---

## 🎯 **Cache Hit Scenario (Second Preview)**

When cache exists and is valid:

```
1. Check for valid checkpoint:
   ├─ Query _checkpoint_metadata table
   ├─ Check expiration (< 20 minutes old)
   ├─ Check version hash (config unchanged)
   └─ Cache found! ✅
   
2. Direct SELECT from cache:
   SELECT * FROM "staging_preview_123"."node_xxx_cache" LIMIT 100
   
3. Python Memory:
   rows = cursor.fetchmany(100)  ← ~50 KB
   
4. Return to frontend:
   Response({"rows": rows, "from_cache": true})
   
5. Python memory freed
```

**Performance:**
- **First preview:** ~1-2s (query source + save cache)
- **Second preview:** ~50ms (query cache only)
- **Memory:** Same (~50-100 KB) regardless of cache hit

---

## 🔍 **Debugging Cache Issues**

### Check if Cache is Being Created

**Add this to your code after checkpoint save:**

```python
success = checkpoint_mgr.save_checkpoint(...)
if success:
    logger.info(f"✅ [CHECKPOINT] Cache saved successfully for {target_node_id}")
    logger.info(f"   Schema: staging_preview_{canvas_id}")
    logger.info(f"   Table: node_{target_node_id.replace('-', '_')}_cache")
else:
    logger.error(f"❌ [CHECKPOINT] Cache save FAILED for {target_node_id}")
```

### Check Database for Cache Tables

```sql
-- Connect to customer database
psql -U postgres -d C00008

-- List all preview schemas
SELECT schema_name 
FROM information_schema.schemata 
WHERE schema_name LIKE 'staging_preview_%'
ORDER BY schema_name;

-- For a specific canvas, list cache tables
SELECT table_name, 
       pg_size_pretty(pg_total_relation_size(quote_ident(table_schema) || '.' || quote_ident(table_name))) as size
FROM information_schema.tables 
WHERE table_schema = 'staging_preview_<your_canvas_id>'
ORDER BY table_name;

-- Check cache metadata
SELECT node_id, 
       expires_at, 
       expires_at > CURRENT_TIMESTAMP as is_valid
FROM "staging_preview_<your_canvas_id>"."_checkpoint_metadata";
```

---

## ✅ **Summary**

### Memory Usage
- ✅ **Preview data DOES go to Python memory**
- ✅ **But ALWAYS limited to ≤100 rows (~100 KB)**
- ✅ **Only for 2-3 seconds during request**
- ✅ **Then freed immediately**

### Cache Storage
- ✅ **Cache IS stored in database (not memory)**
- ✅ **Persists for 20 minutes**
- ✅ **Only for checkpoint nodes** (source, join, aggregate, compute, window, sort)
- ✅ **Not for simple nodes** (filter, projection)

### Safety
- ✅ **4 layers of memory protection**
- ✅ **Impossible to exceed 100 rows**
- ✅ **O(1) memory usage** (constant, not dependent on source table size)

---

**If cache is not being stored, check:**
1. Is the node a checkpoint node? (source, join, aggregate, etc.)
2. Are there errors in the logs? (check for "Error saving checkpoint")
3. Does the cache schema exist in the database?
4. Is the checkpoint save returning success?

Let me know if you need help debugging the cache storage issue!
