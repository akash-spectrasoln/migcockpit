# ============================================================
# Data Migration Cockpit - PowerShell Startup Script
# Starts all required services with better control
# Usage: .\start_all_services.ps1
# ============================================================

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Data Migration Cockpit - Starting All Services" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory and navigate to project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BaseDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $BaseDir

# Check if we're in the right directory
if (-not (Test-Path "manage.py")) {
    Write-Host "[ERROR] Please run this script from the scripts directory" -ForegroundColor Red
    Write-Host "Current directory: $PWD" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Function to check if port is available
function Test-Port {
    param([int]$Port)
    $connection = Test-NetConnection -ComputerName localhost -Port $Port -WarningAction SilentlyContinue
    return $connection.TcpTestSucceeded
}

# Function to start service in new window
function Start-ServiceWindow {
    param(
        [string]$Title,
        [string]$Command,
        [string]$WorkingDir
    )
    
    $process = Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/k", "title $Title && cd /d `"$WorkingDir`" && $Command" `
        -WindowStyle Minimized `
        -PassThru
    
    return $process
}

Write-Host "[1/8] Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python is not installed or not in PATH" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[2/8] Checking Node.js installation..." -ForegroundColor Yellow
$skipFrontend = $false
try {
    $nodeVersion = node --version 2>&1
    Write-Host "[OK] $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "[WARNING] Node.js is not installed. Frontend will not start." -ForegroundColor Yellow
    $skipFrontend = $true
}

Write-Host "[3/8] Checking Redis..." -ForegroundColor Yellow
if (Test-Port -Port 6379) {
    Write-Host "[OK] Redis appears to be running on port 6379" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Redis may not be running on port 6379" -ForegroundColor Yellow
    Write-Host "[INFO] Please ensure Redis is installed and running" -ForegroundColor Yellow
}

Write-Host "[4/8] Checking PostgreSQL..." -ForegroundColor Yellow
if (Test-Port -Port 5433) {
    Write-Host "[OK] PostgreSQL appears to be running on port 5433" -ForegroundColor Green
} else {
    Write-Host "[WARNING] PostgreSQL may not be running on port 5433" -ForegroundColor Yellow
    Write-Host "[INFO] Database: datamigrate, User: akash" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[5/8] Starting Django Server (port 8000)..." -ForegroundColor Yellow
if (Test-Port -Port 8000) {
    Write-Host "[WARNING] Port 8000 is already in use" -ForegroundColor Yellow
} else {
    $djangoProcess = Start-ServiceWindow `
        -Title "Django Server - Port 8000" `
        -Command "python manage.py runserver 8000" `
        -WorkingDir $BaseDir
    Start-Sleep -Seconds 3
    Write-Host "[OK] Django server started" -ForegroundColor Green
}

Write-Host "[6/8] Starting Celery Worker..." -ForegroundColor Yellow
# On Windows use --pool=solo to avoid "ValueError: not enough values to unpack" (prefork pool bug)
    $celeryProcess = Start-ServiceWindow `
        -Title "Celery Worker" `
        -Command "celery -A datamigrationapi worker --loglevel=info --pool=solo" `
        -WorkingDir $BaseDir
Start-Sleep -Seconds 2
Write-Host "[OK] Celery worker started" -ForegroundColor Green

Write-Host "[7/8] Starting FastAPI Microservices..." -ForegroundColor Yellow

$extractionProcess = Start-ServiceWindow `
    -Title "Extraction Service - Port 8001" `
    -Command "python main.py" `
    -WorkingDir "$BaseDir\services\extraction_service"
Start-Sleep -Seconds 2

$migrationProcess = Start-ServiceWindow `
    -Title "Migration Orchestrator - Port 8003" `
    -Command "python main.py" `
    -WorkingDir "$BaseDir\services\migration_service"
Start-Sleep -Seconds 2

# Ensure WebSocket server deps (python-socketio) so /socket.io/ works; otherwise 403
$wsReq = Join-Path $BaseDir "services\websocket_server\requirements.txt"
if (Test-Path $wsReq) {
    Write-Host "[INFO] Installing WebSocket server deps (python-socketio) for real-time updates..." -ForegroundColor Gray
    pip install -q -r $wsReq 2>$null
}
$websocketProcess = Start-ServiceWindow `
    -Title "WebSocket Server - Port 8004" `
    -Command "python main.py" `
    -WorkingDir "$BaseDir\services\websocket_server"
Start-Sleep -Seconds 2

Write-Host "[OK] All FastAPI services started" -ForegroundColor Green

if (-not $skipFrontend) {
    Write-Host "[8/8] Starting React Frontend (port 3000)..." -ForegroundColor Yellow
    if (Test-Port -Port 3000) {
        Write-Host "[WARNING] Port 3000 is already in use" -ForegroundColor Yellow
    } else {
        $frontendProcess = Start-ServiceWindow `
            -Title "React Frontend - Port 3000" `
            -Command "npm run dev" `
            -WorkingDir "$BaseDir\frontend"
        Write-Host "[OK] Frontend started" -ForegroundColor Green
    }
} else {
    Write-Host "[8/8] Skipping Frontend (Node.js not found)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  All Services Started!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Service URLs:" -ForegroundColor White
Write-Host "  - Django API:        http://localhost:8000" -ForegroundColor Cyan
Write-Host "  - Django Admin:      http://localhost:8000/admin" -ForegroundColor Cyan
Write-Host "  - Frontend:          http://localhost:3000" -ForegroundColor Cyan
Write-Host "  - Extraction API:     http://localhost:8001/docs" -ForegroundColor Cyan
Write-Host "  - Migration API:    http://localhost:8003/docs" -ForegroundColor Cyan
Write-Host "  - WebSocket Server:  http://localhost:8004/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "All services are running in minimized windows." -ForegroundColor Yellow
Write-Host "Check the taskbar for service windows." -ForegroundColor Yellow
Write-Host ""
Write-Host "To stop all services, run: .\stop_all_services.ps1" -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to continue"

