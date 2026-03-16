@echo off
REM Start script for all services (Windows)
REM Usage: start_services.bat

echo Starting Data Migration Cockpit Services...

REM Start Redis (if installed as Windows service, it should already be running)
echo Checking Redis...

REM Start Django server
echo Starting Django server on port 8000...
start "Django Server" cmd /k "cd datamigration-migcockpit && python manage.py runserver 8000"

REM Start Celery worker
echo Starting Celery worker...
start "Celery Worker" cmd /k "cd datamigration-migcockpit && celery -A datamigrationapi worker --loglevel=info"

REM Start Extraction Service
echo Starting Extraction Service on port 8001...
start "Extraction Service" cmd /k "cd datamigration-migcockpit\services\extraction_service && python main.py"

REM Start Migration Orchestrator
echo Starting Migration Orchestrator on port 8003...
start "Migration Orchestrator" cmd /k "cd datamigration-migcockpit\services\migration_service && python main.py"

REM Start WebSocket Server
echo Starting WebSocket Server on port 8004...
start "WebSocket Server" cmd /k "cd datamigration-migcockpit\services\websocket_server && python main.py"

REM Start Frontend
echo Starting React frontend on port 3000...
start "React Frontend" cmd /k "cd datamigration-migcockpit\frontend && npm run dev"

echo.
echo All services started in separate windows!
echo Django: http://localhost:8000
echo Frontend: http://localhost:3000
echo Extraction Service: http://localhost:8001/docs
echo Migration Orchestrator: http://localhost:8003/docs
echo WebSocket Server: http://localhost:8004/docs
echo.
pause

