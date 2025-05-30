# AI Video Ingest Tool - Adobe Premiere Pro Extension

A powerful Adobe CEP extension that integrates with the AI Video Ingest Tool API to provide advanced video management capabilities directly within Premiere Pro.

## Features

- **Authentication**: Secure login to access your video library
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
- Python API server running on http://localhost:8000

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
python api_server.py
```

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

## Configuration

Edit `cep.config.ts` to modify:
- Extension ID and name
- Panel dimensions
- Host application versions
- Debug settings

## License

MIT
