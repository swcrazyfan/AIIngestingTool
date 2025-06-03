#!/bin/bash

# Exit on error
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Define Prefect port
PREFECT_PORT=${PREFECT_PORT:-4201} # Use environment variable if set, otherwise default to 4201

# Function to check and kill processes on a port
check_and_clear_port() {
    local port=$1
    local service=$2
    local expected_patterns=("${@:3}")  # All arguments after port and service
    
    # Get PIDs using the port
    local pids=$(lsof -ti:$port 2>/dev/null)
    
    if [ -n "$pids" ]; then
        echo -e "${YELLOW}Port $port is in use. Checking process...${NC}"
        
        for pid in $pids; do
            # Get process info
            local process_info=$(ps -p $pid -o comm=,args= 2>/dev/null || echo "Unknown process")
            
            # Check if it's one of our expected processes
            local is_ours=false
            for pattern in "${expected_patterns[@]}"; do
                if echo "$process_info" | grep -q "$pattern"; then
                    is_ours=true
                    break
                fi
            done
            
            if $is_ours; then
                echo -e "${GREEN}  Found our $service process (PID: $pid). Killing it...${NC}"
                kill -9 $pid 2>/dev/null || true
            else
                echo -e "${RED}  WARNING: Port $port is used by an unrelated process:${NC}"
                echo -e "${RED}    PID: $pid${NC}"
                echo -e "${RED}    Process: $process_info${NC}"
                echo -e "${RED}  Please close this process manually or use a different port.${NC}"
                exit 1
            fi
        done
        
        # Wait a moment for port to be released
        sleep 1
    fi
}

# Clean up any existing processes on required ports
echo -e "${YELLOW}Checking for existing services...${NC}"

# Check port 8000 (API server) - look for our specific patterns
check_and_clear_port 8000 "API server" \
    "video_ingest_tool.api.server" \
    "python.*video_ingest_tool.*api.*server" \
    "api_server.py" \
    "api_server_new.py"

# Check port for Prefect services (server or worker if associated by lsof)
check_and_clear_port $PREFECT_PORT "Prefect service (server/worker)" \
    "prefect server" \
    "prefect.*server.*start" \
    "prefect worker.*video-processing-pool" # Pattern to catch workers if lsof links them to port

# Also kill any existing prefect worker processes (they don't use a specific port)
echo -e "${YELLOW}Checking for existing Prefect workers...${NC}"
worker_pids=$(pgrep -f "prefect worker.*video-processing-pool" 2>/dev/null || true)
if [ -n "$worker_pids" ]; then
    echo -e "${GREEN}  Found existing Prefect worker processes. Killing them...${NC}"
    echo "$worker_pids" | xargs kill -9 2>/dev/null || true
fi

echo -e "${GREEN}Services cleared, proceeding with startup...${NC}\n"

# Use the conda executable directly and activate the environment
export PATH="/opt/homebrew/Caskroom/miniforge/base/bin:$PATH"
source /opt/homebrew/Caskroom/miniforge/base/etc/profile.d/conda.sh
conda activate video-ingest

# Verify conda environment is active
echo -e "${GREEN}Active conda environment: $CONDA_DEFAULT_ENV${NC}"
if [ "$CONDA_DEFAULT_ENV" != "video-ingest" ]; then
    echo -e "${RED}Error: Failed to activate video-ingest conda environment${NC}"
    exit 1
fi

# Verify prefect is available
if ! command -v prefect &> /dev/null; then
    echo -e "${RED}Error: prefect command not found in video-ingest environment${NC}"
    exit 1
fi

echo -e "${GREEN}Prefect version: $(prefect version)${NC}"

# Set environment variables for Prefect
export PREFECT_API_DATABASE_CONNECTION_URL="sqlite+aiosqlite:///./data/prefect.db"
export PREFECT_API_URL="http://127.0.0.1:$PREFECT_PORT/api"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    
    # Kill API server
    if [ ! -z "$API_PID" ] && kill -0 $API_PID 2>/dev/null; then
        echo "Stopping API server (PID: $API_PID)..."
        kill -TERM $API_PID 2>/dev/null || true
        # Give it a moment to terminate gracefully
        sleep 1
        # Force kill if still running
        if kill -0 $API_PID 2>/dev/null; then
            echo "  Force killing API server..."
            kill -9 $API_PID 2>/dev/null || true
        fi
    fi
    
    # Kill worker
    if [ ! -z "$WORKER_PID" ] && kill -0 $WORKER_PID 2>/dev/null; then
        echo "Stopping Prefect worker (PID: $WORKER_PID)..."
        kill -TERM $WORKER_PID 2>/dev/null || true
        sleep 1
        if kill -0 $WORKER_PID 2>/dev/null; then
            echo "  Force killing Prefect worker..."
            kill -9 $WORKER_PID 2>/dev/null || true
        fi
    fi
    
    # Kill Prefect server
    if [ ! -z "$SERVER_PID" ] && kill -0 $SERVER_PID 2>/dev/null; then
        echo "Stopping Prefect server (PID: $SERVER_PID)..."
        kill -TERM $SERVER_PID 2>/dev/null || true
        sleep 1
        if kill -0 $SERVER_PID 2>/dev/null; then
            echo "  Force killing Prefect server..."
            kill -9 $SERVER_PID 2>/dev/null || true
        fi
    fi
    
    # Also clean up any orphaned processes
    echo "Checking for orphaned processes..."
    pkill -f "video_ingest_tool.api.server" 2>/dev/null || true
    pkill -f "prefect worker.*video-processing-pool" 2>/dev/null || true
    
    echo -e "${GREEN}All services stopped.${NC}"
    
    # Exit with appropriate code
    if [ "${1:-0}" != "0" ]; then
        exit ${1:-1}
    fi
}

