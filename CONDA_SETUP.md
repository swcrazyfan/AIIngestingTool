# Conda Setup Guide for AI-Powered Video Ingest & Catalog Tool

This document provides steps to create and set up a Conda environment for running the AI-Powered Video Ingest & Catalog Tool.

## 1. Install Miniconda (if you don't have it already)

Download and install Miniconda from: https://docs.conda.io/en/latest/miniconda.html

## 2. Create a New Conda Environment

```bash
# Create a new environment named 'video-ingest' with Python 3.11 (or your preferred version)
# You can use Python 3.9, 3.10, 3.11, or 3.12
conda create -n video-ingest python=3.11

# Activate the environment
conda activate video-ingest
```

## 3. Install Dependencies

```bash
# Install conda packages
conda install -c conda-forge ffmpeg exiftool av libmagic

# Install pip requirements
pip install -r requirements.txt

# Note: If you're on Windows, you may need additional steps for python-magic:
# See: https://github.com/ahupp/python-magic#installation
```

## 4. Verify Installation

Verify that ffmpeg and exiftool are installed correctly:

```bash
# Check ffmpeg
ffmpeg -version

# Check exiftool
exiftool -ver
```

## 5. Run the Tool

With the conda environment activated, run the tool:

```bash
# Basic usage
python video_ingestor.py /path/to/your/videos

# With options
python video_ingestor.py /path/to/your/videos --output-dir my_output --limit 5
```

## 6. Troubleshooting

### Common Issues

1. **FFmpeg not found**: Ensure it's installed in your conda environment or system PATH.
   
2. **ExifTool not found**: Check your installation or download directly from the ExifTool website.
   
3. **Missing dependencies**: Try installing individual packages if they fail during bulk installation:
   ```bash
   pip install package-name
   ```

4. **Permissions issues**: Ensure you have read permissions for the video files and write permissions for the output directory.

5. **Python-magic issues**: On Windows, you may need to install additional dependencies for python-magic:
   - Follow instructions at: https://github.com/ahupp/python-magic#installation

## 7. Deactivating the Environment

When you're finished, deactivate the conda environment:

```bash
conda deactivate
```
