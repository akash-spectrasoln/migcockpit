# Test Plan: Calculated Columns Fix

## Issue Fixed
Calculated columns were being included in SQL SELECT clause as if they were base columns, causing SQL errors when they don't exist in the database.

## Changes Made
1. **Filter calculated columns from `selected_columns`** (lines 9980-9986)
   - Calculated columns are removed from `selected_columns` before building SELECT clause
   - Only base columns are included in `selected_columns`

2. **Exclude calculated columns from SELECT clause** (lines 10630-10683)
   - SELECT clause building logic separates base columns from calculated columns
   - Only base columns are added to `select_parts`
   - Calculated columns are logged but NOT included in SQL SELECT

3. **Calculated columns evaluated in Python** (lines 10929-10966)
   - Calculated columns are evaluated AFTER fetching base data
   - Uses `evaluate_calculated_expression` function

## Test Steps

### Test Case 1: Add a Simple Calculated Column
1. Open projection node configuration
2. Add a calculated column with expression: `UPPER(table_name)` or `new_rec + mod_rec`
3. Save the projection configuration
4. Click preview/execute

**Expected Behavior:**
- ✅ SELECT clause should NOT include the calculated column name
- ✅ SELECT clause should only include base columns (e.g., `"tr_id", "table_name", "start_time"`)
- ✅ Logs should show: `"[Calculated Column] 'column_name' will be evaluated in Python, NOT in SQL SELECT"`
- ✅ Calculated column values should appear in preview data
- ✅ Calculated column should appear at the END of projection fields sequence

**Check Logs For:**
```
[Projection] Removed X calculated columns from selected_columns: ['calc_col_name']
[Calculated Column] 'calc_col_name' will be evaluated in Python, NOT in SQL SELECT
[SQL] Final SELECT clause: "tr_id", "table_name", ... (NO calculated column names)
[Calculated Column] Need to evaluate X calculated columns in Python: ['calc_col_name']
[Calc Column] Row 1: calc_col_name = <calculated_value>
```

### Test Case 2: Multiple Calculated Columns
1. Add 2-3 calculated columns
2. Verify all are excluded from SELECT clause
3. Verify all are evaluated and appear in preview

### Test Case 3: Calculated Column with Complex Expression
1. Add calculated column: `CONCAT(table_name, '_', CAST(total_rec AS TEXT))`
2. Verify it's evaluated correctly in Python

### Test Case 4: Edge Cases
- Calculated column name matches a base column name (should be handled by conflict check)
- Empty expression (should log error and skip)
- Calculated column referencing another calculated column (should work if order is correct)

## Verification Points

### ✅ Backend Logs Should Show:
1. `"[Projection] Removed X calculated columns from selected_columns"` - confirms filtering
2. `"[Calculated Column] 'name' will be evaluated in Python, NOT in SQL SELECT"` - confirms exclusion from SELECT
3. `"[SQL] Final SELECT clause: ..."` - should NOT contain calculated column names
4. `"[Calculated Column] Need to evaluate X calculated columns in Python"` - confirms Python evaluation
5. `"[Calc Column] Row X: name = value"` - confirms successful evaluation

### ✅ Frontend Should Show:
1. Calculated column appears in projection fields sequence (at the end)
2. Calculated column values appear in preview data
3. No errors in browser console

### ❌ Should NOT See:
- SQL errors about non-existent columns
- Calculated column names in SELECT clause
- Missing calculated column values in preview

## Debugging Commands

If issues persist, check:
```python
# In Django shell or add logging:
print(f"calculated_columns: {calculated_columns}")
print(f"calculated_col_names_set: {calculated_col_names_set}")
print(f"selected_columns before filter: {output_columns}")
print(f"selected_columns after filter: {selected_columns}")
print(f"output_metadata_columns: {[c.get('name') for c in output_metadata_columns]}")
print(f"base_columns_for_select: {[c.get('name') for c in base_columns_for_select]}")
print(f"calculated_columns_for_eval: {[c.get('name') for c in calculated_columns_for_eval]}")
```