# Set up cleanup on script exit
trap 'cleanup 130' INT     # Ctrl+C returns 130
trap 'cleanup 143' TERM    # SIGTERM returns 143  
trap 'cleanup' EXIT        # Normal exit

# Create log directory if it doesn't exist
mkdir -p logs

# Start the Prefect server in the background
echo -e "${YELLOW}Starting Prefect server on port $PREFECT_PORT...${NC}"
conda run -n video-ingest prefect server start --port $PREFECT_PORT > logs/prefect_server.log 2>&1 &
SERVER_PID=$!

# Wait for the server to be ready by checking the health endpoint
echo "Checking server health at http://127.0.0.1:$PREFECT_PORT/api/health..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s http://127.0.0.1:$PREFECT_PORT/api/health >/dev/null 2>&1; then
        echo -e "${GREEN}Prefect server is ready!${NC}"
        break
    fi
    echo "Attempt $((attempt + 1))/$max_attempts - Server not ready yet..."
    sleep 2
    attempt=$((attempt + 1))
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}Error: Server failed to start within expected time${NC}"
    exit 1
fi

# Create concurrency limits (Needs Prefect Server to be up)
echo -e "${YELLOW}Creating concurrency limits...${NC}"
conda run -n video-ingest prefect concurrency-limit create video_compression_step 2 2>/dev/null || echo "  video_compression_step limit already exists"
conda run -n video-ingest prefect concurrency-limit create ai_analysis_step 1 2>/dev/null || echo "  ai_analysis_step limit already exists"
conda run -n video-ingest prefect concurrency-limit create transcription_step 2 2>/dev/null || echo "  transcription_step limit already exists"
conda run -n video-ingest prefect concurrency-limit create embedding_step 1 2>/dev/null || echo "  embedding_step limit already exists"
echo -e "${GREEN}Concurrency limits created or verified.${NC}"

# Start the Prefect worker (Needs Prefect Server to be up)
echo -e "${YELLOW}Starting Prefect worker...${NC}"
conda run -n video-ingest prefect worker start --pool video-processing-pool --type process > logs/prefect_worker.log 2>&1 &
WORKER_PID=$!

# Start the API server (Needs Prefect Server to be up for its internal operations)
# This can be started now that Prefect server is confirmed healthy,
# concurrency limits are set, and worker is starting.
# Running in FOREGROUND for direct terminal output, and logging to file.
echo -e "${YELLOW}Starting API server in FOREGROUND (and logging to file) with DEBUG MODE...${NC}"
conda run --no-capture-output -n video-ingest python -m video_ingest_tool.api.server --port 8000 --debug 2>&1 | tee logs/api_server.log

# The script will now block here until the API server (python command above) exits or is interrupted.
# When Ctrl+C is pressed, the INT trap will execute the cleanup function.

# Health checks for API server are not strictly needed here if it's foreground,
# as failure to start would be obvious. But keeping them doesn't hurt if they were after backgrounding.
# The main point is the script now waits on the python process.

# All echo statements about PIDs and 'All services started' might be misleading
# if they print before the foreground API server actually shows its own "started" messages.
# Consider moving them into the cleanup or just noting that Ctrl+C is the way to stop.

echo -e "${GREEN}API server is running in the foreground. Press Ctrl+C to stop all services.${NC}"

# No explicit 'wait' command is needed here because the python script (API server)
# is running in the foreground. The shell script will wait for it to complete.
# The traps for INT, TERM, EXIT will handle cleanup.

# The original echos about PIDs and "All services started" might be less relevant now,
# or should be rephrased as the script is now "managing an interactive session".
# For instance, API_PID is not set in a way the current cleanup function can use if it's foreground.
# The cleanup will rely on pkill for the API server if it's foreground.
# Let's adjust cleanup for this.
