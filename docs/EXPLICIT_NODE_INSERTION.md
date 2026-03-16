# Explicit Node Insertion Rules

## Core Principles

**Nodes can only be added via explicit user actions.**
**No implicit start/end insertion.**
**Source node is always the root.**

## Source Node Constraints

### Rules

1. **Exactly one Source node per pipeline**
   - Only one Source node allowed
   - Attempting to add a second Source node is rejected

2. **Source node is always the root**
   - Source node has no incoming edges
   - Cannot insert nodes before Source node
   - Source node cannot be preceded by any other node

3. **Source node creation method**
   - Source nodes can ONLY be created via table drop from sidebar
   - Cannot be created via edge insertion
   - Cannot be created via output handle insertion

## Allowed Node Addition Methods

### ✅ Method 1: Edge-Based Insertion (Insert Between Nodes)

**UI Interaction:**
- User hovers over an edge between two nodes
- Edge highlights and shows "➕ Insert node" button
- User clicks button or edge

**Visual:**
```
Before: A ─────────▶ B
After:  A ──▶ X ──▶ B
```

**Backend Behavior:**
- Remove edge: `A → B`
- Add edges: `A → X` and `X → B`
- Preserve cache for A and all upstream nodes
- Invalidate cache for B and all downstream nodes

**API Endpoint:**
- `POST /api/pipeline/insert-node/`
- Requires: `canvas_id`, `new_node`, `source_node_id`, `target_node_id`

**Validation:**
- Cannot insert before Source node
- Cannot insert Source node between other nodes
- Edge must exist between source and target

### ✅ Method 2: Output Handle-Based Addition (Add After Node)

**UI Interaction:**
- User hovers over a node's output handle (right side)
- Shows "➕ Add next node" menu
- User selects node type from menu

**Visual:**
```
Before: A ──▶
After:  A ──▶ X

If A already has downstream:
Before: A ──▶ B
After:  A ──▶ B
         \
          ──▶ X  (parallel branch)
```

**Backend Behavior:**
- Add edge: `A → X`
- Do NOT remove or modify existing edges
- Parallel branches are allowed
- Preserve cache for A and upstream
- Only new branch (X and downstream) recomputes

**API Endpoint:**
- `POST /api/pipeline/add-node-after/`
- Requires: `canvas_id`, `new_node`, `source_node_id`

**Validation:**
- Cannot add Source node via output handle
- Only one Source node allowed per pipeline

## Explicitly Disallowed Actions

### ❌ Adding Node Before Source
- **Error**: "Cannot insert nodes before Source node. Source node is always the root."
- **Status**: `400 Bad Request`

### ❌ Adding Node to Empty Canvas
- **Behavior**: Generic node drops to empty canvas are disabled
- **Message**: "Please insert nodes by clicking on an edge or a node's output handle."
- **Exception**: Table drops (Source nodes) are still allowed

### ❌ Adding Source Node via Edge Insertion
- **Error**: "Source node can only be added via table drop, not via edge insertion."
- **Status**: `400 Bad Request`

### ❌ Adding Source Node via Output Handle
- **Error**: "Source node can only be added via table drop, not via output handle insertion."
- **Status**: `400 Bad Request`

### ❌ Adding Second Source Node
- **Error**: "Only one Source node is allowed per pipeline. Source node is always the root."
- **Status**: `400 Bad Request`

## Graph Invariants

### Always True

1. **Graph is a DAG**
   - No cycles allowed
   - Validated after every insertion

2. **Source node constraints**
   - Source node has no incoming edges
   - All non-source nodes have at least one incoming edge

3. **Node insertion never rebuilds pipeline**
   - Only mutates edges
   - Nodes are never recreated

## Cache & Recompute Invariants

### Edge-Based Insertion
- ✅ Preserve cache for source node and all upstream
- ❌ Invalidate cache for target node and all downstream
- 🔄 Recompute starts from inserted node

### Output Handle-Based Addition
- ✅ Preserve cache for source node and all upstream
- ❌ Invalidate cache only for new branch (new node and downstream)
- ✅ Preserve cache for existing parallel branches
- 🔄 Recompute starts from new node

## UI Requirements

### Edge Hover
- Show "➕ Insert node" button on edge hover
- Edge highlights (thicker, darker color)
- Button appears at edge center

### Output Handle Hover
- Show "➕ Add next node" menu on output handle hover
- Menu shows available node types
- Menu appears next to output handle

### Visual Feedback
- Disabled actions show error toast
- Successful insertions show success message
- Cache invalidation logged in console

## Implementation Files

### Frontend
- `frontend/src/components/Canvas/DataFlowCanvasChakra.tsx` - Main canvas component
- `frontend/src/components/Canvas/EdgeTypes.tsx` - Edge component with insert button
- `frontend/src/components/Canvas/EdgeInsertButton.tsx` - Insert button component
- `frontend/src/components/Canvas/OutputHandleMenu.tsx` - Output handle menu component
- `frontend/src/components/Canvas/NodeTypesChakra.tsx` - Node components with output handles

### Backend
- `api/views/node_management.py` - Edge-based insertion (`NodeInsertionView`)
- `api/views/node_addition.py` - Output handle-based addition (`AddNodeAfterView`)
- `api/utils/graph_utils.py` - DAG validation
- `api/utils/cache_aware_execution.py` - Cache invalidation utilities

## Success Criteria

✅ Users can only add nodes where it makes semantic sense
✅ No ambiguity about start or end
✅ Cache reuse is maximized
✅ Preview recomputation is minimal
✅ Pipeline behavior is predictable and explainable
✅ Source node constraints are enforced
✅ Only two explicit insertion methods available

## Testing Checklist

- [ ] Cannot add node before Source node
- [ ] Cannot add Source node via edge insertion
- [ ] Cannot add Source node via output handle
- [ ] Cannot add second Source node
- [ ] Edge-based insertion works correctly
- [ ] Output handle-based addition works correctly
- [ ] Parallel branches work correctly
- [ ] Cache invalidation works correctly
- [ ] DAG validation works correctly
- [ ] UI shows correct insertion options
- [ ] Error messages are clear and helpful
