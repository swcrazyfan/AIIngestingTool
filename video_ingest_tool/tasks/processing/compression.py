"""
Video compression step for the video ingest tool.

Compresses the video file using ffmpeg and stores the path to the compressed file.
"""

from typing import Any, Dict, Optional, Callable
from ...video_processor.compression import VideoCompressor
from ...config import DEFAULT_COMPRESSION_CONFIG
# from ...api.progress_tracker import get_progress_tracker # Import moved into function
import os
from prefect import task, runtime # Import runtime for flow_run_id

@task
def video_compression_step(
    data: Dict[str, Any],
    logger=None, # Prefect's built-in logger will be used if not None
    compression_fps: int = DEFAULT_COMPRESSION_CONFIG['fps'],
    compression_bitrate: str = DEFAULT_COMPRESSION_CONFIG['video_bitrate'],
    data_base_dir: Optional[str] = None, # Base data directory (e.g., /path/to/data)
    tracker_flow_run_id: Optional[str] = None # Explicitly passed ID for ProgressTracker
) -> Dict[str, Any]:
    """
    Compress a video file using configurable settings and track progress.
    
    Args:
        data: Pipeline data containing file_path, checksum, clip_id, etc.
        logger: Optional logger
        compression_fps: Target FPS for compression
        compression_bitrate: Target bitrate for compression
        data_base_dir: Base data directory for organized output structure
        tracker_flow_run_id: Flow run ID for progress tracking
        
    Returns:
        Dict with compressed video path and metadata
    """
    from ...api.progress_tracker import get_progress_tracker
    from ...video_processor.compression import VideoCompressor
    from prefect import get_run_logger
    
    if logger is None:
        logger = get_run_logger()
    
    progress_tracker = get_progress_tracker()
    file_path = data.get('file_path')
    checksum = data.get('checksum')
    clip_id = data.get('clip_id')
    file_name = data.get('file_name', os.path.basename(file_path) if file_path else 'unknown')
    
    if not file_path:
        raise ValueError("file_path is required in data")
    
    # Determine the actual file to compress (might be the original or already compressed)
    actual_file_to_compress = file_path
    original_file_path_for_tracking = file_path
    
    # Use tracker_flow_run_id if provided, otherwise try to get from context
    _effective_tracker_id = tracker_flow_run_id
    if not _effective_tracker_id:
        try:
            from prefect.context import get_run_context
            run_context = get_run_context()
            _effective_tracker_id = str(run_context.flow_run.id)
        except Exception:
            _effective_tracker_id = None
    
    # Progress callback for VideoCompressor
    def compression_progress_callback(progress_data):
        if _effective_tracker_id and original_file_path_for_tracking:
            progress_tracker.update_file_step(
                flow_run_id=_effective_tracker_id,
                file_path=original_file_path_for_tracking,
                step_name=progress_data.get('step_name', 'video_compression'),
                step_progress=progress_data.get('step_progress', 0),
                step_status=progress_data.get('step_status', 'processing'),
                compression_update=progress_data.get('compression_update', {})
            )
    
    # Determine output directory structure: data/clips/{filename}_{clip_id}/compressed/
    if data_base_dir and clip_id:
        # New organized structure
        base_filename = os.path.splitext(file_name)[0]
        clip_dir_name = f"{base_filename}_{clip_id}"
        clip_base_dir = os.path.join(data_base_dir, "clips", clip_dir_name)
        compressed_output_dir = os.path.join(clip_base_dir, "compressed")
    elif data_base_dir:
        # Fallback to data/compressed if no clip_id
        compressed_output_dir = os.path.join(data_base_dir, "compressed")
    else:
        # Final fallback - put compressed videos next to source
        base_output_dir = os.path.dirname(os.path.abspath(actual_file_to_compress))
        compressed_output_dir = os.path.join(base_output_dir, "compressed")
        logger.warning(f"data_base_dir not provided, using fallback output directory: {base_output_dir}")

    os.makedirs(compressed_output_dir, exist_ok=True)

    compression_config_overrides = {
        'fps': compression_fps,
        'video_bitrate': compression_bitrate
    }
    
    # Initial progress update to set the step to "video_compression"
    if _effective_tracker_id and original_file_path_for_tracking:
        logger.info(f"Setting initial progress for video_compression: {original_file_path_for_tracking} using tracker_id: {_effective_tracker_id}")
        progress_tracker.update_file_step(
            flow_run_id=_effective_tracker_id,
            file_path=original_file_path_for_tracking,
            step_name="video_compression",
            step_progress=0,
            step_status="processing"
        )
    else:
        logger.warning(f"Could not set initial progress for video_compression: _effective_tracker_id ({_effective_tracker_id}) or original_file_path_for_tracking ({original_file_path_for_tracking}) missing.")

    compressor = VideoCompressor(
        config=compression_config_overrides,
        progress_callback=compression_progress_callback if _effective_tracker_id else None
    )

    logger.info(f"Starting video compression for: {actual_file_to_compress} (tracking as {original_file_path_for_tracking} with tracker_id: {_effective_tracker_id})")
    
    compressed_path = None # Initialize in case of early error before assignment
    try:
        compressed_path = compressor.compress_video(
            input_path=actual_file_to_compress,
            output_dir=compressed_output_dir,
            flow_run_id=_effective_tracker_id, # Pass the correct tracker ID
            file_path_for_tracker=original_file_path_for_tracking
        )
        logger.info(f"Video compression complete. Output: {compressed_path}")
        
        if _effective_tracker_id:
             compression_progress_callback({
                 'step_name': "video_compression",
                 'step_progress': 100,
                 'step_status': "completed",
                 'compression_update': {} # Empty or could contain final stats
            })

    except Exception as e:
        logger.error(f"Video compression failed for {actual_file_to_compress}: {str(e)}")
        if _effective_tracker_id: # Use _effective_tracker_id
            compression_progress_callback({
                'step_name': "video_compression",
                'step_status': "failed",
                'compression_update': {'error_detail': str(e)}
            })
        raise # Re-raise the exception to fail the Prefect task

    return {
        'compressed_video_path': compressed_path,
        'original_file_path': original_file_path_for_tracking # Pass along for consistency
    }