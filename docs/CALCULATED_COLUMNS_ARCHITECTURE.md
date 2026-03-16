# Calculated Columns Architecture - Single Source of Truth

## Problem Statement

Currently, calculated columns are stored in multiple locations:
- `node.data.config.calculatedColumns`
- `node.data.calculatedColumns`
- `node.data.projection.calculatedColumns`
- `CanvasNode.config_json` (JSON field)

This causes:
- Inconsistency in detection
- Difficulty in querying/managing calculated columns
- Data duplication
- Hard to track changes/history

## Proposed Solution: Single Database Table

Create a dedicated `CalculatedColumn` model that stores all calculated columns with a foreign key to `CanvasNode`.

## Architecture Flowchart

```mermaid
flowchart TD
    Start([User Adds Calculated Column]) --> Frontend[Frontend: ProjectionConfigPanel]
    
    Frontend --> Validate{Validate Expression}
    Validate -->|Invalid| Error[Show Error]
    Validate -->|Valid| SaveClick[User Clicks Save]
    
    SaveClick --> API[POST /api/canvas/nodes/{node_id}/calculated-columns/]
    
    API --> CheckNode{Node Exists?}
    CheckNode -->|No| Return404[Return 404]
    CheckNode -->|Yes| CheckType{Node Type = PROJECTION?}
    
    CheckType -->|No| Return400[Return 400: Only projection nodes]
    CheckType -->|Yes| ProcessSave[Process Save Request]
    
    ProcessSave --> DeleteOld[Delete Old CalculatedColumns<br/>WHERE node_id = node_id]
    DeleteOld --> InsertNew[Insert New CalculatedColumns<br/>One row per calculated column]
    
    InsertNew --> UpdateConfig[Update CanvasNode.config_json<br/>calculatedColumns: []<br/>Keep for backward compatibility]
    
    UpdateConfig --> ReturnSuccess[Return Success + CalculatedColumns List]
    ReturnSuccess --> FrontendUpdate[Frontend Updates UI]
    
    FrontendUpdate --> End([End])
    
    style Start fill:#e1f5ff
    style End fill:#e1f5ff
    style API fill:#fff4e1
    style ProcessSave fill:#e8f5e9
    style InsertNew fill:#e8f5e9
    style Error fill:#ffebee
    style Return404 fill:#ffebee
    style Return400 fill:#ffebee
```

## Retrieval Flowchart

```mermaid
flowchart TD
    Start([User Clicks Projection Node]) --> GetNode[GET /api/canvas/nodes/{node_id}/]
    
    GetNode --> FetchNode[Fetch CanvasNode from DB]
    FetchNode --> CheckExists{Node Exists?}
    
    CheckExists -->|No| Return404[Return 404]
    CheckExists -->|Yes| FetchCalculated[Fetch CalculatedColumns<br/>WHERE node_id = node_id<br/>ORDER BY display_order]
    
    FetchCalculated --> BuildResponse[Build Response]
    BuildResponse --> AddToConfig[Add calculatedColumns array<br/>to node.data.config]
    
    AddToConfig --> ReturnNode[Return Node with CalculatedColumns]
    ReturnNode --> Frontend[Frontend Displays CalculatedColumns]
    
    Frontend --> End([End])
    
    style Start fill:#e1f5ff
    style End fill:#e1f5ff
    style FetchCalculated fill:#e8f5e9
    style BuildResponse fill:#e8f5e9
    style Return404 fill:#ffebee
```

## Deletion Flowchart

