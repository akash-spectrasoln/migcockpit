# How to Restart Migration Service to Enable Filter Pushdown

## Problem
The Migration Service is running as a background process and hasn't picked up the new filter pushdown code.

## Solution: Restart the Service

### Option 1: Restart via Terminal (Recommended)

1. **Find the running process**:
   ```powershell
   # Look for the running service in your terminal
   # It should show something like:
   # C:\Users\akash\Desktop\migcockpit-qoder\migcockpit\datamigration-migcockpit\s...
   ```

2. **Stop the service**:
   - Press `Ctrl+C` in the terminal where the service is running
   - Or kill the process by PID

3. **Restart the service**:
   ```powershell
   cd c:\Users\akash\Desktop\migcockpit-qoder\migcockpit\datamigration-migcockpit
   python services/migration_service/main.py
   ```

### Option 2: Use the Workflow (If Available)

If you have a workflow defined for starting the service:
```bash
# Run the start service workflow
```

## What to Look For After Restart

When you click **"Validate"** again, you should see these new logs:

```
[VALIDATE] ═══ Step 2: Filter Pushdown Analysis ═══
[VALIDATE] Imported filter_optimizer successfully
[VALIDATE] Pushdown analysis completed, result: <class 'dict'>
```

Then either:
- **If filters can be pushed**:
  ```
  [VALIDATE] ✓ Filter pushdown plan generated:
  [VALIDATE]   → Push 1 filter(s) to node 9aad5245...
  ```

- **If no filters to push**:
  ```
  [VALIDATE] ℹ No filter pushdown opportunities found (no filter nodes or filters cannot be pushed)
  ```

## Troubleshooting

### If you see: `Failed to import filter_optimizer`
- Check that `filter_optimizer.py` exists:
  ```powershell
  ls services\migration_service\planner\filter_optimizer.py
  ```

### If you see: `Filter pushdown analysis failed`
- Check the traceback in the logs
- The service will continue without pushdown (safe fallback)

### If you don't see the Step 2 logs at all
- The service hasn't restarted yet
- Make sure you're looking at the Migration Service logs, not the API logs

## Current Pipeline Analysis

Based on your logs, your pipeline has:
- **9 nodes**: 2 sources, 1 join, 1 filter, 1 projection, 1 destination
- **8 edges**
- **Filter node**: `72fa1a4e-7f04-4f8f-8d5c-22bd1ebefe09`

The filter node is **after the JOIN**, so the pushdown analyzer should:
1. Detect the filter on `_L_cmp_id = 1`
2. Trace back through the JOIN to find it comes from the left table's `cmp_id`
3. Attempt to push it to the source node `9aad5245-4245-4027-9011-d1de83f597f8`

**Expected result**: Filter pushed to source, reducing data before JOIN.
