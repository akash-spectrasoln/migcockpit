# Adaptive Node Caching Strategy

## Core Philosophy

**Cache nodes based on cost and reuse — not fixed intervals.**

Do NOT cache every N nodes. Instead, cache strategic nodes that significantly reduce recomputation.

Node caches act as checkpoints, not permanent storage.

## Cache Layers

### 1️⃣ In-Memory Cache (Default)

- Used for most nodes
- Fastest access
- No DB writes
- Cleared on session end
- Memory pressure triggers spill to checkpoint

### 2️⃣ Node Cache Table (Checkpoint)

- Used selectively for strategic nodes
- Single generic table: `CANVAS_CACHE.preview_node_cache`
- Stores preview results as JSONB
- Rewritten when upstream logic changes
- Feeds downstream nodes

## Caching Rules

### ✅ Rule 1 — Filter Nodes (High Priority)

Cache a Filter node if any of the following are true:

- Row reduction is significant (≈ 30–40%+)
- Filter is frequently edited by user
- Filter separates "heavy" upstream from many downstream nodes
- Filter is a pushdown candidate

**Layer**: CHECKPOINT (persistent)

### ✅ Rule 2 — Join Nodes (Fan-out / Cost Based)

Cache a Join node if:

- Join output is used by multiple downstream nodes (fan_out > 1)
- Join is expensive to recompute
- Join sits early in a deep pipeline (depth ≥ 3)

**Layer**: CHECKPOINT (persistent)

### ✅ Rule 3 — Depth-Based (Soft Rule)

Instead of "every 5 nodes", apply:

```
IF depth_since_last_cache ≥ 5
AND node cost != LOW
THEN cache
```

**Cost Classification**:
- **LOW**: Source, rename-only Projection, trivial Compute
- **MEDIUM**: Filter, Projection with calculated columns, non-trivial Compute
- **HIGH**: Join, Aggregate

**Layer**: CHECKPOINT if depth ≥ 5, MEMORY otherwise

### ✅ Rule 4 — Memory Pressure

If in-memory preview data exceeds threshold (100MB):

- Spill to checkpoint cache
- Continue downstream from cache

**Layer**: CHECKPOINT

## Nodes That SHOULD NOT Be Cached

❌ Pure Projection (rename-only)
❌ Trivial Compute (`_output_df = _input_df`)
❌ Source node (already DB-backed)

## Cache Table Design

### Single Generic Table

```sql
CREATE TABLE CANVAS_CACHE.preview_node_cache (
    pipeline_id VARCHAR(255) NOT NULL,
    node_id VARCHAR(255) NOT NULL,
    node_version_hash VARCHAR(64) NOT NULL,
    upstream_version_hash VARCHAR(64),
    node_type VARCHAR(50),
    row_data JSONB,
    column_metadata JSONB,
    row_count INTEGER,
    created_at TIMESTAMP,
    last_accessed TIMESTAMP,
    PRIMARY KEY (pipeline_id, node_id)
)
```

**Key Features**:
- One table for all nodes (not per-node tables)
- Version hashing for cache validation
- JSONB for flexible data storage
- Automatic rewrite on conflict (ON CONFLICT DO UPDATE)

## Cache Rewrite vs Invalidation

### ❌ Bad Approach

```
Delete cache → Recompute all downstream nodes
```

### ✅ Correct Approach

```
Rewrite affected node cache → Downstream nodes automatically consume updated data
```

**Benefits**:
- Preserves downstream caches
- Faster updates
- Cleaner semantics

## Filter Pushdown + Cache Interaction

When a filter becomes pushdown-safe or its condition changes:

1. Recompile upstream SQL
2. Recompute data up to the filter
3. Rewrite the filter's node cache table
4. Keep downstream caches intact unless invalidated by lineage

## Execution Flow

```
DB → In-Memory → Optional Node Cache → In-Memory → …
```

### Flowchart

```
                 ┌──────────────┐
                 │  Start Node  │
                 └──────┬───────┘
                        │
                ┌───────▼────────┐
                │ Has Preview    │
                │ Cache Upstream?│
                └───────┬────────┘
                        │YES
                        ▼
              ┌────────────────────┐
              │ Use Cached Preview │
              └────────┬───────────┘
                       │
                       ▼
        ┌────────────────────────────────┐
        │ Is Node Costly or Strategic?   │
        │ (Filter / Join / Depth / Mem)  │
        └───────────┬────────────────────┘
                    │YES
                    ▼
        ┌────────────────────────────────┐
        │ Write / Rewrite Node Cache     │
        │ (Checkpoint)                  │
        └───────────┬────────────────────┘
                    │
                    ▼
        ┌────────────────────────────────┐
        │ Continue Downstream from Cache │
        └────────────────────────────────┘

                        │NO
                        ▼
        ┌────────────────────────────────┐
        │ Transform Locally (In-Memory) │
        └────────────────────────────────┘
```

## Example: Deep Pipeline with Checkpoints

```
Source
  ↓
Join                  ← CACHE CHECKPOINT (expensive, fan-out)
  ↓
Filter A              ← CACHE CHECKPOINT (row reduction 40%)
  ↓
Projection            ← MEMORY CACHE (low cost)
  ↓
Compute               ← MEMORY CACHE (medium cost)
  ↓
Join                  ← NO CACHE (not strategic)
  ↓
Filter B              ← CACHE CHECKPOINT (depth ≥ 5, reduction)
  ↓
Aggregate
```

## Decision Function

```python
SHOULD_CACHE(node):
  IF node.type == FILTER and reduction_estimate ≥ 0.3:
      return True, CHECKPOINT
  IF node.type == JOIN and fan_out > 1:
      return True, CHECKPOINT
  IF depth_since_last_cache ≥ 5 and node.cost != LOW:
      return True, CHECKPOINT
  IF memory_pressure == HIGH:
      return True, CHECKPOINT
  IF node.cost in [MEDIUM, HIGH]:
      return True, MEMORY
  return False, MEMORY
```

## Implementation

### Key Classes

1. **AdaptiveCacheManager**: Main cache manager
   - `should_cache()`: Decision logic
   - `get_cache()`: Retrieve from memory or checkpoint
   - `save_cache()`: Save to appropriate layer
   - `rewrite_cache()`: Rewrite cache on upstream changes

2. **CacheStrategy Utilities**: Pipeline analysis
   - `compute_depth_since_last_cache()`: Calculate depth
   - `compute_fan_out()`: Count downstream nodes
   - `is_filter_pushdown_candidate()`: Check pushdown eligibility

### Integration Points

1. **Pipeline Execution** (`api/views/pipeline.py`):
   - Check cache before executing node
   - Decide caching after node execution
   - Rewrite cache on filter pushdown

2. **SQL Compiler** (`api/utils/sql_compiler.py`):
   - Track column lineage for pushdown analysis
   - Signal cache rewrite when filters are pushed down

## Hard Rules

❌ Do NOT cache every N nodes blindly
❌ Do NOT create DB tables per node
❌ Do NOT invalidate downstream unnecessarily
❌ Do NOT mix preview and execution semantics

## Success Criteria

✅ Fast preview even for deep pipelines
✅ Minimal DB calls
✅ Stable downstream behavior
✅ Clean cache rewrites
✅ Scales to many nodes

## Future Enhancements

1. **Predictive Caching**: Cache nodes likely to be edited
2. **Cost-Based Spilling**: More sophisticated memory management
3. **Cache Warming**: Pre-cache common pipeline patterns
4. **Distributed Caching**: Share caches across sessions