```mermaid
flowchart TD
    Start([User Deletes/Closes Calculated Column]) --> Frontend[Frontend: Remove from UI]
    
    Frontend --> SaveClick[User Clicks Save]
    
    SaveClick --> API[POST /api/canvas/nodes/{node_id}/calculated-columns/]
    
    API --> CheckNode{Node Exists?}
    CheckNode -->|No| Return404[Return 404]
    CheckNode -->|Yes| CheckType{Node Type = PROJECTION?}
    
    CheckType -->|No| Return400[Return 400: Only projection nodes]
    CheckType -->|Yes| ProcessSave[Process Save Request]
    
    ProcessSave --> DeleteAll[Delete ALL CalculatedColumns<br/>WHERE node_id = node_id]
    
    DeleteAll --> CheckNew{New CalculatedColumns<br/>in Request?}
    
    CheckNew -->|Yes| InsertNew[Insert New CalculatedColumns<br/>One row per calculated column]
    CheckNew -->|No| SkipInsert[Skip Insert - All Deleted]
    
    InsertNew --> UpdateConfig[Update CanvasNode.config_json<br/>calculatedColumns: []<br/>Keep for backward compatibility]
    SkipInsert --> UpdateConfig
    
    UpdateConfig --> ReturnSuccess[Return Success + CalculatedColumns List<br/>Empty if all deleted]
    ReturnSuccess --> FrontendUpdate[Frontend Updates UI<br/>Removes Deleted Columns]
    
    FrontendUpdate --> End([End])
    
    style Start fill:#e1f5ff
    style End fill:#e1f5ff
    style API fill:#fff4e1
    style ProcessSave fill:#e8f5e9
    style DeleteAll fill:#ffebee
    style InsertNew fill:#e8f5e9
    style Return404 fill:#ffebee
    style Return400 fill:#ffebee
```

## Individual Deletion Flowchart

```mermaid
flowchart TD
    Start([User Clicks Delete on Single Column]) --> Frontend[Frontend: Show Delete Confirmation]
    
    Frontend --> Confirm{User Confirms?}
    Confirm -->|No| Cancel[Cancel - Keep Column]
    Confirm -->|Yes| DeleteAPI[DELETE /api/canvas/nodes/{node_id}/calculated-columns/{column_id}/]
    
    DeleteAPI --> CheckNode{Node Exists?}
    CheckNode -->|No| Return404[Return 404]
    CheckNode -->|Yes| CheckColumn{CalculatedColumn<br/>Exists?}
    
    CheckColumn -->|No| Return404Col[Return 404: Column Not Found]
    CheckColumn -->|Yes| CheckOwner{Column Belongs<br/>to Node?}
    
    CheckOwner -->|No| Return403[Return 403: Forbidden]
    CheckOwner -->|Yes| DeleteColumn[DELETE CalculatedColumn<br/>WHERE id = column_id]
    
    DeleteColumn --> UpdateConfig[Update CanvasNode.config_json<br/>Remove from calculatedColumns array]
    
    UpdateConfig --> ReturnSuccess[Return Success]
    ReturnSuccess --> FrontendUpdate[Frontend Removes Column from UI]
    
    FrontendUpdate --> End([End])
    Cancel --> End
    
    style Start fill:#e1f5ff
    style End fill:#e1f5ff
    style DeleteAPI fill:#fff4e1
    style DeleteColumn fill:#ffebee
    style UpdateConfig fill:#e8f5e9
    style Return404 fill:#ffebee
    style Return400 fill:#ffebee
    style Return403 fill:#ffebee
```

## Execution Flowchart (Preview Data)

