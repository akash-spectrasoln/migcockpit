# Pipeline Rules: Column Naming, Conditions, and All Scenarios

This document explains **column naming conventions** at each stage (source → staging → staging → destination), **filter conditions** (AND vs OR), and **all scenarios** including parallel nodes and branches.

---

## 1. Column Name Types

| Type | Format | Example | Used Where |
|------|--------|---------|------------|
| **db_name** | Actual DB column | `cmp_id`, `employee_range` | Source tables, WHERE clauses on source |
| **technical_name** | `{source_id[:8]}_{db_name}` | `4fa62c23_cmp_id` | Staging tables (to avoid collisions) |
| **business_name** | Display/label | `cmp_id`, `Company ID` | Destination tables, UI |
| **_L_ / _R_** | Join disambiguation | `_L_cmp_id`, `_R_cmp_id` | Join output when both sides have same column |

---

## 2. Source → Staging (First Materialization)

### 2.1 Single-Branch Source

**When:** One source feeds one branch (e.g. source → projection → filter → join).

**Column rule:**
- **Read from source:** Use `db_name` (actual column names)
- **Write to staging:** Use `technical_name` = `{prefix}_{db_name}`

```sql
-- Source has: cmp_id, employee_range, pricing
-- Staging gets:
SELECT "cmp_id" AS "4fa62c23_cmp_id", "employee_range" AS "4fa62c23_employee_range", "pricing" AS "4fa62c23_pricing"
FROM "public"."tool_company"
```

**Filter rule:** Filters from `filter_pushdown_plan` are applied at source with **AND**. Use `db_name` in WHERE.

---

### 2.2 Shared Source (Multiple Branches)

**When:** One source feeds 2+ branches (e.g. tool_company → branch1 to JOIN, branch2 to destination).

**Column rule:** Same as single-branch — `db_name` in SELECT, `technical_name` in output.

**Filter rule:**
- **At source:** `(branch1_filter) OR (branch2_filter) OR ...` — only when **all** branches have filters
- **Within each branch:** Conditions are **AND**ed
- **If any branch has no filters:** No source filter (load all rows)

```sql
-- Branch 1: pricing = '0.02'
-- Branch 2: is_trial = 'FALSE' AND employee_range = '50-100'
-- Source staging:
SELECT ... FROM "public"."tool_company"
WHERE (pricing = '0.02') OR ((UPPER(is_trial::text) = 'FALSE') AND employee_range = '50-100')
```

---

## 3. Staging → Staging (Intermediate Materialization)

### 3.1 Branch Terminal (Feeds JOIN)

**When:** Node at end of branch, feeds into JOIN.

**Column rule:**
- **Read from:** Previous staging (uses `technical_name` like `4fa62c23_cmp_id`)
- **Output:** Keep **technical_name** — do **not** alias to business_name. The JOIN expects `l."39ef59b7_*"` and `r."4fa62c23_*"`; aliasing would break the join key references.

**Filter rule:** Each branch applies its **own** filter when reading from shared staging. Conditions **AND**ed within branch.

```sql
-- Reading from shared source staging, applying branch1 filter (technical names only, no AS):
SELECT "4fa62c23_billed_to", "4fa62c23_billing_start_date", "4fa62c23_cmp_id", ...
FROM "staging_jobs"."job_xxx_node_4fa62c23-..."
WHERE "4fa62c23_pricing" = '0.02'
```

---

### 3.2 JOIN Result

**When:** Two staging tables are joined.

**Column rule:**
- **Left staging:** Columns like `39ef59b7_cmp_id`, `39ef59b7_connection_id`
- **Right staging:** Columns like `4fa62c23_cmp_id`, `4fa62c23_cmp_name`
- **Join output:** Keep both; for **ambiguous** columns (same base name on both sides), use `_L_` and `_R_` suffixes

```sql
SELECT l."39ef59b7_connection_id", l."39ef59b7_cmp_id", r."4fa62c23_cmp_id", r."4fa62c23_cmp_name", ...
FROM left_staging l
INNER JOIN right_staging r ON l."39ef59b7_cmp_id" = r."4fa62c23_cmp_id"
```

