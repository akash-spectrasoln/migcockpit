# Execution Plan and Metadata: Complete Guide

This document explains how the execution plan is built (source → intermediate staging → destination), every rule set, every linear node case, how metadata is created, and how it is used.

---

## 1. High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ VALIDATE (API)                                                                           │
│ 1. validate_pipeline()                                                                    │
│ 2. generate_all_node_metadata() → writes to CANVAS_CACHE.node_cache_metadata              │
│ 3. _load_node_metadata_from_cache() → populates config["node_output_metadata"]            │
│ 4. detect_materialization_points() → which nodes get staging tables                      │
│ 5. build_execution_plan() → compiles SQL for each level                                  │
│ 6. save_execution_plan_to_db() (if persist)                                              │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ EXECUTE (Orchestrator)                                                                   │
│ 1. _load_node_metadata_from_cache() → config["node_output_metadata"] from DB             │
│ 2. _enrich_config_with_metadata() → source columns from LIMIT 0                          │
│ 3. _ensure_source_metadata_for_plan() → technical_name = {prefix}_{db_name}                │
│ 4. build_execution_plan() OR load from DB                                                │
│ 5. For each level: CREATE TABLE staging AS SELECT ... (or run on source DB)              │
│ 6. destination_create_sql, final_insert_sql, cleanup_sql                                │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Execution Plan Structure

The execution plan is built in `planner/execution_plan.py` by `build_execution_plan()`.

### 2.1 Inputs

| Input | Purpose |
|------|---------|
| `nodes` | List of pipeline nodes (source, projection, filter, join, aggregation, destination, etc.) |
| `edges` | Connections between nodes |
| `materialization_points` | Dict of node_id → MaterializationPoint (which nodes get staging tables) |
| `config` | Contains `node_output_metadata`, `source_configs`, `filter_pushdown_plan`, etc. |
| `job_id` | Unique job identifier for staging table names |
| `shared_source_terminals` | source_id → [terminal_ids] when one source feeds multiple branches |

### 2.2 Output: ExecutionPlan

```python
ExecutionPlan(
    job_id=str,
    staging_schema="staging_jobs",
    levels=[ExecutionLevel(level_num, queries, node_ids), ...],
    destination_create_sql=str,   # CREATE TABLE for each destination
    final_insert_sql=str,         # INSERT INTO destination FROM staging
    destination_creates=[...],    # One per destination
    final_inserts=[...],          # One per destination
    cleanup_sql=str,              # DROP staging tables
    total_queries=int
)
```

### 2.3 Execution Levels (Topological Order)

Levels are built via `_build_execution_levels()` — a topological sort so dependencies run first.

- **Level 0:** Source nodes (and shared source staging if applicable)
- **Level 1+:** Branch terminals, JOINs, aggregations, pre-destination staging

For each node in each level, the plan chooses:

| Node Type | Action |
|-----------|--------|
| `destination` | **Skip** (handled separately) |
| `source` + in materialization_points + shared_source_terminals | `compile_source_staging_sql()` |
| `join` | `compile_join_sql()` |
| `aggregation` | `compile_aggregation_sql()` |
| In materialization_points | `compile_staging_table_sql()` |
| Otherwise | **Skip** (part of linear chain, no staging) |

---

## 3. Materialization Rules (When Staging Tables Are Created)

Staging tables are created **only at boundaries**. Linear chains between boundaries are compiled as nested SQL (no intermediate CREATE TABLE).

### 3.1 Rule Set (from `materialization.py`)

| Boundary | MaterializationReason | When |
|---------|----------------------|------|
| **A. Branch end before JOIN** | `BRANCH_END_BEFORE_JOIN` | The node immediately before a JOIN (each branch gets one staging) |
| **B. JOIN result** | `JOIN_RESULT` | The JOIN node output is always materialized |
| **B. Aggregation result** | `AGGREGATION_RESULT` | The aggregation node output is materialized |
| **B3. Compute anchor** | `COMPUTE_MULTI_BRANCH` | Compute node when: window functions, multi-upstream, or multiple downstream branches |
| **B3b. Multi-branch feed** | `MULTI_BRANCH_FEED` | Any node that feeds 2+ downstream branches |
| **B4. Pre-compute staging** | `PRE_COMPUTE_STAGING` | Parent of compute node (when compute is anchor) |
| **C. Pre-destination staging** | `PRE_DESTINATION_STAGING` | The single parent of each destination node |
| **Shared source** | `SHARED_SOURCE` | One source feeds 2+ branches; materialize source once (optional, depends on `should_share_source`) |

