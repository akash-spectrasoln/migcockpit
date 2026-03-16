# Migration Execution: How Data Flows (Extraction vs Filter Pushdown)

## Who fetches the data during execution?

**The Extraction Service fetches the data from the source database.** The Orchestrator does **not** connect to the source DB or run SELECTs itself.

Flow:

1. **Orchestrator (Migration Service, port 8003)**  
   - Runs the pipeline (source → filter/join/… → destination).  
   - For each **source** node it calls the Extraction Service:  
     `POST {extraction_service_url}/extract` with `connection_config`, `table_name`, `schema_name`, `chunk_size`, and optionally `filter_spec`.  
   - It then **waits** for the extraction job to finish (polls `GET /extract/{job_id}/status`).  
   - When the job is "completed", the orchestrator gets the result (today: placeholder; in a full implementation it would fetch the extracted rows).  
   - So the orchestrator **requests** extraction and **waits** for it; it does **not** read from the source DB.

2. **Extraction Service (port 8001)**  
   - Receives the `/extract` request and starts a **background** extraction job.  
   - It uses a **connector** (e.g. `PostgreSQLConnector`) to connect to the **source database** (host, port, database, user, password from `connection_config`).  
   - It runs **SELECT** (with optional WHERE from `filter_spec`) and reads rows in chunks.  
   - So the Extraction Service is the component that **actually fetches** data from the source.

**Summary:**  
- **Orchestrator** = coordinates the pipeline and **asks** the Extraction Service to extract.  
- **Extraction Service** = connects to the source DB and **fetches** the data.

---

## Current behavior (what we use today)

1. **Source nodes**
   - The **Migration Orchestrator** calls the **Extraction Service** with:
     - `connection_config`, `table_name`, `schema_name`, `chunk_size`
     - **No** `where_clause` or filter is sent.
   - The Extraction Service reads the **full table** from the source DB (with optional `where_clause` if we added it later).
   - So today: **we fetch all rows** from the source table for each source node.

2. **Transform nodes (filter, join, projection, calculated, compute)**
   - In the migration path, the orchestrator treats them as **pass-through**:
     - It takes the **first available previous result** that has `data` and passes it unchanged to the next step.
   - Filter conditions, join logic, projection, and calculated columns are **not** applied in the migration orchestrator; that logic lives in the **Django pipeline API** (used for preview/design), not in the migration execution path.
   - So today: **no filtering or transformation** is applied during migration execution—only extraction and then loading.

3. **Destination node**
   - Receives whatever data was passed from the previous step (currently the first source’s full dataset) and loads it (e.g. HANA/PostgreSQL loader).

**Summary:** We effectively **fetch full table(s) from the extraction service** and **do not** push filters to extraction or apply filter/join/projection/calculated columns in the migration pipeline. The “real” pipeline (filter, join, projection) is used in the Django pipeline API for preview, not in the migration orchestrator.

---

## Two possible approaches

### Approach A: Fetch all, then apply in memory (or in a later step)

- **Extraction:** `SELECT * FROM table` (no WHERE).
- **Downstream:** A separate step (orchestrator or another service) applies filter, join, projection, calculated columns on the in-memory (or streamed) dataset.

**Pros**
- Works for **any** filter, including filters on **calculated columns** (those columns don’t exist in the source DB, so they can’t be pushed to extraction).
- Single place for complex logic (joins, expressions).

**Cons**
- More data over the wire and in memory.
- Slower for large tables when the filter could have been pushed down.

---

### Approach B: Push filters to extraction (when possible) — **preferred when safe**

- **Extraction:** `SELECT * FROM table WHERE <conditions>` **only when the filter uses columns that exist in the source table** (i.e. **not** created/calculated columns).
- Only rows matching the filter are read from the DB and sent to the next step.

**Rule we enforce:** Filters are pushed to extraction **only if** every column referenced in the filter is a **source table column**. If the filter uses any **created** or **calculated** column (from a projection/calculated node), we **do not** push—we fetch full data and apply the filter downstream after those columns exist.

**Pros**
- Less data transferred and processed.
- Faster and more scalable when filters are selective and only use source columns.

**Cons**
- **Cannot** be used when the filter uses **calculated/created columns** (those don’t exist in the source table; must compute after fetch).
- Requires the orchestrator to check that filter columns are source columns only before pushing.

---

## Which is better?

- **When filters use only source columns:**  
  **Push filters to extraction (Approach B)** is better: less data, faster, same result.

- **When filters use calculated columns (or other expressions not in the source):**  
  You **must** fetch first and then apply the filter in a downstream step (Approach A for that part).

- **Recommended:** **Hybrid**
  - Push to extraction only filters that reference **source table columns** (and that the extraction service can express as a WHERE clause).
  - Apply in a downstream step: filters that use calculated/expression columns, joins, projections, and calculated columns.

---

## What we do for filter pushdown (Approach B)

1. **Orchestrator** (`services/migration_service/orchestrator.py`)
   - For each source node, we only push a filter when **both**:
     - The filter comes from a **filter node** that is a **direct** downstream of this source (edge: source → filter). If there is a projection/calculated/join in between, we do **not** push (the filter might use created/calculated columns).
     - We do **not** push when the filter references any column that is **created or calculated** (output of a projection/calculated node). So we only push when the filter uses **source table columns** only.
   - When pushable: build a filter spec (same format as the extraction service’s filter API) and pass it in the extraction request.
   - When not pushable: send no filter; fetch full table and apply filter later in a transform step.

2. **Extraction Service**
   - Already has optional `where_clause` (and possibly filter spec) on the request.
   - The **worker** must use it correctly: today it expects a simple key-value `filters` dict; for arbitrary WHERE you’d need either a **raw WHERE string** (with strict validation) or a **structured filter spec** that the connector turns into SQL (like the existing `execute_filter` in the connectors).

3. **Transform nodes in the orchestrator**
   - Implement real filter/join/projection/calculated steps (instead of pass-through) so that:
     - When we didn’t push a filter (e.g. calculated column), we apply it here.
     - When we did push a filter, we don’t double-apply (or we merge safely).
   - Implement proper input chaining (e.g. for joins: two inputs, not “first result with data”).

---

## Calculated/created columns and filters

- **Calculated/created columns** are defined in the canvas (e.g. projection expressions, calculated columns) and **do not exist** in the source table.
- **Rule we enforce:** Filters are pushed to extraction **only when** they use **source table columns** (columns that exist in the source). If the filter references any **created** or **calculated** column, we **do not** push—we fetch full data and apply the filter downstream.
- In practice we only push when the **direct** downstream of the source is a **filter** node (no projection/calculated in between). That way we know the filter only sees source columns. If the direct child is projection, calculated, or join, we do not push.