**Filter rule:** Post-join filters on source columns (e.g. `_L_cmp_id = 1`) are pushed to source when possible. Otherwise applied at join output.

---

### 3.3 Post-Join Linear Chain

**When:** JOIN → projection → filter → ...

**Column rule:** Read from join staging using `technical_name` or `_L_`/`_R_` names. Output keeps `technical_name` for consistency.

**Filter rule:** Filters **AND**ed. Post-join filters on left/right columns use `_build_filter_col_to_upstream` to map `_L_cmp_id` → `39ef59b7_cmp_id` (actual join output column).

---

## 4. Staging → Destination

### 4.1 Column Mapping

**Destination columns:** Use **business_name** (e.g. `cmp_id`, `employee_range`).

**Staging columns:** Depends on path:
- **Destination-feeding path:** Staging is aliased to **business_name** (`cmp_id`, `employee_range`)
- **Otherwise:** Staging has **technical_name** (`4fa62c23_cmp_id`)

**INSERT rule:** Map each destination column to staging column:
1. Try `business_name` (when staging was aliased)
2. Try `technical_name`
3. Use NULL if column missing in staging

```sql
-- When staging has business-name aliases:
INSERT INTO "public"."current_destination" ("cmp_id", "employee_range", ...)
SELECT "cmp_id", "employee_range", ... FROM staging

-- When staging has technical names:
INSERT INTO "public"."current_destination" ("cmp_id", "employee_range", ...)
SELECT "4fa62c23_cmp_id", "4fa62c23_employee_range", ... FROM staging
```

---

## 5. Scenarios: Parallel Nodes and Branches

### 5.1 Single Source, Single Branch

```
Source → Projection → Filter → Destination
```

- **Materialization:** Source (optional), Pre-destination
- **Column flow:** db_name → technical_name → business_name (at destination)
- **Filters:** AND at source (if pushed) or in segment

---

### 5.2 Single Source, Two Branches to JOIN

```
        ┌→ Proj → Filter → [JOIN left]
Source ─┤
        └→ Proj → Filter → [JOIN right]
```

- **Materialization:** Shared source, Branch terminal (left), Branch terminal (right), JOIN result
- **Column flow:** Source staging has `technical_name`; each branch reads and applies its filter
- **Filters:** OR at source (if both have filters), AND within each branch

---

### 5.3 Single Source, One Branch to JOIN + One to Destination

```
        ┌→ Proj → Filter → [JOIN right]
Source ─┤
        └→ Proj → Filter → Destination
```

- **Materialization:** Shared source (MULTI_BRANCH_FEED), Branch terminal (JOIN), Pre-destination (other branch)
- **Column flow:** Same shared source staging; each branch reads with its own filter
- **Filters:** OR at source; destination-feeding branch aliases to business_name at its staging

---

### 5.4 Two Sources, JOIN, Then Destination

```
Source1 → Filter → [JOIN left]  → Proj → Filter → Destination
Source2 → Filter → [JOIN right]
```

- **Materialization:** Source1 staging, Source2 staging, JOIN result, Pre-destination
- **Column flow:** Each source uses its own prefix (e.g. `39ef59b7_*`, `4fa62c23_*`); JOIN combines; post-join uses both
- **Filters:** Each source gets its own pushed filters (AND); post-join filters applied at join output or pushed back when possible

---

### 5.5 Multiple Destinations

```
                    ┌→ Destination1
Source → ... → JOIN ┤
                    └→ Destination2
```

- **Materialization:** Standard boundaries; each destination has its pre-destination staging
- **INSERT:** Each destination gets its own `CREATE TABLE` and `INSERT` statement
- **Column flow:** Schema anchor (join/source) defines full column set; each destination may select a subset

---

### 5.6 N-Way Branch (Source Feeds N Branches)

```
        ┌→ Branch1 → ...
Source ─┼→ Branch2 → ...
        └→ Branch3 → ...
```