### 3.2 Linear Node Cases (No Staging)

**Linear segment** = chain with single parent, single child, no JOIN, no branching.

| Case | Example | Staging? |
|------|---------|----------|
| Source → Projection → Filter | Single branch | No staging for projection/filter; only at boundaries |
| Source → Filter → Projection → Filter | Linear chain | No staging in middle |
| Projection → Filter → Destination | Pre-destination is materialized | Only the node before destination gets staging |
| Join → Projection → Filter → Destination | Post-join linear | Join result + pre-destination get staging; projection/filter are flattened |
| Source → Compute (inline) | Compute has no window functions, single child | No staging; computed as expression in SELECT |

**Key rule:** Linear nodes (projection, filter, sort, inline compute) are **never** materialized. They are compiled as nested SELECT inside the segment that ends at a boundary.

---

## 4. Source → Intermediate Staging → Destination

### 4.1 Source → First Staging

**Single-branch source:**
```sql
-- db_name in SELECT, technical_name in output
SELECT "cmp_id" AS "4fa62c23_cmp_id", "employee_range" AS "4fa62c23_employee_range", ...
FROM "public"."tool_company"
WHERE <filter_pushdown>  -- AND conditions
```

**Shared source (one source, multiple branches):**
```sql
-- Same pattern; filter at source: (branch1_filter) OR (branch2_filter) when all branches have filters
CREATE TABLE staging_jobs.job_xxx_node_4fa62c23-... AS
SELECT ... FROM "public"."tool_company"
WHERE (pricing = '0.02') OR ((is_trial = 'FALSE') AND employee_range = '50-100')
```

### 4.2 Intermediate Staging (Staging → Staging)

**Branch terminal (feeds JOIN):**
- Reads from shared source staging or own source staging
- Output: **technical names only** (no AS to business names) — JOIN expects `l."39ef59b7_*"` and `r."4fa62c23_*"`
- Filter: `WHERE "4fa62c23_pricing" = '0.02'` (AND within branch)

**JOIN:**
- Left staging has `39ef59b7_*` (technical names), right has `4fa62c23_*` (technical names).
- These are **already unique** (different source prefixes), so no `_L_`/`_R_` needed in the physical columns.
- JOIN output staging table uses these technical names directly (fetched from pre-staging tables).

```sql
CREATE TABLE staging_jobs.job_xxx_node_join-... AS
SELECT l."39ef59b7_connection_id", l."39ef59b7_cmp_id", r."4fa62c23_cmp_id", r."4fa62c23_cmp_name", ...
FROM left_staging l
INNER JOIN right_staging r ON l."39ef59b7_cmp_id" = r."4fa62c23_cmp_id"
```

- **Metadata** for the join node has `technical_name` (e.g. `39ef59b7_cmp_id`, `4fa62c23_cmp_id`) and `business_name` (e.g. `connection_id`, `cmp_id_left`, `cmp_id_right` for conflicting).
- **Destination** uses metadata to map staging `technical_name` → destination `business_name`.
- *Note:* `_L_`/`_R_` is only used when both sides have the **exact same** column name (rare); normally left/right prefixes make names unique.

**Post-join linear:**
- Reads from join staging (technical names).
- Flattened from join staging through projection → filter → pre-destination.

### 4.3 Staging → Destination

**Destination CREATE:**
- Uses `node_output_metadata` for the **schema anchor** (source, join, or aggregation)
- Columns normalized: `_L_X` / `_R_X` → business names (`cmp_id_left`, `cmp_id_right`)
- `CREATE TABLE IF NOT EXISTS "schema"."table" ("col1" BIGINT, "col2" TEXT, ...)`

**Destination INSERT:**
- For each destination column (business name), resolve staging column (technical name) via metadata
- If staging has the column: `SELECT "4fa62c23_cmp_id"` 
- If staging does not (e.g. projection dropped it): `NULL`
- `INSERT INTO dest (cmp_id, cmp_name, ...) SELECT "4fa62c23_cmp_id", NULL, ... FROM staging`

### 4.4 NULL Values in Destination: When and Why

