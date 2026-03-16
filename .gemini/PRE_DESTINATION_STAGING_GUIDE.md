# Pre-Destination Staging (BOUNDARY C) - Implementation Guide

## Overview

**BOUNDARY C** creates a **staging table before the destination** to enable data verification and review before the final INSERT. This is a critical feature for production ETL systems.

---

## 🎯 Purpose

### Why Pre-Destination Staging?

1. **Data Verification** - Review transformed data before loading to destination
2. **Quality Checks** - Run validation queries on staging table
3. **Rollback Safety** - Can discard staging table if data is incorrect
4. **Audit Trail** - Staging table serves as snapshot of transformation result
5. **Debugging** - Inspect intermediate results without affecting destination

---

## 📋 Three Physical Boundaries

| Boundary | Purpose | Example |
|----------|---------|---------|
| **A: Branch end before JOIN** | Materialize each JOIN input | `source → proj → filter → (STAGE) → JOIN` |
| **B: JOIN output** | Materialize JOIN result | `JOIN → (STAGE)` |
| **C: Pre-destination staging** | Materialize before destination | `compute → (STAGE) → destination` |

---

## ✅ Universal Linear-Segment Reuse Rule (Still Enforced)

### Key Point: BOUNDARY C Does NOT Violate the Rule

**Why?** Because the entire upstream chain (including post-JOIN linear segment) is compiled as **ONE nested SQL** into the staging table.

```
JOIN → projection → filter → compute → (STAGE as ONE nested SQL) → destination
       └──────────────────────────────┘
              Linear segment
           Compiled as nested SQL
```

**NOT** broken into multiple staging tables:
```
❌ WRONG: JOIN → (stage) → projection → (stage) → filter → (stage) → compute → (stage)
```

**✅ CORRECT**: JOIN → projection → filter → compute → (ONE stage with nested SQL)

---

## 🔄 Data Flow

### Your Canvas Example

```
trad_connections → proj → filter → (STAGE) → ┐
                                              ├→ JOIN → (STAGE) → proj → compute → (STAGE) → dest
trad_log_updates → proj → (STAGE) ───────────┘
                                                      └─────────────────┘
                                                      Nested SQL into
                                                      staging table
```

### Materialization Points (4 total)

```
1. filter: BRANCH_END_BEFORE_JOIN
2. proj_2: BRANCH_END_BEFORE_JOIN
3. join: JOIN_RESULT
4. compute: PRE_DESTINATION_STAGING
```

---

## 📝 Generated SQL

### Level 0 (Parallel)

```sql
-- Branch 1 end
CREATE TABLE "staging_job_abc.node_filter" AS
SELECT * FROM (
    SELECT id, name, status FROM (
        SELECT * FROM "trad_connections"
    ) proj
) filt
WHERE status = 'active';

-- Branch 2 end
CREATE TABLE "staging_job_abc.node_proj2" AS
SELECT connection_id, update_time FROM (
    SELECT * FROM "trad_log_updates"
) proj2;
```

### Level 1

```sql
-- JOIN
CREATE TABLE "staging_job_abc.node_join" AS
SELECT l.*, r.*
FROM "staging_job_abc.node_filter" l
INNER JOIN "staging_job_abc.node_proj2" r
ON l."id" = r."connection_id";
```

### Level 2 (Pre-Destination Staging)

```sql
-- Post-JOIN linear chain compiled as ONE nested SQL
CREATE TABLE "staging_job_abc.node_compute" AS
SELECT *, CURRENT_TIMESTAMP AS processed_at
FROM (
    SELECT id, name, status, connection_id, update_time
    FROM (
        SELECT * FROM "staging_job_abc.node_join"
    ) proj3
) comp;
```

**Key**: `proj3 → comp` compiled as **nested SQL**, not separate staging tables!

### Final INSERT (From Staging Table)

```sql
-- Simple SELECT from staging table
INSERT INTO "dest_pointers"
SELECT * FROM "staging_job_abc.node_compute";
```

---

## 🔍 Data Verification Workflow

### Before Final INSERT

```sql
-- 1. Check row count
SELECT COUNT(*) FROM "staging_job_abc.node_compute";

-- 2. Sample data
SELECT * FROM "staging_job_abc.node_compute" LIMIT 100;

-- 3. Validate data quality
SELECT 
    COUNT(*) as total_rows,
    COUNT(DISTINCT id) as unique_ids,
    MIN(processed_at) as earliest,
    MAX(processed_at) as latest
FROM "staging_job_abc.node_compute";

-- 4. Check for nulls
SELECT 
    SUM(CASE WHEN id IS NULL THEN 1 ELSE 0 END) as null_ids,
    SUM(CASE WHEN name IS NULL THEN 1 ELSE 0 END) as null_names
FROM "staging_job_abc.node_compute";
```

### If Data is Correct

```sql
-- Proceed with final INSERT
INSERT INTO "dest_pointers"
SELECT * FROM "staging_job_abc.node_compute";

-- Cleanup
DROP SCHEMA "staging_job_abc" CASCADE;
```

### If Data is Incorrect

```sql
-- Just drop the staging schema (no destination affected)
DROP SCHEMA "staging_job_abc" CASCADE;

-- Fix the issue and re-run the pipeline
```

---

## ✅ Benefits

### 1. Safety

- **No direct writes** to destination until verification
- **Rollback capability** - discard staging if needed
- **Destination protected** from bad data

