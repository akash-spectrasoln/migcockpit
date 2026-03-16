# Node Insertion and Deletion with Cache-Aware Recomputation

## Core Principles

**Pipelines are DAGs, not linear scripts.**
**Nodes are replaceable units, not hard-linked steps.**

### Key Invariants

1. Adding a node rewires edges
2. Deleting a node bridges its parents to its children
3. Cache invalidation happens only downstream
4. Recompute resumes from nearest upstream cache

## ADD NODE (Insert Between)

### Before
```
A ──▶ B ──▶ C
```

### After Insert X Between B and C
```
A ──▶ B ──▶ X ──▶ C
```

### What Happens

1. **Edge Rewiring**:
   - Remove edge: `B → C`
   - Add edges: `B → X` and `X → C`

2. **Cache Behavior**:
   - ✅ Cache for A and B remains valid
   - ❌ Cache for C and downstream nodes becomes invalid
   - ⚪ X has no cache yet

3. **Preview Behavior**:
   - Recompute from nearest upstream cache
   - Flow: `Cache(B) → X → C → ...`
   - ✅ No DB re-fetch
   - ✅ Minimal recomputation
   - ✅ Fast UI response

### API Endpoint

**POST** `/api/pipeline/insert-node/`

**Request Body**:
```json
{
  "canvas_id": 1,
  "new_node": {
    "id": "uuid",
    "type": "filter",
    "config": {...},
    "position": {"x": 100, "y": 200}
  },
  "source_node_id": "node-b-id",
  "target_node_id": "node-c-id"
}
```

**Response**:
```json
{
  "success": true,
  "node_id": "new-node-uuid",
  "preserved_caches": ["node-b-id"],
  "invalidated_nodes": ["node-c-id", "node-d-id"],
  "message": "Node inserted successfully. 2 downstream caches invalidated."
}
```

## DELETE NODE (Auto-Bridge)

### Before
```
A ──▶ B ──▶ X ──▶ C ──▶ D
```

### After Delete X
```
A ──▶ B ──▶ C ──▶ D
```

### What Happens

1. **Identify Parents & Children**:
   - Parents of X: `{B}`
   - Children of X: `{C}`

2. **Reconnect (Auto-Bridge)**:
   - Remove edges: `B → X` and `X → C`
   - Add edge: `B → C`

3. **Metadata Compatibility Check**:
   - Validate `B.output_metadata` satisfies `C.input_metadata`
   - If incompatible:
     - Mark C as invalid
     - Show UI warning
     - Do NOT crash pipeline

4. **Cache Handling**:
   - ❌ Delete cache of X
   - ❌ Invalidate caches for C and downstream
   - ✅ Preserve caches for A, B

### API Endpoint

**POST** `/api/pipeline/delete-node/`

**Request Body**:
```json
{
  "canvas_id": 1,
  "node_id": "node-x-id"
}
```

**Response**:
```json
{
  "success": true,
  "deleted_node_id": "node-x-id",
  "bridged_edges": ["node-b-id → node-c-id"],
  "invalidated_nodes": ["node-c-id", "node-d-id"],
  "warnings": ["Metadata incompatibility: Filter requires columns {col1} which are not in parent output"],
  "message": "Node deleted successfully. 2 downstream caches invalidated."
}
```

## RECOMPUTE FROM CACHE

### API Endpoint

**POST** `/api/pipeline/recompute/`

**Request Body**:
```json
{
  "canvas_id": 1,
  "target_node_id": "node-c-id"
}
```

**Response**:
```json
{
  "success": true,
  "nearest_cache_node": "node-b-id",
  "message": "Recompute should start from cached node node-b-id",
  "recompute_path": ["node-b-id", "node-x-id", "node-c-id"]
}
```

## Implementation Details

### Edge Rewiring Logic

**Insert Node**:
```python
# Remove: B → C
# Add: B → X, X → C
```

**Delete Node**:
```python
# Remove: B → X, X → C
# Add: B → C (auto-bridge)
```

### Cache Invalidation