| Cause | Behavior | Fix |
|-------|----------|-----|
| **Projection excludes column** | Column not in `final_config.get("columns")` → not selected in staging → NULL in destination | By design; add column to projection if needed |
| **Filter uses column in WHERE but not in SELECT** | Column used in `WHERE col = value` but not in projection → staging lacked it → NULL | **Fixed:** Filter-condition columns are now added to SELECT in both `flatten_segment` and `flatten_segment_from_source` |
| **Schema anchor has more columns than parent** | Destination schema from anchor; parent staging has fewer columns → NULL for missing | Correct; `staging_cols_set` from parent metadata |

### 4.5 Calculated Column Flow

**In `flatten_segment_from_source`** (source → staging):
- Projection `calculated_columns` are resolved via `calc_col_map` (built from projection/compute config).
- Expression references source columns (`db_name` or `technical_name`); output uses `technical_name`.
- If reading from **source table**: calculated columns are computed in the SELECT (e.g. `(UPPER("status")) AS "a4e7e754_upper_trial"`).
- If reading from **shared staging**: staging already has them; we pass through.

**Downstream:** Once in staging, calculated columns act as normal columns. Downstream nodes (filter, projection, destination) reference them by `technical_name`.

### 4.6 Edge Cases

| # | Scenario | Behavior |
|---|----------|----------|
| 1 | Filter uses column in WHERE, projection excludes it | Filter-condition columns are now included in SELECT when available upstream |
| 2 | Projection explicitly excludes columns | NULL by design; optional validation warning can be added |
| 3 | Calculated column from source | Fetched via `calc_col_map`; flows as normal column |
| 4 | Calculated column in projection before destination | Technical name `{node_id[:8]}_{name}` in staging; metadata has `technical_name` |
| 5 | Schema anchor has more columns than parent | INSERT uses NULL for missing; correct |
| 6 | Post-join segment: Filter is final node | Filter-condition columns are now added to SELECT |

---

## 5. Metadata: Creation

### 5.1 When Metadata Is Created

| Trigger | Where | What |
|---------|-------|------|
| **Validate** | `migration_routes.py` → `generate_all_node_metadata()` | Generates metadata for all nodes, saves to `node_cache_metadata` |
| **Canvas save** | `api/utils/metadata_sync.py` → `update_node_metadata_for_canvas()` | Calls `generate_all_node_metadata()` after save |
| **Node insert** | `node_management.py` | Calls `update_node_metadata_for_canvas()` after insert |
| **Node delete** | `node_management.py` | Calls `delete_node_metadata_from_cache()` then `update_node_metadata_for_canvas()` |

### 5.2 Metadata Generator (`metadata_generator.py`)

Processes nodes in **topological order** (sources first, then downstream).

| Node Type | Function | How |
|-----------|----------|-----|
| **Source** | `_generate_source_metadata()` | Connects to actual source DB, queries `information_schema.columns`; `technical_name = {node_id[:8]}_{col_name}` |
| **Join** | `_generate_join_metadata()` | Reads left/right metadata from DB; uses business names; conflicting columns → `{base}_left`, `{base}_right` |
| **Filter** | `_generate_filter_metadata()` | Pass-through from upstream |
| **Projection** | `_generate_projection_metadata()` | Selected columns from upstream + `_append_calculated_columns_to_metadata()` |
| **Aggregation** | `_read_upstream_metadata_fallback()` | Reads from upstream node |
| **Other** | `_read_upstream_metadata_fallback()` | Reads from first upstream |

### 5.3 Metadata Storage

**Table:** `CANVAS_CACHE.node_cache_metadata`

| Column | Purpose |
|--------|---------|
| `canvas_id` | Canvas ID |
| `node_id` | Node ID (unique per canvas) |
| `columns` | JSONB: list of `{business_name, technical_name, db_name, base, datatype, source, ...}` |
| `is_valid` | Whether metadata is current |

**Calculated columns** (from projection `calculated_columns`):
- `technical_name = {projection_node_id[:8]}_{name}`
- `source = "calculated"`, `isCalculated = True`

---

## 6. Metadata: Usage

### 6.1 When Metadata Is Loaded

