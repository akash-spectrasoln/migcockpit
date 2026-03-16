# Scripts Directory

This directory contains all startup and shutdown scripts for the Data Migration Cockpit application.

## Windows Scripts

### Batch Files (.bat)
- **`start_all_services.bat`** - Start all services (recommended)
- **`stop_all_services.bat`** - Stop all services
- **`start_services.bat`** - Legacy startup script (kept for compatibility)

### PowerShell Files (.ps1)
- **`start_all_services.ps1`** - Start all services with enhanced features
- **`stop_all_services.ps1`** - Stop all services with enhanced features

## Linux/Mac Scripts

- **`start_services.sh`** - Start all services on Linux/Mac

## Usage

### Windows (Recommended)
```batch
cd scripts
start_all_services.bat
```

### Windows (PowerShell)
```powershell
cd scripts
.\start_all_services.ps1
```

### Linux/Mac
```bash
cd scripts
chmod +x start_services.sh
./start_services.sh
```

## To Stop Services

### Windows
```batch
cd scripts
stop_all_services.bat
```

### Windows (PowerShell)
```powershell
cd scripts
.\stop_all_services.ps1
```

### Linux/Mac
Press `Ctrl+C` in the terminal where services are running.

## Services Started

- Django API Server (port 8000)
- React Frontend (port 3000)
- Celery Worker
- Extraction Service (port 8001)
- Migration Orchestrator (port 8003)
- WebSocket Server (port 8004)

For detailed documentation, see `../docs/README_STARTUP.md`

