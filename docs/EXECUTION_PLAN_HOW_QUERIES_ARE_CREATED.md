# How the Execution Plan and Queries Are Created

This doc maps your **pipeline graph** (sources → projections → join → new projections → filters → compute → destination) to the **execution plan JSON** (levels, queries, `final_insert_sql`).

## High-level flow

1. **Graph + config** → **Materialization points** (which nodes get staging tables)
2. **Graph** → **Topological levels** (execution order)
3. **Per level** → **SQL compilation** (CREATE TABLE … AS … for each materialized node or JOIN)
4. **Destination** → **Final INSERT** and **cleanup SQL**

All of this happens in `services/migration_service/planner/` and is invoked from `main.py` (validate) or the pushdown orchestrator (run).

---

## How staging tables are physically created (end-to-end)

Staging tables are **not** created at validate time. They are created at **run time** when the pipeline is executed. Here is the full flow.

### 1. Decide *which* nodes get staging tables

**File:** `planner/materialization.py` → `detect_materialization_points(nodes, edges, job_id)`

- The function walks the graph and marks only **boundary** nodes as materialization points.
- For each such node it sets a **staging table name**: `staging_job_{job_id}.node_{node_id}` (e.g. `staging_job_abc123.node_5d2647be-...`).
- Boundaries are: **branch end before JOIN**, **JOIN result**, **pre-destination** (node that feeds the destination), and **shared source** (one source feeding multiple branches).
- Result: a dict `materialization_points[node_id] = MaterializationPoint(staging_table="staging_job_... .node_...")` and optionally `shared_source_terminals[source_id] = [terminal_ids]`.

So at this step we only **decide** which staging tables will exist and their names; no SQL is run yet.

### 2. Build the execution plan (SQL strings only)

**File:** `planner/execution_plan.py` → `build_execution_plan(nodes, edges, materialization_points, config, job_id, shared_source_terminals)`

- **Staging schema name:** `staging_schema = f"staging_job_{job_id}"` (e.g. `staging_job_abc123`).
- **Levels:** Nodes are sorted topologically into levels (level 0 = sources, then next level, etc.).
- **Per level, per node:**
  - If node is **source** and in `shared_source_terminals` → append one query from `compile_source_staging_sql(...)`.
  - If node is **join** → append one query from `compile_join_sql(...)`.
  - If node is in **materialization_points** (branch end or pre-destination) → append one query from `compile_staging_table_sql(...)`.
- Each “query” is a **CompiledSQL** object whose `.sql` is a full statement, e.g.  
  `CREATE TABLE "staging_job_abc123"."node_5d2647be-..." AS SELECT ... FROM "public"."some_table" ...`
- **Cleanup:** `cleanup_sql = 'DROP SCHEMA IF EXISTS "staging_job_abc123" CASCADE'`.

So the plan is a list of **levels**, each level containing a list of **SQL strings**. No database connection is used here; it’s pure planning.

### 3. Generate the CREATE TABLE … AS SQL for each staging table

**File:** `planner/sql_compiler.py`

- **Branch end / pre-destination:** `compile_staging_table_sql(node_id, ...)`  
  - Calls `compile_nested_sql(node_id, ...)` to build a nested SELECT from this node back to a source or to another staging table.  
  - Then wraps it: `CREATE TABLE "staging_job_{job_id}"."node_{node_id}" AS <nested SELECT or flattened SELECT>`.  
  - Flattening (when possible) turns nested subqueries into one flat `SELECT ... FROM base_table [WHERE ...]` so a single CREATE TABLE AS runs one query.
- **JOIN:** `compile_join_sql(join_node_id, ...)`  
  - Builds `CREATE TABLE "staging_job_{job_id}"."node_{join_id}" AS SELECT ... FROM left_staging l JOIN right_staging r ON ...`.
- **Shared source:** `compile_source_staging_sql(source_id, branch_terminal_ids, ...)`  
  - Builds one `CREATE TABLE "staging_job_{job_id}"."node_{source_id}" AS SELECT <union of columns + calculated expressions> FROM base_table ...`.

So every staging table in the plan has a **single** `CREATE TABLE ... AS <SELECT>` statement.

