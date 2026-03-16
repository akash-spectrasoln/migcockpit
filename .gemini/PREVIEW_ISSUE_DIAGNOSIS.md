# Preview Issue Diagnosis & Fix

## 🔴 Problem

**Symptom:** Source node preview works, but projection and other downstream nodes fail with SQL error:

```
column "nc_config_source_config" does not exist 
LINE 1: SELECT source_config AS nc_config_source_config FROM "GENERAL".source
HINT: Perhaps you meant to reference the column "source.nc_config"
```

## 🔍 Root Cause Analysis

### Issue 1: Source Node Misconfiguration

The error indicates that a source node is configured to query the **metadata table** `"GENERAL".source` instead of an actual data table.

**Evidence:**
- Error shows: `FROM "GENERAL".source`
- This is the system metadata table that stores source configurations
- It should NOT be used as a data source for ETL

### Issue 2: Column Name Mismatch

The SQL compiler is trying to:
1. Get metadata from `"GENERAL".source` table
2. Apply a prefix (`nc_config_`) to column names
3. Generate SQL like: `SELECT source_config AS nc_config_source_config`

But the actual column in the database might be `nc_config` (without the `source_` prefix).

## 🎯 Solution

### Fix 1: Check Source Node Configuration

**Action:** Verify that the source node is pointing to a valid data table, not the metadata table.

**Steps:**
1. Open the canvas
2. Click on the source node (`tool_connection [public]`)
3. Check the configuration:
   - Schema: Should be your data schema (e.g., `public`, not `GENERAL`)
   - Table: Should be your data table (e.g., `customers`, not `source`)

### Fix 2: Add Error Handling for Metadata Table

We should prevent users from accidentally selecting the metadata table as a source.

**File:** `api/utils/sql_compiler.py`

**Add validation in `_build_source_cte`:**

```python
def _build_source_cte(self, node: Dict[str, Any]) -> Tuple[str, Dict]:
    # ... existing code ...
    
    schema = config.get('schema', 'public')
    table_name = config.get('tableName')
    
    # VALIDATION: Prevent using metadata tables as data sources
    if schema == 'GENERAL' and table_name in ['source', 'destination', 'canvas', 'node_cache_metadata']:
        raise ValueError(
            f"Cannot use metadata table '{schema}.{table_name}' as data source. "
            f"Please select a valid data table from your source database."
        )
    
    # ... rest of code ...
```

### Fix 3: Better Error Messages

**File:** `api/views/pipeline.py`

**Wrap SQL compilation errors:**

```python
try:
    sql_query, sql_params, metadata = compiler.compile(
        target_node_id=target_node_id,
        page_size=page_size
    )
except ValueError as e:
    error_msg = str(e)
    if 'metadata table' in error_msg.lower() or 'GENERAL' in error_msg:
        return Response({
            "error": "Source Configuration Error",
            "message": error_msg,
            "hint": "Please check your source node configuration and ensure it points to a valid data table."
        }, status=status.HTTP_400_BAD_REQUEST)
    raise
```

## 🔧 Immediate Fix (User Action)

**If you're seeing this error:**

1. **Check your source node:**
   - Click on the source node in the canvas
   - Verify the schema and table name
   - If it shows `GENERAL.source`, this is wrong!

2. **Reconfigure the source:**
   - Schema: Change to your data schema (e.g., `public`)
   - Table: Select a valid data table (e.g., `customers`, `orders`, etc.)
   - Save the node

3. **Refresh the preview:**
   - Click on any downstream node
   - Preview should now work

## 📋 Prevention

### Add UI Validation

**File:** `frontend/src/components/Canvas/SourceNodeConfig.tsx`

**Add table selection filter:**

```typescript
// Filter out metadata tables from table list
const dataTablesOnly = tables.filter(table => {
  // Exclude GENERAL schema metadata tables
  if (table.schema === 'GENERAL' && 
      ['source', 'destination', 'canvas', 'node_cache_metadata'].includes(table.name)) {
    return false;
  }
  return true;
});
```

## 🎓 Why This Happens

1. **Metadata tables are visible:** The `GENERAL` schema contains system tables that manage sources, destinations, and canvases
2. **User can select any table:** The UI doesn't filter out metadata tables
3. **SQL compiler treats it as data:** The compiler doesn't validate that the table is a metadata table
4. **Column name conflicts:** Metadata tables have different column structures than data tables

## ✅ Verification

After fixing, test:

1. **Source node preview:** Should show actual data
2. **Projection node preview:** Should show filtered columns
3. **Join node preview:** Should show joined data
4. **No SQL errors:** All previews should work without column name errors

---

**Status:** Diagnosis complete - awaiting user confirmation of source node configuration
**Next Step:** Check source node config in UI and reconfigure if needed
