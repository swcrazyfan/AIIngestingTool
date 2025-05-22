# Adobe Premiere Pro Integration Setup
## AI Video Ingest Tool - Complete Installation Guide

This guide will help you set up the AI Video Ingest Tool as a native Premiere Pro panel on macOS.

## 📋 Prerequisites

- **Adobe Premiere Pro 2020 or later**
- **Python 3.9+** with your video ingest tool installed
- **macOS** (this guide is specifically for Mac)

## 🔧 Step 1: Install Python Dependencies

First, install the additional dependencies needed for the HTTP API:

```bash
cd /Users/developer/Development/GitHub/AIIngestingTool
pip install flask flask-cors
```

## 🔧 Step 2: Download Required Libraries

You need to download the CEP interface libraries:

### CSInterface.js
```bash
cd /Users/developer/Development/GitHub/AIIngestingTool/premiere_pro_panel/js/lib
curl -o CSInterface.js https://raw.githubusercontent.com/Adobe-CEP/CEP-Resources/master/CEP_9.x/CSInterface.js
```

### jQuery (Optional but recommended)
```bash
curl -o jquery-3.6.0.min.js https://code.jquery.com/jquery-3.6.0.min.js
```

## 🔧 Step 3: Enable CEP Debug Mode

Adobe Premiere Pro needs to be in debug mode to load unsigned extensions:

```bash
# Enable debug mode for various CEP versions
defaults write com.adobe.CSXS.9 PlayerDebugMode 1
defaults write com.adobe.CSXS.10 PlayerDebugMode 1
defaults write com.adobe.CSXS.11 PlayerDebugMode 1
defaults write com.adobe.CSXS.12 PlayerDebugMode 1
```

## 🔧 Step 4: Install the CEP Panel

Create a symbolic link to install the panel:

```bash
# Create the CEP extensions directory if it doesn't exist
sudo mkdir -p "/Library/Application Support/Adobe/CEP/extensions"

# Create symbolic link to your panel
sudo ln -sf "/Users/developer/Development/GitHub/AIIngestingTool/premiere_pro_panel" "/Library/Application Support/Adobe/CEP/extensions/AIVideoIngestTool"
```

**Alternative (User-level installation):**
```bash
# User-level installation (doesn't require sudo)
mkdir -p ~/Library/Application\ Support/Adobe/CEP/extensions
ln -sf "/Users/developer/Development/GitHub/AIIngestingTool/premiere_pro_panel" ~/Library/Application\ Support/Adobe/CEP/extensions/AIVideoIngestTool
```

## 🚀 Step 5: Start the API Server

The panel needs the Python API server running:

```bash
cd /Users/developer/Development/GitHub/AIIngestingTool
python api_server.py
```

You should see:
```
🚀 Starting Video Ingest API Server...
📡 CEP Panel can connect to: http://localhost:8000
🔍 Health check: http://localhost:8000/api/health
✅ Backend modules loaded successfully
⚡ Ready for Adobe Premiere Pro CEP panel!
```

## 🎬 Step 6: Launch Premiere Pro

1. **Start Adobe Premiere Pro**
2. **Open the Panel:**
   - Go to **Window** → **Extensions** → **AI Video Ingest Tool**
   - The panel should appear on the right side

3. **Verify Connection:**
   - Look for "Connected" status in the panel header
   - If it shows "API Offline", make sure the Python server is running

## 🎯 Using the Panel

### Basic Workflow:

1. **Select Directory**: Click "Choose Video Directory" to select a folder containing videos
2. **Configure Options**: 
   - ✅ Recursive Scan (include subfolders)
   - ✅ AI Analysis (comprehensive video analysis)
   - ✅ Generate Embeddings (for semantic search)
   - ✅ Store in Database (requires Supabase setup)
3. **Start Processing**: Click "Start Processing" and watch the progress
4. **Search Videos**: Use the search box to find specific content
5. **Add to Timeline**: Click "Timeline" to add videos directly to your sequence

### Panel Actions:

- **➕ Timeline**: Adds video to current timeline position
- **📁 Import**: Imports video to project panel only  
- **👁️ Reveal**: Opens file location in Finder

## 🔧 Troubleshooting

### Panel Not Showing
```bash
# Check if debug mode is enabled
defaults read com.adobe.CSXS.9 PlayerDebugMode
defaults read com.adobe.CSXS.10 PlayerDebugMode

# Re-enable if needed
defaults write com.adobe.CSXS.9 PlayerDebugMode 1
defaults write com.adobe.CSXS.10 PlayerDebugMode 1

# Restart Premiere Pro
```

### API Connection Issues
```bash
# Check if server is running
curl http://localhost:8000/api/health

# If not responding, restart the server
cd /Users/developer/Development/GitHub/AIIngestingTool
python api_server.py
```

### Panel Shows "API Offline"
1. Make sure `api_server.py` is running
2. Check that port 8000 isn't blocked by firewall
3. Restart both the server and Premiere Pro

### Import/Timeline Errors
1. Make sure you have an active sequence for timeline operations
2. Check that video files are accessible and not corrupted
3. Verify file paths are correct (shown in panel)

## 🛠 Development and Debugging

### View Panel Console
1. Right-click in the panel → **Inspect**
2. This opens Chrome DevTools for debugging
3. Check Console tab for JavaScript errors

### Server Logs
The Python server shows detailed logs in the terminal where you started it.

### Panel Structure
```
premiere_pro_panel/
├── CSXS/
│   └── manifest.xml          # Panel configuration
├── css/
│   └── styles.css           # Panel styling
├── js/
│   ├── lib/
│   │   ├── CSInterface.js   # Adobe CEP library
│   │   └── jquery.min.js    # jQuery (optional)
│   └── main.js              # Main panel logic
├── jsx/
│   └── main.jsx             # ExtendScript for Premiere Pro
└── index.html               # Panel HTML structure
```

## 🎨 Customization

### Change Panel Size
Edit `CSXS/manifest.xml`:
```xml
<Geometry>
    <Size>
        <Height>800</Height>  <!-- Adjust height -->
        <Width>500</Width>    <!-- Adjust width -->
    </Size>
</Geometry>
```

### Add More Search Options
Edit `js/main.js` to add custom search types or filters.

### Modify Panel Appearance  
Edit `css/styles.css` to change colors, layout, or styling.

## 🚀 Advanced Features

### Database Integration
If you have Supabase configured:
1. Enable "Store in Database" option
2. Use "Generate Embeddings" for semantic search
3. Search across all processed videos

### Batch Processing
The panel can process entire directory trees with thousands of videos.

### AI Analysis
Enable AI Analysis to get:
- Full transcriptions
- Content summaries  
- Activity detection
- Technical quality assessment
- Automatic tagging

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Look at browser console (right-click panel → Inspect)
3. Check Python server logs in terminal
4. Verify all prerequisites are installed

The panel integrates seamlessly with your existing Python backend, giving you a professional video management interface directly inside Premiere Pro!