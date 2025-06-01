# AI Video Ingest Tool - Adobe Premiere Pro Extension

A powerful Adobe CEP extension that integrates with the AI Video Ingest Tool API to provide advanced video management capabilities directly within Premiere Pro.

## Features

- **Local DuckDB Integration**: Works directly with local DuckDB database (no authentication required)
- **Video Library**: Browse and search your processed videos
- **Advanced Search**: 
  - Hybrid search combining semantic and full-text
  - Semantic search using AI embeddings
  - Full-text search through metadata
  - Transcript search
- **Find Similar**: Discover videos similar to any clip
- **Direct Integration**: 
  - Add videos to timeline at playhead position
  - Reveal files in Finder
- **Video Processing**: 
  - Select directories for batch processing
  - Configure AI analysis options
  - Real-time progress monitoring
  - Process videos with metadata extraction

## Development

### Prerequisites

- Node.js 16+
- Yarn
- Adobe Premiere Pro 2020 or later
- Python API server running on http://localhost:8001

### Installation

1. Install dependencies:
```bash
yarn install
```

2. Build the extension:
```bash
yarn build
```

3. Start development mode:
```bash
yarn dev
```

### API Server

The extension requires the Python API server to be running:

```bash
cd /Users/developer/Development/GitHub/AIIngestingTool
conda activate video-ingest
python -m video_ingest_tool.api.server --port 8001
```

**Note**: Authentication has been completely removed. The extension now works directly with a local DuckDB database without requiring user accounts, login, or internet connectivity for core functionality.

### Scripts

- `yarn dev` - Start development with hot reload
- `yarn build` - Build for production
- `yarn zxp` - Package as ZXP for distribution
- `yarn serve` - Serve built files

## Architecture

- **React 18** with TypeScript
- **Axios** for API communication
- **React Query** for data fetching
- **SCSS** for styling
- **ExtendScript** for Premiere Pro integration
- **Local DuckDB**: Uses DuckDB for local data storage (no cloud/remote database required)

## Configuration

Edit `cep.config.ts` to modify:
- Extension ID and name
- Panel dimensions
- Host application versions
- Debug settings

## API Endpoints

The extension communicates with these local API endpoints:

- `GET /api/health` - Health check
- `GET /api/clips` - List videos with filtering and pagination
- `GET /api/clips/{id}` - Get detailed video information
- `GET /api/search` - Search videos by query
- `GET /api/search/similar` - Find similar videos
- `POST /api/ingest` - Start video processing
- `GET /api/progress` - Get processing progress
- `GET /api/thumbnail/{id}` - Get video thumbnails

## Guest Mode

The extension supports a "Guest Mode" for demonstrations:
- Read-only access to the interface
- Limited functionality
- No video processing capabilities
- Useful for showcasing features without a full setup

## License

MIT