### 2. Debugging

- **Inspect results** before final load
- **Run ad-hoc queries** on staging table
- **Compare** with expected results

### 3. Audit Trail

- **Snapshot** of transformation result
- **Timestamp** of when data was processed
- **Reproducibility** - can recreate staging table

### 4. Quality Assurance

- **Automated checks** on staging table
- **Data validation** before load
- **Alerts** if quality thresholds not met

---

## 🎯 Implementation Details

### Code Location

**`planner/materialization.py`** - Lines 102-122

```python
# BOUNDARY C: Pre-destination staging
# Materialize the parent node before destination
# This creates ONE staging table for the entire upstream chain
# The upstream chain (including post-JOIN linear segment) is compiled as nested SQL
for node_id, node in node_map.items():
    node_type = _get_node_type(node)
    
    if node_type in ("destination", "destination-postgresql", "destination-postgres"):
        parents = reverse_adjacency.get(node_id, [])
        if parents:
            parent_id = parents[0]
            
            # Always materialize the parent before destination
            # This allows data verification before final INSERT
            if parent_id not in materialization_points:
                materialization_points[parent_id] = MaterializationPoint(
                    node_id=parent_id,
                    reason=MaterializationReason.PRE_DESTINATION_STAGING,
                    staging_table=f"staging_job_{job_id}.node_{parent_id}"
                )
```

### Execution Flow

1. **Build execution plan** - Detects compute_1 needs staging
2. **Level 2 execution** - Creates `staging_job_abc.node_compute` with nested SQL
3. **Verification** (optional) - User/system checks staging table
4. **Final INSERT** - Simple `SELECT * FROM staging_table`
5. **Cleanup** - Drop staging schema

---

## 📊 Comparison: With vs Without BOUNDARY C

### Without BOUNDARY C

```sql
-- Final INSERT with nested SQL
INSERT INTO "dest_pointers"
SELECT *, CURRENT_TIMESTAMP AS processed_at
FROM (
    SELECT id, name, status, connection_id, update_time
    FROM (
        SELECT * FROM "staging_job_abc.node_join"
    ) proj3
) comp;
```

**Issues**:
- ❌ No way to verify data before INSERT
- ❌ If INSERT fails, hard to debug
- ❌ No staging snapshot for audit

### With BOUNDARY C

```sql
-- Step 1: Create staging table
CREATE TABLE "staging_job_abc.node_compute" AS
SELECT *, CURRENT_TIMESTAMP AS processed_at
FROM (
    SELECT id, name, status, connection_id, update_time
    FROM (
        SELECT * FROM "staging_job_abc.node_join"
    ) proj3
) comp;

-- Step 2: Verify (optional)
SELECT COUNT(*) FROM "staging_job_abc.node_compute";

-- Step 3: Final INSERT
INSERT INTO "dest_pointers"
SELECT * FROM "staging_job_abc.node_compute";
```

**Benefits**:
- ✅ Can verify data before INSERT
- ✅ Easy to debug if issues arise
- ✅ Staging snapshot for audit
- ✅ Rollback capability

---

## 🧪 Testing

Run the test suite to see BOUNDARY C in action:

```bash
cd services/migration_service
python test_sql_pushdown.py
```

**Expected output**:

```
TEST 3: Complex Pipeline (User's Canvas)
================================================================================

2. Materialization points:
   - filter_1: branch_end_before_join
   - proj_2: branch_end_before_join
   - join_1: join_result
   - compute_1: pre_destination_staging

3. Execution levels:
   Level 0: ['trad_conn', 'trad_log', 'proj_1', 'filter_1', 'proj_2']
   Level 1: ['join_1']
   Level 2: ['proj_3', 'compute_1', 'dest_1']

   Total queries: 4
   Total staging tables: 4
   Pre-destination staging: staging_job_test_job_003.node_compute_1 ✓
   Post-JOIN chain: Compiled as nested SQL into staging table ✓
   Final INSERT: FROM staging table (allows verification) ✓
```

---

## ✅ Compliance with Universal Linear-Segment Reuse Rule

### Does BOUNDARY C Violate the Rule?

**NO!** ✅

### Why Not?

The rule states: **Linear segments → nested SQL (zero intermediate staging)**

BOUNDARY C creates **ONE staging table** for the **ENTIRE linear segment** compiled as **nested SQL**.

```
JOIN → proj → filter → compute
       └──────────────────────┘
       Linear segment
       Compiled as ONE nested SQL
       Into ONE staging table
```

**NOT** broken into multiple staging tables:
```
❌ WRONG: proj → (stage) → filter → (stage) → compute → (stage)
```

**✅ CORRECT**: proj → filter → compute → (ONE stage)

---

## 🎯 Summary

### BOUNDARY C Provides

- ✅ **Data verification** before final INSERT
- ✅ **Staging snapshot** for audit/debugging
- ✅ **Rollback capability** if data is incorrect
- ✅ **Quality checks** on staging table
- ✅ **Production safety** - no direct writes to destination

### Still Maintains

- ✅ **Universal Linear-Segment Reuse Rule** (nested SQL for linear chains)
- ✅ **Minimal materialization** (only at physical boundaries)
- ✅ **Deterministic execution** (identical SQL for same input)
- ✅ **Zero Python row processing** (all in database)

**BOUNDARY C is a production-critical feature that enhances safety without violating core principles!** ✅
