#!/bin/bash

# Startup script to launch API and Frontend servers
# Linux and Bash only
# Usage: ./startup.sh [--api|-api] [--gui|-gui] [--foreground|-f]

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
        --foreground|-f)
            FOREGROUND=true
            ;;
        *)
            echo -e "${RED}Unknown option: $arg${NC}"
            echo "Usage: ./startup.sh [--api|-api] [--gui|-gui] [--foreground|-f]"
            exit 1
            ;;
    esac
done

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
    # Kill any remaining Python/Node processes
    pkill -f "python -m app.main" 2>/dev/null || true
    pkill -f "npm run dev" 2>/dev/null || true
    echo -e "${GREEN}Servers stopped.${NC}"
    exit 0
}

# Set up trap to cleanup on Ctrl+C or exit
trap cleanup SIGINT SIGTERM EXIT

# Create logs directory if it doesn't exist
mkdir -p logs

# Check if both servers are requested in foreground mode
if [ "$FOREGROUND" = true ] && [ "$START_API" = true ] && [ "$START_GUI" = true ]; then
    echo -e "${RED}Error: Cannot run both servers in foreground simultaneously.${NC}"
    echo -e "${YELLOW}Use: ./startup.sh -f --api  or  ./startup.sh -f --gui${NC}"
    echo -e "${YELLOW}Or run in background mode: ./startup.sh${NC}"
    exit 1
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
    echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"
    echo -e "${YELLOW}Or run in foreground mode: ./startup.sh -f --api  or  ./startup.sh -f --gui${NC}"
    wait
fi
