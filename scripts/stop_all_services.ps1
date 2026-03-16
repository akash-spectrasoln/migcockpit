# ============================================================
# Data Migration Cockpit - PowerShell Stop Script
# Stops all running services
# Usage: .\stop_all_services.ps1
# ============================================================

# Get script directory and navigate to project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BaseDir = Join-Path $ScriptDir ".."
Set-Location $BaseDir

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Stopping All Data Migration Cockpit Services" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Function to kill process by port
function Stop-ProcessByPort {
    param([int]$Port)
    
    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    foreach ($conn in $connections) {
        if ($conn.State -eq "Listen") {
            $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
            if ($process) {
                Write-Host "[INFO] Stopping process on port $Port (PID: $($process.Id), Name: $($process.ProcessName))" -ForegroundColor Yellow
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

Write-Host "[INFO] Stopping services by window title..." -ForegroundColor Yellow

# Stop by window title
$windowTitles = @(
    "Django Server",
    "Celery Worker",
    "Extraction Service",
    "Migration Orchestrator",
    "WebSocket Server",
    "React Frontend"
)

foreach ($title in $windowTitles) {
    Get-Process | Where-Object { $_.MainWindowTitle -like "*$title*" } | Stop-Process -Force -ErrorAction SilentlyContinue
}

Write-Host "[INFO] Stopping services by port..." -ForegroundColor Yellow

# Stop by port
$ports = @(8000, 8001, 8003, 8004, 3000)
foreach ($port in $ports) {
    Stop-ProcessByPort -Port $port
}

# Additional cleanup - kill Python processes that might be Django/Celery
Write-Host "[INFO] Cleaning up remaining Python processes..." -ForegroundColor Yellow
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*manage.py*" -or
    $_.CommandLine -like "*celery*" -or
    $_.CommandLine -like "*main.py*"
}

foreach ($proc in $pythonProcesses) {
    Write-Host "[INFO] Stopping Python process: $($proc.ProcessName) (PID: $($proc.Id))" -ForegroundColor Yellow
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "[OK] All services stopped!" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to continue"

