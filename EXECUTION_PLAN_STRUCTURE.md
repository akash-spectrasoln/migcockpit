# Execution Plan JSON Structure

## Overview
When a pipeline is validated, the Migration Service generates an **Execution Plan** that is serialized to JSON and stored in the customer database's `CANVAS_CACHE.execution_plans` table.

## Database Schema

```sql
CREATE SCHEMA IF NOT EXISTS "CANVAS_CACHE";

CREATE TABLE IF NOT EXISTS "CANVAS_CACHE"."execution_plans" (
    canvas_id VARCHAR(255),
    plan_hash VARCHAR(64),
    plan_data JSONB,              -- The full execution plan as JSON
    staging_schema VARCHAR(255),   -- e.g., "staging_job_abc123"
    total_queries INTEGER,         -- Total number of SQL queries
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,          -- Auto-expires after 24 hours
    PRIMARY KEY (canvas_id, plan_hash)
);
```

## JSON Structure

The `plan_data` column contains a JSON object with this structure:

```json
{
  "job_id": "validate_123_1770967854",
  "staging_schema": "staging_job_validate_123_1770967854",
  "total_queries": 4,
  "cleanup_sql": "DROP SCHEMA IF NOT EXISTS \"staging_job_validate_123_1770967854\" CASCADE",
  
  "destination_create_sql": "CREATE TABLE IF NOT EXISTS \"public\".\"target_table\" (\n  \"customer_id\" BIGINT,\n  \"order_date\" TIMESTAMP,\n  \"total_amount\" DOUBLE PRECISION\n)",
  
  "final_insert_sql": "INSERT INTO \"public\".\"target_table\" (\"customer_id\", \"order_date\", \"total_amount\")\nSELECT \"customer_id\", \"order_date\", \"total_amount\" FROM (\n  SELECT * FROM \"staging_job_validate_123_1770967854\".\"node_abc123\"\n) sub",
  
  "levels": [
    {
      "level_num": 0,
      "node_ids": ["source_node_1", "source_node_2"],
      "queries": [
        {
          "sql": "CREATE TABLE \"staging_job_validate_123_1770967854\".\"node_source_1\" AS\nSELECT \"customer_id\", \"order_date\" FROM \"public\".\"orders\"",
          "is_nested": false,
          "dependencies": ["source_node_1"]
        },
        {
          "sql": "CREATE TABLE \"staging_job_validate_123_1770967854\".\"node_source_2\" AS\nSELECT \"product_id\", \"price\" FROM \"public\".\"products\"",
          "is_nested": false,
          "dependencies": ["source_node_2"]
        }
      ]
    },
    {
      "level_num": 1,
      "node_ids": ["join_node_1"],
      "queries": [
        {
          "sql": "CREATE TABLE \"staging_job_validate_123_1770967854\".\"node_join_1\" AS\nSELECT l.*, r.* FROM \"staging_job_validate_123_1770967854\".\"node_source_1\" l\nINNER JOIN \"staging_job_validate_123_1770967854\".\"node_source_2\" r\nON l.\"product_id\" = r.\"product_id\"",
          "is_nested": false,
          "dependencies": ["source_node_1", "source_node_2"]
        }
      ]
    },
    {
      "level_num": 2,
      "node_ids": ["filter_node_1"],
      "queries": [
        {
          "sql": "CREATE TABLE \"staging_job_validate_123_1770967854\".\"node_filter_1\" AS\nSELECT * FROM (\n  SELECT * FROM \"staging_job_validate_123_1770967854\".\"node_join_1\"\n) filt\nWHERE \"total_amount\" > 100",
          "is_nested": false,
          "dependencies": ["join_node_1"]
        }
      ]
    }
  ]
}
```

## Key Components

### 1. Top-Level Metadata
- **job_id**: Unique identifier for this validation/execution
- **staging_schema**: Temporary schema name for intermediate tables
- **total_queries**: Count of all SQL queries to execute
- **cleanup_sql**: SQL to drop the staging schema after completion

### 2. Destination Setup
- **destination_create_sql**: Creates the target table (if needed)
- **final_insert_sql**: Inserts final data from staging to destination

### 3. Execution Levels
Each level represents a **parallel execution group** (topologically sorted):

- **level_num**: Sequential level number (0-indexed)
- **node_ids**: List of node IDs in this level
- **queries**: Array of SQL queries to execute in this level

### 4. Query Objects
Each query contains:
- **sql**: The actual SQL statement to execute
- **is_nested**: `false` for CREATE TABLE, `true` for nested SELECT
- **dependencies**: Node IDs this query depends on

## Execution Flow

1. **Validate** → Generate plan → Save to `CANVAS_CACHE.execution_plans`
2. **Execute** → Retrieve plan from DB → Execute level by level:
   - Level 0: Source nodes (parallel)
   - Level 1: Joins/transforms depending on Level 0 (parallel within level)
   - Level 2: Further transforms (parallel within level)
   - ...
   - Final: Insert into destination
   - Cleanup: Drop staging schema

## Plan Hash
The plan is hashed (SHA-256) based on:
- job_id
- staging_schema
- Level structure (node IDs and query counts per level)
- total_queries

This hash ensures plan uniqueness and enables caching/versioning.

## Retrieval

To retrieve the latest plan for a canvas:

```sql
SELECT plan_data 
FROM "CANVAS_CACHE"."execution_plans"
WHERE canvas_id = '123' 
  AND expires_at > CURRENT_TIMESTAMP
ORDER BY created_at DESC 
LIMIT 1;
```

## Auto-Expiry
Plans automatically expire 24 hours after creation to prevent stale data.