```mermaid
flowchart TD
    Start([User Clicks Preview on Projection Node]) --> ExecuteAPI[POST /api/pipeline/execute/]
    
    ExecuteAPI --> GetNode[Get Target Node from Request]
    
    GetNode --> FetchCalculated[Fetch CalculatedColumns from DB<br/>WHERE node_id = target_node_id<br/>ORDER BY display_order]
    
    FetchCalculated --> CheckEmpty{CalculatedColumns<br/>Empty?}
    
    CheckEmpty -->|Yes| NoCalc[No Calculated Columns<br/>Process Base Columns Only]
    CheckEmpty -->|No| HasCalc[Has Calculated Columns]
    
    HasCalc --> FilterBase[Filter Base Columns<br/>Remove calculated column names<br/>from selected_columns]
    
    FilterBase --> BuildSelect[Build SQL SELECT<br/>ONLY Base Columns<br/>Exclude calculated columns]
    
    BuildSelect --> ExecuteSQL[Execute SQL Query<br/>Get Base Data]
    ExecuteSQL --> GetRows[Get Base Rows from Database]
    
    GetRows --> EvaluateCalc[For Each Row:<br/>Evaluate CalculatedColumns<br/>in Python using expressions]
    
    EvaluateCalc --> AddToRows[Add Calculated Column Values<br/>to Each Row<br/>row[calc_name] = evaluated_value]
    
    AddToRows --> BuildProjectedRows[Build projected_rows<br/>Iterate through output_metadata_columns<br/>Base columns first, then calculated]
    
    BuildProjectedRows --> BuildProjectedColumns[Build projected_columns<br/>Schema metadata<br/>Includes calculated columns at end]
    
    BuildProjectedColumns --> BuildResponse[Build Response:<br/>rows: projected_rows<br/>columns: projected_columns]
    
    NoCalc --> BuildResponse
    
    BuildResponse --> ReturnData[Return Preview Data<br/>with Calculated Columns]
    
    ReturnData --> Frontend[Frontend Displays Preview<br/>Shows Base + Calculated Columns]
    
    Frontend --> End([End])
    
    style Start fill:#e1f5ff
    style End fill:#e1f5ff
    style FetchCalculated fill:#e8f5e9
    style FilterBase fill:#fff4e1
    style EvaluateCalc fill:#e8f5e9
    style AddToRows fill:#e8f5e9
    style BuildResponse fill:#e8f5e9
    style ReturnData fill:#c8e6c9
    style Frontend fill:#c8e6c9
```

## Preview Data Flow Details

### Step-by-Step Process:

1. **User Clicks Preview** → Triggers `POST /api/pipeline/execute/` with `targetNodeId`

2. **Fetch Calculated Columns** → Backend queries:
   ```python
   CalculatedColumn.objects.filter(node_id=target_node_id).order_by('display_order')
   ```

3. **Filter Base Columns** → Remove calculated column names from `selected_columns`:
   ```python
   selected_columns = [col for col in output_columns if col not in calculated_col_names_set]
   ```

4. **Build SQL SELECT** → Only includes base columns:
   ```sql
   SELECT "tr_id", "table_name", "start_time", ... 
   -- NO calculated columns in SELECT
   ```

5. **Execute SQL** → Get base data rows from database

6. **Evaluate Calculated Columns** → For each row, evaluate expressions:
   ```python
   for row in rows:
       for calc_col in calculated_columns:
           row[calc_col.name] = evaluate_calculated_expression(
               calc_col.expression, 
               row, 
               available_columns
           )
   ```

7. **Build Response** → Include calculated columns:
   ```python
   {
       "rows": [
           {
               "tr_id": 14758,
               "table_name": "custtrans",
               "tern": "CUSTTRANS"  # ← Calculated column value
           }
       ],
       "columns": [
           {"name": "tr_id", "source": "base"},
           {"name": "table_name", "source": "base"},
           {"name": "tern", "source": "calculated"}  # ← At the end
       ]
   }
   ```

8. **Frontend Displays** → Preview table shows:
   - Base columns first
   - Calculated columns at the end
   - All with their evaluated values

### Key Points:

✅ **Calculated columns ARE included in preview data**  
✅ **They appear at the END of the column list**  
✅ **Values are evaluated in Python, not SQL**  
✅ **Order is preserved via `display_order` field**

## Database Schema

```python
class CalculatedColumn(models.Model):
    """Calculated columns for projection nodes - Single Source of Truth"""
    
    node = models.ForeignKey(
        CanvasNode, 
        on_delete=models.CASCADE, 
        related_name='calculated_columns',
        verbose_name='Node'
    )
    name = models.CharField(max_length=255, verbose_name='Column Name')
    expression = models.TextField(verbose_name='Expression Formula')
    data_type = models.CharField(
        max_length=50, 
        default='STRING',
        choices=[
            ('STRING', 'String'),
            ('INTEGER', 'Integer'),
            ('DECIMAL', 'Decimal'),
            ('BOOLEAN', 'Boolean'),
            ('DATE', 'Date'),
            ('DATETIME', 'DateTime'),
        ],
        verbose_name='Data Type'
    )
    display_order = models.IntegerField(default=0, verbose_name='Display Order')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Created At')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated At')
    
    class Meta:
        db_table = 'calculated_columns'
        verbose_name = 'Calculated Column'
        verbose_name_plural = 'Calculated Columns'
        unique_together = ['node', 'name']  # One calculated column name per node
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['node', 'display_order']),
            models.Index(fields=['node', 'name']),
        ]
    
    def __str__(self):
        return f"{self.node.business_name} - {self.name}"
```

