@echo off
REM ============================================================
REM Data Migration Cockpit - Stop All Services Script
REM Stops all running services
REM ============================================================

echo.
echo ============================================================
echo   Stopping All Data Migration Cockpit Services
echo ============================================================
echo.

echo [INFO] Stopping Django server...
taskkill /FI "WINDOWTITLE eq Django Server*" /T /F >nul 2>&1
taskkill /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *Django*" /T /F >nul 2>&1

echo [INFO] Stopping Celery worker...
taskkill /FI "WINDOWTITLE eq Celery Worker*" /T /F >nul 2>&1
taskkill /FI "IMAGENAME eq celery.exe" /T /F >nul 2>&1

echo [INFO] Stopping FastAPI services...
taskkill /FI "WINDOWTITLE eq Extraction Service*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Migration Orchestrator*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq WebSocket Server*" /T /F >nul 2>&1

echo [INFO] Stopping Frontend...
taskkill /FI "WINDOWTITLE eq React Frontend*" /T /F >nul 2>&1
taskkill /FI "IMAGENAME eq node.exe" /FI "WINDOWTITLE eq *Frontend*" /T /F >nul 2>&1

REM Kill processes by port (more reliable)
echo [INFO] Killing processes on service ports...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8003" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8004" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

echo.
echo [OK] All services stopped!
echo.
pause