| Phase | Where | Action |
|-------|-------|--------|
| **Validate** | `migration_routes.py` | `_load_node_metadata_from_cache()` → populates `config["node_output_metadata"]` |
| **Execute** | `execute_pipeline_pushdown.py` | `_load_node_metadata_from_cache()` before building plan |
| **Execute** | `execute_pipeline_pushdown.py` | `_enrich_config_with_metadata()` for source columns (LIMIT 0) |
| **Execute** | `execute_pipeline_pushdown.py` | `_ensure_source_metadata_for_plan()` ensures `technical_name` on all source columns |

### 6.2 Where Metadata Is Used

| Consumer | File | Use |
|----------|------|-----|
| **SQL compiler** | `sql_compiler.py` | Column names for SELECT, AS aliases, JOIN ON clause, calculated columns |
| **Execution plan** | `execution_plan.py` | Destination CREATE (schema anchor columns), INSERT (staging → dest mapping) |
| **Filter optimizer** | `filter_optimizer.py` | Lineage for pushdown (`_L_cmp_id` → `39ef59b7_cmp_id` → `cmp_id`) |

### 6.3 config["node_output_metadata"] Structure

```python
config["node_output_metadata"] = {
    "node_id_1": {
        "columns": [
            {"business_name": "cmp_id", "technical_name": "4fa62c23_cmp_id", "db_name": "cmp_id", "base": "4fa62c23...", "datatype": "BIGINT"},
            {"business_name": "upper_trial", "technical_name": "a4e7e754_upper_trial", "db_name": None, "base": "a4e7e754...", "source": "calculated"}
        ]
    },
    ...
}
```

### 6.4 Key Mappings

| Purpose | Lookup |
|---------|--------|
| **Staging column name** | `technical_name` from metadata |
| **Destination column name** | `business_name` (user-facing, shown in UI, editable) |
| **Source column (db)** | `db_name` or `name` |
| **JOIN ON clause** | `_name_to_staging_col()` returns `technical_name` for left/right |
| **Filter pushdown** | Lineage: `_L_cmp_id` → `39ef59b7_cmp_id` → `cmp_id` (source) |

---

## 7. End-to-End Example

**Pipeline:** Source (tool_company) → Projection → Filter → Destination

1. **Materialization:** Only pre-destination (the projection before destination) gets staging.
2. **Metadata:** Source → from DB; Projection → selected columns + calculated from config; Filter → pass-through.
3. **Execution level 0:** Source is not in materialization_points (single branch, no shared source) → **Skip**.
4. **Execution level 1:** Pre-destination projection is in materialization_points → `compile_staging_table_sql()`:
   - Flattens: source → projection → filter (nested or flattened SELECT)
   - `CREATE TABLE staging_jobs.job_xxx_node_xxx AS SELECT ... FROM (SELECT ... FROM "public"."tool_company")`
5. **Destination:** `_generate_destination_create_one()` uses schema anchor (source) metadata; `_generate_final_insert_one()` maps staging technical names to destination business names.

---

## 8. Quick Reference

| Concept | Location |
|---------|----------|
| Materialization rules | `planner/materialization.py` — `detect_materialization_points()` |
| Linear = no staging | Only boundary nodes in `materialization_points` |
| Nested SQL | `planner/sql_compiler.py` — `compile_nested_sql()`, `traverse_upstream()` |
| Flatten segment | `planner/sql_compiler.py` — `flatten_segment_from_source()` |
| Metadata generation | `planner/metadata_generator.py` — `generate_all_node_metadata()` |
| Metadata storage | `CANVAS_CACHE.node_cache_metadata` |
| Metadata load | `execute_pipeline_pushdown.py` — `_load_node_metadata_from_cache()` |
| Destination CREATE | `execution_plan.py` — `_generate_destination_create_one()` |
| Destination INSERT | `execution_plan.py` — `_generate_final_insert_one()` |

---

## 9. Two Metadata Sources (Should Match)

There are **two** places that store node column metadata. They should be the same after explicit Save Pipeline.

### 9.1 Source A: Canvas.configuration (Django DB)

| What | `node.data.output_metadata.columns` inside `Canvas.configuration` JSON |
| Where stored | Django DB — `api_canvas.configuration` |
| Written by | Frontend config panels (ProjectionConfigPanel, FilterConfigPanel, etc.) via `onUpdate` → save-configuration |
| Read by | Frontend when loading canvas; node display (column count); config panels for upstream columns |
| Key files | `ProjectionConfigPanel.tsx` (handleSave), `EnhancedFilterConfigPanel.tsx`, `DataFlowCanvasChakra.tsx` |

