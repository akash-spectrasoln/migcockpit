# Data Migration Cockpit - Startup Guide

This guide explains how to start and stop all services for the Data Migration Cockpit application.

## Quick Start

### Windows (Recommended)

**Option 1: Batch Script (Easiest)**
```batch
start_all_services.bat
```

**Option 2: PowerShell Script (More Control)**
```powershell
.\start_all_services.ps1
```

**To Stop All Services:**
```batch
stop_all_services.bat
```
or
```powershell
.\stop_all_services.ps1
```

### Linux/Mac

```bash
chmod +x start_services.sh
./start_services.sh
```

Press `Ctrl+C` to stop all services.

## Services Overview

The application consists of the following services:

| Service | Port | Description |
|---------|------|-------------|
| Django API | 8000 | Main REST API and admin interface |
| React Frontend | 3000 | User interface (Vite dev server) |
| Celery Worker | - | Background task processor |
| Extraction Service | 8001 | FastAPI service for data extraction |
| Migration Orchestrator | 8003 | FastAPI service for migration coordination |
| WebSocket Server | 8004 | Real-time communication server |
| Redis | 6379 | Message broker for Celery |
| PostgreSQL | 5433 | Main database |

## Prerequisites

### Required

1. **Python 3.8+**
   ```bash
   python --version
   ```

2. **Node.js 16+ and npm**
   ```bash
   node --version
   npm --version
   ```

3. **PostgreSQL**
   - Database: `datamigrate`
   - User: `akash`
   - Port: `5433`
   - Password: `SecurePassword123!`

4. **Redis**
   - Port: `6379`
   - Windows: Download from [Microsoft Archive](https://github.com/microsoftarchive/redis/releases)
   - Linux: `sudo apt-get install redis-server` or `brew install redis`
   - Mac: `brew install redis`

### Python Dependencies

Install Python packages:
```bash
pip install -r requirements.txt
```

### Frontend Dependencies

Install Node.js packages:
```bash
cd frontend
npm install
```

## Manual Startup (Alternative)

If you prefer to start services manually:

### 1. Start Redis
```bash
# Windows (if installed as service, it should auto-start)
redis-server

# Linux/Mac
redis-server
```

### 2. Start Django
```bash
python manage.py runserver 8000
```

### 3. Start Celery Worker
```bash
celery -A datamigrationapi worker --loglevel=info
```

### 4. Start FastAPI Services

**Extraction Service:**
```bash
cd services/extraction_service
python main.py
```

**Migration Orchestrator:**
```bash
cd services/migration_service
python main.py
```

**WebSocket Server:**
```bash
cd services/websocket_server
python main.py
```

### 5. Start Frontend
```bash
cd frontend
npm run dev
```

## Service URLs

Once all services are running, access them at:

- **Frontend**: http://localhost:3000
- **Django API**: http://localhost:8000
- **Django Admin**: http://localhost:8000/admin
- **API Docs (Extraction)**: http://localhost:8001/docs
- **API Docs (Migration)**: http://localhost:8003/docs
- **API Docs (WebSocket)**: http://localhost:8004/docs

## Troubleshooting

### Port Already in Use

If a port is already in use, you can:

1. **Find the process using the port:**
   ```bash
   # Windows
   netstat -ano | findstr :8000
   
   # Linux/Mac
   lsof -i :8000
   ```

2. **Kill the process:**
   ```bash
   # Windows
   taskkill /PID <process_id> /F
   
   # Linux/Mac
   kill -9 <process_id>
   ```

### Redis Not Running

**Windows:**
- Check if Redis service is running: `services.msc`
- Or start manually: `redis-server`

**Linux/Mac:**
```bash
redis-server
```

### PostgreSQL Connection Issues

Verify PostgreSQL is running and accessible:
```bash
# Test connection
psql -h localhost -p 5433 -U akash -d datamigrate
```

### Celery Not Processing Tasks

1. Ensure Redis is running
2. Check Celery worker logs for errors
3. Verify `CELERY_BROKER_URL` in `settings.py`

### Frontend Not Loading

1. Check if Node.js is installed: `node --version`
2. Install dependencies: `cd frontend && npm install`
3. Check for port conflicts (default: 3000)

## Development vs Production

### Development (Current Setup)
- All services run locally
- Hot reload enabled for frontend
- Debug mode enabled for Django

### Production
- Use process managers (PM2, Supervisor, systemd)
- Configure reverse proxy (Nginx)
- Use production database settings
- Enable HTTPS
- Set up monitoring and logging

## Scripts Reference

### Windows Scripts

- `start_all_services.bat` - Start all services (batch)
- `stop_all_services.bat` - Stop all services (batch)
- `start_all_services.ps1` - Start all services (PowerShell)
- `stop_all_services.ps1` - Stop all services (PowerShell)

### Linux/Mac Scripts

- `start_services.sh` - Start all services
- Press `Ctrl+C` to stop

## Next Steps

1. **Create Superuser** (if not already done):
   ```bash
   python manage.py createsuperuser
   ```

2. **Run Migrations** (if not already done):
   ```bash
   python manage.py migrate
   ```

3. **Access the Application**:
   - Open http://localhost:5173 in your browser
   - Login with your superuser credentials

## Support

For issues or questions:
1. Check service logs in the console windows
2. Verify all prerequisites are installed
3. Ensure all ports are available
4. Check database and Redis connections