## Benefits

1. **Single Source of Truth**: All calculated columns stored in one table
2. **Easy Querying**: Can query all calculated columns for a node with simple SQL
3. **Data Integrity**: Foreign key ensures calculated columns are deleted when node is deleted
4. **Order Preservation**: `display_order` field ensures columns appear in correct order
5. **History Tracking**: `created_at` and `updated_at` track when columns were added/modified
6. **Backward Compatibility**: Still update `config_json` for legacy support, but DB is primary source

## Deletion Behavior

### When User Closes/Deletes Calculated Column:

1. **Frontend Action**: User removes calculated column from UI (closes tab, clicks delete, etc.)
2. **Save Trigger**: When user clicks "Save Projection", frontend sends updated list
3. **Backend Processing**:
   - **DELETE ALL** existing calculated columns for the node: `CalculatedColumn.objects.filter(node=node).delete()`
   - **INSERT NEW** calculated columns from request (if any)
   - If request has empty `calculated_columns` array, all are deleted
4. **Result**: Database is synchronized with UI state

### Key Points:

- **Cascade Delete**: When a node is deleted, all its calculated columns are automatically deleted (via `on_delete=CASCADE`)
- **Replace Strategy**: POST endpoint replaces ALL calculated columns (not incremental)
- **Empty Array = Delete All**: Sending `calculated_columns: []` deletes all columns
- **Individual Delete**: DELETE endpoint allows removing single column without affecting others

## Migration Strategy

1. Create `CalculatedColumn` model
2. Create migration to add table
3. Create API endpoints:
   - `GET /api/canvas/nodes/{node_id}/calculated-columns/`
   - `POST /api/canvas/nodes/{node_id}/calculated-columns/` (replaces all)
   - `PUT /api/canvas/nodes/{node_id}/calculated-columns/{id}/` (update single)
   - `DELETE /api/canvas/nodes/{node_id}/calculated-columns/{id}/` (delete single)
4. Update frontend to use new endpoints
5. Update backend execution logic to fetch from DB instead of config
6. Optional: Migrate existing calculated columns from `config_json` to new table

## API Endpoints

### GET Calculated Columns
```
GET /api/canvas/nodes/{node_id}/calculated-columns/
Response: [
  {
    "id": 1,
    "name": "tern",
    "expression": "UPPER(table_name)",
    "data_type": "STRING",
    "display_order": 0
  }
]
```

### POST Calculated Columns (Save/Replace All)
```
POST /api/canvas/nodes/{node_id}/calculated-columns/
Body: {
  "calculated_columns": [
    {
      "name": "tern",
      "expression": "UPPER(table_name)",
      "data_type": "STRING",
      "display_order": 0
    }
  ]
}
Response: {
  "success": true,
  "calculated_columns": [...]
}

Note: This endpoint REPLACES all calculated columns for the node.
If calculated_columns is empty array [], all columns are deleted.
```

### DELETE Single Calculated Column
```
DELETE /api/canvas/nodes/{node_id}/calculated-columns/{column_id}/
Response: {
  "success": true,
  "message": "Calculated column deleted successfully"
}
```

### PUT Update Single Calculated Column
```
PUT /api/canvas/nodes/{node_id}/calculated-columns/{column_id}/
Body: {
  "name": "tern_updated",
  "expression": "LOWER(table_name)",
  "data_type": "STRING",
  "display_order": 0
}
Response: {
  "success": true,
  "calculated_column": {...}
}
```

### Execution Flow
```
POST /api/pipeline/execute/
Body: {
  "nodes": [...],
  "targetNodeId": "node-uuid"
}

Backend:
1. Fetch CalculatedColumn.objects.filter(node_id=targetNodeId)
2. Extract calculated column names
3. Filter them out from selected_columns
4. Build SELECT with only base columns
5. Evaluate calculated columns in Python
6. Return combined result
```
