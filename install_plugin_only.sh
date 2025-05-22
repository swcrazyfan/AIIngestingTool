#!/bin/bash

# AI Video Ingest Tool - Plugin Installation Only
# This script only installs the Premiere Pro panel (no Python setup)

echo "🎬 AI Video Ingest Tool - Plugin Installation"
echo "============================================="

# Check if we're in the right directory
if [ ! -f "api_server.py" ]; then
    echo "❌ Error: Please run this script from the AIIngestingTool directory"
    echo "   Expected: /Users/developer/Development/GitHub/AIIngestingTool"
    exit 1
fi

echo "📋 Current directory: $(pwd)"

# Step 1: Download required CEP libraries if missing
echo ""
echo "📚 Checking CEP libraries..."
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

# Step 2: Enable CEP Debug Mode
echo ""
echo "🔧 Enabling CEP Debug Mode..."
defaults write com.adobe.CSXS.11 PlayerDebugMode 1
defaults write com.adobe.CSXS.12 PlayerDebugMode 1
defaults write com.adobe.CSXS.12 LogLevel 6
echo "  ✅ Debug mode enabled for CEP versions 11-12"

# Step 3: Install the panel
echo ""
echo "🔗 Installing CEP panel..."

PANEL_SOURCE="$(pwd)/premiere_pro_panel"
PANEL_DEST="/Library/Application Support/Adobe/CEP/extensions/AIVideoIngestTool"
USER_PANEL_DEST="$HOME/Library/Application Support/Adobe/CEP/extensions/AIVideoIngestTool"

# Remove existing installations first
echo "  🧹 Cleaning up existing installations..."
sudo rm -rf "$PANEL_DEST" 2>/dev/null
rm -rf "$USER_PANEL_DEST" 2>/dev/null

# Try system-wide installation first
if sudo mkdir -p "/Library/Application Support/Adobe/CEP/extensions" 2>/dev/null && sudo ln -sf "$PANEL_SOURCE" "$PANEL_DEST" 2>/dev/null; then
    echo "  ✅ Panel installed system-wide: $PANEL_DEST"
    # Fix permissions for system install
    sudo chmod -R 755 "$PANEL_DEST"
else
    # Fall back to user installation
    echo "  📝 System installation failed, trying user installation..."
    mkdir -p "$HOME/Library/Application Support/Adobe/CEP/extensions"
    ln -sf "$PANEL_SOURCE" "$USER_PANEL_DEST"
    echo "  ✅ Panel installed for current user: $USER_PANEL_DEST"
fi

# Step 4: Clear CEP cache to ensure fresh load
echo ""
echo "🧹 Clearing CEP cache..."
rm -rf ~/Library/Caches/Adobe/CEP* 2>/dev/null
echo "  ✅ CEP cache cleared"

# Step 5: Verify installation
echo ""
echo "🔍 Verifying installation..."
if [ -L "$PANEL_DEST" ] || [ -L "$USER_PANEL_DEST" ]; then
    echo "  ✅ Plugin symlink created successfully"
    
    # Check if the target files exist
    if [ -f "$PANEL_SOURCE/index.html" ]; then
        echo "  ✅ Plugin files are accessible"
    else
        echo "  ⚠️  Warning: Plugin files may not be accessible"
    fi
else
    echo "  ❌ Plugin installation may have failed"
fi

# Final instructions
echo ""
echo "🎉 Plugin Installation Complete!"
echo "================================"
echo ""
echo "Next steps:"
echo "1. 🎬 Open Premiere Pro 2025"
echo ""
echo "2. 📱 Open the panel:"
echo "   Window → Extensions → AI Video Ingest Tool"
echo ""
echo "3. 🚀 Start your API server (in your conda env):"
echo "   python api_server.py"
echo ""
echo "4. ✅ Verify the connection status shows 'Connected' in the panel"
echo ""
echo "🔧 If panel doesn't appear:"
echo "• Restart Premiere Pro completely"
echo "• Check: defaults read com.adobe.CSXS.12 PlayerDebugMode"
echo "• Should return: 1"
echo ""
echo "🎯 Plugin ready for use!"
