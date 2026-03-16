# Edge-Based Node Insertion Fix

## Problem Statement

The "Insert node between two nodes" feature was not working reliably. Clicking an edge did not correctly insert a node by rewiring the graph.

## Solution Implemented

### Frontend Changes

1. **Edge Click Handler** (`EdgeTypes.tsx`)
   - Edge component dispatches custom event with edge context:
     - `edgeId`: The clicked edge ID
     - `sourceNodeId`: Parent node ID (A)
     - `targetNodeId`: Child node ID (B)

2. **Node Type Selection Modal** (`NodeTypeSelectionModal.tsx`)
   - New modal component for selecting node type
   - Shows available node types (Filter, Projection, Join, etc.)
   - User-friendly UI with icons and descriptions

3. **Edge Insertion Handler** (`DataFlowCanvasChakra.tsx`)
   - Listens for `edge-insert` custom events
   - Opens node type selection modal
   - Calls backend API with correct data structure:
     ```typescript
     {
       canvas_id: number,
       new_node: { id, type, config, position },
       source_node_id: string,  // A
       target_node_id: string   // B
     }
     ```
   - Reloads canvas state after successful insertion

4. **API Client** (`api-client.ts`)
   - Added `pipelineApi.insertNode()` method
   - Calls `POST /api/pipeline/insert-node/`

### Backend Changes

1. **Mandatory Order** (`NodeInsertionView.post()`)
   
   **Step 1: Remove the existing edge**
   ```python
   # Remove edge A → B
   for edge in edges:
       if edge.source == source_node_id and edge.target == target_node_id:
           continue  # Skip this edge
       new_edges.append(edge)
   ```

   **Step 2: Create the new node**
   ```python
   new_node = {
       'id': new_node_id,
       'data': {
           'type': node_type,
           'config': config,
           'input_nodes': [source_node_id]  # X has A as input
       },
       'position': position
   }
   new_nodes = nodes + [new_node]
   ```

   **Step 3: Create new edges**
   ```python
   # Add edge A → X
   new_edges.append({
       'id': f"{source_node_id}-{new_node_id}",
       'source': source_node_id,
       'target': new_node_id,
       'sourceHandle': 'output',
       'targetHandle': 'input'
   })
   
   # Add edge X → B
   new_edges.append({
       'id': f"{new_node_id}-{target_node_id}",
       'source': new_node_id,
       'target': target_node_id,
       'sourceHandle': 'output',
       'targetHandle': 'input'
   })
   ```

   **Step 4: Update node configs**
   ```python
   # Remove A from B.input_nodes
   # Add X to B.input_nodes
   for node in new_nodes:
       if node.id == target_node_id:
           input_nodes = node.data.input_nodes
           input_nodes.remove(source_node_id)  # Remove A
           input_nodes.append(new_node_id)      # Add X
   ```

2. **Validation**
   - Verifies original edge A → B is removed
   - Verifies edges A → X and X → B exist
   - Validates DAG structure
   - Returns error if validation fails

3. **Cache Handling**
   - Preserves cache for A and all upstream nodes
   - Invalidates cache for B and all downstream nodes
   - Does NOT invalidate upstream caches

## Required Behavior (Authoritative)

### Before Insertion
```
A ─────────▶ B
```

### After Insertion
```
A ──▶ X ──▶ B
```

### Graph Structure
- ✅ Original edge A → B removed
- ✅ Edge A → X created
- ✅ Edge X → B created
- ✅ Node X created with `input_nodes: [A]`
- ✅ Node B updated: `input_nodes` removes A, adds X

### Cache Behavior
- ✅ Cache for A preserved
- ✅ Cache for upstream nodes preserved
- ❌ Cache for B invalidated
- ❌ Cache for downstream nodes invalidated

## Validation Checklist

After insertion, verify:

- [x] Graph contains exactly two edges: A → X, X → B
- [x] Original edge A → B no longer exists
- [x] Node X has `input_nodes: [A]`
- [x] Node B has `input_nodes` updated (A removed, X added)
- [x] Downstream preview updates correctly
- [x] Upstream preview remains unchanged
- [x] Cache invalidation works correctly

## API Endpoint

**POST** `/api/pipeline/insert-node/`

**Request Body:**
```json
{
  "canvas_id": 1,
  "new_node": {
    "id": "uuid",
    "type": "filter",
    "config": {},
    "position": {"x": 100, "y": 200}
  },
  "source_node_id": "node-a-id",
  "target_node_id": "node-b-id"
}
```

**Response:**
```json
{
  "success": true,
  "node_id": "new-node-uuid",
  "preserved_caches": ["node-a-id"],
  "invalidated_nodes": ["node-b-id", "node-c-id"],
  "nodes": [...],  // Updated nodes array
  "edges": [...],  // Updated edges array
  "message": "Node inserted successfully. 2 downstream caches invalidated."
}
```

## Forbidden Behavior (Must Not Happen)

❌ Keeping the original edge (A → B)
❌ Creating (A → X) without (X → B)
❌ Guessing parent/child nodes
❌ Recomputing entire pipeline
❌ Invalidating upstream caches

## Guiding Rule

**Insert in between = remove one edge, add two edges.**
**Nothing more. Nothing less.**

## Files Modified

### Frontend
- `frontend/src/components/Canvas/EdgeTypes.tsx` - Edge click handler
- `frontend/src/components/Canvas/NodeTypeSelectionModal.tsx` - New modal component
- `frontend/src/components/Canvas/DataFlowCanvasChakra.tsx` - Edge insertion handler
- `frontend/src/lib/axios/api-client.ts` - API client method
- `frontend/src/constants/server-routes.ts` - API route

### Backend
- `api/views/node_management.py` - NodeInsertionView with mandatory order
- `api/views/node_addition.py` - AddNodeAfterView (output handle-based)

## Testing

1. **Test Edge Click**
   - Click on an edge between two nodes
   - Verify modal opens with node type options
   - Select a node type
   - Verify node is inserted correctly

2. **Test Graph Structure**
   - Verify original edge is removed
   - Verify two new edges are created
   - Verify node positions are correct

3. **Test Cache Behavior**
   - Preview upstream node (should use cache)
   - Preview inserted node (should recompute)
   - Preview downstream node (should recompute)

4. **Test Validation**
   - Try inserting before Source node (should fail)
   - Try inserting Source node (should fail)
   - Verify error messages are clear
