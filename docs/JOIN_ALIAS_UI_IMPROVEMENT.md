# Join Output Column Alias UI Improvement

## Overview

Updated the Join configuration UI to automatically detect column name conflicts and pre-populate alias fields with `_l`/`_r` suffixes, matching the backend's conflict resolution behavior.

## Problem

Previously, when both left and right tables had columns with the same name (e.g., both have `name`), the UI would show both as `name` in the alias field by default. However, the backend automatically resolves this by adding `_l` and `_r` suffixes (e.g., `name_l`, `name_r`). This created confusion because:

1. Users saw `name` in the UI but the actual output was `name_l` and `name_r`
2. Downstream nodes would fail if they referenced `name` instead of the resolved names
3. Users couldn't see what the actual output column names would be

## Solution

### Frontend Changes

**File:** `frontend/src/components/Canvas/JoinConfigPanel.tsx`

#### 1. Auto-Conflict Detection in `initializeOutputColumns`

When generating default output columns, the function now:

- **Detects conflicts**: Checks if a column name exists in both left and right tables
- **Auto-resolves**: Sets default `outputName` with suffixes:
  - Left table columns → `{column}_l` if conflict exists
  - Right table columns → `{column}_r` if conflict exists
- **Tracks uniqueness**: Maintains a `usedOutputNames` set to ensure no duplicates

**Example:**
```typescript
// Before:
Left:  name → outputName: "name"
Right: name → outputName: "name"  // Conflict!

// After:
Left:  name → outputName: "name_l"  // Auto-resolved
Right: name → outputName: "name_r"  // Auto-resolved
```

#### 2. Enhanced Validation

The `updateOutputColumnName` function now:

- **Prevents duplicates**: Still blocks duplicate output names
- **Suggests resolution**: When a duplicate is detected, suggests the appropriate suffix:
  - Left table → suggests `{name}_l`
  - Right table → suggests `{name}_r`

**Example Error Message:**
```
Output field name "name" is already used. Consider using "name_l"
```

### User Experience

1. **Default Behavior**: 
   - Conflicting columns automatically get `_l`/`_r` suffixes in the alias field
   - Users see exactly what the output column names will be

2. **Editable Aliases**:
   - Users can click on any alias field to edit it
   - Users can double-click to focus and rename
   - Changes are validated in real-time

3. **Visual Clarity**:
   - Left table columns show `__L__.column_name → alias_field`
   - Right table columns show `__R__.column_name → alias_field`
   - Alias fields show the resolved names by default

## Implementation Details

### Conflict Detection Logic

```typescript
// Track used output names
const usedOutputNames = new Set<string>()

// Left table columns
leftCols.forEach(col => {
  let outputName = col
  
  // Check for conflict with right table
  if (rightColumnNames.has(col)) {
    outputName = `${col}_l`  // Auto-resolve
  }
  
  usedOutputNames.add(outputName)
  // ... add to defaultColumns
})

// Right table columns
rightCols.forEach(col => {
  let outputName = col
  
  // Check for conflict with left table
  if (leftColumnNames.has(col)) {
    outputName = `${col}_r`  // Auto-resolve
  }
  
  usedOutputNames.add(outputName)
  // ... add to defaultColumns
})
```

### UI Components

The alias fields are rendered as editable `Input` components:

```tsx
<Input
  size="xs"
  value={col.outputName || col.column}
  onChange={(e) => {
    updateOutputColumnName('left', col.column, e.target.value)
  }}
  onBlur={(e) => {
    // Validate on blur
    if (!e.target.value.trim()) {
      updateOutputColumn('left', col.column, { outputName: col.column })
    }
  }}
  placeholder={col.column}
/>
```

## Benefits

1. **Clarity**: Users see exactly what output column names will be
2. **Consistency**: Frontend matches backend behavior
3. **Prevention**: Conflicts resolved before they cause issues
4. **Flexibility**: Users can still customize aliases if needed
5. **User-Friendly**: Clear visual indication of conflicts

## Example Scenarios

### Scenario 1: Both tables have `id` column

**Before:**
```
Left:  __L__.id → id
Right: __R__.id → id  (conflict!)
```

**After:**
```
Left:  __L__.id → id_l
Right: __R__.id → id_r
```

### Scenario 2: Both tables have `status` column

**Before:**
```
Left:  __L__.status → status
Right: __R__.status → status  (conflict!)
```

**After:**
```
Left:  __L__.status → status_l
Right: __R__.status → status_r
```

### Scenario 3: No conflicts

**Before & After (unchanged):**
```
Left:  __L__.name → name
Right: __R__.email → email  (no conflict)
```

## Backend Compatibility

The frontend changes are fully compatible with the backend:

- Backend's `_build_join_cte()` already handles conflicts with `_l`/`_r` suffixes
- Frontend now pre-populates these same suffixes
- Both frontend and backend use the same conflict resolution strategy
- No breaking changes to the API contract

## Testing

Test scenarios:

1. **Conflict Detection**: Create join with duplicate column names → verify `_l`/`_r` suffixes appear
2. **No Conflicts**: Create join with unique column names → verify no suffixes
3. **Manual Override**: Edit alias field → verify custom name is saved
4. **Duplicate Prevention**: Try to set duplicate alias → verify error message with suggestion
5. **Downstream Nodes**: Verify Filter/Projection nodes can reference resolved column names

## Related Files

- `frontend/src/components/Canvas/JoinConfigPanel.tsx` - Join configuration UI
- `api/utils/sql_compiler.py` - Backend SQL compilation (already handles conflicts)
- `docs/JOIN_UNIQUENESS_ENFORCEMENT.md` - Backend uniqueness enforcement

## Summary

The UI now automatically detects and resolves column name conflicts by pre-populating alias fields with `_l`/`_r` suffixes. This ensures:

✅ Users see exactly what output column names will be  
✅ Frontend matches backend behavior  
✅ Conflicts are resolved before causing issues  
✅ Users can still customize aliases if needed  
✅ Clear visual indication of conflicts  

This eliminates confusion and ensures downstream nodes can safely reference join output columns.
