# Canvas Architecture & Data Migration System - Setup Guide

## Overview

This system implements a modern canvas-based data migration interface with:
- **React SPA Frontend** - Drag-and-drop canvas interface
- **Django REST API** - Main backend for authentication and business logic
- **FastAPI Microservices** - High-performance data operations
- **Celery + Redis** - Background task processing
- **WebSocket Server** - Real-time updates

## Architecture

```
React Frontend (Port 3000)
    ↓
Django REST API (Port 8000)
    ↓
FastAPI Services:
  - Extraction Service (Port 8001)
  - Transformation Service (Port 8002)
  - Migration Orchestrator (Port 8003)
  - WebSocket Server (Port 8004)
    ↓
Celery Workers + Redis
    ↓
Source DBs (MySQL/Oracle/SQL Server) → SAP HANA
```

## Prerequisites

- Python 3.9+
- Node.js 18+
- PostgreSQL (for Django)
- Redis (for Celery)
- SAP HANA (destination database)

## Installation

### 1. Backend Setup

```bash
cd datamigration-migcockpit

# Install Python dependencies
pip install -r requirements.txt

# Run Django migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### 3. Start Services

#### Terminal 1: Django Server
```bash
python manage.py runserver
```

#### Terminal 2: Redis
```bash
redis-server
```

#### Terminal 3: Celery Worker
```bash
celery -A datamigrationapi worker --loglevel=info
```

#### Terminal 4: Extraction Service
```bash
cd services/extraction_service
python main.py
```

#### Terminal 5: Transformation Service
```bash
cd services/transformation_service
python main.py
```

#### Terminal 6: Migration Orchestrator
```bash
cd services/migration_service
python main.py
```

#### Terminal 7: WebSocket Server
```bash
cd services/websocket_server
python main.py
```

## API Endpoints

### Canvas API
- `GET /api/canvas/` - List all canvases
- `POST /api/canvas/` - Create canvas
- `GET /api/canvas/{id}/` - Get canvas details
- `PUT /api/canvas/{id}/` - Update canvas
- `DELETE /api/canvas/{id}/` - Delete canvas
- `POST /api/canvas/{id}/save-configuration/` - Save canvas configuration

### Migration Jobs API
- `GET /api/migration-jobs/` - List all jobs
- `POST /api/migration-jobs/execute/` - Execute migration
- `GET /api/migration-jobs/{id}/status/` - Get job status
- `GET /api/migration-jobs/{id}/logs/` - Get job logs
- `POST /api/migration-jobs/{id}/cancel/` - Cancel job

## Usage

1. **Access Frontend**: http://localhost:3000
2. **Login** with your credentials
3. **Create Canvas**: Drag and drop source, transform, and destination nodes
4. **Configure Nodes**: Click nodes to configure connection details
5. **Save Canvas**: Click "Save" button
6. **Execute Migration**: Click "Execute" button
7. **Monitor Progress**: Real-time updates via WebSocket

## Database Models

### Canvas
- Stores canvas configurations
- Links to Customer and User
- Contains nodes and edges as JSON

### MigrationJob
- Tracks migration executions
- Stores status, progress, and statistics
- Links to Canvas and Customer

## Performance Considerations

- **Chunked Processing**: Data processed in 10K-100K row batches
- **Connection Pooling**: Reused database connections
- **Parallel Extraction**: Multiple workers per source
- **Caching**: Redis for metadata and progress
- **Streaming**: Large datasets streamed instead of loaded into memory

## Troubleshooting

### Frontend not connecting to backend
- Check CORS settings in Django settings.py
- Verify API_BASE_URL in frontend .env

### Celery tasks not running
- Ensure Redis is running
- Check Celery worker logs
- Verify broker_url in celery.py

### Migration service errors
- Check FastAPI service logs
- Verify database connection strings
- Ensure all services are running

## Development Notes

- Models are in `api/models/canvas.py` and `api/models/migration_job.py`
- Views are in `api/views/canvas_views.py` and `api/views/migration_views.py`
- FastAPI services are in `services/` directory
- Frontend components are in `frontend/src/components/Canvas/`

## Next Steps

1. Configure database connections in Django admin
2. Set up source and destination connections
3. Create your first canvas
4. Test with small datasets first
5. Monitor performance and optimize as needed

