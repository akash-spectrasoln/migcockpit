# Calculated Columns Debug Logging Guide

## Overview
This document explains the comprehensive debug logging added to track calculated columns through their entire lifecycle: **save → storage → fetch → execution → response**.

---

## 1. SAVE: When User Clicks "Save Projection"

### Location
**File:** `datamigration-migcockpit/api/views/canvas_views.py`  
**Method:** `CanvasViewSet.save_configuration()`  
**Endpoint:** `POST /api/canvas/{id}/save-configuration/`

### What to Look For
When a user saves a projection node with calculated columns, you should see:

```
================================================================================
[SAVE DEBUG] Saving canvas configuration for canvas_id=123
[SAVE DEBUG] Node: node-abc123 (type=projection)
[SAVE DEBUG]   - config.calculatedColumns: 1 columns
[SAVE DEBUG]       * net: new_rec + total_rec + mod_rec + del_rec
[SAVE DEBUG]   - data.calculatedColumns: 0 columns
[SAVE DEBUG]   - output_metadata calculated columns: 1 columns
[SAVE DEBUG]       * net: new_rec + total_rec + mod_rec + del_rec
================================================================================
```

### Interpretation
- **config.calculatedColumns**: Should contain the calculated columns from the frontend
- **data.calculatedColumns**: Alternative location (usually empty)
- **output_metadata calculated columns**: Should match config.calculatedColumns

**✅ PASS:** At least one location shows the calculated column with its expression  
**❌ FAIL:** All three show 0 columns → **Frontend is not sending calculated columns!**

---

## 2. FETCH: When User Clicks "Preview" on Projection Node

### Location
**File:** `datamigration-migcockpit/api/views.py`  
**Method:** `PipelineQueryExecutionView.post()` (Projection section)  
**Endpoint:** `POST /api/pipeline/execute/`

### What to Look For (Initial Detection)
When the backend starts processing a preview request:

```
================================================================================
[FETCH DEBUG] Starting preview for projection node: node-abc123
[FETCH DEBUG] Source 1: projection_config.calculatedColumns = 1 columns
[FETCH DEBUG]   * net: new_rec + total_rec + mod_rec + del_rec
[FETCH DEBUG] Source 2: target_node_data.calculatedColumns = 0 columns
[FETCH DEBUG] Source 3: projection_metadata.calculatedColumns = 0 columns
[FETCH DEBUG] ✓ Found CanvasNode in database: Projection_xyz
[FETCH DEBUG] Source 4 (DB): CanvasNode.config_json.calculatedColumns = 1 columns
[FETCH DEBUG]   * net: new_rec + total_rec + mod_rec + del_rec
================================================================================
```

### Interpretation
The backend checks **4 sources** for calculated columns:
1. **projection_config.calculatedColumns** (from request)
2. **target_node_data.calculatedColumns** (from request)
3. **projection_metadata.calculatedColumns** (from request)
4. **CanvasNode.config_json.calculatedColumns** (from database - FALLBACK)

**✅ PASS:** At least one source shows the calculated column  
**❌ FAIL:** All 4 sources show 0 columns → **Calculated column was never saved!**

### What to Look For (After Merge)
After checking all sources:

```
[FETCH DEBUG] Merging calculated columns from all sources:
[FETCH DEBUG]   - From config: 1
[FETCH DEBUG]   - From data: 0
[FETCH DEBUG]   - From projection: 0
[FETCH DEBUG]   - From database: 1
[FETCH DEBUG]   - TOTAL (after deduplication): 1
[FETCH DEBUG] Final calculated columns list:
[FETCH DEBUG]   * net: new_rec + total_rec + mod_rec + del_rec
================================================================================
```

**✅ PASS:** TOTAL > 0 and expression is shown  
**❌ FAIL:** `⚠️ NO CALCULATED COLUMNS DETECTED FROM ANY SOURCE!` → **Calculated column was not persisted**

---

## 3. EXECUTION: SQL Query Generation & Python Evaluation

### What to Look For (SQL Generation)
```
[SQL] Final SELECT clause: "tr_id", "table_name", "start_time", ..., "net"
[Calculated Column] Summary: 1 calculated columns
```

**✅ PASS:** Calculated column `net` is **NOT** in SELECT clause  
**❌ FAIL:** Calculated column `net` is in SELECT clause → **Backend will try to fetch it from database (ERROR!)**

### What to Look For (Python Evaluation)
```
[Calculated Column] Processing 1 calculated columns in Python
[Calc Column] Row 1: net = 150
[Calc Column] Row 2: net = 200
[Calc Column] Row 3: net = 175
```

**✅ PASS:** Shows evaluated values for each row  
**❌ FAIL:** `net = None` or no evaluation logs → **Expression evaluation failed**

---

## 4. RESPONSE: What's Sent to Frontend

### Location
End of projection execution, just before `return Response()`

