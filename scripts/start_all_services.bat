@echo off
REM ============================================================
REM Data Migration Cockpit - Complete Startup Script
REM Starts all required services for the application
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   Data Migration Cockpit - Starting All Services
echo ============================================================
echo.

REM Get script directory and navigate to project root
set SCRIPT_DIR=%~dp0
set BASE_DIR=%SCRIPT_DIR%..
cd /d "%BASE_DIR%"

REM Check if we're in the right directory
if not exist "manage.py" (
    echo [ERROR] Please run this script from the scripts directory
    echo Current directory: %CD%
    pause
    exit /b 1
)

echo [1/8] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    pause
    exit /b 1
)
python --version

echo [2/8] Checking Node.js installation...
node --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Node.js is not installed. Frontend will not start.
    set SKIP_FRONTEND=1
) else (
    node --version
    set SKIP_FRONTEND=0
)

echo [3/8] Checking Redis...
REM Check if Redis is running (Windows Redis typically runs as a service)
netstat -an | findstr ":6379" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Redis may not be running on port 6379
    echo [INFO] Please ensure Redis is installed and running
    echo [INFO] You can download Redis for Windows from: https://github.com/microsoftarchive/redis/releases
) else (
    echo [OK] Redis appears to be running
)

echo [4/8] Checking PostgreSQL connection...
REM This is informational - actual connection will be tested by Django
echo [INFO] Ensure PostgreSQL is running on port 5433
echo [INFO] Database: datamigrate, User: akash

echo.
echo [5/8] Starting Django Server (port 8000)...
start "Django Server - Port 8000" /min cmd /k "cd /d %BASE_DIR% && python manage.py runserver 8000"
timeout /t 3 /nobreak >nul

echo [6/8] Starting Celery Worker...
start "Celery Worker" /min cmd /k "cd /d %BASE_DIR% && celery -A datamigrationapi worker --loglevel=info"
timeout /t 2 /nobreak >nul

echo [7/8] Starting FastAPI Microservices...
start "Extraction Service - Port 8001" /min cmd /k "cd /d %BASE_DIR%\services\extraction_service && python main.py"
timeout /t 2 /nobreak >nul

start "Migration Orchestrator - Port 8003" /min cmd /k "cd /d %BASE_DIR%\services\migration_service && python main.py"
timeout /t 2 /nobreak >nul

start "WebSocket Server - Port 8004" /min cmd /k "cd /d %BASE_DIR%\services\websocket_server && python main.py"
timeout /t 2 /nobreak >nul


start "React Frontend - Port 3000" /min cmd /k "cd /d %BASE_DIR%\frontend && npm run dev"

echo.
echo ============================================================
echo   All Services Started!
echo ============================================================
echo.
echo Service URLs:
echo   - Django API:        http://localhost:8000
echo   - Django Admin:      http://localhost:8000/admin
echo   - Frontend:          http://localhost:3000
echo   - Extraction API:    http://localhost:8001/docs
echo   - Migration API:     http://localhost:8003/docs
echo   - WebSocket Server:   http://localhost:8004/docs
echo.
echo All services are running in minimized windows.
echo Check the taskbar for service windows.
echo.
echo To stop all services, run: stop_all_services.bat
echo.
pause

