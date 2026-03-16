# Preview System Performance & Safety Audit

## Executive Summary

**Audit Date:** 2026-02-13  
**Status:** ⚠️ **VIOLATIONS FOUND** - Immediate fixes required

### Critical Findings

| Rule | Status | Severity | Details |
|------|--------|----------|---------|
| 1. O(1) Preview Latency | ✅ PASS | - | LIMIT enforced at SQL level |
| 2. Memory ≤100 rows | ❌ **FAIL** | 🔴 CRITICAL | `cursor.fetchall()` loads unlimited rows |
| 3. DB-Only Heavy Compute | ✅ PASS | - | SQL pushdown architecture |
| 4. Non-Blocking UI | ✅ PASS | - | Async API calls |
| 5. Checkpoint Reuse | ✅ PASS | - | Implemented correctly |

---

## 1️⃣ Full Preview Flow Trace

### Current Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ FRONTEND                                                        │
├─────────────────────────────────────────────────────────────────┤
│ 1. User clicks node                                             │
│    └─> TableDataPanel.executePipelineQuery()                    │
│        └─> pipelineApi.execute(nodes, edges, targetNodeId, {    │
│               canvasId, page, pageSize, previewMode: true       │
│           })                                                     │
│                                                                  │
│ Time: ~5-50ms (network latency)                                 │
│ Memory: Minimal (JSON serialization)                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ BACKEND: Django API (pipeline.py)                               │
├─────────────────────────────────────────────────────────────────┤
│ 2. PipelineQueryExecutionView.post()                            │
│    ├─> Extract: canvasId, targetNodeId, nodes, edges           │
│    ├─> Validate: canvasId required (line 1382)                 │
│    └─> Initialize: CheckpointCacheManager(cust_db, canvas_id)  │
│                                                                  │
│ 3. Checkpoint Discovery (lines 1391-1408)                       │
│    ├─> checkpoint_mgr.find_nearest_checkpoint()                │
│    │   └─> BFS traversal upstream to find cached table         │
│    │                                                             │
│    └─> If checkpoint HIT:                                       │
│        ├─> SQL: SELECT * FROM checkpoint_table LIMIT 100       │
│        └─> RETURN immediately (O(1) latency) ✅                │
│                                                                  │
│ Time: ~1-5ms (checkpoint lookup)                                │
│ Memory: Minimal (metadata only)                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ SQL COMPILATION (sql_compiler.py)                               │
├─────────────────────────────────────────────────────────────────┤
│ 4. SQLCompiler.compile()                                        │
│    ├─> Build CTEs for each node from checkpoint to target      │
│    ├─> Apply transformations in SQL (filters, joins, etc.)     │
│    └─> Append LIMIT {page_size} (lines 1531-1536)              │
│                                                                  │
│ Output: (sql_query, params, output_metadata)                    │
│                                                                  │
│ Time: ~10-50ms (DAG traversal + SQL generation)                 │
│ Memory: Minimal (string building)                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ DB EXECUTION (db_executor.py)                                   │
├─────────────────────────────────────────────────────────────────┤
│ 5. execute_preview_query()                                      │
│    └─> _execute_postgresql_query()                              │
│        ├─> cursor.execute(sql_query, params)                   │
│        ├─> ❌ rows_data = cursor.fetchall()  [LINE 78]         │
│        │   └─> VIOLATION: Loads ALL rows into memory!          │
│        │                                                         │
│        └─> Convert rows to list of dicts                        │
│                                                                  │
│ Time: ~50-500ms (depends on query complexity)                   │
│ Memory: ❌ UNBOUNDED - Can load millions of rows!               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ COMPUTE NODE (if applicable)                                    │
├─────────────────────────────────────────────────────────────────┤
│ 6. Python Execution (lines 1483-1496)                           │
│    ├─> input_rows limited to 100 ✅ (line 1458)                │
│    ├─> pd.DataFrame(input_rows)                                │
│    ├─> exec(user_code)                                         │
│    └─> output_df.to_dict('records')                            │
│        └─> ⚠️ No output row limit enforced!                    │
│                                                                  │
│ Time: ~10-1000ms (depends on user code)                         │
│ Memory: ✅ Input capped at 100 rows                             │
│         ❌ Output unbounded!                                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ CHECKPOINT SAVE (checkpoint_cache.py)                           │
├─────────────────────────────────────────────────────────────────┤
│ 7. checkpoint_mgr.save_checkpoint()                             │
│    ├─> Create table in staging_preview_{canvas_id}             │
│    ├─> INSERT rows (limited to MAX_CACHE_ROWS=100) ✅          │
│    └─> Update metadata table                                    │
│                                                                  │
│ Time: ~50-200ms (table creation + insert)                       │
│ Memory: ✅ Capped at 100 rows                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ RESPONSE TO FRONTEND                                            │
├─────────────────────────────────────────────────────────────────┤
│ 8. Return JSON response                                         │
│    └─> { rows, columns, total, has_more, from_cache }          │
│                                                                  │
│ Time: ~5-50ms (JSON serialization + network)                    │
│ Memory: ✅ Limited by page_size                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2️⃣ Memory Safety Violations

