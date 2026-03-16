# Filter Builder UI - Blinking/Flickering & Layout Issues - PRODUCTION FIX

## 🔴 ROOT CAUSE ANALYSIS

### **Issue 1: Infinite Re-render Loop (CRITICAL)**
**Location:** `EnhancedFilterConfigPanel.tsx`, Lines 158-245

**Problem:**
```typescript
useEffect(() => {
  // ... code ...
  loadAvailableColumns() // ❌ Function called without dependency
}, [node?.id, nodes, edges, directFilterMode])
```

**Why it causes blinking:**
- `loadAvailableColumns()` is called on EVERY render when `nodes` or `edges` change
- `nodes` and `edges` are **new array references** on every parent re-render
- This triggers the effect → calls `loadAvailableColumns()` → updates state → triggers re-render → repeat
- **Result:** Continuous flickering as the component re-renders in a loop

### **Issue 2: Unstable Dependencies in useEffect**
**Location:** Lines 248-308, 311-315

**Problem:**
```typescript
useEffect(() => {
  // Depends on nodes and edges arrays
}, [node?.id, node?.data.input_nodes, nodes, edges, directFilterMode])
```

**Why it's unstable:**
- `nodes` and `edges` are **array references** that change on every canvas update
- Even if the content is the same, the reference changes
- React sees this as a "new" dependency and re-runs the effect
- **Result:** Excessive re-renders and flickering

### **Issue 3: State Updates During Render**
**Location:** Lines 199-235

**Problem:**
```typescript
if (node.id !== lastNodeId) {
  setConditions(normalizedConditions) // ❌ State update in useEffect
  setExpression(savedExpression)
  setMode(savedMode)
  setLastNodeId(node.id)
} else {
  if (savedConditions.length > 0 && conditions.length === 0) {
    setConditions(normalizedConditions) // ❌ Another state update
  }
}
```

**Why it causes issues:**
- Multiple `setState` calls in a single effect
- Each `setState` triggers a re-render
- Conditional state updates create unpredictable behavior
- **Result:** Multiple renders per interaction, causing blink

### **Issue 4: CSS Layout Constraints**
**Location:** Lines 1288-1296, 1441

**Problem:**
```typescript
<Box
  w="400px"
  h="100%"  // ❌ Fixed height prevents expansion
  display="flex"
  flexDirection="column"
  overflow="hidden"  // ❌ Prevents vertical expansion
>
  {/* ... */}
  <TabPanel p={4} overflowY="auto" flex={1}>  // ❌ Scroll instead of expand
```

**Why it doesn't expand:**
- Parent has `overflow="hidden"` - prevents natural height expansion
- `h="100%"` forces it to fill parent, not expand beyond
- `TabPanel` has `overflowY="auto"` - creates scroll instead of expanding
- **Result:** Panel doesn't grow when conditions are added

---

## 🔍 CONFIRMING DEBUG STEPS

### **Step 1: Detect Re-render Loop**
```typescript
// Add to component top
useEffect(() => {
  console.log('🔄 RENDER:', {
    nodeId: node?.id,
    nodesLength: nodes?.length,
    edgesLength: edges?.length,
    conditionsLength: conditions.length
  })
})
```

**Expected:** Should log once per user action  
**Actual (bug):** Logs continuously in a loop

### **Step 2: Track State Updates**
```typescript
// Add before each setState
console.log('📝 STATE UPDATE:', stateVariable, newValue)
```

**Expected:** One log per user interaction  
**Actual (bug):** Multiple logs for single action

### **Step 3: Measure Layout**
```typescript
// Add ref to container
const containerRef = useRef<HTMLDivElement>(null)

useEffect(() => {
  if (containerRef.current) {
    console.log('📐 HEIGHT:', containerRef.current.scrollHeight)
  }
}, [conditions])
```

**Expected:** Height increases when conditions added  
**Actual (bug):** Height stays constant (400px or parent height)

---

## ✅ FIXED REACT CODE

### **Fix 1: Stabilize useEffect Dependencies**

