# Checkpoint Cache Visual Flows

## Flow 1: Cache Creation (SQL-Based)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER PREVIEWS JOIN NODE C                            │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ find_nearest_checkpoint(C)   │
                    │ BFS: C → B → A               │
                    │ Result: No cache found       │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SQL COMPILER                                         │
│                                                                              │
│  Build CTE chain from Source A → Join C:                                    │
│                                                                              │
│  WITH source_cte AS (                                                        │
│    SELECT * FROM "public"."customers" LIMIT 100                              │
│  ),                                                                          │
│  filter_b_cte AS (                                                           │
│    SELECT * FROM source_cte WHERE status = 'active'                          │
│  ),                                                                          │
│  join_c_cte AS (                                                             │
│    SELECT s.*, o.order_id, o.amount                                          │
│    FROM filter_b_cte s                                                       │
│    LEFT JOIN "public"."orders" o ON s.customer_id = o.customer_id            │
│  )                                                                           │
│  SELECT * FROM join_c_cte LIMIT 100                                          │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATABASE EXECUTION                                   │
│                                                                              │
│  Execute SQL query                                                           │
│  ├─ Read customers table                                                     │
│  ├─ Apply filter (status='active')                                           │
│  ├─ Join with orders table                                                   │
│  └─ Return ≤100 rows                                                         │
│                                                                              │
│  ✅ All processing in database                                               │
│  ✅ No data in Python yet                                                    │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CHECKPOINT CACHE CREATION                                 │
│                                                                              │
│  For Node A (source):                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ CREATE TABLE "staging_preview_123"."node_A_cache" AS                │   │
│  │ SELECT * FROM "public"."customers" LIMIT 100                        │   │
│  │                                                                     │   │
│  │ INSERT INTO "_checkpoint_metadata" VALUES (                         │   │
│  │   'A', hash('A:config'), '', expires_at, column_metadata           │   │
│  │ )                                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  For Node C (join):                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ CREATE TABLE "staging_preview_123"."node_C_cache" AS                │   │
│  │ SELECT * FROM (                                                     │   │
│  │   -- Full SQL from source to join                                  │   │
│  │ ) _sub LIMIT 100                                                    │   │
│  │                                                                     │   │
│  │ INSERT INTO "_checkpoint_metadata" VALUES (                         │   │
│  │   'C', hash('C:config'), hash('upstream'), expires_at, columns     │   │
│  │ )                                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ✅ Tables created in database                                               │
│  ✅ Still no data in Python                                                  │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FETCH RESULT FOR RESPONSE                                 │
│                                                                              │
│  cursor.fetchmany(100)  -- ✅ Get ≤100 rows                                  │
│  rows = enforce_preview_memory_limit(rows, 100)  -- ✅ Guard                 │
│                                                                              │
│  Memory usage: ~10-100 KB                                                    │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │   RESPONSE TO FRONTEND       │
                    │   {                          │
                    │     rows: [...],  // ≤100    │
                    │     from_cache: false        │
                    │   }                          │
                    └──────────────────────────────┘
```

---

## Flow 2: Cache Hit (Direct)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    USER PREVIEWS JOIN NODE C (AGAIN)                         │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ find_nearest_checkpoint(C)   │
                    │ Check C: join node           │
                    │ ├─ Cache exists? YES ✅      │
                    │ ├─ Expired? NO ✅            │
                    │ └─ Hash matches? YES ✅      │
                    │ Result: CACHE HIT!           │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DIRECT CACHE SELECT                                  │
│                                                                              │
│  SQL: SELECT * FROM "staging_preview_123"."node_C_cache" LIMIT 100           │
│                                                                              │
│  ✅ No SQL compilation needed                                                │
│  ✅ No upstream traversal                                                    │
│  ✅ Instant response                                                         │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATABASE EXECUTION                                   │
│                                                                              │
│  Read from cache table (already materialized)                                │
│  Return ≤100 rows                                                            │
│                                                                              │
│  Latency: ~50ms (vs ~500ms without cache)                                   │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FETCH RESULT FOR RESPONSE                                 │
│                                                                              │
│  cursor.fetchmany(100)  -- ✅ Get ≤100 rows                                  │
│                                                                              │
│  Memory usage: ~10-100 KB                                                    │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │   RESPONSE TO FRONTEND       │
                    │   {                          │
                    │     rows: [...],  // ≤100    │
                    │     from_cache: true ✅      │
                    │   }                          │
                    └──────────────────────────────┘
```