### 4. Create the staging schema and run the queries (run time)

**File:** `orchestrator/execute_pipeline_pushdown.py`

When the pipeline **runs** (not at validate):

1. **Create staging schema (empty)**  
   - `_create_staging_schema(db_connection, execution_plan.staging_schema)`  
   - Executes: `DROP SCHEMA IF EXISTS "staging_job_{job_id}" CASCADE` then `CREATE SCHEMA "staging_job_{job_id}"`.  
   - So the schema exists but has **no tables** yet.

2. **Execute each level’s queries in order**  
   - For each `level` in `execution_plan.levels`:  
     - For each `compiled_sql` in `level.queries`:  
       - `_execute_sql(db_connection, compiled_sql.sql)`.  
   - Each `compiled_sql.sql` is one of the `CREATE TABLE ... AS ...` statements from step 3.  
   - So the **first** such execution creates the first staging table inside `staging_job_{job_id}`; the next creates the second; and so on.  
   - Execution order follows the plan (e.g. source/branch staging first, then JOIN, then pre-destination), so dependencies (e.g. JOIN reading from branch tables) are satisfied.

3. **Destination and cleanup**  
   - Run `destination_create_sql` if present (create destination table).  
   - Run `final_insert_sql` (INSERT into destination from the last staging table).  
   - Run `cleanup_sql`: `DROP SCHEMA IF EXISTS "staging_job_{job_id}" CASCADE`, which **drops the staging schema and all staging tables** in it.

So: **staging tables are created** when the executor runs the corresponding `CREATE TABLE ... AS` from the plan, and **removed** when the executor runs the cleanup SQL at the end of the job.

---

## Step 1: Materialization points

**File:** `planner/materialization.py` → `detect_materialization_points(nodes, edges, job_id)`

Only **four kinds of boundaries** get staging tables; everything else is compiled as **nested SQL** (no extra tables).

| Boundary | When | Your pipeline |
|----------|------|----------------|
| **A. Branch end before JOIN** | End of each branch that feeds a JOIN | Projection on `tool_connection` (node `5d26...`) and projection on `tool_log` (node `30a8...`) |
| **B. JOIN result** | Output of every JOIN node | Join node `ee67...` |
| **D. Shared source** | One source feeds multiple branches to a JOIN | Source materialized once; branch terminals read from `staging.node_<source_id>` |
| **C. Pre-destination** | Single node that feeds the destination | The last node before `dest_postres` (e.g. the “New projection” that feeds destination, node `72fa...`) |

So you get **4 staging tables** in the typical two-branch pipeline (or **5** when one source feeds both branches: one source staging + two branch terminals + join + pre-destination):

- 2 from branch ends (one per source branch), or 1 shared source staging + 2 branch terminals when one source feeds both branches
- 1 from the JOIN
- 1 from the node right before the destination

Filters, compute, and other projections in between do **not** get their own tables; they are inlined into nested SQL.

**Return value:** `detect_materialization_points` returns a tuple `(materialization_points, shared_source_terminals)`. The second is a map `source_id -> [terminal_id, ...]` used when compiling the source staging table.

---

## Step 2: Execution levels (topological order)

**File:** `planner/execution_plan.py` → `_build_execution_levels(nodes, edges)`

- Builds a **DAG** from `nodes` and `edges`.
- **Topological sort**: level 0 = nodes with no incoming edges (sources), then level 1 = nodes whose parents are done, etc.
- Result: `execution_levels = [ level0_nodes, level1_nodes, level2_nodes, ... ]`.

In your pipeline:

- **Level 0**: the two source nodes (or the first nodes in each branch).
- **Level 1**: next nodes (e.g. the two projections on `tool_connection` and `tool_log`).  
  → These are **materialization boundary A** (branch ends before JOIN), so they get **2 queries** in the plan (your “level 1”).
- **Level 2**: the JOIN node.  
  → **Materialization boundary B**, so **1 query** (your “level 2”).
- **Levels 3–6**: the “New projection”, “New filter”, “New projection”, “New filter” along the chain.  
  → None of these are materialization points, so **no queries** at these levels.
