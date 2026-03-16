# Filter Panel Expansion - Additional Fix Required

## Issue
The filter panel still doesn't expand vertically because the **parent container** in `DataFlowCanvasChakra.tsx` has `overflowY="auto"` which creates a scroll container instead of allowing natural expansion.

## Location
**File:** `frontend/src/components/Canvas/DataFlowCanvasChakra.tsx`  
**Line:** 2335

## Current Code (Line 2335):
```typescript
<Box flex={1} overflowY="auto" overflowX="hidden">
```

## Required Fix:
```typescript
<Box flex={1} display="flex" flexDirection="column">
```

## Why This Fix Is Needed

The filter panel component (`EnhancedFilterConfigPanel`) has been fixed to expand with:
- `minH="100%"` and `maxH="100vh"`
- `overflow="visible"`

However, its **parent container** still has `overflowY="auto"`, which:
1. Creates a scroll container
2. Prevents the child from expanding beyond the parent's fixed height
3. Forces scrolling instead of natural expansion

## Manual Fix Steps

1. Open `frontend/src/components/Canvas/DataFlowCanvasChakra.tsx`
2. Go to **line 2335**
3. Find this line:
   ```typescript
   <Box flex={1} overflowY="auto" overflowX="hidden">
   ```
4. Replace with:
   ```typescript
   <Box flex={1} display="flex" flexDirection="column">
   ```
5. Save the file
6. The frontend will hot-reload automatically

## Expected Result After Fix

✅ Filter panel expands vertically when conditions are added  
✅ No scrollbar on the parent container  
✅ Natural height growth up to viewport limit  
✅ Smooth, responsive UI

## Alternative: Keep Scroll but Allow Expansion

If you want to keep the scroll behavior but still allow expansion up to a point:

```typescript
<Box flex={1} display="flex" flexDirection="column" maxH="100vh" overflowY="auto">
```

This allows:
- Natural expansion up to viewport height
- Scrolling if content exceeds viewport
- Better UX for very long filter lists

## Testing After Fix

1. Open filter panel
2. Add 5+ conditions
3. **Expected:** Panel grows taller
4. **Before:** Panel stays same height, scrolls internally

---

**Status:** ⚠️ Manual fix required  
**Priority:** High (UX issue)  
**Estimated Time:** 30 seconds
