# AI-Powered Video Ingest & Catalog Tool

A comprehensive CLI solution for video ingestion, metadata extraction, and cataloging.

## Features

- Content Discovery: Scan directories for video files and create checksums
- Technical Metadata Extraction: Extract detailed information from video files
- Thumbnail Generation: Create thumbnails from videos
- Computer Vision Analysis: Analyze exposure and visual quality
- Task Queue System: Asynchronous processing with Procrastinate and PostgreSQL

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd AIIngestingTool
```

2. Install dependencies:
```bash
pip install -r video_ingest_tool/requirements.txt
```

If you encounter issues with specific dependencies, you can install them individually as needed.

## Database Setup (for Queue Mode)

1. Make sure PostgreSQL is running and accessible
2. Create the database:
```bash
createdb videoingestor
```

3. Apply the schema:
```bash
python -m video_ingest_tool schema
```

4. Check database connection:
```bash
python -m video_ingest_tool db-status
```

## Usage

### Process Videos Directly

Process videos without using the task queue:

```bash
python -m video_ingest_tool ingest /path/to/videos
```

Options:
- `--no-recursive`: Don't scan subdirectories
- `--output-dir=DIR`: Specify output directory (default: 'output')
- `--limit=N`: Process only N files (default: 0 = unlimited)

### Process Videos with Task Queue

Queue videos for processing:

```bash
python -m video_ingest_tool ingest /path/to/videos --queue
```

Then start a worker to process the queued videos:

```bash
python -m video_ingest_tool worker
```

Worker options:
- `--queue=NAME`: Process specific queue (can be specified multiple times)
- `--concurrency=N`: Number of concurrent jobs (default: 1)

### Database Management

Initialize or update the database schema:

```bash
python -m video_ingest_tool schema
```

Check database connection status:

```bash
python -m video_ingest_tool db-status
```

## Output

The tool generates:
- JSON metadata files in the `json_output` directory
- Thumbnails in the `output/thumbnails` directory
- Logs in the `logs` directory

## License

Copyright © 2025