- **Materialization:** Shared source (if `should_share_source` or MULTI_BRANCH_FEED)
- **Filters at source:** `(F1) OR (F2) OR (F3)` when **all** branches have filters
- **Filters in branches:** Each applies its own (AND within branch)

---

### 5.7 Aggregation Branch

```
Source → Filter → [Aggregation] → Destination
```

- **Materialization:** Pre-aggregation staging, Aggregation result, Pre-destination
- **Column flow:** Group-by and aggregate columns; HAVING for aggregate filters

---

### 5.8 Compute Node (Inline vs Anchor)

- **Inline:** Calculated as expression in flat SELECT; no extra staging
- **Anchor:** When window functions, multi-upstream refs, or multiple downstream branches → pre-compute staging

---

## 6. Condition Summary Table

| Scenario | Condition Logic | Where Applied |
|----------|-----------------|---------------|
| Single branch | AND | Source or in-segment |
| Multiple branches (shared source) | OR at source | Source staging |
| Within one branch | AND | Branch staging |
| Post-join filter on source col | Push to source if possible | Source or join output |
| Duplicate predicates | Dedupe (exact + semantic) | All WHERE clauses |

---

## 7. Column Naming Summary Table

| Stage | Read Using | Write Using |
|-------|------------|-------------|
| Source table | db_name | — |
| Source → Staging | db_name | technical_name (`prefix_db`) |
| Staging → Staging (branch to JOIN) | technical_name | technical_name (no AS) |
| Staging → Staging (branch to destination) | technical_name | technical_name |
| Staging → Staging (JOIN) | technical_name (l/r) | technical_name |
| Staging → Destination | business_name or technical_name | business_name |

---

## 8. Destination Writing Flow (End-to-End)

### 8.1 How Staging Before Destination Is Created

1. **Materialization** (`materialization.py`): `detect_materialization_points` marks the node **immediately before** each destination as `PRE_DESTINATION_STAGING`.
2. **Compilation** (`execution_plan.py` → `sql_compiler.py`): For each materialized node, `compile_staging_table_sql` is called. It flattens the segment from the nearest upstream materialization (or source) to that node.
3. **Column names in staging**: The staging table uses **technical names only** (e.g. `4fa62c23_cmp_id`, `4fa62c23_billed_to`). No aliasing to business names.
4. **Example** (node a4e7e754 → current_destination):
   - Segment: source 4fa62c23 → projection → filter → a4e7e754 (projection)
   - Staging columns: `4fa62c23_cmp_id`, `4fa62c23_billed_to`, `4fa62c23_employee_range`, etc.
   - Calculated columns keep technical form: `4fa62c23_0377bcbd_upper_trial`, `4fa62c23_3ed804ac_lower_trial`

### 8.2 How Destination CREATE Is Done

1. **Schema anchor**: For each destination, we find the schema anchor (source, join, or aggregation) by walking up from the destination's parent.
2. **Column list**: We use `node_output_metadata` for the schema anchor. Columns are normalized: `_L_X` / `_R_X` → business names (`connection_id`, `cmp_id_left`, `cmp_id_right`, etc.).
3. **CREATE TABLE**: Uses `business_name` for each column. No technical names, no `_L_`/`_R_` in the destination schema.

### 8.3 How Destination INSERT Mapping Works

1. **Destination columns**: Business names from normalized anchor metadata (e.g. `cmp_id`, `cmp_name`, `employee_range`).
2. **Staging columns**: Technical names (e.g. `4fa62c23_cmp_id`). The staging table has these exact column names.
3. **Mapping logic** (`_generate_final_insert_one`):
   - For each destination column (business name), resolve the **staging column** (technical name) via `technical_name` from metadata or lookup.
   - If the staging table has that column: `SELECT "4fa62c23_cmp_id"` (staging column name).
   - If the staging table does **not** have it (e.g. projection dropped it): `NULL`.
4. **Result**: `INSERT INTO dest (cmp_id, cmp_name, ...) SELECT "4fa62c23_cmp_id", NULL, ... FROM staging`

### 8.4 Why NULLs Appear

