#!/bin/bash

# AI Video Ingest Tool - Quick Setup Script for macOS
# This script helps set up the Premiere Pro panel quickly

echo "🎬 AI Video Ingest Tool - Premiere Pro Panel Setup"
echo "================================================="

# Check if we're in the right directory
if [ ! -f "api_server.py" ]; then
    echo "❌ Error: Please run this script from the AIIngestingTool directory"
    echo "   Expected: /Users/developer/Development/GitHub/AIIngestingTool"
    exit 1
fi

echo "📋 Current directory: $(pwd)"

# Step 1: Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip install flask flask-cors

# Step 2: Download required libraries
echo ""
echo "📚 Downloading CEP libraries..."
cd premiere_pro_panel/js/lib

# Download CSInterface.js
if [ ! -f "CSInterface.js" ]; then
    echo "  Downloading CSInterface.js..."
    curl -s -o CSInterface.js https://raw.githubusercontent.com/Adobe-CEP/CEP-Resources/master/CEP_12.x/CSInterface.js
    echo "  ✅ CSInterface.js downloaded"
else
    echo "  ✅ CSInterface.js already exists"
fi

# Download jQuery
if [ ! -f "jquery-3.6.0.min.js" ]; then
    echo "  Downloading jQuery..."
    curl -s -o jquery-3.6.0.min.js https://code.jquery.com/jquery-3.6.0.min.js
    echo "  ✅ jQuery downloaded"
else
    echo "  ✅ jQuery already exists"
fi

cd ../../..

# Step 3: Enable CEP Debug Mode
echo ""
echo "🔧 Enabling CEP Debug Mode..."
defaults write com.adobe.CSXS.11 PlayerDebugMode 1
defaults write com.adobe.CSXS.12 PlayerDebugMode 1
echo "  ✅ Debug mode enabled for CEP versions 11-12"

# Step 4: Install the panel
echo ""
echo "🔗 Installing CEP panel..."

PANEL_SOURCE="$(pwd)/premiere_pro_panel"
PANEL_DEST="/Library/Application Support/Adobe/CEP/extensions/AIVideoIngestTool"
USER_PANEL_DEST="$HOME/Library/Application Support/Adobe/CEP/extensions/AIVideoIngestTool"

# Try system-wide installation first
if sudo mkdir -p "/Library/Application Support/Adobe/CEP/extensions" 2>/dev/null && sudo ln -sf "$PANEL_SOURCE" "$PANEL_DEST" 2>/dev/null; then
    echo "  ✅ Panel installed system-wide: $PANEL_DEST"
else
    # Fall back to user installation
    echo "  📝 System installation failed, trying user installation..."
    mkdir -p "$HOME/Library/Application Support/Adobe/CEP/extensions"
    ln -sf "$PANEL_SOURCE" "$USER_PANEL_DEST"
    echo "  ✅ Panel installed for current user: $USER_PANEL_DEST"
fi

# Step 5: Test API server
echo ""
echo "🧪 Testing API server..."
python -c "
try:
    import sys
    sys.path.insert(0, '.')
    from video_ingest_tool.config import setup_logging
    print('  ✅ Backend modules are accessible')
except ImportError as e:
    print(f'  ⚠️  Backend import issue: {e}')
    print('     The panel will still work with limited functionality')
"

# Final instructions
echo ""
echo "🎉 Setup Complete!"
echo "=================="
echo ""
echo "Next steps:"
echo "1. 🚀 Start the API server:"
echo "   python api_server.py"
echo ""
echo "2. 🎬 Open Premiere Pro"
echo ""
echo "3. 📱 Open the panel:"
echo "   Window → Extensions → AI Video Ingest Tool"
echo ""
echo "4. ✅ Verify the connection status shows 'Connected'"
echo ""
echo "🔧 Troubleshooting:"
echo "• If panel doesn't appear, restart Premiere Pro"  
echo "• If API shows offline, make sure api_server.py is running"
echo "• Check INSTALLATION.md for detailed troubleshooting"
echo ""
echo "🎯 Ready to process videos directly in Premiere Pro!"
