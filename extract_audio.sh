#!/bin/bash

# Configuration
INPUT_VIDEO="/Users/developer/Development/GitHub/AIIngestingTool/Wizard/PANA0061.MP4"
OUTPUT_AUDIO="/Users/developer/Development/GitHub/AIIngestingTool/Wizard/PANA0061_audio_32kbps.wav"

# Check if input file exists
if [ ! -f "$INPUT_VIDEO" ]; then
    echo "Error: Input video file not found: $INPUT_VIDEO"
    exit 1
fi

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "Error: ffmpeg is not installed. Please install it first:"
    echo "  macOS: brew install ffmpeg"
    echo "  Ubuntu/Debian: sudo apt install ffmpeg"
    echo "  Windows: Download from https://ffmpeg.org/download.html"
    exit 1
fi

echo "Extracting audio from: $INPUT_VIDEO"
echo "Output file: $OUTPUT_AUDIO"
echo "Target bitrate: 32kbps"
echo ""

# Extract audio and compress to 32kbps WAV
# -i: input file
# -vn: disable video (audio only)
# -acodec pcm_s16le: use PCM 16-bit little-endian codec for WAV
# -ar 22050: set sample rate to 22.05kHz (suitable for 32kbps)
# -ac 1: mono audio (helps achieve lower bitrate)
# -ab 32k: set audio bitrate to 32kbps
# -y: overwrite output file if it exists

ffmpeg -i "$INPUT_VIDEO" \
       -vn \
       -acodec pcm_s16le \
       -ar 22050 \
       -ac 1 \
       -ab 32k \
       -y \
       "$OUTPUT_AUDIO"

# Check if the conversion was successful
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Audio extraction completed successfully!"
    echo "📁 Output file: $OUTPUT_AUDIO"
    
    # Display file information
    if command -v ffprobe &> /dev/null; then
        echo ""
        echo "📊 Audio file information:"
        ffprobe -v quiet -print_format compact=print_section=0:nokey=1:escape=csv -show_entries stream=duration,bit_rate,sample_rate,channels "$OUTPUT_AUDIO"
    fi
    
    # Display file size
    if command -v du &> /dev/null; then
        echo "📏 File size: $(du -h "$OUTPUT_AUDIO" | cut -f1)"
    fi
    
else
    echo ""
    echo "❌ Audio extraction failed!"
    exit 1
fi
