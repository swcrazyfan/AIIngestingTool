#!/bin/bash
# Check required dependencies and provide helpful messages

echo "=== AI-Powered Video Ingest & Catalog Tool - Dependency Check ==="
echo ""

# Check Python version
python_version=$(python --version 2>&1)
echo "Python version: $python_version"
if [[ $python_version != *"Python 3."* ]]; then
    echo "⚠️  Warning: Python 3.x is required."
fi

# Check FFmpeg
if command -v ffmpeg &> /dev/null; then
    ffmpeg_version=$(ffmpeg -version | head -n 1)
    echo "FFmpeg: $ffmpeg_version"
else
    echo "❌ FFmpeg not found! Please install FFmpeg."
    echo "   Visit: https://ffmpeg.org/download.html"
fi

# Check ExifTool
if command -v exiftool &> /dev/null; then
    exiftool_version=$(exiftool -ver)
    echo "ExifTool: v$exiftool_version"
else
    echo "❌ ExifTool not found! Please install ExifTool."
    echo "   Visit: https://exiftool.org/"
fi

# Check required Python packages
echo ""
echo "Checking Python packages..."
pip_modules=$(pip list)

required_packages=("ffmpeg-python" "pymediainfo" "PyExifTool" "opencv-python" "typer" "rich" "pydantic" "structlog" "numpy" "pillow" "python-magic")

for package in "${required_packages[@]}"; do
    if echo "$pip_modules" | grep -q "$package"; then
        echo "✅ $package"
    else
        echo "❌ $package not found. Please install it with: pip install $package"
    fi
done

echo ""
echo "If all checks pass, you can run the tool with:"
echo "python video_ingestor.py /path/to/videos"
echo ""
echo "For detailed setup instructions, see CONDA_SETUP.md"
