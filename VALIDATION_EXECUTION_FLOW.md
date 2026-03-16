# Validation & Execution Flow with Filter Pushdown

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER CLICKS "VALIDATE"                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: Validate DAG Structure                                  │
│  - Check for cycles                                             │
│  - Verify source/destination nodes exist                        │
│  - Validate JOIN configurations                                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: Analyze Filter Pushdown Opportunities                   │
│  - Build column lineage (track where columns come from)         │
│  - Identify calculated columns                                  │
│  - Analyze each filter node:                                    │
│    • Can this filter be pushed to source?                       │
│    • Is it on a calculated column? (substitute expression)      │
│    • Is it after a JOIN? (handle column renaming)               │
│  - Generate pushdown_plan: {node_id: [filters_to_inject]}      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: Detect Materialization Points                           │
│  - Identify which nodes need staging tables                     │
│  - Mark JOIN nodes, complex transformations                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 4: Build Execution Plan (WITH PUSHDOWN)                    │
│  - Compile SQL for each node                                    │
│  - Inject pushed-down filters into source queries               │
│  - Example:                                                      │
│    • Source: SELECT * FROM orders WHERE (qty * price) > 1000    │
│    • JOIN: Already filtered, processes less data                │
│  - Organize into parallel execution levels                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 5: Compute Plan Hash                                       │
│  - Hash = SHA256(nodes + edges + materialization_points)        │
│  - Same pipeline → Same hash (idempotent)                       │
│  - Different pipeline → Different hash                          │
│  - Note: Hash does NOT include pushdown algorithm version       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 6: Check Database for Existing Plan                        │
│  SELECT * FROM CANVAS_CACHE.execution_plans                     │
│  WHERE canvas_id = ? AND plan_hash = ?                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
                ▼                         ▼
         ┌──────────┐              ┌──────────┐
         │ FOUND    │              │ NOT FOUND│
         └─────┬────┘              └─────┬────┘
               │                         │
               │                         ▼
               │              ┌─────────────────────────┐
               │              │ Save New Plan to DB     │
               │              │  - plan_data (JSON)     │
               │              │  - plan_hash            │
               │              │  - expires_at (+24h)    │
               │              └─────┬───────────────────┘
               │                    │
               └────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Return Validation Result                                        │
