# Quick Filter Implementation - Remaining Tasks

## Status: Projection Node ✅ COMPLETE | Quick Filter ⚙️ IN PROGRESS

### Completed Work:

#### 1. Projection Node Backend (✅ COMPLETE)
- File: `api/views.py` (lines 8393-8599)
- Functionality: Full projection execution with column selection and mapping
- Result: Projection nodes now display projected data correctly

#### 2. Quick Filter UI Foundation (✅ COMPLETE)
- File: `frontend/src/components/Canvas/TablesList.tsx`
- Changes:
  - Added `Filter` icon import
  - Added `onQuickFilter` prop to interface
  - Added Filter icon button to each table item
  - Click handler triggers `onQuickFilter(table, sourceId)`

### Remaining Implementation:

#### Step 1: Update SourceConnectionsSidebar.tsx
**File**: `frontend/src/components/Canvas/SourceConnectionsSidebar.tsx`

Add to interface (line ~41-45):
```typescript
interface SourceConnectionsSidebarProps {
  selectedSourceId?: number
  onSourceSelect?: (source: Source) => void
  onTableDrag?: (table: { schema: string; table_name: string }) => void
  onQuickFilter?: (table: { schema: string; table_name: string }, sourceId: number) => void
}
```

Update component signature (line ~47-51):
```typescript
export const SourceConnectionsSidebar: React.FC<SourceConnectionsSidebarProps> = ({
  selectedSourceId,
  onSourceSelect,
  onTableDrag,
  onQuickFilter,
}) => {
```

Pass prop to TablesList (line ~258-262):
```typescript
<TablesList
  sourceId={source.source_id}
  onTableDrag={onTableDrag}
  onQuickFilter={onQuickFilter}
  forceRefresh={forceRefreshSourceId === source.source_id}
/>
```

#### Step 2: Implement handleQuickFilter in Canvas Page
**File**: `frontend/src/pages/CanvasPage.tsx` (or similar)

Add handler function:
```typescript
const handleQuickFilter = useCallback((table: { schema: string; table_name: string }, sourceId: number) => {
  // 1. Find or create Source node
  const existingSourceNode = nodes.find(
    n => n.data.type === 'source' && 
         n.data.config?.sourceId === sourceId &&
         n.data.config?.tableName === table.table_name
  )
  
  let sourceNode
  if (existingSourceNode) {
    sourceNode = existingSourceNode
  } else {
    // Create new source node
    const newSourceNode = {
      id: `source-${Date.now()}`,
      type: 'source',
      position: { x: 100, y: 100 },
      data: {
        id: `source-${Date.now()}`,
        label: table.table_name,
        type: 'source',
        config: {
          sourceId,
          tableName: table.table_name,
          schema: table.schema,
        }
      }
    }
    sourceNode = newSourceNode
    setNodes(nds => [...nds, newSourceNode])
  }
  
  // 2. Create Filter node
  const filterNode = {
    id: `filter-${Date.now()}`,
    type: 'filter',
    position: { 
      x: sourceNode.position.x + 250, 
      y: sourceNode.position.y 
    },
    data: {
      id: `filter-${Date.now()}`,
      label: `Filter: ${table.table_name}`,
      type: 'filter',
      config: {
        sourceId,
        tableName: table.table_name,
        schema: table.schema,
        conditions: []
      }
    }
  }
  
  // 3. Create edge
  const edge = {
    id: `edge-${sourceNode.id}-${filterNode.id}`,
    source: sourceNode.id,
    target: filterNode.id,
    type: 'smoothstep'
  }
  
  // 4. Add filter node and edge
  setNodes(nds => [...nds, filterNode])
  setEdges(eds => [...eds, edge])
  
  // 5. Select the filter node
  setSelectedNodeId(filterNode.id)
  
  // 6. Open filter configuration panel (if needed)
  // This depends on your panel state management
  
}, [nodes, setNodes, setEdges])
```

Pass to sidebar:
```typescript
<SourceConnectionsSidebar
  selectedSourceId={selectedSourceId}
  onSourceSelect={handleSourceSelect}
  onTableDrag={handleTableDrag}
  onQuickFilter={handleQuickFilter}
/>
```

#### Step 3: Auto-execute Filter
The filter will auto-execute when selected due to existing logic in `TableDataPanel.tsx` (lines 170-274).

### Testing Checklist:
- [ ] Click Filter icon on a table in sidebar
- [ ] Verify Source node is created (or reused if exists)
- [ ] Verify Filter node is created and connected
- [ ] Verify Filter config panel opens
- [ ] Add filter conditions and save
- [ ] Verify filtered data appears in preview panel
- [ ] Verify no duplicate nodes are created on second click

### Files Modified:
1. ✅ `api/views.py` - Projection execution
2. ✅ `frontend/src/components/Canvas/TablesList.tsx` - Filter icon
3. ⚙️ `frontend/src/components/Canvas/SourceConnectionsSidebar.tsx` - Pass through prop
4. ⚙️ `frontend/src/pages/CanvasPage.tsx` - Implement handler

