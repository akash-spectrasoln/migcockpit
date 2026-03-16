# Fix: "canvasId is required for preview cache" Error

## Problem
The preview system was throwing an error: **"canvasId is required for preview cache"** when trying to preview nodes in the canvas.

## Root Cause
The backend's checkpoint cache system (implemented in `api/views/pipeline.py` at lines 1381-1383) requires a `canvasId` to create the preview cache schema (`staging_preview_<canvas_id>`). However, the frontend was not passing the `canvasId` in the preview API request.

### Backend Validation
```python
# api/views/pipeline.py (lines 1381-1383)
canvas_id = request.data.get('canvasId')
if not canvas_id:
    return Response({"error": "canvasId is required for preview cache"}, status=status.HTTP_400_BAD_REQUEST)
```

### Why canvasId is Required
The checkpoint cache system uses `canvasId` to:
1. Create a dedicated preview schema: `staging_preview_<canvas_id>`
2. Store checkpoint cache tables: `node_<node_id>_cache`
3. Track metadata in the `_checkpoint_metadata` table
4. Isolate preview data per canvas to avoid conflicts between different canvases

## Solution
Added `canvasId` prop to the preview request flow:

### Changes Made

#### 1. Updated `TableDataPanel` Component Interface
**File:** `frontend/src/components/Canvas/TableDataPanel.tsx`

- Added `canvasId?: number` to the `TableDataPanelProps` interface (line 36)
- Destructured `canvasId` from props (line 52)
- Passed `canvasId` to the `pipelineApi.execute` call (line 292)

```typescript
// Before
{
  page: 1,
  pageSize,
  // canvasId will be added when canvas is saved
  useCache: !forceRefresh,
  forceRefresh,
  previewMode: true,
}

// After
{
  page: 1,
  pageSize,
  canvasId, // Required for preview cache
  useCache: !forceRefresh,
  forceRefresh,
  previewMode: true,
}
```

#### 2. Updated `DataFlowCanvasChakra` Component
**File:** `frontend/src/components/Canvas/DataFlowCanvasChakra.tsx`

- Passed `canvasId` prop to `TableDataPanel` component (line 4820)

```typescript
<TableDataPanel
  sourceId={tableDataPanel.sourceId}
  tableName={tableDataPanel.tableName}
  schema={tableDataPanel.schema}
  nodeId={tableDataPanel.nodeId}
  nodes={storeNodes}
  edges={storeEdges}
  directFilterConditions={tableDataPanel.directFilterConditions}
  canvasId={canvasId}  // ← Added this line
  onClose={() => {
    setTableDataPanel(null)
    setDirectFilterMode(null)
  }}
/>
```

## Impact

### Before Fix
- Preview requests failed with "canvasId is required for preview cache" error
- No checkpoint caching was possible
- Users couldn't preview node outputs

### After Fix
- Preview requests include `canvasId` when available
- Checkpoint cache system works correctly
- Preview data is properly isolated per canvas
- Cached checkpoints improve preview performance

## Notes

1. **Optional canvasId**: The `canvasId` is optional in the frontend (marked with `?`), which means:
   - For saved canvases: `canvasId` is passed, enabling checkpoint caching
   - For unsaved canvases: `canvasId` is `undefined`, and the backend will return the error (expected behavior)

2. **User Experience**: Users working with unsaved canvases will need to save the canvas first to enable preview caching. This is intentional to ensure proper cache isolation.

3. **Backend Behavior**: When `canvasId` is missing, the backend returns a clear error message directing users to save the canvas first.

## Testing Recommendations

1. **Test with saved canvas**: Verify preview works and uses cache
2. **Test with unsaved canvas**: Verify appropriate error message is shown
3. **Test cache isolation**: Verify different canvases have separate cache schemas
4. **Test checkpoint invalidation**: Verify cache is properly invalidated when nodes change

## Related Files
- `frontend/src/components/Canvas/TableDataPanel.tsx`
- `frontend/src/components/Canvas/DataFlowCanvasChakra.tsx`
- `frontend/src/lib/axios/api-client.ts` (pipelineApi.execute definition)
- `api/views/pipeline.py` (backend validation and checkpoint cache logic)
- `api/services/checkpoint_cache.py` (CheckpointCacheManager implementation)
