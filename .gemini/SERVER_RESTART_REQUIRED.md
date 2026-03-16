# Server Restart Required - Code Changes Not Loaded

## 🔴 Current Status

**Symptom:**
- Preview is working (HTTP 200 response with data)
- But checkpoint save is still failing with old error
- Error log shows old behavior (trying to use SQL for source nodes)

**Root Cause:**
The Django development server has **NOT reloaded the new code** yet.

---

## 🔧 Solution: Manual Server Restart

### Why Auto-Reload Might Not Work

Django's auto-reload can be unreliable when:
1. Multiple files are changed quickly
2. Changes are made while a request is processing
3. The file watcher misses the change

### Manual Restart Steps

1. **Find the terminal running Django**
   - Look for the terminal with output like:
     ```
     [13/Feb/2026 13:03:27] "POST /api/pipeline/execute/ HTTP/1.1" 200 33508
     ```

2. **Stop the server**
   - Press `Ctrl+C` in that terminal
   - Wait for it to fully stop

3. **Restart the server**
   ```bash
   cd c:\Users\akash\Desktop\migcockpit-qoder\migcockpit\datamigration-migcockpit
   python manage.py runserver
   ```

4. **Verify the restart**
   - Look for the startup message:
     ```
     Django version X.X.X, using settings 'datamigration.settings'
     Starting development server at http://127.0.0.1:8000/
     ```

5. **Test the preview**
   - Click preview on source node
   - Check logs for:
     - ✅ No "relation does not exist" errors
     - ✅ Checkpoint saved successfully
     - ✅ Data displays in UI

---

## ✅ Expected Behavior After Restart

### Source Node Preview

**Logs should show:**
```
[INFO] PipelineQueryExecutionView: NEW REQUEST
[INFO] Executing PostgreSQL query with 1 parameters
[INFO] Checkpoint saved successfully for ee677f5f-4f70-4a3f-afb3-a6a7ab3bf516
[200] "POST /api/pipeline/execute/ HTTP/1.1" 200 33508
```

**No errors about:**
- ❌ `relation "public.tool_connection" does not exist`
- ❌ `column "src_config" does not exist`

### Cache Table Created

**In customer database (C00008):**
```sql
-- Cache schema created
CREATE SCHEMA IF NOT EXISTS "staging_preview_<canvas_id>"

-- Cache table created with data
CREATE TABLE "staging_preview_<canvas_id>"."node_<node_id>_cache" (...)
-- Contains ≤100 rows from source table

-- Metadata table updated
INSERT INTO "staging_preview_<canvas_id>"."_checkpoint_metadata" (...)
```

### Subsequent Previews

**Second preview of same source node:**
- ✅ Fetches from cache (instant, <50ms)
- ✅ No query to source database
- ✅ Response includes `"from_cache": true`

**Preview of downstream projection node:**
- ✅ Uses source cache in SQL
- ✅ No query to source database
- ✅ Fast response (<150ms)

---

## 🎯 Verification Checklist

After restarting, verify:

- [ ] Server starts without errors
- [ ] Source node preview works
- [ ] No "relation does not exist" error in logs
- [ ] Checkpoint save succeeds (check logs)
- [ ] Second preview is faster (cache hit)
- [ ] Projection node preview works
- [ ] All downstream nodes work

---

## 📊 Performance Expectations

| Action | First Time | Cache Hit |
|--------|-----------|-----------|
| Source preview | ~1-2s | ~50ms |
| Projection preview | ~1-2s | ~150ms |
| Join preview | ~2-3s | ~200ms |

---

## 🐛 If Still Failing After Restart

If you still see errors after a proper restart:

1. **Check Python process**
   ```bash
   # Windows
   tasklist | findstr python
   
   # Kill any stray Python processes
   taskkill /F /IM python.exe
   ```

2. **Clear Python cache**
   ```bash
   # Delete .pyc files
   find . -name "*.pyc" -delete
   find . -name "__pycache__" -type d -delete
   ```

3. **Restart with verbose logging**
   ```bash
   python manage.py runserver --verbosity 3
   ```

4. **Check the actual code loaded**
   - Add a print statement in the code
   - Verify it appears in logs after restart

---

**Status:** ✅ Code fixed, awaiting server restart
**Next Step:** Manual server restart required