---

## Flow 3: Cache Hit (Upstream) - Nested Query

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    USER PREVIEWS FILTER NODE F                               │
│                                                                              │
│  Pipeline: A (source) → B (filter) → C (join) → D (proj) → E (agg) → F      │
│  Caches: A ✅  C ✅  E ✅                                                     │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ find_nearest_checkpoint(F)   │
                    │ BFS: F → E → D → C → B → A   │
                    │                              │
                    │ Check F: filter → no cache   │
                    │ Check E: aggregate → CACHE!✅│
                    │                              │
                    │ Result: Use E's cache        │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SQL COMPILER                                         │
│                                                                              │
│  Build CTE chain from E's cache → F:                                         │
│                                                                              │
│  WITH checkpoint_cte AS (                                                    │
│    SELECT * FROM "staging_preview_123"."node_E_cache"  -- ✅ Use cache!      │
│  ),                                                                          │
│  filter_f_cte AS (                                                           │
│    SELECT * FROM checkpoint_cte                                              │
│    WHERE order_count > 5  -- Apply F's filter                                │
│  )                                                                           │
│  SELECT * FROM filter_f_cte LIMIT 100                                        │
│                                                                              │
│  ✅ Start from E's cache table (not from source!)                            │
│  ✅ Only compile E → F (skip A → E)                                          │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATABASE EXECUTION                                   │
│                                                                              │
│  Execute nested query:                                                       │
│  ├─ Read from node_E_cache (already materialized)                            │
│  ├─ Apply filter (order_count > 5)                                           │
│  └─ Return ≤100 rows                                                         │
│                                                                              │
│  ✅ Cache table used as SQL subquery                                         │
│  ✅ NOT loaded into Python memory                                            │
│  ✅ Fast execution (skip A → E computation)                                  │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FETCH RESULT FOR RESPONSE                                 │
│                                                                              │
│  cursor.fetchmany(100)  -- ✅ Get ≤100 rows                                  │
│                                                                              │
│  Memory usage: ~10-100 KB                                                    │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │   RESPONSE TO FRONTEND       │
                    │   {                          │
                    │     rows: [...],  // ≤100    │
                    │     from_cache: false        │
                    │   }                          │
                    └──────────────────────────────┘