### 9.2 Source B: node_cache_metadata (Customer DB)

| What | `columns` JSONB in `CANVAS_CACHE.node_cache_metadata` |
| Where stored | Customer DB (e.g. C00008) — `CANVAS_CACHE.node_cache_metadata` |
| Written by | `update_node_metadata_for_canvas()` → `generate_all_node_metadata()` (only on explicit Save Pipeline) |
| Read by | `_load_node_metadata_from_cache()` → populates `config["node_output_metadata"]` for Validate/Execute |
| Key files | `api/utils/metadata_sync.py`, `metadata_generator.py`, `execute_pipeline_pushdown.py` |

### 9.3 How They Are Built

| Source | Builds from |
|--------|-------------|
| **A (Canvas.configuration)** | Frontend: `includedColumns`, `selectedColumns`, `calculatedColumns` from config; builds `output_metadata` in config panel save |
| **B (node_cache_metadata)** | Backend: `config.includedColumns`, `config.selectedColumns`, `config.calculatedColumns`; upstream from `_read_metadata_from_db()` |

Both use the same config fields. Source B does **not** read `output_metadata` from the node; it recomputes from config.

### 9.4 When They Can Diverge

- **Auto-save** (add destination, rename): `skip_metadata_sync: true` → Source B is **not** updated. Source A has latest config.
- **Column naming**: A may use `name`; B uses `business_name` / `technical_name` (both valid).
- **Order**: May differ; both are valid if column sets match.

### 9.5 Downstream Propagation When Upstream Changes

When you add a column (e.g. calculated column) to an upstream projection (p1) and save it, the new schema must propagate to downstream nodes (Filter, p2). The frontend now cascades `output_metadata` automatically:

- **On Projection save**: When a projection's `output_metadata` changes, it propagates to all downstream Filter nodes (schema-transparent). Those Filters pass the new columns through so downstream projections (p2) see them when their config panel loads.
- **Save Pipeline**: Backend `update_node_metadata_for_canvas` regenerates metadata for all nodes in topological order and writes to `node_cache_metadata`, so Validate/Execute use the correct schema.

### 9.6 Which Is "Correct"?

| Use case | Source of truth |
|----------|------------------|
| **Validate / Execute** | Source B (`node_cache_metadata`) — backend uses this |
| **UI display (column count, config panels)** | Source A (`node.data.output_metadata`) — frontend uses this |

To verify they match: after explicit Save Pipeline, query both and compare column names/counts:

```sql
-- Source B (customer DB)
SELECT node_id, jsonb_array_length(columns) as col_count, columns
FROM "CANVAS_CACHE".node_cache_metadata
WHERE canvas_id = <your_canvas_id>;
```

Source A is in `Canvas.configuration` → `nodes[].data.output_metadata.columns` (inspect via API or Django admin).

---

## 10. Migration Service Standalone Mode

The migration service runs on port 8003 and may be started **without** the Django `api` package on `PYTHONPATH`. In that case:

| Component | Without `api` | With `api` |
|-----------|---------------|------------|
| **Metadata generation** | Skipped (returns 0) | Generates live metadata for all nodes |
| **Filter optimizer lineage** | Reads from cache via `psycopg2` | Same (no longer uses `get_customer_db_connection`) |
| **Execute pipeline** | Uses `connection_config` + `psycopg2` | Same |

### 10.1 Lineage Cache Read (Fixed)

`filter_optimizer` previously imported `get_customer_db_connection` from `api.utils.db_connection`, causing `No module named 'api'` when the migration service ran standalone. It now connects directly with `psycopg2` using `connection_config` from the validate request, so lineage can be read from `CANVAS_CACHE.node_cache_metadata` without Django.

### 10.2 Log Messages to Expect

- `[METADATA] Django 'api' package not available` — Normal when running standalone; metadata generation is skipped.
- `[LINEAGE] No canvas_id in config` — Validate was called without `canvas_id`; lineage cannot be read from cache.
- `relation "public.tool_user" does not exist` — Source table does not exist in the customer DB; fix source config or create the table.
- `column 'X' not in source and not a calculated column` — Projection expects columns that are not in the upstream node; fix projection config.
