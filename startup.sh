#!/bin/bash

# Startup script to launch API, Frontend, and optionally the background worker
# Linux and Bash only
# Usage: ./startup.sh [--api|-api] [--gui|-gui] [--worker|-worker] [--foreground|-f]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
readonly GREEN='\033[0;32m'
readonly BLUE='\033[0;34m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly NC='\033[0m'

# Parse command line arguments
START_API=true
START_GUI=true
START_WORKER=false
FOREGROUND=false

for arg in "$@"; do
    case "$arg" in
        --api|-api)
            START_API=true
            START_GUI=false
            ;;
        --gui|-gui)
            START_GUI=true
            START_API=false
            ;;
        --worker|-worker)
            START_WORKER=true
            ;;
        --foreground|-f)
            FOREGROUND=true
            ;;
        *)
            echo -e "${RED}Unknown option: $arg${NC}"
            echo "Usage: ./startup.sh [--api|-api] [--gui|-gui] [--worker|-worker] [--foreground|-f]"
            exit 1
            ;;
    esac
done

# -f --worker: run only worker in foreground (no API, no GUI)
if [ "$FOREGROUND" = true ] && [ "$START_WORKER" = true ]; then
    START_API=false
    START_GUI=false
fi

echo -e "${BLUE}Starting Quote-Image Pipeline MVP...${NC}"

# Function to cleanup background processes on exit
cleanup() {
    echo -e "\n${YELLOW}Stopping servers...${NC}"
    if [ -f logs/api.pid ]; then
        kill "$(cat logs/api.pid)" 2>/dev/null || true
        rm -f logs/api.pid
    fi
    if [ -f logs/frontend.pid ]; then
        kill "$(cat logs/frontend.pid)" 2>/dev/null || true
        rm -f logs/frontend.pid
    fi
    if [ -f logs/worker.pid ]; then
        kill "$(cat logs/worker.pid)" 2>/dev/null || true
        rm -f logs/worker.pid
    fi
    # Kill any remaining Python/Node processes
    pkill -f "python -m app.main" 2>/dev/null || true
    pkill -f "python -m app.worker" 2>/dev/null || true
    pkill -f "npm run dev" 2>/dev/null || true
    echo -e "${GREEN}Servers stopped.${NC}"
    exit 0
}

# Set up trap to cleanup on Ctrl+C or exit
trap cleanup SIGINT SIGTERM EXIT

# Create logs directory if it doesn't exist
mkdir -p logs

# With -f, exactly one of API, GUI, or worker may run
if [ "$FOREGROUND" = true ]; then
    n=0
    [ "$START_API" = true ]  && n=$((n + 1))
    [ "$START_GUI" = true ]  && n=$((n + 1))
    [ "$START_WORKER" = true ] && n=$((n + 1))
    if [ "$n" -gt 1 ]; then
        echo -e "${RED}Error: Use -f with exactly one of --api, --gui, --worker.${NC}"
        echo -e "${YELLOW}Examples: ./startup.sh -f --api  or  ./startup.sh -f --gui  or  ./startup.sh -f --worker${NC}"
        exit 1
    fi
    if [ "$n" -eq 0 ]; then
        echo -e "${RED}Error: Use -f with one of --api, --gui, --worker.${NC}"
        exit 1
    fi
fi

# Start API server
if [ "$START_API" = true ]; then
    if [ "$FOREGROUND" = true ]; then
        echo -e "${GREEN}Starting API server in foreground...${NC}"
        cd "$SCRIPT_DIR"
        if [ -d "venv" ]; then
            source venv/bin/activate
        fi
        echo -e "${BLUE}API: http://localhost:8000${NC}"
        echo -e "${BLUE}API Docs: http://localhost:8000/docs${NC}"
        echo ""
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        python -m app.main
    else
        (
            cd "$SCRIPT_DIR"
            if [ -d "venv" ]; then
                source venv/bin/activate
            fi
            python -m app.main > logs/api.log 2>&1
        ) &
        API_PID=$!
        echo $API_PID > logs/api.pid
        echo -e "${GREEN}API server started (PID: $API_PID, logs: logs/api.log)${NC}"
        echo -e "${BLUE}API: http://localhost:8000${NC}"
        echo -e "${BLUE}API Docs: http://localhost:8000/docs${NC}"
    fi
fi

# Start worker (READY jobs in PROCESSING tasks)
if [ "$START_WORKER" = true ]; then
    if [ "$FOREGROUND" = true ]; then
        echo -e "${GREEN}Starting worker in foreground...${NC}"
        cd "$SCRIPT_DIR"
        if [ -d "venv" ]; then
            source venv/bin/activate
        fi
        echo -e "${BLUE}Worker processes READY jobs in PROCESSING tasks.${NC}"
        echo ""
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        python -m app.worker
    else
        (
            cd "$SCRIPT_DIR"
            if [ -d "venv" ]; then
                source venv/bin/activate
            fi
            python -m app.worker > logs/worker.log 2>&1
        ) &
        WORKER_PID=$!
        echo $WORKER_PID > logs/worker.pid
        echo -e "${GREEN}Worker started (PID: $WORKER_PID, logs: logs/worker.log)${NC}"
    fi
fi

# Start Frontend server
if [ "$START_GUI" = true ]; then
    if [ "$FOREGROUND" = true ]; then
        echo -e "${GREEN}Starting Frontend server in foreground...${NC}"
        cd "$SCRIPT_DIR/frontend"
        if [ ! -d "node_modules" ]; then
            echo -e "${YELLOW}Installing frontend dependencies...${NC}"
            npm install
        fi
        echo -e "${BLUE}Frontend: http://localhost:3000${NC}"
        echo ""
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        npm run dev
    else
        (
            cd "$SCRIPT_DIR/frontend"
            if [ ! -d "node_modules" ]; then
                npm install
            fi
            npm run dev > ../logs/frontend.log 2>&1
        ) &
        FRONTEND_PID=$!
        echo $FRONTEND_PID > logs/frontend.pid
        echo -e "${GREEN}Frontend server started (PID: $FRONTEND_PID, logs: logs/frontend.log)${NC}"
        echo -e "${BLUE}Frontend: http://localhost:3000${NC}"
    fi
fi

# Wait for background processes if not in foreground mode
if [ "$FOREGROUND" = false ]; then
    echo ""
    echo -e "${BLUE}Servers are running in the background.${NC}"
    [ "$START_WORKER" = true ] && echo -e "${BLUE}Worker processes READY jobs in PROCESSING tasks.${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"
    echo -e "${YELLOW}Or run in foreground: ./startup.sh -f --api  or  -f --gui  or  -f --worker${NC}"
    wait
fi