```typescript
// BEFORE (Lines 158-245)
useEffect(() => {
  if (directFilterMode) {
    loadAvailableColumnsForDirectFilter()
    // ...
  } else if (node) {
    // ...
    loadAvailableColumns() // ❌ Unstable
  }
}, [node?.id, nodes, edges, directFilterMode]) // ❌ Unstable arrays

// AFTER - Use useMemo to stabilize node lookups
const inputNodeId = useMemo(() => {
  if (!node || directFilterMode) return null
  
  const inputNodeIds = node.data.input_nodes || []
  if (inputNodeIds.length > 0) return inputNodeIds[0]
  
  const inputEdge = edges?.find((e) => e.target === node.id)
  return inputEdge?.source || null
}, [node?.id, node?.data.input_nodes, edges?.length, directFilterMode])

const inputNode = useMemo(() => {
  if (!inputNodeId || !nodes) return null
  return nodes.find((n) => n.id === inputNodeId) || null
}, [inputNodeId, nodes?.length])

// Separate effect for loading conditions (runs once per node change)
useEffect(() => {
  if (!node || directFilterMode) return
  
  const config = node.data.config || {}
  const savedConditions = config.conditions || []
  const savedExpression = config.expression || ''
  const savedMode = config.mode || 'builder'
  
  // Only update if node changed
  if (node.id !== lastNodeId) {
    const normalized = Array.isArray(savedConditions)
      ? savedConditions.map((c: any) => ({
          id: c.id || `condition-${Date.now()}-${Math.random()}`,
          column: c.column || '',
          operator: c.operator || '=',
          value: c.value,
          logicalOperator: c.logicalOperator || 'AND',
        }))
      : []
    
    setConditions(normalized)
    setExpression(savedExpression || '')
    setMode(savedMode || 'builder')
    setLastNodeId(node.id)
  }
}, [node?.id]) // ✅ Only node.id dependency

// Separate effect for loading columns (runs when input node changes)
useEffect(() => {
  if (!node || directFilterMode) return
  if (!inputNode) {
    setAvailableColumns([])
    return
  }
  
  // Load columns from input node metadata
  if (inputNode.data.output_metadata?.columns) {
    const cols = inputNode.data.output_metadata.columns.map((col: any) => ({
      name: typeof col === 'string' ? col : (col.name || col.column_name),
      type: typeof col === 'string' ? 'TEXT' : (col.datatype || col.data_type || 'TEXT'),
    }))
    setAvailableColumns(cols)
    setHasUpstreamMetadata(true)
  } else {
    // Async load if needed
    loadAvailableColumns()
  }
}, [inputNode?.id, inputNode?.data.output_metadata]) // ✅ Stable dependencies
```

### **Fix 2: Batch State Updates**

```typescript
// BEFORE (Lines 510-519)
const addCondition = () => {
  const newCondition: FilterCondition = {
    id: `condition-${Date.now()}`,
    column: '',
    operator: '=',
    value: '',
    logicalOperator: conditions.length > 0 ? 'AND' : undefined,
  }
  setConditions([...conditions, newCondition]) // ❌ Single setState
}

// AFTER - Use functional update to avoid stale closure
const addCondition = useCallback(() => {
  setConditions((prev) => [
    ...prev,
    {
      id: `condition-${Date.now()}-${Math.random()}`, // ✅ More unique
      column: '',
      operator: '=',
      value: '',
      logicalOperator: prev.length > 0 ? 'AND' : undefined,
    },
  ])
}, []) // ✅ No dependencies - stable function
```

### **Fix 3: Memoize Expensive Computations**

```typescript
// BEFORE (Lines 1482-1547) - Inline map in render
{conditions.map((condition, index) => (
  <Box key={condition.id}> {/* ❌ Recreated on every render */}
    {/* ... */}
  </Box>
))}

// AFTER - Memoize condition rendering
const ConditionItem = React.memo<{
  condition: FilterCondition
  index: number
  onUpdate: (id: string, updates: Partial<FilterCondition>) => void
  onRemove: (id: string) => void
  availableColumns: Array<{ name: string; type: string }>
}>(({ condition, index, onUpdate, onRemove, availableColumns }) => {
  return (
    <Box key={condition.id}>
      {index > 0 && (
        <HStack mb={2}>
          <Select
            size="sm"
            value={condition.logicalOperator || 'AND'}
            onChange={(e) =>
              onUpdate(condition.id, {
                logicalOperator: e.target.value as 'AND' | 'OR',
              })
            }
            w="80px"
          >
            <option value="AND">AND</option>
            <option value="OR">OR</option>
          </Select>
          <Text fontSize="xs" color="gray.500">
            (previous condition)
          </Text>
        </HStack>
      )}
      {/* Rest of condition UI */}
    </Box>
  )
})

// In main component
const updateCondition = useCallback((id: string, updates: Partial<FilterCondition>) => {
  setConditions((prev) =>
    prev.map((c) => {
      if (c.id === id) {
        const cleanedUpdates = { ...updates }
        if (updates.column) {
          cleanedUpdates.column = updates.column.includes('(')
            ? updates.column.split('(')[0].trim()
            : updates.column.trim()
        }
        return { ...c, ...cleanedUpdates }
      }
      return c
    })
  )
  setValidationError(null)
}, [])

const removeCondition = useCallback((id: string) => {
  setConditions((prev) => prev.filter((c) => c.id !== id))
}, [])

// In render
{conditions.map((condition, index) => (
  <ConditionItem
    key={condition.id}
    condition={condition}
    index={index}
    onUpdate={updateCondition}
    onRemove={removeCondition}
    availableColumns={availableColumns}
  />
))}
```

---

## 🎨 REQUIRED CSS FIXES

### **Fix 1: Allow Vertical Expansion**

