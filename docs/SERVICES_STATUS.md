# Services Status

## All Services Started! 🚀

### Services Running:

1. **Django REST API** 
   - Port: 8000
   - URL: http://localhost:8000
   - API Docs: http://localhost:8000/api/docs
   - Status: ✅ Running

2. **React Frontend**
   - Port: 3000
   - URL: http://localhost:3000
   - Status: ✅ Running

3. **Extraction Service (FastAPI)**
   - Port: 8001
   - URL: http://localhost:8001
   - API Docs: http://localhost:8001/docs
   - Status: ✅ Running

4. **Migration Orchestrator (FastAPI)**
   - Port: 8003
   - URL: http://localhost:8003
   - API Docs: http://localhost:8003/docs
   - Status: ✅ Running

5. **WebSocket Server**
   - Port: 8004
   - URL: http://localhost:8004
   - Health: http://localhost:8004/health
   - Status: ✅ Running

6. **Celery Worker**
   - Broker: Redis (localhost:6379)
   - Status: ✅ Running

## Quick Access

- **Frontend Application**: http://localhost:3000
- **Django Admin**: http://localhost:8000/admin (if configured)
- **API Documentation**: http://localhost:8000/api/docs

## Next Steps

1. **Access the Application**:
   - Open http://localhost:3000 in your browser
   - You'll be redirected to login page

2. **Login**:
   - Use your credentials (or create a superuser if needed)
   - After login, you'll be redirected to Canvas page

3. **Start Building Pipelines**:
   - Drag nodes from the palette
   - Configure each node
   - Connect nodes to build pipeline
   - Save and execute

## Service Dependencies

- **Django** requires: PostgreSQL database
- **Frontend** requires: Django API running
- **FastAPI Services** can run independently
- **WebSocket Server** requires: Migration Service for broadcasts
- **Celery** requires: Redis running

## Troubleshooting

If a service fails to start:

1. **Check Port Availability**:
   ```powershell
   netstat -ano | findstr ":8000"
   ```

2. **Check Logs**:
   - Each service runs in a separate window/process
   - Check the terminal output for errors

3. **Common Issues**:
   - Port already in use → Stop the process using that port
   - Database connection error → Check PostgreSQL is running
   - Redis not running → Start Redis service
   - Module not found → Install missing dependencies

## Stopping Services

To stop all services:
- Close each terminal window
- Or use `Ctrl+C` in each service terminal
- Or use Task Manager to end Python/Node processes

## Service Health Checks

- Django: http://localhost:8000/api/api-projects-list/ (requires auth)
- Extraction: http://localhost:8001/health
- Migration: http://localhost:8003/health
- WebSocket: http://localhost:8004/health

