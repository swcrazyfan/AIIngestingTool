"""
Video compression step for the video ingest tool.

Registered as a step in the flows registry.

Compresses the video file using ffmpeg and stores the path to the compressed file.
"""

from typing import Any, Dict, Optional
from ...flows.registry import register_step
from ...video_processor.compression import VideoCompressor
from ...config import DEFAULT_COMPRESSION_CONFIG
import os
from prefect import task

@register_step(
    name="video_compression",
    enabled=False,  # Only enabled when AI analysis is enabled or by config
    description="Compress video using ffmpeg and store compressed path"
)
@task
def video_compression_step(
    data: Dict[str, Any],
    logger=None,
    compression_fps: int = DEFAULT_COMPRESSION_CONFIG['fps'],
    compression_bitrate: str = DEFAULT_COMPRESSION_CONFIG['video_bitrate'],
    thumbnails_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compress the video file and store the path in the pipeline data.
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        compression_fps: Frame rate for compression
        compression_bitrate: Bitrate for compression
        thumbnails_dir: Directory for run outputs (to determine compressed dir)
    Returns:
        Dict with 'compressed_video_path'
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data for compression step")

    # Determine output directory for compressed files
    run_dir = None
    if thumbnails_dir:
        run_dir = os.path.dirname(thumbnails_dir)
    else:
        run_dir = os.path.dirname(os.path.abspath(file_path))

    compressed_dir = os.path.join(run_dir, "compressed")
    os.makedirs(compressed_dir, exist_ok=True)

    # Prepare compression config
    compression_config = {
        'fps': compression_fps,
        'video_bitrate': compression_bitrate
    }
    compressor = VideoCompressor(compression_config)

    if logger:
        logger.info(f"Compressing video for AI analysis: {file_path}")

    compressed_path = compressor.compress(file_path, compressed_dir)

    if logger:
        logger.info(f"Compression complete: {compressed_path}")

    return {
        'compressed_video_path': compressed_path
    } 