- **Level 7**: the node that feeds the destination (e.g. the Compute or the last projection before destination).  
  → **Materialization boundary C**, so **1 query** (your “level 7”).

So the plan has **4 total queries** across levels 1, 2, and 7.

---

## Step 3: How each query is compiled

**File:** `planner/execution_plan.py` → `build_execution_plan()` loop over levels

For each level, for each node in that level:

- **Skip** destination nodes.
- If node is **JOIN** → `compile_join_sql(...)` → one `CREATE TABLE staging_job_... .node_<join_id> AS SELECT ... FROM left_staging JOIN right_staging ON ...`.
- If node is **in materialization_points** (branch end or pre-destination) → `compile_staging_table_sql(...)`.

### What `compile_staging_table_sql` does

**File:** `planner/sql_compiler.py`

1. **Nested SQL**  
   `compile_nested_sql(node_id, ...)` walks **upstream** from this node until it hits:
   - a **source** (SELECT from DB table, with optional pushdown WHERE), or  
   - a **materialized** node (SELECT * FROM staging table).

   Along the way it applies:
   - **Source**: table + filters (and only needed columns if we have metadata).
   - **Projection**: only necessary base columns + calculated column expressions.
   - **Filter**: WHERE.
   - **Compute**: computed columns.
   - **Join**: not in this chain (joins are compiled separately).

   So for the **pre-destination** node you get one long nested SELECT (source → proj → join → proj → filter → proj → filter → compute).

2. **Staging table**  
   - Staging name: `staging_job_{job_id}.node_{node_id}`.  
   - If we can **flatten** that nested SELECT into a single `SELECT ... FROM base_table [WHERE ...]` (or one JOIN), we do it; otherwise we wrap it as `SELECT col_list FROM ( nested ) nested`.  
   - Result:  
     `CREATE TABLE "staging_job_...".\"node_..." AS <that SELECT>`.

So:

- **Level 1 (branch ends)**  
  - One query per branch: `CREATE TABLE ... AS SELECT <cols> FROM "public"."tool_connection" WHERE ...` and same for `"public"."tool_log"`.  
  - Columns come from projection config / metadata; nested subqueries are flattened when possible.

- **Level 2 (JOIN)**  
  - One query: `CREATE TABLE ... AS SELECT ... FROM left_staging l INNER JOIN right_staging r ON ...`.

- **Level 7 (pre-destination)**  
  - One query: `CREATE TABLE ... AS SELECT <cols> FROM ( nested chain from join → projections → filters → compute ) nested`.  
  - That nested chain is the “New projection (26 COLS)” → “New filter” → “New projection (25 COLS)” → “New filter” → “Compute” compiled into a single nested SELECT, then wrapped (or flattened if possible).

---

## Step 4: Final INSERT and cleanup

**File:** `planner/execution_plan.py` → `_generate_final_insert()`, and then `cleanup_sql`

- **Final INSERT**  
  - Destination = `dest_postres` (e.g. `"public"."demo_data"`).  
  - Source = the **pre-destination staging table** (the one from the level-7 query).  
  - So:  
    `INSERT INTO "public"."demo_data" SELECT * FROM "staging_job_...".\"node_72fa..."`.

- **Cleanup**  
  - `DROP SCHEMA IF EXISTS "staging_job_validate_11_1771305342" CASCADE`.

---

## Summary mapping (your pipeline → plan)

| Pipeline element | Plan / query |
|------------------|--------------|
| tool_connection (source) + Projection (18 COLS) | Level 1, 1st query: CREATE TABLE node_5d26... AS SELECT … FROM "public"."tool_connection" WHERE ... |
| tool_log (source) + Projection (9 COLS) | Level 1, 2nd query: CREATE TABLE node_30a8... AS SELECT … FROM "public"."tool_log" |
| Join (INNER, 1 KEY) | Level 2, 1 query: CREATE TABLE node_ee67... AS SELECT … FROM node_30a8... l INNER JOIN node_5d26... r ON ... |
| New projection (26) → New filter → New projection (25) → New filter → Compute | Compiled as **nested SQL**; no extra staging. |
| Node that feeds dest_postres | Level 7, 1 query: CREATE TABLE node_72fa... AS SELECT … FROM ( nested SQL above ) nested |
| dest_postres | final_insert_sql: INSERT INTO "public"."demo_data" SELECT * FROM node_72fa... |
| Staging schema | cleanup_sql: DROP SCHEMA ... CASCADE |

