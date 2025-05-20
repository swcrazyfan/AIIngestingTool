# AI-Powered Video Ingest & Catalog Tool - Alpha Test

This is an alpha version of the AI-Powered Video Ingest & Catalog Tool, which automates the analysis, categorization, and retrieval of video content at scale. This initial version focuses on the first two steps of the workflow:

1. **Content Discovery Phase** - Scanning directories for video files and creating checksums for deduplication
2. **Technical Metadata Extraction** - Extracting detailed technical information from video files

## Features Implemented

- Directory scanning with recursive option
- Video file identification
- Checksum generation for deduplication
- Technical metadata extraction using various tools:
  - MediaInfo (via pymediainfo)
  - FFmpeg (via PyAV)
  - ExifTool
- Thumbnail generation at specified intervals
- Basic exposure analysis
- Shot type estimation
- Quality score calculation
- Rich terminal output with progress tracking
- Comprehensive logging to timestamped files
- JSON output for each processed file and summary

## Requirements

- Python 3.9+ (3.10, 3.11, and 3.12 are fully supported)
- FFmpeg installed and available in PATH
- ExifTool installed and available in PATH
- Required Python packages (see requirements.txt)

## Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd AIIngestingTool
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Ensure FFmpeg and ExifTool are installed:
   - **FFmpeg**: [Download from ffmpeg.org](https://ffmpeg.org/download.html)
   - **ExifTool**: [Download from exiftool.org](https://exiftool.org/)

## Usage

Run the tool with a directory containing video files:

```
python video_ingestor.py /path/to/videos
```

### Options

- `--recursive/--no-recursive` (`-r/-nr`): Scan subdirectories (default: True)
- `--output-dir` (`-o`): Output directory for thumbnails and JSON (default: "output")
- `--limit` (`-l`): Limit number of files to process (0 = no limit)

### Example

```
python video_ingestor.py /path/to/videos --output-dir my_output --limit 5
```

## Output

The tool creates the following outputs:

- **logs/**: Directory containing timestamped log files
- **json_output/**: Directory containing JSON files with extracted metadata
  - Individual JSON file for each video
  - Summary JSON file with all processed videos
- **output/thumbnails/**: Generated thumbnail images, organized by video checksum

## Alpha Test Notes

This is an alpha version focusing on core functionality:
- No database integration yet
- No task queuing system
- All operations are logged to terminal and files
- All data is stored as JSON files

## Next Steps

Future versions will incorporate:
1. Task queuing system (Procrastinate)
2. Database integration (Supabase)
3. Multimodal AI analysis (Gemini Flash 2.0)
4. Vector embeddings for semantic search
5. Full CLI command suite