**Insert**:
- Invalidate: Target node and all downstream nodes
- Preserve: All upstream nodes

**Delete**:
- Delete: Removed node cache
- Invalidate: All children and their descendants
- Preserve: All upstream nodes

### Metadata Compatibility

Checks performed before auto-bridging:

1. **Filter**: Required columns exist in parent output
2. **Projection**: Selected base columns exist in parent output
3. **Join**: Parent has output columns (both inputs needed)
4. **Aggregate**: Grouping/aggregation columns exist in parent output
5. **Compute**: Static validation difficult (fails at execution if incompatible)

### Cache-Aware Execution

**Flow**:
1. Check if target node is cached → Use cache
2. If not cached, find nearest upstream cache
3. Resume execution from cache
4. Execute only nodes from cache to target

**Benefits**:
- ✅ No DB re-fetch unless required
- ✅ Minimal recomputation
- ✅ Fast UI response
- ✅ Scales with pipeline depth

## Example Scenarios

### Scenario 1: Insert Filter After Join

**Before**:
```
Source → Join → Projection
```

**After Insert Filter**:
```
Source → Join → Filter → Projection
```

**Cache Behavior**:
- Join cache: ✅ Preserved
- Projection cache: ❌ Invalidated
- Filter cache: ⚪ Created on first execution

**Recompute**:
- Resume from Join cache
- Execute: Join (cached) → Filter → Projection

### Scenario 2: Delete Filter

**Before**:
```
Source → Join → Filter → Projection
```

**After Delete Filter**:
```
Source → Join → Projection
```

**Cache Behavior**:
- Join cache: ✅ Preserved
- Filter cache: ❌ Deleted
- Projection cache: ❌ Invalidated (needs recompute)

**Recompute**:
- Resume from Join cache
- Execute: Join (cached) → Projection

### Scenario 3: Insert Node with Metadata Incompatibility

**Before**:
```
Source(id, name) → Projection(select: id, name)
```

**After Insert Filter**:
```
Source(id, name) → Filter(status = 'ACTIVE') → Projection(select: id, name)
```

**Issue**: Filter requires `status` column which doesn't exist in Source

**Behavior**:
- Insert succeeds (edge rewiring works)
- Filter marked as invalid
- UI shows warning
- Preview fails at Filter execution (expected)

## Code Structure

### Key Files

1. **`api/views/node_management.py`**:
   - `NodeInsertionView`: Handles node insertion
   - `NodeDeletionView`: Handles node deletion with auto-bridging
   - `PipelineRecomputeView`: Finds recompute path from cache

2. **`api/utils/cache_aware_execution.py`**:
   - `find_nearest_upstream_cache()`: Finds nearest cache upstream
   - `get_execution_path_from_cache()`: Gets execution path
   - `invalidate_downstream_caches()`: Invalidates downstream caches
   - `validate_metadata_compatibility()`: Validates metadata compatibility

### Key Functions

**Insert Node**:
- Rewires edges: `B → C` becomes `B → X → C`
- Invalidates downstream caches
- Preserves upstream caches

**Delete Node**:
- Finds parents and children
- Auto-bridges: `Parent → X → Child` becomes `Parent → Child`
- Validates metadata compatibility
- Invalidates downstream caches
- Preserves upstream caches

**Recompute**:
- Finds nearest upstream cache
- Returns execution path from cache to target
- Enables incremental execution

## Success Criteria

✅ Nodes can be added anywhere in pipeline
✅ Nodes can be deleted safely
✅ Downstream nodes update correctly
✅ Preview remains fast (resumes from cache)
✅ Cache reuse is maximized
✅ Metadata incompatibilities are detected
✅ Pipeline doesn't crash on incompatibility

## Hard Rules

❌ Do NOT recreate pipeline on insert/delete
❌ Do NOT invalidate upstream caches
❌ Do NOT force DB re-fetch
❌ Do NOT silently break metadata contracts
❌ Do NOT crash on metadata incompatibility

## Final Guiding Rule

**Insert rewires forward.**
**Delete bridges backward.**
**Recompute flows downstream only.**