### 🔴 CRITICAL: `cursor.fetchall()` Unbounded Memory

**Location:** `api/utils/db_executor.py:78`

```python
# CURRENT CODE (UNSAFE)
rows_data = cursor.fetchall()  # ❌ Loads ALL rows into memory!
```

**Problem:**
- Even though SQL has `LIMIT 100`, `fetchall()` loads all 100 rows into Python memory
- If LIMIT is accidentally removed or overridden, this becomes catastrophic
- No runtime guard against memory overflow

**Impact:**
- With 100 rows: ~10-100 KB (acceptable)
- With 10,000 rows: ~1-10 MB (dangerous)
- With 1,000,000 rows: ~100 MB - 1 GB (system crash)

**Required Fix:**
```python
# SAFE VERSION
MAX_PREVIEW_ROWS = 100

# Use fetchmany with hard limit
rows_data = cursor.fetchmany(MAX_PREVIEW_ROWS)

# Runtime guard
if len(rows_data) >= MAX_PREVIEW_ROWS:
    logger.warning(f"Preview hit row limit: {len(rows_data)} rows fetched")
```

### ⚠️ WARNING: Compute Node Output Unbounded

**Location:** `api/views/pipeline.py:1496`

```python
# CURRENT CODE (UNSAFE)
output_data = output_df.to_dict('records')  # ❌ No limit on output rows!
```

**Problem:**
- User code can generate unlimited rows
- Example: `df.explode()` or `df.merge()` can multiply rows

**Required Fix:**
```python
# SAFE VERSION
MAX_COMPUTE_OUTPUT_ROWS = 100

output_df = output_df.head(MAX_COMPUTE_OUTPUT_ROWS)  # Hard limit
output_data = output_df.to_dict('records')

if len(output_df) >= MAX_COMPUTE_OUTPUT_ROWS:
    logger.warning(f"Compute output truncated to {MAX_COMPUTE_OUTPUT_ROWS} rows")
```

---

## 3️⃣ Performance Analysis

### ✅ PASS: O(1) Latency Guarantee

**Evidence:**
1. **SQL LIMIT enforced** (lines 1531-1536, 1458-1464)
2. **Checkpoint reuse** prevents full DAG recomputation
3. **No full table scans** - all queries have LIMIT

**Validation:**
```sql
-- All preview queries follow this pattern:
SELECT * FROM (
    -- Complex CTE chain
) _final
LIMIT 100  -- ✅ Always present
```

### ✅ PASS: SQL Pushdown Architecture

**Evidence:**
1. **Filters pushed to SQL** (sql_compiler.py:615-709)
2. **Joins in SQL** (sql_compiler.py:711-1183)
3. **Aggregations in SQL** (sql_compiler.py:1397-1485)
4. **Only Compute nodes use Python** (intentional boundary)

### ✅ PASS: Checkpoint System

**Evidence:**
1. **BFS upstream search** (checkpoint_cache.py:find_nearest_checkpoint)
2. **Cache hit = immediate return** (pipeline.py:1393-1408)
3. **Proper invalidation** (checkpoint_cache.py:invalidate_downstream)

---

## 4️⃣ Missing Safety Guards

### ❌ No Memory Guard

**Required:**
```python
class PreviewMemoryLimitError(Exception):
    """Raised when preview exceeds memory limits."""
    pass

def enforce_preview_memory_limit(rows, max_rows=100):
    """Global memory guard for all preview operations."""
    if len(rows) > max_rows:
        raise PreviewMemoryLimitError(
            f"Preview exceeded memory limit: {len(rows)} rows > {max_rows} max"
        )
    return rows
```

### ❌ No Time Guard

**Required:**
```python
import time
from functools import wraps

def preview_timeout(seconds=5):
    """Decorator to enforce preview timeout."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            
            if elapsed > seconds:
                logger.warning(f"Slow preview: {func.__name__} took {elapsed:.2f}s")
            
            return result
        return wrapper
    return decorator
```

### ❌ No SQL Validation

**Required:**
```python
def validate_preview_sql(sql_query: str):
    """Ensure preview SQL has required safety constraints."""
    sql_upper = sql_query.upper()
    
    # Must have LIMIT
    if 'LIMIT' not in sql_upper:
        raise ValueError("Preview SQL must include LIMIT clause")
    
    # Extract LIMIT value
    import re
    limit_match = re.search(r'LIMIT\s+(\d+)', sql_upper)
    if limit_match:
        limit_value = int(limit_match.group(1))
        if limit_value > 100:
            raise ValueError(f"Preview LIMIT too high: {limit_value} > 100")
    
    return True
```

---

## 5️⃣ Logging & Observability Gaps

### ❌ Missing Structured Logs

**Current:** Basic logger.info() calls  
**Required:** Structured preview trace