- NULLs occur when the **staging table** does not contain a column that the destination expects.
- Example: `current_destination` expects `cmp_name`, `pricing`, `is_trial`; the staging a4e7e754 (projection) does not include those columns → `NULL`.
- Example: `join_destination_d2` staging (11fc988c) only has `39ef59b7_cmp_id` (filter selected one column) → all other columns are `NULL`.

### 8.5 Code Flow Summary

| Step | File | Function |
|------|------|----------|
| Detect staging before dest | `materialization.py` | `detect_materialization_points` (PRE_DESTINATION_STAGING) |
| Create staging SQL | `sql_compiler.py` | `compile_staging_table_sql` → `flatten_segment_from_source` |
| Destination CREATE | `execution_plan.py` | `_generate_destination_create_one` |
| Destination INSERT | `execution_plan.py` | `_generate_final_insert_one` |

---

## 9. Quick Decision Tree

1. **Is this a source?** → Use db_name in SELECT, technical_name in output
2. **Does source feed 2+ branches?** → OR filters at source (if all have filters)
3. **Is this a branch reading from shared staging?** → Apply only this branch's filter (AND)
4. **Does this feed a JOIN?** → Keep technical_name (no AS to business)
5. **Does this feed a destination?** → Staging keeps technical names; INSERT maps to business
6. **Is this a JOIN?** → Use technical_name; _L_/_R_ normalized to business for destination
7. **Building destination INSERT?** → Map staging technical_name → destination business_name

---

## 10. Staging Diagram (Example Pipeline)

For a pipeline with **tool_company** (shared source, two branches) and **tool_connection** (single branch) feeding a JOIN and two destinations:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ LEVEL 0 (Source → Staging)                                                                   │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│  tool_company (public)                    tool_connection (public)                           │
│         │                                        │                                          │
│         ▼                                        ▼                                          │
│  job_..._node_4fa62c23-...              job_..._node_c5858bbe-...                            │
│  (shared source staging)                (tool_connection staging)                            │
│  cols: 4fa62c23_*, lower_trial,         cols: 39ef59b7_*                                      │
│        upper_trial                      filter: cmp_id = 1                                   │
│  filter: (pricing='0.02') OR                                                                 │
│          (is_trial='FALSE' AND employee_range='50-100')                                       │
│                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ LEVEL 2 (Branch from shared source)                                                         │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│  job_..._node_4fa62c23-...  ──────►  job_..._node_e2b024a7-...                                │
│  (shared staging)                   (branch to JOIN – technical names only)                  │
│                                     filter: 4fa62c23_pricing = '0.02'                       │
│                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ LEVEL 3 (JOIN)                                                                              │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│  job_..._node_c5858bbe-...  (L)     job_..._node_e2b024a7-...  (R)                          │
│         │                                    │                                              │
│         └──────────── INNER JOIN ─────────────┘                                               │
│                      ON l.39ef59b7_cmp_id = r.4fa62c23_cmp_id                               │
│                              │                                                              │
│                              ▼                                                              │
│                   job_..._node_c253a973-...                                                   │
│                   (join result: 39ef59b7_* + 4fa62c23_*)                                      │
│                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ LEVEL 4 (Branch to destination)                                                             │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│  job_..._node_4fa62c23-...  ──────►  job_..._node_a4e7e754-...                               │
│  (shared staging)                   (branch to current_destination)                          │
│                                     filter: is_trial='FALSE' AND employee_range='50-100'     │
│                                     output: technical names (INSERT maps to business)        │
│                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ LEVEL 5 (Post-join filter → destination)                                                    │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│  job_..._node_c253a973-...  ──────►  job_..._node_11fc988c-...                              │
│  (join result)                      filter: 39ef59b7_cmp_id = 1                             │
│                                              │                                              │
│                                              ▼                                              │
│                                    join_destination_d2                                      │
│                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ DESTINATIONS                                                                                │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│  current_destination  ◄──  job_..._node_a4e7e754-...  (from tool_company branch)           │
│  join_destination_d2  ◄──  job_..._node_11fc988c-...  (from join result)                    │
│                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```
