#!/bin/bash

# Set environment variables for Prefect
export PREFECT_API_DATABASE_CONNECTION_URL="sqlite+aiosqlite:///./data/prefect.db"
export PREFECT_API_URL="http://127.0.0.1:4200/api"

# Start the Prefect server in the background
prefect server start &
SERVER_PID=$!

# Wait a few seconds to ensure the server is up
sleep 5

# Set concurrency limits (adjust tags and limits as needed)

prefect concurrency-limit create video_compression_step 2 || true
prefect concurrency-limit create ai_video_analysis_step 10 || true
prefect concurrency-limit create analyze_exposure_step 5 || true
prefect concurrency-limit create detect_focal_length_step 5 || true
# Add more as needed...

# Start the Prefect worker in the background
prefect worker start --pool my-pool &
WORKER_PID=$!

# Trap SIGINT and SIGTERM to kill both processes
trap "echo 'Stopping Prefect server and worker...'; kill $SERVER_PID $WORKER_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# Wait for both processes to finish
wait $SERVER_PID $WORKER_PID