```

---

## Flow 4: Compute Node (Memory-Based Cache)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    USER PREVIEWS COMPUTE NODE C                              │
│                                                                              │
│  Pipeline: A (source) → B (filter) → C (compute) → D (projection)            │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ find_nearest_checkpoint(C)   │
                    │ BFS: C → B → A               │
                    │                              │
                    │ Check C: compute → no cache  │
                    │ Check B: filter → skip       │
                    │ Check A: source → CACHE! ✅  │
                    │                              │
                    │ Result: Use A's cache        │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SQL COMPILER                                         │
│                                                                              │
│  Build CTE chain from A's cache → B:                                         │
│                                                                              │
│  WITH checkpoint_cte AS (                                                    │
│    SELECT * FROM "staging_preview_123"."node_A_cache"                        │
│  ),                                                                          │
│  filter_b_cte AS (                                                           │
│    SELECT * FROM checkpoint_cte WHERE year = 2024                            │
│  )                                                                           │
│  SELECT * FROM filter_b_cte LIMIT 100                                        │
│                                                                              │
│  ✅ Stop before compute node (Python boundary)                               │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATABASE EXECUTION                                   │
│                                                                              │
│  Execute SQL → Get input rows                                                │
│  Return ≤100 rows                                                            │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FETCH INPUT FOR COMPUTE                                   │
│                                                                              │
│  cursor.fetchmany(100)  -- ✅ Get ≤100 rows                                  │
│  input_rows = enforce_preview_memory_limit(rows, 100)                        │
│                                                                              │
│  Memory usage: ~10-100 KB (input data)                                       │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PYTHON EXECUTION                                     │
│                                                                              │
│  import pandas as pd                                                         │
│  input_df = pd.DataFrame(input_rows)  # ≤100 rows                            │
│                                                                              │
│  # User code                                                                 │
│  _output_df = input_df.copy()                                                │
│  _output_df['moving_avg'] = input_df['sales'].rolling(7).mean()             │
│                                                                              │
│  # Truncate output                                                           │
│  if len(_output_df) > 100:                                                   │
│      _output_df = _output_df.head(100)  # ✅ Hard limit                      │
│                                                                              │
│  output_rows = _output_df.to_dict('records')  # ≤100 rows                    │
│                                                                              │
│  Memory peak: ~100-200 KB (input + output)                                   │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CREATE COMPUTE CACHE TABLE                                │
│                                                                              │
│  CREATE TABLE "staging_preview_123"."node_C_cache" (                         │
│    date TEXT,                                                                │
│    sales TEXT,                                                               │
│    moving_avg TEXT                                                           │
│  );                                                                          │
│                                                                              │
│  INSERT INTO "staging_preview_123"."node_C_cache" VALUES                     │
│    ('2024-01-01', '1000', '950.5'),                                          │
│    ('2024-01-02', '1100', '975.2'),                                          │
│    ...  -- ≤100 rows                                                         │
│                                                                              │
│  INSERT INTO "_checkpoint_metadata" VALUES (                                 │
│    'C', hash('C:config'), hash('upstream'), expires_at, columns             │
│  );                                                                          │
│                                                                              │
│  ✅ Data moved from Python → Database                                        │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │   RESPONSE TO FRONTEND       │
                    │   {                          │
                    │     rows: [...],  // ≤100    │
                    │     from_cache: false        │
                    │   }                          │
                    │                              │
                    │  Final memory: ~10-100 KB    │
                    └──────────────────────────────┘
```

---

## Cache Table Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CACHE TABLE LIFECYCLE                                │
└─────────────────────────────────────────────────────────────────────────────┘

TIME: T=0 (First preview)
┌──────────────────────────────────────────────────────────────┐
│ Schema: staging_preview_123                                  │
│ Tables: (none)                                               │
└──────────────────────────────────────────────────────────────┘

TIME: T=1 (After previewing Join C)
┌──────────────────────────────────────────────────────────────┐
│ Schema: staging_preview_123                                  │
│ Tables:                                                      │
│   ├─ node_A_cache (100 rows) [expires: T+20min]             │
│   └─ node_C_cache (100 rows) [expires: T+20min]             │
│                                                              │
│ Metadata:                                                    │
│   ├─ A: hash=abc123, upstream=, expires=T+20min             │
│   └─ C: hash=def456, upstream=xyz789, expires=T+20min       │
└──────────────────────────────────────────────────────────────┘

TIME: T=5 (After previewing Aggregate E)
┌──────────────────────────────────────────────────────────────┐
│ Schema: staging_preview_123                                  │
│ Tables:                                                      │
│   ├─ node_A_cache (100 rows) [expires: T+20min]             │
│   ├─ node_C_cache (100 rows) [expires: T+20min]             │
│   └─ node_E_cache (100 rows) [expires: T+25min]             │
│                                                              │
│ Metadata:                                                    │
│   ├─ A: hash=abc123, upstream=, expires=T+20min             │
│   ├─ C: hash=def456, upstream=xyz789, expires=T+20min       │
│   └─ E: hash=ghi789, upstream=jkl012, expires=T+25min       │
└──────────────────────────────────────────────────────────────┘

