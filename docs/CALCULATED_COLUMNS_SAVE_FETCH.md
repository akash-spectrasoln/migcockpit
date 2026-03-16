# Calculated Columns: Where They Are Saved and Fetched

## Current Implementation (Before Database Table)

### Where Calculated Columns Are Saved

**Location:** `CanvasNode.config_json` (JSON field in database)

**When:** When user clicks "Save Projection" in the frontend

**Structure:**
```json
{
  "calculatedColumns": [
    {
      "name": "tern",
      "expression": "UPPER(table_name)",
      "dataType": "STRING"
    }
  ],
  "output_columns": [...],
  "includedColumns": [...]
}
```

**Database Table:** `pipeline_nodes`
**Field:** `config_json` (JSONB/JSON field)

### Where Calculated Columns Are Fetched

**During Preview/Execution:**

1. **Primary Source: Request Data** (from frontend)
   - `node.data.config.calculatedColumns`
   - `node.data.calculatedColumns`
   - `node.data.projection.calculatedColumns`

2. **Fallback Source: Database** (if not in request)
   - `CanvasNode.config_json.calculatedColumns`
   - Fetched using: `CanvasNode.objects.filter(node_id=target_node_id).first()`

**Code Location:** `api/views.py` lines 9843-9885

### The Problem

**Issue:** Calculated columns are NOT showing in preview data

**Root Cause:**
- Frontend may not send calculated columns in request when clicking preview
- Backend was only checking request data, not database
- If calculated columns aren't in request, they're not detected

**Fix Applied:**
- Added database fallback to fetch calculated columns from `CanvasNode.config_json`
- Now checks both request data AND database
- Ensures calculated columns are always available

### Flow Diagram

```
User Saves Calculated Column
    ↓
Frontend: ProjectionConfigPanel.handleSave()
    ↓
POST /api/canvas/{id}/save-configuration/
    ↓
Backend: CanvasViewSet.save_configuration()
    ↓
Canvas.configuration.nodes[].data.config.calculatedColumns = [...]
    ↓
SAVE TO DATABASE: CanvasNode.config_json.calculatedColumns
    ↓
─────────────────────────────────────────────────────────
User Clicks Preview
    ↓
Frontend: TableDataPanel.executePipelineQuery()
    ↓
POST /api/pipeline/execute/
Body: { nodes: [...], targetNodeId: "..." }
    ↓
Backend: PipelineQueryExecutionView.post()
    ↓
CHECK 1: Request Data
  - node.data.config.calculatedColumns ❌ (may be missing)
  - node.data.calculatedColumns ❌ (may be missing)
  - node.data.projection.calculatedColumns ❌ (may be missing)
    ↓
CHECK 2: Database (NEW FIX)
  - CanvasNode.objects.filter(node_id=target_node_id)
  - canvas_node.config_json.calculatedColumns ✅ (FOUND!)
    ↓
USE CALCULATED COLUMNS FROM DATABASE
    ↓
Evaluate Calculated Columns
    ↓
Return Preview Data WITH Calculated Columns ✅
```

### Verification Steps

1. **Check if calculated columns are saved:**
   ```sql
   SELECT node_id, config_json->'calculatedColumns' 
   FROM pipeline_nodes 
   WHERE node_id = 'your-node-id';
   ```

2. **Check logs during preview:**
   Look for:
   ```
   [Calculated Column] ✓ Fetched X calculated columns from database
   [Calculated Column] Database calculated columns: ['tern', ...]
   ```

3. **Verify calculated columns are evaluated:**
   Look for:
   ```
   [Calculated Column] Final calculated columns list (X total)
   [Calc Column] Row 1: tern = 'CUSTTRANS'
   ```

### Next Steps (Future: Database Table Approach)

When implementing the `CalculatedColumn` model:

1. **Save:** `CalculatedColumn.objects.create(node=canvas_node, ...)`
2. **Fetch:** `CalculatedColumn.objects.filter(node_id=target_node_id)`
3. **Delete:** `CalculatedColumn.objects.filter(node=canvas_node).delete()`

This will provide:
- Single source of truth
- Better querying
- Easier management
- History tracking