│  {                                                               │
│    "success": true,                                             │
│    "metadata": {                                                │
│      "plan_hash": "abc123...",                                  │
│      "plan_persisted": true,                                    │
│      "staging_schema": "staging_job_...",                       │
│      "levels": 3,                                               │
│      "total_queries": 4                                         │
│    }                                                             │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════
                    LATER: USER CLICKS "EXECUTE"
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│ Step 1: Retrieve Latest Plan from DB                            │
│  SELECT plan_data FROM CANVAS_CACHE.execution_plans             │
│  WHERE canvas_id = ? AND expires_at > NOW()                     │
│  ORDER BY created_at DESC LIMIT 1                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: Validate Plan Freshness (FUTURE)                        │
│  - Compute hash of current pipeline                             │
│  - Compare with stored plan_hash                                │
│  - If mismatch → REJECT or auto-regenerate                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: Execute Plan Level by Level                             │
│  - Level 0: Source nodes (parallel) - WITH PUSHED FILTERS       │
│  - Level 1: JOINs (parallel within level)                       │
│  - Level 2: Transformations (parallel within level)             │
│  - ...                                                           │
│  - Final: INSERT into destination                               │
│  - Cleanup: DROP staging schema                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Questions & Answers

### Q1: When does filter pushdown happen?
**A:** During **validation** (Step 2), before building the execution plan.

### Q2: If a plan already exists, do we rewrite it?
**A:** It depends:
- **Same pipeline structure** → Same hash → **Use existing plan** (no rewrite)
- **Different pipeline** → Different hash → **Create new plan** (with pushdown)

### Q3: What if we improve the pushdown algorithm later?
**A:** The plan hash is based on **pipeline structure**, not the optimization algorithm:
- **Existing plans** will continue to use the old (less optimized) SQL
- **New validations** will use the improved algorithm
- To force re-optimization: User must click "Validate" again

**Future Enhancement:** Add a "force refresh" option or version the algorithm in the hash.

### Q4: Does pushdown affect the plan hash?
**A:** No, the hash is computed from:
- Node IDs, types, and configs
- Edge structure
- Materialization points

The **optimizations** (pushdown) are applied during plan building but don't change the hash. This means:
- ✅ Same pipeline always gets same hash (good for caching)
- ⚠️ Algorithm improvements don't invalidate old plans (may want to version this)

---

## Example: Filter Pushdown in Action

### Pipeline
```
Source(orders) → Projection(total = qty * price) → Filter(total > 1000) → Destination
```

### Step 2: Pushdown Analysis
```python
pushdown_plan = {
  "source_node_id": [
    {
      "expression": "quantity * unit_price",
      "operator": ">",
      "value": 1000,
      "where_clause": "(quantity * unit_price) > 1000"
    }
  ]
}
```

### Step 4: Execution Plan (WITHOUT Pushdown)
```json
{
  "levels": [
    {
      "level_num": 0,
      "queries": [{
        "sql": "CREATE TABLE staging.source AS SELECT * FROM orders"
      }]
    },
    {
      "level_num": 1,
      "queries": [{
        "sql": "CREATE TABLE staging.projection AS SELECT *, quantity * unit_price AS total FROM staging.source"
      }]
    },
    {
      "level_num": 2,
      "queries": [{
        "sql": "CREATE TABLE staging.filter AS SELECT * FROM staging.projection WHERE total > 1000"
      }]
    }
  ]
}
```

### Step 4: Execution Plan (WITH Pushdown)
```json
{
  "levels": [
    {
      "level_num": 0,
      "queries": [{
        "sql": "CREATE TABLE staging.source AS SELECT *, quantity * unit_price AS total FROM orders WHERE (quantity * unit_price) > 1000"
      }]
    }
  ]
}
```

**Result:** 
- Processes only 1% of data (if filter is selective)
- Eliminates 2 staging tables
- Reduces from 3 levels to 1 level

---

## Database Schema

```sql
CREATE TABLE "CANVAS_CACHE"."execution_plans" (
    canvas_id VARCHAR(255),
    plan_hash VARCHAR(64),           -- SHA-256 of pipeline structure
    plan_data JSONB,                 -- Full execution plan (with pushdown)
    staging_schema VARCHAR(255),
    total_queries INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,            -- Auto-expires after 24 hours
    PRIMARY KEY (canvas_id, plan_hash)  -- Prevents duplicates
);
```

**Key Points:**
- `plan_hash` ensures same pipeline = same plan (no duplicates)
- `expires_at` prevents stale plans from accumulating
- `plan_data` contains the optimized SQL (with pushdown already applied)

---

## Implementation Status

| Feature | Status | Notes |
|---------|--------|-------|
| **Filter pushdown analysis** | ✅ Implemented | `filter_optimizer.py` |
| **Integration with validation** | ✅ Implemented | `main.py` Step 2 |
| **SQL injection** | ⏳ TODO | Need to update `sql_compiler.py` |
| **Plan freshness check** | ⏳ TODO | Before execution |
| **Force refresh option** | ⏳ TODO | UI enhancement |

---

## Next Steps

1. **Update SQL Compiler** - Modify `sql_compiler.py` to:
   - Accept `filter_pushdown_plan` in config
   - Inject WHERE clauses into source queries
   - Handle expression substitution for calculated columns

2. **Add Freshness Check** - In `/execute` endpoint:
   - Compute hash of current pipeline
   - Compare with stored plan hash
   - Reject if mismatch (or auto-regenerate)

3. **Test & Validate** - Ensure:
   - Pushdown doesn't break existing queries
   - Performance improvements are measurable
   - Edge cases are handled (aggregates, window functions)