So: **only necessary fields** are selected at projections (and we add calculated columns as expressions); **only three boundaries** get staging tables (branch ends, JOIN, pre-destination); and nested SELECTs are **flattened to a single query** when the chain is a simple source → projection (and optionally filter) so you get one optimized CREATE TABLE per plan query.

---

## How calculated columns (e.g. UPPER_STATUS) work

**Defined where:** In a **projection** node, config keys `calculated_columns` or `calculatedColumns`: each entry has `name` (e.g. `"UPPER_STATUS"`) and `expression` (e.g. `UPPER("status")`).

**At compile time (sql_compiler):**

1. **Projection SELECT**  
   `_apply_projection` builds the SELECT as: **base columns** (only those needed) plus **calculated columns as expressions**, e.g.  
   `SELECT "connection_id", ..., (UPPER("status")) AS "UPPER_STATUS" FROM ( ... ) proj`.

2. **Flattening (with calculated columns)**  
   When we flatten to a single query, we **reuse the inner SELECT list** instead of replacing it with column names only. So the flattened SQL is  
   `SELECT "connection_id", ..., (UPPER("status")) AS "UPPER_STATUS" FROM "public"."tool_connection" WHERE ...`  
   — one flat query with the expression included. We only substitute the column list when the inner is `SELECT * FROM ...`.

3. **Inferred columns**  
   `_infer_columns` for that projection returns both base column names and calculated column names (e.g. `UPPER_STATUS`), so downstream nodes and the CREATE TABLE column list see the full output schema.

**In the execution plan:**

- **Level 1 (tool_connection branch):** The query is a **single flat query** that includes the calculated expression:  
  `CREATE TABLE ... AS SELECT "connection_id", ..., (UPPER("status")) AS "UPPER_STATUS" FROM "public"."tool_connection" WHERE "cmp_id" = 1 AND "connection_id" > 20`  
  So the expression is evaluated in SQL and the staging table gets a real `UPPER_STATUS` column.

- **Level 2 (JOIN):** The join SELECT list includes `r."UPPER_STATUS"` from the right branch, so the join result table has that column.

- **Level 7 (pre-destination):** The SELECT from the join staging table lists all columns needed for the destination, including any calculated columns that were carried through (e.g. `UPPER_STATUS` if it’s in the projection).

So **UPPER_STATUS** is computed once in SQL at the first projection (as `UPPER("status")`), stored in the branch staging table, then carried through the JOIN and into the final staging table and destination.

**Important:** Calculated column expressions (e.g. `UPPER(message)`) are **rewritten** at compile time so that column references use the **technical_name** that exists in the upstream/staging table. So if the upstream has `"9aad5245_message"`, the emitted SQL is `(UPPER("9aad5245_message")) AS "5d2647be_UPPER_MESSAGE"`. This avoids "column message does not exist" when the actual table uses technical_name.

---

## Staging table columns, JOIN, and destination (technical_name flow)

End-to-end: how column names are chosen, how staging tables are filled, how the JOIN reads them, and how data reaches the destination.

### 1. Column names in staging tables (technical_name)

- **Source staging / branch staging**  
  - The compiler uses **node_output_metadata** (from cache + enrich). Each column has `name`, `db_name`, and `technical_name` (e.g. `{source_id[:8]}_message`).
  - The **SELECT** that feeds a staging table uses: **db_name** (or name) to read from the base table, and **technical_name** for the `AS` alias. So the staging table’s column names are **technical_name**, not db_name.
  - For **source nodes**, metadata is merged with the **actual table columns** (from a live `LIMIT 0` on the customer/source DB) so we never select a column that doesn’t exist (e.g. stale cache with `job_name` when the table has no such column).

- **Projection (branch end)**  
  - Base columns are emitted as `"technical_name"` (from metadata). Calculated columns are emitted as `(expression) AS "technical_name"`, and **expression** is rewritten so every column reference uses quoted **technical_name** (e.g. `UPPER("9aad5245_message")`), so the expression matches the upstream columns.
  - So every **staging table** (source or projection) has columns named by **technical_name**.

