# Execution Plan Validation and Freshness Check

## Problem Statement
We need to ensure that:
1. **No duplicate plans**: Same canvas + same structure = same plan_hash (already handled by PRIMARY KEY)
2. **Plan freshness**: Before executing, verify the stored plan matches the current pipeline
3. **Filter pushdown**: Filters should be pushed to source queries (future optimization)

## Solution

### 1. Plan Hash Uniqueness ✅
**Status**: IMPLEMENTED

The plan hash now includes:
- Node IDs, types, and config hashes
- Edge structure (source → target)
- Materialization points
- Total query count

This ensures:
- Different pipelines = different hashes
- Same pipeline = same hash (idempotent)
- Config changes = new hash

### 2. Plan Freshness Validation
**Status**: TO BE IMPLEMENTED

Before executing a stored plan, we must:

```python
def validate_plan_freshness(canvas_id: str, stored_plan_hash: str, current_nodes: List, current_edges: List) -> bool:
    """
    Verify that the stored plan matches the current pipeline structure.
    
    Returns:
        True if plan is fresh, False if stale
    """
    # Compute hash of current pipeline
    current_hash = compute_plan_hash(current_nodes, current_edges)
    
    # Compare with stored hash
    if current_hash != stored_plan_hash:
        logger.warning(f"[PLAN VALIDATION] Stale plan detected!")
        logger.warning(f"  Stored hash: {stored_plan_hash[:12]}...")
        logger.warning(f"  Current hash: {current_hash[:12]}...")
        return False
    
    return True
```

**Integration Point**: `/execute` endpoint should:
1. Retrieve latest plan from DB
2. Compute hash of current pipeline
3. Compare hashes
4. If mismatch: reject execution OR auto-regenerate plan

### 3. Filter Pushdown Optimization
**Status**: FUTURE WORK

Current behavior:
```sql
-- INEFFICIENT: Filter applied AFTER join
SELECT * FROM (
  SELECT * FROM staging.node_join
) filt
WHERE "_L_cmp_id" = 1
```

Desired behavior:
```sql
-- EFFICIENT: Filter pushed to source
SELECT * FROM (
  SELECT * FROM public.tool_log WHERE "cmp_id" = 1  -- Filter at source
) proj
```

**Implementation Strategy**:
1. Analyze filter predicates during plan building
2. Determine which filters can be pushed down (based on column provenance)
3. Inject WHERE clauses into source SELECT statements
4. Remove redundant filters from downstream nodes

**Complexity**: HIGH
- Requires column lineage tracking
- Must handle JOIN column renaming (e.g., `cmp_id` → `_L_cmp_id`)
- Must preserve filter semantics across transformations

## Execution Flow with Validation

```
┌─────────────────┐
│  User clicks    │
│   "Execute"     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 1. Fetch latest plan from DB   │
│    WHERE canvas_id = X          │
│    ORDER BY created_at DESC     │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 2. Compute current pipeline hash│
│    (from nodes + edges in DB)   │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ 3. Compare hashes               │
│    stored_hash == current_hash? │
└────────┬────────────────────────┘
         │
         ├─── YES ──────────────────┐
         │                          ▼
         │                   ┌──────────────┐
         │                   │ Execute plan │
         │                   └──────────────┘
         │
         └─── NO ───────────────────┐
                                    ▼
                             ┌──────────────────┐
                             │ REJECT execution │
                             │ "Plan is stale,  │
                             │  please validate"│
                             └──────────────────┘
```

## Database Queries

### Check for existing plan:
```sql
SELECT plan_hash, created_at 
FROM "CANVAS_CACHE"."execution_plans"
WHERE canvas_id = '11' 
  AND expires_at > CURRENT_TIMESTAMP
ORDER BY created_at DESC 
LIMIT 1;
```

### Validate freshness:
```python
stored_plan = get_latest_plan(connection_config, canvas_id)
if stored_plan:
    stored_hash = stored_plan.get('plan_hash')
    current_hash = compute_plan_hash(nodes, edges)
    
    if stored_hash != current_hash:
        raise PlanStaleError(
            f"Stored plan is outdated. Please re-validate the pipeline."
        )
```

## Next Steps

1. ✅ **Improve plan hash** - Include full pipeline structure
2. ⏳ **Add freshness check** - Validate before execution
3. ⏳ **Auto-regenerate option** - Allow execute to trigger re-validation
4. 🔮 **Filter pushdown** - Optimize query performance (future)

## Notes

- The PRIMARY KEY `(canvas_id, plan_hash)` already prevents true duplicates
- Multiple validations of the same pipeline will result in UPDATE (not INSERT)
- Plan expiry (24h) ensures old plans don't accumulate
- Filter pushdown is a performance optimization, not a correctness issue
