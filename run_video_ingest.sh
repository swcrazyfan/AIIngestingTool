#!/bin/bash
# Run the video ingest tool as a module

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Check if args are provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 /path/to/videos [options]"
    echo "Example: $0 /path/to/videos --limit 5"
    exit 1
fi

# Run the module
python -m video_ingest_tool "$@"