```typescript
// BEFORE (Lines 1288-1296)
<Box
  w="400px"
  h="100%"  // ❌ Forces fixed height
  bg={bg}
  borderLeftWidth="1px"
  borderColor={borderColor}
  display="flex"
  flexDirection="column"
  overflow="hidden"  // ❌ Prevents expansion
>

// AFTER
<Box
  w="400px"
  minH="100%"  // ✅ Minimum height, can expand
  maxH="100vh"  // ✅ Limit to viewport height
  bg={bg}
  borderLeftWidth="1px"
  borderColor={borderColor}
  display="flex"
  flexDirection="column"
  overflow="visible"  // ✅ Allow natural expansion
>
```

### **Fix 2: Fix TabPanel Scrolling**

```typescript
// BEFORE (Line 1441)
<TabPanel p={4} overflowY="auto" flex={1}>

// AFTER
<TabPanel 
  p={4} 
  overflowY="auto"  // Keep scroll for long lists
  flex="1 1 auto"  // ✅ Allow shrink and grow
  minH="0"  // ✅ Allow flexbox to work properly
>
```

### **Fix 3: Proper VStack Spacing**

```typescript
// BEFORE (Line 1465)
<VStack align="stretch" spacing={4}>

// AFTER
<VStack 
  align="stretch" 
  spacing={4}
  w="full"  // ✅ Full width
  pb={4}  // ✅ Bottom padding for last item
>
```

---

## 🛡️ PREVENTIVE BEST PRACTICES

### **1. Use Stable Keys for Lists**
```typescript
// ❌ BAD - Index as key
{conditions.map((condition, index) => (
  <Box key={index}>

// ✅ GOOD - Stable unique ID
{conditions.map((condition) => (
  <Box key={condition.id}>
```

### **2. Memoize Callbacks**
```typescript
// ❌ BAD - New function on every render
<Button onClick={() => updateCondition(id, { value: e.target.value })}>

// ✅ GOOD - Stable callback
const handleUpdate = useCallback((id: string, value: any) => {
  updateCondition(id, { value })
}, [updateCondition])

<Button onClick={() => handleUpdate(id, e.target.value)}>
```

### **3. Avoid Object/Array Dependencies**
```typescript
// ❌ BAD - Array reference changes
useEffect(() => {
  // ...
}, [nodes, edges])

// ✅ GOOD - Use length or specific IDs
useEffect(() => {
  // ...
}, [nodes?.length, edges?.length, specificNodeId])
```

### **4. Use useMemo for Derived State**
```typescript
// ❌ BAD - Computed in render
const inputNode = nodes.find(n => n.id === inputNodeId)

// ✅ GOOD - Memoized
const inputNode = useMemo(
  () => nodes?.find(n => n.id === inputNodeId),
  [nodes?.length, inputNodeId]
)
```

### **5. Batch State Updates**
```typescript
// ❌ BAD - Multiple setState calls
setConditions(newConditions)
setExpression(newExpression)
setMode(newMode)

// ✅ GOOD - Single state object or use reducer
const [filterState, setFilterState] = useState({
  conditions: [],
  expression: '',
  mode: 'builder'
})

setFilterState(prev => ({
  ...prev,
  conditions: newConditions,
  expression: newExpression,
  mode: newMode
}))
```

### **6. Flexbox Layout Rules**
```typescript
// ✅ Parent container
<Box display="flex" flexDirection="column" minH="100%" maxH="100vh">
  {/* Fixed header */}
  <Box flexShrink={0}>{/* Header content */}</Box>
  
  {/* Scrollable content */}
  <Box flex="1 1 auto" overflowY="auto" minH="0">
    {/* Dynamic content */}
  </Box>
  
  {/* Fixed footer */}
  <Box flexShrink={0}>{/* Footer content */}</Box>
</Box>
```

---

## 📋 IMPLEMENTATION CHECKLIST

- [ ] Replace all `useEffect` with stable dependencies
- [ ] Add `useMemo` for `inputNode` and `inputNodeId`
- [ ] Convert `addCondition`, `updateCondition`, `removeCondition` to `useCallback`
- [ ] Memoize `ConditionItem` component
- [ ] Change container `h="100%"` to `minH="100%" maxH="100vh"`
- [ ] Change container `overflow="hidden"` to `overflow="visible"`
- [ ] Update `TabPanel` flex to `flex="1 1 auto" minH="0"`
- [ ] Add unique IDs to all conditions (`Date.now() + Math.random()`)
- [ ] Test: Add 5 conditions - should expand smoothly without flicker
- [ ] Test: Change node selection - should load once without loop
- [ ] Test: Edit condition value - should update without full re-render

---

## 🎯 EXPECTED RESULTS AFTER FIX

✅ **No more blinking/flickering** - Component renders only on actual state changes  
✅ **Smooth expansion** - Panel grows vertically as conditions are added  
✅ **Stable performance** - useEffect runs only when necessary  
✅ **No re-render loops** - Dependencies are stable and predictable  
✅ **Responsive UI** - Immediate feedback on user interactions