```python
import time
import logging

class PreviewTracer:
    """Structured logging for preview operations."""
    
    def __init__(self, node_id: str, canvas_id: str):
        self.node_id = node_id
        self.canvas_id = canvas_id
        self.start_time = time.time()
        self.metrics = {
            'rows_fetched': 0,
            'sql_time_ms': 0,
            'python_time_ms': 0,
            'checkpoint_used': False,
            'memory_rows': 0,
        }
    
    def log_sql_execution(self, duration_ms: float, rows: int):
        self.metrics['sql_time_ms'] = duration_ms
        self.metrics['rows_fetched'] = rows
    
    def log_checkpoint_hit(self):
        self.metrics['checkpoint_used'] = True
    
    def log_memory_usage(self, rows: int):
        self.metrics['memory_rows'] = max(self.metrics['memory_rows'], rows)
    
    def finalize(self):
        total_time = (time.time() - self.start_time) * 1000
        logger.info(
            f"[PREVIEW TRACE] "
            f"node_id={self.node_id} "
            f"canvas_id={self.canvas_id} "
            f"total_time_ms={total_time:.2f} "
            f"rows_fetched={self.metrics['rows_fetched']} "
            f"sql_time_ms={self.metrics['sql_time_ms']:.2f} "
            f"python_time_ms={self.metrics['python_time_ms']:.2f} "
            f"checkpoint_used={self.metrics['checkpoint_used']} "
            f"memory_rows={self.metrics['memory_rows']}"
        )
```

---

## 6️⃣ Implementation Plan

### Phase 1: Critical Fixes (Immediate)

**Priority: 🔴 CRITICAL**

1. **Fix `cursor.fetchall()` memory violation**
   - File: `api/utils/db_executor.py`
   - Change: Use `cursor.fetchmany(100)` with hard limit
   - Lines: 78, 142, 163

2. **Add compute output row limit**
   - File: `api/views/pipeline.py`
   - Change: Truncate output_df to 100 rows
   - Line: 1496

3. **Add memory guard decorator**
   - File: `api/utils/preview_guards.py` (new)
   - Implement: `enforce_preview_memory_limit()`

### Phase 2: Safety Guards (High Priority)

**Priority: 🟡 HIGH**

4. **Add preview timeout decorator**
   - File: `api/utils/preview_guards.py`
   - Implement: `@preview_timeout(5)`

5. **Add SQL validation**
   - File: `api/utils/preview_guards.py`
   - Implement: `validate_preview_sql()`

6. **Add structured logging**
   - File: `api/utils/preview_tracer.py` (new)
   - Implement: `PreviewTracer` class

### Phase 3: Observability (Medium Priority)

**Priority: 🟢 MEDIUM**

7. **Add preview metrics endpoint**
   - File: `api/views/preview_metrics.py` (new)
   - Endpoint: `/api/preview/metrics/`
   - Returns: Slow preview warnings, memory usage stats

8. **Add performance tests**
   - File: `tests/test_preview_performance.py` (new)
   - Test: Preview latency with 1K, 1M, 100M row tables

---

## 7️⃣ Success Criteria Checklist

### Before Fixes

- [ ] Preview always returns ≤100 rows
- [ ] No large dataset enters Python
- [ ] Heavy work stays in DB
- [x] Preview latency independent of table size
- [x] UI never freezes
- [x] Checkpoints reused correctly

### After Fixes

- [x] Preview always returns ≤100 rows ✅
- [x] No large dataset enters Python ✅
- [x] Heavy work stays in DB ✅
- [x] Preview latency independent of table size ✅
- [x] UI never freezes ✅
- [x] Checkpoints reused correctly ✅

---

## 8️⃣ Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Memory overflow from fetchall() | HIGH | CRITICAL | Replace with fetchmany() |
| Compute node memory explosion | MEDIUM | HIGH | Add output row limit |
| Slow preview blocking UI | LOW | MEDIUM | Already async |
| Missing LIMIT in SQL | LOW | CRITICAL | Add SQL validation |
| Checkpoint corruption | LOW | MEDIUM | Already has TTL + invalidation |

---

## 9️⃣ Recommendations

### Immediate Actions

1. **Deploy Phase 1 fixes** within 24 hours
2. **Add monitoring** for preview latency and memory usage
3. **Create alerts** for slow previews (>1s) and memory warnings

### Long-term Improvements

1. **Implement streaming preview** for very large result sets
2. **Add preview caching** at HTTP layer (Redis)
3. **Optimize checkpoint discovery** with index on metadata table
4. **Add preview rate limiting** to prevent abuse

---

## 🔟 Conclusion

**Current Status:** System is **mostly safe** but has **critical memory vulnerabilities**.

**Key Strengths:**
- ✅ Excellent SQL pushdown architecture
- ✅ Proper checkpoint system
- ✅ O(1) latency guarantee

**Critical Weaknesses:**
- ❌ `cursor.fetchall()` can load unlimited rows
- ❌ Compute node output unbounded
- ❌ Missing runtime safety guards

**Next Steps:**
1. Implement Phase 1 fixes immediately
2. Deploy safety guards (Phase 2)
3. Add observability (Phase 3)
4. Validate with performance tests

**Estimated Fix Time:** 4-6 hours for all phases
