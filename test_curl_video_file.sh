#!/bin/bash

echo "=== Testing Video Processing with Direct Curl (File Method) ==="

# Load environment variables
source .env 2>/dev/null || true

# Get video model and API key from environment
VIDEO_MODEL=${VIDEO_MODEL:-"gemini-2.0-flash"}
API_KEY=${GEMINI_API_KEY}

if [ -z "$API_KEY" ]; then
    echo "ERROR: GEMINI_API_KEY not found in environment"
    exit 1
fi

echo "Using API Key: ${API_KEY:0:10}...${API_KEY: -4}"
echo "Using Model: $VIDEO_MODEL"

# Set video path
VIDEO_PATH="/Users/developer/Development/GitHub/AIIngestingTool/data/clips/PANA0068_f6d2207a-b152-4cdc-90dc-b6527f72cedd/compressed/PANA0068_compressed.mp4"

if [ ! -f "$VIDEO_PATH" ]; then
    echo "ERROR: Video file not found at $VIDEO_PATH"
    exit 1
fi

echo "Video file: $VIDEO_PATH"
echo "Video size: $(du -h "$VIDEO_PATH" | cut -f1)"

# Detect base64 flags
if [[ "$(base64 --version 2>&1)" = *"FreeBSD"* ]]; then
  B64FLAGS="--input"
else
  B64FLAGS="-w0"
fi

echo "Base64 flags: $B64FLAGS"
echo ""
echo "Encoding video to base64..."

# Create temporary file for the JSON payload
TEMP_JSON=$(mktemp /tmp/video_request.XXXXXX.json)
VIDEO_B64=$(base64 $B64FLAGS "$VIDEO_PATH")

echo "Creating JSON payload in temporary file..."

# Create the JSON payload
cat > "$TEMP_JSON" << EOF
{
  "contents": [{
    "parts":[
        {
          "inline_data": {
            "mime_type":"video/mp4",
            "data": "$VIDEO_B64"
          }
        },
        {"text": "Please summarize the video in 3 sentences."}
    ]
  }]
}
EOF

echo "JSON payload created: $TEMP_JSON"
echo "Payload size: $(du -h "$TEMP_JSON" | cut -f1)"
echo ""

# Make the curl request
echo "Making curl request to Google API..."
echo ""

curl_response=$(curl -w "\nHTTP_STATUS_CODE:%{http_code}\nTIME_TOTAL:%{time_total}s\n" \
    "https://generativelanguage.googleapis.com/v1beta/models/$VIDEO_MODEL:generateContent?key=$API_KEY" \
    -H 'Content-Type: application/json' \
    -X POST \
    -d @"$TEMP_JSON" 2>&1)

echo "=== CURL RESPONSE ==="
echo "$curl_response"
echo ""

# Extract status code from response
status_code=$(echo "$curl_response" | grep "HTTP_STATUS_CODE:" | cut -d: -f2)
time_total=$(echo "$curl_response" | grep "TIME_TOTAL:" | cut -d: -f2)

echo "=== RESPONSE ANALYSIS ==="
echo "HTTP Status Code: $status_code"
echo "Total Time: $time_total"

if [ "$status_code" = "200" ]; then
    echo "✅ SUCCESS: Video processing worked!"
elif [ "$status_code" = "500" ]; then
    echo "❌ FAILED: 500 Internal Server Error (same as Python SDK)"
elif [ "$status_code" = "400" ]; then
    echo "❌ FAILED: 400 Bad Request"
else
    echo "❌ FAILED: HTTP $status_code"
fi

# Try to extract and pretty print JSON response
echo ""
echo "=== JSON RESPONSE (if any) ==="
response_json=$(echo "$curl_response" | grep -v "HTTP_STATUS_CODE:" | grep -v "TIME_TOTAL:")
if command -v jq >/dev/null 2>&1; then
    echo "$response_json" | jq . 2>/dev/null || echo "$response_json"
else
    echo "$response_json"
fi

# Clean up temporary file
echo ""
echo "Cleaning up temporary file: $TEMP_JSON"
rm -f "$TEMP_JSON" 