### 2. JOIN: reading from the two projection staging tables

- The JOIN runs:  
  `CREATE TABLE staging.node_<join_id> AS SELECT ... FROM left_staging l JOIN right_staging r ON ...`
- **ON clause:** Condition columns (leftColumn, rightColumn from config) are mapped to staging column names via **node_output_metadata**: `_name_to_staging_col(node_id, config_name)` returns **technical_name** for that node. So the ON clause uses `l."technical_name"` and `r."technical_name"`.
- **SELECT list:** For each column from the left and right branches, the compiler resolves to the **staging column name** (technical_name) with `_name_to_staging_col`, then emits `l."technical_name"` and `r."technical_name"`. So the JOIN **always reads from staging using technical_name**, not db_name or display name.
- Collision handling: if the same technical_name appears on both sides, the JOIN aliases them as `_L_technical_name` and `_R_technical_name` in the join result.

### 3. Pre-destination staging and final INSERT

- The **pre-destination** staging table is built by compiling the nested SQL from the node that feeds the destination (e.g. join → projections → filters → compute). That nested SQL reads from the **JOIN staging table**, whose columns are already technical_name (and possibly `_L_` / `_R_` prefixed for collisions). So all column names in the pre-destination staging table are again technical_name (or derived from it).
- **final_insert_sql:**  
  `INSERT INTO "schema"."dest_table" SELECT * FROM "staging_job_{job_id}"."node_<pre_dest_id>"`  
  So the destination receives the same column set as the last staging table (technical_name-based). Column mapping to destination column names (if different) is handled by the planner/destination config if applicable.

### Summary

| Stage | Column names used |
|-------|-------------------|
| Source SELECT → staging | Read by db_name/name from base table; **output** (staging columns) = **technical_name** |
| Projection SELECT → staging | Base and calculated columns **output** as **technical_name**; expressions rewritten to reference **technical_name** |
| JOIN SELECT from l / r | **technical_name** only (`_name_to_staging_col`) for both ON and SELECT list |
| Pre-destination staging | Same technical_name (and _L_/_R_ if from JOIN) |
| INSERT into destination | `SELECT *` from pre-destination staging (technical_name columns) |

---

## Shared source (one source, multiple projections)

When **one source node** feeds **two or more branches** that later join (e.g. Source → ProjA → Join and Source → ProjB → Join), the planner treats that as a **fourth boundary (D. Shared source)**:

1. **Detection** (`materialization.py`): For each JOIN branch terminal, we walk back to the source. If the same source feeds more than one terminal, that source is added to materialization points with reason `SHARED_SOURCE`, and we store `shared_source_terminals[source_id] = [terminal_id_1, terminal_id_2, ...]`.

2. **Source staging query** (`sql_compiler.compile_source_staging_sql`): We build **one** `CREATE TABLE staging.node_<source_id> AS SELECT ... FROM base_table` with:
   - **Union of base columns** required by any branch (from each projection’s `columns` / `selectedColumns` along the path from terminal to source).
   - **All calculated column expressions** from all those projections (e.g. ProjA’s `(UPPER("status")) AS "UPPER_STATUS"`, ProjB’s `(qty * price) AS "total_amt"`). Calculated column names are excluded from the base column list so they appear only as expressions.
   - Pushdown filters for that source (same as for a single-branch source).

3. **Execution order**: The source node appears at level 0. When building the plan, if the node is a source and it is in materialization points with `shared_source_terminals[source_id]` set, we emit the source staging query at that level. Branch terminal queries are emitted at the next level and now **read from the source staging table** (because the source is in materialization points, `compile_nested_sql` stops at the source and returns `SELECT * FROM staging.node_source`).

4. **Branch terminal compilation**: Each branch terminal (ProjA, ProjB) still goes through `compile_staging_table_sql`. Upstream traversal stops at the source and uses `SELECT * FROM staging.node_source`; then projection/filter logic selects only that branch’s columns. So calculated columns appear **once** in the source staging table and are then just selected by name in the branch staging tables.
