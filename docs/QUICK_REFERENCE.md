# Quick Reference Guide

## Starting the Application

### 1. Start Backend Services

```powershell
# Terminal 1: Django
cd datamigration-migcockpit
python manage.py runserver 8000

# Terminal 2: Frontend
cd datamigration-migcockpit\frontend
npm run dev

# Terminal 3: WebSocket Server (optional, for real-time updates)
cd datamigration-migcockpit\services\websocket_server
python main.py

# Terminal 4: FastAPI Services (if needed)
# Extraction Service
cd datamigration-migcockpit\services\extraction_service
python main.py

# Migration Service
cd datamigration-migcockpit\services\migration_service
python main.py
```

### 2. Access the Application

- **Frontend**: http://localhost:3000
- **Django API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs
- **FastAPI Docs**: 
  - Extraction: http://localhost:8001/docs
  - Migration: http://localhost:8003/docs

## Using the Canvas

### Creating a Pipeline

1. **Add Source Node**
   - Drag "MySQL Source" (or Oracle/SQL Server) from palette
   - Click node to open configuration panel
   - Select source connection
   - Enter table name
   - Configure filters (optional)

2. **Add Transform Node**
   - Drag "Data Mapping" (or Filter/Clean/Validate) from palette
   - Click node to configure
   - Set up mapping rules, filters, or validation rules

3. **Add Destination Node**
   - Drag "SAP HANA" from palette
   - Click node to configure
   - Select destination connection
   - Enter target table name
   - Choose load mode (insert/upsert/replace)

4. **Connect Nodes**
   - Drag from source node output handle
   - Connect to transform node input handle
   - Drag from transform node output handle
   - Connect to destination node input handle

5. **Validate Pipeline**
   - Click "Validate" button
   - Review errors/warnings
   - Fix any issues

6. **Save Canvas**
   - Click "Save" button
   - Canvas is saved to database

7. **Execute Migration**
   - Click "Execute" button
   - Job starts in background
   - Navigate to "Jobs" page to monitor

## Monitoring Jobs

### Jobs Page Features

- **Filter Jobs**: By status, search term, date range
- **Real-Time Updates**: WebSocket for running jobs
- **Job Details**: Click job to see details sidebar
- **Logs**: View real-time logs for running jobs
- **Cancel**: Cancel running jobs

### WebSocket Events

- `status` - Overall job status update
- `node_progress` - Per-node progress update
- `complete` - Job completed
- `error` - Job failed
- `cancelled` - Job cancelled

## API Endpoints

### Canvas
- `GET /api/canvas/` - List canvases
- `POST /api/canvas/` - Create canvas
- `GET /api/canvas/{id}/` - Get canvas
- `PUT /api/canvas/{id}/` - Update canvas
- `POST /api/canvas/{id}/save-configuration/` - Save configuration

### Migration Jobs
- `POST /api/migration-jobs/execute/` - Execute migration
- `GET /api/migration-jobs/` - List jobs
- `GET /api/migration-jobs/{id}/status/` - Get job status
- `GET /api/migration-jobs/{id}/logs/` - Get job logs
- `POST /api/migration-jobs/{id}/cancel/` - Cancel job

### Metadata
- `GET /api/metadata/tables/?source_id={id}` - Get tables
- `GET /api/metadata/columns/?source_id={id}&table_name={name}` - Get columns
- `GET /api/metadata/validation_rules/` - Get validation rules
- `POST /api/metadata/validate_pipeline/` - Validate pipeline

## Adding New Node Types

### 1. Register in Frontend

Edit `frontend/src/types/nodeRegistry.ts`:

```typescript
registerNodeType({
  id: 'source-postgres',
  category: 'source',
  label: 'PostgreSQL Source',
  description: 'Extract data from PostgreSQL',
  icon: 'Database',
  color: 'blue',
  defaultConfig: { ... },
  configSchema: [ ... ],
})
```

### 2. Add Backend Support

- **For Sources**: Add connector in `services/extraction_service/connectors/`
- **For Destinations**: Add loader in `services/migration_service/`

### 3. Done!

Node automatically appears in palette and is configurable.

## Troubleshooting

### Canvas not loading
- Check Django server is running
- Check authentication token
- Check browser console

### WebSocket not connecting
- Check WebSocket server is running on port 8004
- Check CORS settings
- Check browser console for errors

### Jobs not executing
- Check FastAPI services are running
- Check Celery workers are running
- Check Redis connection
- Review job logs

### Validation errors
- Ensure all required fields are filled
- Check node configurations
- Verify graph connectivity

## Architecture Quick Reference

- **Frontend**: React + TypeScript + Zustand + React Flow
- **Backend**: Django REST API + FastAPI microservices
- **Real-Time**: Socket.IO WebSocket server
- **Background Jobs**: Celery + Redis
- **State Management**: Zustand stores
- **Type Safety**: Pydantic models + TypeScript

## Key Files

- Canvas Store: `frontend/src/store/canvasStore.ts`
- Node Registry: `frontend/src/types/nodeRegistry.ts`
- Enhanced Canvas: `frontend/src/components/Canvas/EnhancedDataFlowCanvas.tsx`
- Jobs Page: `frontend/src/pages/JobsPage.tsx`
- WebSocket Service: `frontend/src/services/websocket.ts`
- Migration Models: `services/migration_service/models.py`
- WebSocket Server: `services/websocket_server/main.py`