TIME: T=21 (After TTL expires for A and C)
┌──────────────────────────────────────────────────────────────┐
│ Schema: staging_preview_123                                  │
│ Tables:                                                      │
│   ├─ node_A_cache (100 rows) [EXPIRED ❌]                   │
│   ├─ node_C_cache (100 rows) [EXPIRED ❌]                   │
│   └─ node_E_cache (100 rows) [expires: T+25min]             │
│                                                              │
│ Next preview will ignore A and C caches                      │
└──────────────────────────────────────────────────────────────┘

TIME: T=30 (User modifies Join C config)
┌──────────────────────────────────────────────────────────────┐
│ Schema: staging_preview_123                                  │
│ Tables:                                                      │
│   ├─ node_A_cache (100 rows) [EXPIRED ❌]                   │
│   ├─ node_C_cache (DROPPED - hash mismatch)                 │
│   └─ node_E_cache (DROPPED - upstream changed)              │
│                                                              │
│ Invalidation cascade: C changed → drop C, E                  │
└──────────────────────────────────────────────────────────────┘
```

---

## Memory Usage Comparison

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MEMORY USAGE: WITH vs WITHOUT CACHE                       │
└─────────────────────────────────────────────────────────────────────────────┘

Scenario: Preview Aggregate E (after Join C)
Pipeline: Source A → Filter B → Join C → Projection D → Aggregate E

WITHOUT CACHE (First preview):
┌──────────────────────────────────────────────────────────────┐
│ Step 1: SQL Compilation (A → E)                             │
│   Memory: ~1 KB (string building)                           │
│                                                              │
│ Step 2: Database Execution                                  │
│   Memory: 0 KB (all in database)                            │
│                                                              │
│ Step 3: Fetch Result                                        │
│   Memory: ~50 KB (100 rows)                                 │
│                                                              │
│ Step 4: Create Cache Tables (A, C, E)                       │
│   Memory: 0 KB (CREATE TABLE in database)                   │
│                                                              │
│ TOTAL PYTHON MEMORY: ~50 KB                                 │
│ LATENCY: ~500ms                                             │
└──────────────────────────────────────────────────────────────┘

WITH CACHE (Second preview, cache hit at C):
┌──────────────────────────────────────────────────────────────┐
│ Step 1: Find Checkpoint                                      │
│   Memory: ~1 KB (metadata lookup)                           │
│   Found: C's cache ✅                                        │
│                                                              │
│ Step 2: SQL Compilation (C → E)                             │
│   Memory: ~1 KB (string building)                           │
│   SQL: WITH cte AS (SELECT * FROM node_C_cache) ...         │
│                                                              │
│ Step 3: Database Execution                                  │
│   Memory: 0 KB (all in database)                            │
│   Reads from C's cache table (not from source!)             │
│                                                              │
│ Step 4: Fetch Result                                        │
│   Memory: ~50 KB (100 rows)                                 │
│                                                              │
│ TOTAL PYTHON MEMORY: ~50 KB                                 │
│ LATENCY: ~150ms (3x faster!)                                │
└──────────────────────────────────────────────────────────────┘

WITH CACHE (Third preview, cache hit at E):
┌──────────────────────────────────────────────────────────────┐
│ Step 1: Find Checkpoint                                      │
│   Memory: ~1 KB (metadata lookup)                           │
│   Found: E's cache ✅                                        │
│                                                              │
│ Step 2: Direct SELECT                                        │
│   Memory: 0 KB                                              │
│   SQL: SELECT * FROM node_E_cache LIMIT 100                 │
│                                                              │
│ Step 3: Database Execution                                  │
│   Memory: 0 KB (all in database)                            │
│                                                              │
│ Step 4: Fetch Result                                        │
│   Memory: ~50 KB (100 rows)                                 │
│                                                              │
│ TOTAL PYTHON MEMORY: ~50 KB                                 │
│ LATENCY: ~50ms (10x faster!)                                │
└──────────────────────────────────────────────────────────────┘
```

---

**Key Insight:** Cache tables reduce **latency**, not **memory usage**.  
Memory usage is always ~50-100 KB regardless of cache hits!

---

**Last Updated:** 2026-02-13