### What to Look For
```
================================================================================
[RESPONSE DEBUG] Returning preview data to frontend
[RESPONSE DEBUG] Total rows: 50
[RESPONSE DEBUG] Total columns: 14
[RESPONSE DEBUG] Base columns (13): ['tr_id', 'table_name', ..., 'user_id']
[RESPONSE DEBUG] Calculated columns (1): 
[RESPONSE DEBUG]   * net: new_rec + total_rec + mod_rec + del_rec
[RESPONSE DEBUG] First row calculated column values:
[RESPONSE DEBUG]   * net = 150
================================================================================
```

### Interpretation
- **Total columns**: Base columns + calculated columns
- **Calculated columns**: Should list names and expressions
- **First row values**: Shows actual evaluated data

**✅ PASS:** Calculated column appears with expression and value  
**❌ FAIL:** 
- Calculated columns (0) → **Not detected or not evaluated**
- `net = None` → **Evaluation failed**
- `net: NO EXPRESSION` → **Expression was lost**

---

## Common Failure Scenarios & Diagnosis

### Scenario 1: Calculated Column Not Shown on Second Preview

**Symptoms:**
```
[FETCH DEBUG] Source 1-3: 0 columns
[FETCH DEBUG] ✗ CanvasNode found but config_json is empty or None
[FETCH DEBUG] ⚠️ NO CALCULATED COLUMNS DETECTED FROM ANY SOURCE!
```

**Root Cause:** Calculated columns were never saved to the database

**Fix:** Check frontend save logic in `ProjectionConfigPanel.handleSave()` - ensure `calculatedColumns` is in the `config` object

---

### Scenario 2: Calculated Column Shows Expression but Value is NULL

**Symptoms:**
```
[RESPONSE DEBUG] Calculated columns (1): 
[RESPONSE DEBUG]   * net: new_rec + total_rec + mod_rec + del_rec
[RESPONSE DEBUG] First row calculated column values:
[RESPONSE DEBUG]   * net = None
```

**Root Cause:** Expression evaluation failed (column names wrong, syntax error, or input columns are NULL)

**Fix:** Check the expression syntax and verify input column names match the actual data

---

### Scenario 3: Calculated Column Included in SQL SELECT

**Symptoms:**
```
[SQL] Final SELECT clause: "tr_id", ..., "net"
ERROR: column "net" does not exist
```

**Root Cause:** Calculated column was not filtered out before building SQL query

**Fix:** Backend should exclude calculated columns from `selected_columns` before SQL generation

---

## Quick Diagnosis Checklist

When debugging calculated columns, check these logs in order:

1. **[SAVE DEBUG]**: Is the calculated column being saved? ✅/❌
2. **[FETCH DEBUG]**: Is it being retrieved from DB or request? ✅/❌
3. **[SQL]**: Is it excluded from SELECT clause? ✅/❌
4. **[Calc Column]**: Is it being evaluated in Python? ✅/❌
5. **[RESPONSE DEBUG]**: Is it in the response with correct values? ✅/❌

If any step fails, that's where the issue is!

---

## Testing Instructions

### Test 1: Save and Load
1. Add a calculated column: `total = new_rec + mod_rec`
2. Click "Save Projection"
3. Check logs for `[SAVE DEBUG]` - verify column is saved
4. Refresh the page
5. Click on projection node again
6. Check logs for `[FETCH DEBUG]` - verify column is loaded from database

### Test 2: Expression Evaluation
1. Add calculated column with simple expression
2. Click "Preview"
3. Check logs for `[Calc Column]` - verify values are evaluated
4. Check logs for `[RESPONSE DEBUG]` - verify values in response

### Test 3: Complex Expression
1. Add calculated column: `rate = (new_rec * 100) / total_rec`
2. Click "Preview"
3. Verify no division by zero errors in logs
4. Check calculated values make sense

---

## Log Files

Logs are written to:
- **Django logs**: Check console or `datamigration-migcockpit/logs/` (if configured)
- **Search for**: `[SAVE DEBUG]`, `[FETCH DEBUG]`, `[RESPONSE DEBUG]`

**Tip:** Use `grep` to filter logs:
```bash
grep "\[SAVE DEBUG\]" logs/django.log
grep "\[FETCH DEBUG\]" logs/django.log
grep "\[RESPONSE DEBUG\]" logs/django.log
```

---

## Summary

The debug logging creates a **complete audit trail** for calculated columns:

```
User Action                  Log Marker           What It Shows
───────────────────────────────────────────────────────────────────
Click "Save Projection"  →  [SAVE DEBUG]     →  What's being saved
Click "Preview"          →  [FETCH DEBUG]    →  Where data comes from
SQL Generation           →  [SQL]            →  Columns in SELECT
Python Evaluation        →  [Calc Column]    →  Evaluated values
Response to Frontend     →  [RESPONSE DEBUG] →  Final data structure
```

Each stage is **independently verifiable**, making it easy to pinpoint where the issue occurs.
