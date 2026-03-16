# Preview Fix - Column Name Issue Resolution

## 🔴 Problem Summary

**Error:**
```
column "src_config" does not exist
LINE 1: SELECT source_config, src_config, created_on FROM "GENERAL".source...
```

**Root Cause:**
The code was trying to SELECT both `source_config` AND `src_config` columns from the `GENERAL.source` table, but your database only has `source_config` (not `src_config`).

This query pattern existed in **TWO files**:
1. `api/utils/sql_compiler.py` - Line ~1900
2. `api/views/pipeline.py` - Line ~1432

---

## ✅ Fixes Applied

### Fix 1: `api/utils/sql_compiler.py`

**Before:**
```python
cursor.execute(f'''
    SELECT {name_column}, {config_column}, created_on
    FROM "GENERAL".source
    WHERE id = %s
''', (source_id,))
```

**After:**
```python
# Check which columns exist in GENERAL.source table
cursor.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_schema = 'GENERAL' AND table_name = 'source'
""")
available_columns = [row[0] for row in cursor.fetchall()]

# Determine which column names exist
name_column = 'source_name' if 'source_name' in available_columns else 'src_name'
config_column = 'source_config' if 'source_config' in available_columns else 'src_config'

# Validate that required columns exist
if name_column not in available_columns:
    raise ValueError(f"Source table missing name column. Available columns: {available_columns}")
if config_column not in available_columns:
    raise ValueError(f"Source table missing config column. Available columns: {available_columns}")

# Get source config - only SELECT columns that actually exist
cursor.execute(f'''
    SELECT "{name_column}", "{config_column}", created_on
    FROM "GENERAL".source
    WHERE id = %s
''', (source_id,))
```

### Fix 2: `api/views/pipeline.py`

**Before:**
```python
cur.execute('SELECT source_config, src_config, created_on FROM "GENERAL".source WHERE id = %s', (source_id,))
row = cur.fetchone()
if row:
    sc_encrypted = row[0] if row[0] else row[1]  # Try both columns
    source_config = decrypt_source_data(sc_encrypted, customer.cust_id, row[2])
```

**After:**
```python
# Check which columns exist in GENERAL.source table
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_schema = 'GENERAL' AND table_name = 'source'
""")
available_columns = [row[0] for row in cur.fetchall()]

# Determine which column name exists
config_column = 'source_config' if 'source_config' in available_columns else 'src_config'

# Query with only the column that exists
cur.execute(f'SELECT "{config_column}", created_on FROM "GENERAL".source WHERE id = %s', (source_id,))
row = cur.fetchone()
if row:
    sc_encrypted = row[0]  # Only one column now
    source_config = decrypt_source_data(sc_encrypted, customer.cust_id, row[1])  # row[1] not row[2]
```

---

## 🚀 How to Apply the Fix

### **CRITICAL: Restart Django Server**

The code changes have been saved to disk, but the server is still running the old code in memory.

**Steps:**

1. **Stop the Django server:**
   - Find the terminal running the server
   - Press `Ctrl+C` to stop it

2. **Restart the Django server:**
   ```bash
   cd c:\Users\akash\Desktop\migcockpit-qoder\migcockpit\datamigration-migcockpit
   python manage.py runserver
   ```

3. **Test the preview:**
   - Click preview on your source node ✅
   - Click preview on your projection node ✅
   - Both should now work!

---

## 🔍 Why This Happened

### Schema Evolution Issue

The codebase was designed to support **two different schema versions**:

**Version 1 (Old):**
- Columns: `src_name`, `src_config`, `created_on`

**Version 2 (New):**
- Columns: `source_name`, `source_config`, `created_on`

The original code tried to handle both by:
```python
# Try to SELECT both columns
SELECT source_config, src_config, created_on ...

# Then use whichever one is not NULL
sc_encrypted = row[0] if row[0] else row[1]
```

**Problem:** PostgreSQL doesn't allow SELECTing non-existent columns, even if you don't use them!

**Solution:** Check which columns exist BEFORE building the SELECT query.

---

## ✅ Verification Checklist

After restarting the server, verify:

- [ ] Source node preview works
- [ ] Projection node preview works
- [ ] Join node preview works (if you have one)
- [ ] No SQL errors in logs
- [ ] Preview data displays correctly in UI

---

## 📊 Impact

**Files Modified:**
1. `api/utils/sql_compiler.py` - Lines 1879-1904
2. `api/views/pipeline.py` - Lines 1432-1449

**Behavior Changed:**
- ✅ Dynamic column detection (supports both schema versions)
- ✅ Clear error messages if columns are missing
- ✅ No more SQL errors for non-existent columns

**Backward Compatibility:**
- ✅ Still supports old schema (`src_name`, `src_config`)
- ✅ Still supports new schema (`source_name`, `source_config`)
- ✅ Automatically detects which version is in use

---

## 🎓 Lessons Learned

1. **Don't hardcode column names** when schema might vary
2. **Check schema before querying** using `information_schema.columns`
3. **Duplicate code = duplicate bugs** - both files had the same issue
4. **Server restart required** for Python code changes to take effect

---

**Status:** ✅ Fixed - Awaiting server restart
**Next Step:** Restart Django server and test previews
