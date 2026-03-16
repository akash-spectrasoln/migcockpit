# Metadata Caching Strategy

## Overview
All node metadata (column definitions with `name`, `technical_name`, `db_name`, `base`) is **persisted to the database** and reused across requests. Metadata is only regenerated when the node configuration changes.

## Database Storage

### Table: `CANVAS_CACHE.node_cache_metadata`
```sql
CREATE TABLE "CANVAS_CACHE".node_cache_metadata (
    id SERIAL PRIMARY KEY,
    canvas_id INTEGER NOT NULL,
    node_id VARCHAR(100) NOT NULL,
    node_name VARCHAR(255),
    node_type VARCHAR(50) NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    config_hash VARCHAR(64),           -- ← Hash of node config
    row_count INTEGER DEFAULT 0,
    column_count INTEGER DEFAULT 0,
    columns JSONB,                     -- ← METADATA STORED HERE
    source_node_ids JSONB,
    created_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_valid BOOLEAN DEFAULT TRUE,
    UNIQUE(canvas_id, node_id)
);
```

### Metadata Structure (JSONB)
```json
{
  "columns": [
    {
      "name": "Company ID",              // User-facing name (can be renamed)
      "technical_name": "9aad5245_cmp_id", // Unique stable ID
      "db_name": "cmp_id",               // Original DB column
      "base": "9aad5245-...",            // Source node ID
      "datatype": "integer",
      "source": "base"                   // "base" or "calculated"
    }
  ]
}
```

## Column Naming Rules

| Field | Purpose | Changes? | Example |
|-------|---------|----------|---------|
| **`name`** | User-facing display name | ✅ Yes (user can rename) | `"Company ID"` |
| **`technical_name`** | Unique stable identifier | ❌ Never | `"9aad5245_cmp_id"` |
| **`db_name`** | Original database column | ❌ Never (until destination) | `"cmp_id"` |
| **`base`** | Source node ID | ❌ Never | `"9aad5245-..."` |

### Technical Name Format
```
{source_node_id_prefix}_{db_name}
```
Example: `9aad5245_cmp_id`

## Cache Validation Flow

### 1. Preview Request
```python
# User clicks node to preview
1. Calculate config_hash = SHA256(node.config)
2. Query: SELECT * FROM node_cache_metadata WHERE canvas_id=X AND node_id=Y
3. If found:
   a. Compare cached_hash with current config_hash
   b. If MATCH → Return cached data + metadata (no execution!)
   c. If DIFFERENT → Invalidate cache, execute node
4. If not found:
   → Execute node, generate metadata, save to cache
```

### 2. Config Change Detection
```python
# When user modifies node:
- Old config: {"filter": "status = 'active'"}
- New config: {"filter": "status = 'pending'"}
- Old hash: "a1b2c3d4"
- New hash: "e5f6g7h8"  ← Different!
- Result: Cache invalidated, next preview regenerates
```

### 3. Metadata Reuse
```python
# Filter pushdown during validation:
1. Read metadata from node_cache_metadata table
2. Use cached columns (name, technical_name, db_name, base)
3. No execution needed!
```

## Implementation

### Save Cache (with metadata)
```python
# api/services/node_cache.py
def save_cache(canvas_id, node_id, node_type, rows, columns, config):
    config_hash = compute_config_hash(config)
    
    # Save to database
    INSERT INTO node_cache_metadata (
        canvas_id, node_id, columns, config_hash, ...
    ) VALUES (%s, %s, %s, %s, ...)
    ON CONFLICT (canvas_id, node_id) DO UPDATE SET
        columns = EXCLUDED.columns,
        config_hash = EXCLUDED.config_hash,
        ...
```

### Get Cache (with validation)
```python
# api/services/node_cache.py
def get_cache(canvas_id, node_id, config=None):
    # Read from database
    SELECT columns, config_hash FROM node_cache_metadata
    WHERE canvas_id = %s AND node_id = %s
    
    # Validate hash
    if config:
        current_hash = compute_config_hash(config)
        if cached_hash != current_hash:
            invalidate_cache(canvas_id, node_id)
            return None  # Force regeneration
    
    return cached_data
```

### Filter Pushdown (reads metadata)
```python
# services/migration_service/planner/filter_optimizer.py
def _build_lineage(self):
    # Read metadata from database
    SELECT node_id, columns FROM node_cache_metadata
    WHERE canvas_id = %s AND is_valid = TRUE
    
    # Build lineage from cached metadata
    for node_id, columns_json in rows:
        for col in columns_json:
            lineage[node_id][col['name']] = {
                'source_node': col['base'],
                'original_name': col['db_name'],
                'technical_name': col['technical_name']
            }
```

## Benefits

### ✅ Performance
- **No re-execution** if config unchanged
- **Instant previews** from cached data
- **Fast validation** using cached metadata

### ✅ Consistency
- **Single source of truth** (database)
- **Metadata persists** across sessions
- **Column renames preserved**

### ✅ Correctness
- **Automatic invalidation** on config change
- **Hash-based validation** ensures freshness
- **Filter pushdown uses accurate lineage**

## Example Scenarios

### Scenario 1: First Preview
```
User clicks Source node → No cache → Execute query → Generate metadata → Save to DB
```

### Scenario 2: Second Preview (No Changes)
```
User clicks Source node → Cache found → Hash matches → Return cached data (instant!)
```

### Scenario 3: Config Changed
```
User modifies filter → Hash changes → Cache invalidated → Next preview regenerates
```

### Scenario 4: Validation (Filter Pushdown)
```
User validates pipeline → Read metadata from DB → Build lineage → Generate pushdown plan
```

## Status

✅ **Implemented**:
- Database schema with `config_hash` field
- Metadata saved to `columns` JSONB
- Cache validation with hash comparison
- Filter pushdown reads from database

✅ **Working**:
- Preview caching
- Metadata persistence
- Config change detection
- Lineage tracking for filter pushdown
