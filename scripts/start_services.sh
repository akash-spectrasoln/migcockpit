#!/bin/bash

# Start script for all services
# Usage: ./start_services.sh

echo "Starting Data Migration Cockpit Services..."

# Start Redis (if not already running)
if ! pgrep -x "redis-server" > /dev/null; then
    echo "Starting Redis..."
    redis-server --daemonize yes
    sleep 2
fi

# Get script directory and navigate to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BASE_DIR"

# Start Django server
echo "Starting Django server on port 8000..."
python manage.py runserver 8000 &
DJANGO_PID=$!

# Start Celery worker
echo "Starting Celery worker..."
celery -A datamigrationapi worker --loglevel=info &
CELERY_PID=$!

# Start Extraction Service
echo "Starting Extraction Service on port 8001..."
cd "$BASE_DIR/services/extraction_service"
python main.py &
EXTRACTION_PID=$!

# Start Migration Orchestrator
echo "Starting Migration Orchestrator on port 8003..."
cd "$BASE_DIR/services/migration_service"
python main.py &
MIGRATION_PID=$!

# Start WebSocket Server
echo "Starting WebSocket Server on port 8004..."
cd "$BASE_DIR/services/websocket_server"
python main.py &
WEBSOCKET_PID=$!

# Start Frontend (if Node.js is available)
if command -v npm &> /dev/null; then
    echo "Starting React frontend on port 3000..."
    cd "$BASE_DIR/frontend"
    npm run dev &
    FRONTEND_PID=$!
fi

echo ""
echo "All services started!"
echo "Django: http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "Extraction Service: http://localhost:8001/docs"
echo "Migration Orchestrator: http://localhost:8003/docs"
echo "WebSocket Server: http://localhost:8004/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for user interrupt
trap "kill $DJANGO_PID $CELERY_PID $EXTRACTION_PID $MIGRATION_PID $WEBSOCKET_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

wait

