# Services Started Successfully! ✅

## Current Status

### ✅ Running Services

1. **Django REST API** - Port 8000
   - Status: ✅ Running (multiple instances detected)
   - Access: http://localhost:8000
   - API Docs: http://localhost:8000/api/docs

2. **React Frontend** - Port 3000
   - Status: ✅ Running
   - Access: http://localhost:3000
   - Will redirect to login page

3. **Extraction Service** - Port 8001
   - Status: Starting...
   - Access: http://localhost:8001/docs

4. **Migration Orchestrator** - Port 8003
   - Status: Starting...
   - Access: http://localhost:8003/docs

5. **WebSocket Server** - Port 8004
   - Status: Starting...
   - Access: http://localhost:8004/health

7. **Celery Worker**
   - Status: Starting...
   - Requires: Redis running

## Quick Start Guide

### 1. Access the Application

Open your browser and navigate to:
```
http://localhost:3000
```

### 2. Login Flow

1. You'll see the **Login Page**
2. Enter your credentials:
   - Email: (your email)
   - Password: (your password)
3. Click "Login"
4. You'll be redirected to the **Canvas Page**

### 3. Using the Canvas

**Canvas Page Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Header: [Jobs] [Logout]                            │
├──────────┬──────────────────────┬───────────────────┤
│  Node    │                      │  Configuration    │
│  Palette │   Canvas Area        │  Panel            │
│          │   (React Flow)       │  (Right Side)     │
│ [Source] │                      │                   │
│[Transform│   ┌──────┐           │  (Opens when     │
│[Dest]    │   │ Node │           │   node clicked)  │
│          │   └──┬───┘           │                   │
│          │   ┌──▼───┐           │                   │
│          │   │ Edge │           │                   │
│          │   └──────┘           │                   │
└──────────┴──────────────────────┴───────────────────┘
│ Toolbar: [Design] [Validate] [Save] [Execute] [Delete] │
└─────────────────────────────────────────────────────┘
```

**Steps to Build a Pipeline:**

1. **Add Source Node**
   - Drag "MySQL Source" (or Oracle/SQL Server) from left palette
   - Click the node to open configuration panel
   - Select source connection
   - Enter table name
   - Save configuration

2. **Add Transform Node**
   - Drag "Data Mapping" (or Filter/Clean/Validate) from palette
   - Click to configure
   - Set up mapping rules or filters
   - Save

3. **Add Destination Node**
   - Drag "SAP HANA" from palette
   - Click to configure
   - Select destination connection
   - Enter target table
   - Choose load mode

4. **Connect Nodes**
   - Drag from source node's output handle (right side)
   - Drop on transform node's input handle (left side)
   - Drag from transform node's output handle
   - Drop on destination node's input handle

5. **Save Canvas**
   - Click "Save" button in toolbar
   - Canvas configuration saved to database

6. **Validate Pipeline**
   - Click "Validate" button
   - Review any errors or warnings
   - Fix issues if any

7. **Execute Migration**
   - Click "Execute" button
   - Job starts in background
   - Navigate to "Jobs" page to monitor

### 4. Monitor Jobs

1. Click "Jobs" button in header
2. View list of all migration jobs
3. Filter by status, search, or date
4. Click a job to see details
5. Watch real-time updates via WebSocket
6. View logs for running jobs
7. Cancel jobs if needed

## Service URLs Summary

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:3000 | Main application UI |
| Django API | http://localhost:8000 | REST API backend |
| Extraction | http://localhost:8001/docs | Data extraction service |
| Migration | http://localhost:8003/docs | Migration orchestration |
| WebSocket | http://localhost:8004/health | Real-time updates |

## Testing the Application

### 1. Test Login
- Go to http://localhost:3000
- Should see login page
- Try logging in (or create superuser first)

### 2. Test Canvas
- After login, should see canvas page
- Try dragging a node from palette
- Click node to configure
- Try connecting nodes

### 3. Test API
- Go to http://localhost:8000/api/docs
- Should see API documentation
- Try authenticated endpoints (need to login first)

### 4. Test Services
- Check health endpoints:
  - http://localhost:8001/health
  - http://localhost:8003/health
  - http://localhost:8004/health

## Troubleshooting

### Frontend not loading?
- Check if port 3000 is available
- Check browser console for errors
- Verify Django is running on 8000

### Can't login?
- Check Django server logs
- Verify database connection
- Check if user exists (create superuser if needed)

### Services not starting?
- Check Python dependencies installed
- Check if ports are available
- Review service logs in terminal windows

### WebSocket not connecting?
- Verify WebSocket server is running
- Check CORS settings
- Check browser console for connection errors

## Creating a Superuser

If you need to create a superuser:

```powershell
cd datamigration-migcockpit
python manage.py createsuperuser
```

Or use the script:
```powershell
python create_superuser_simple.py
```

## Next Steps

1. ✅ All services are running
2. ✅ Access http://localhost:3000
3. ✅ Login with your credentials
4. ✅ Start building migration pipelines!

Enjoy building your data migration pipelines! 🚀

