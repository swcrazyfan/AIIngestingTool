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
    thumbnails_dir: Optional[str] = None, # Used to determine base output directory
    tracker_flow_run_id: Optional[str] = None # Explicitly passed ID for ProgressTracker
) -> Dict[str, Any]:
    """
    Compress the video file, store the path, and report progress.
    Args:
        data: Pipeline data containing file_path (original path of the file)
        logger: Optional logger (Prefect provides one via get_run_logger())
        compression_fps: Frame rate for compression
        compression_bitrate: Bitrate for compression
        thumbnails_dir: Base directory for run outputs (e.g., /path/to/run_id/)
                        Used to create a 'compressed' subdirectory within it.
        tracker_flow_run_id: The specific flow run ID (batch_uuid) to use for progress tracking.
    Returns:
        Dict with 'compressed_video_path'
    """
    actual_file_to_compress = data.get('file_path_for_processing', data.get('file_path'))
    original_file_path_for_tracking = data.get('file_path') # This is the key for the tracker

    if not actual_file_to_compress:
        raise ValueError("Missing 'file_path_for_processing' or 'file_path' in data for compression step")
    if not original_file_path_for_tracking:
        raise ValueError("Missing 'file_path' for progress tracking key")

    if logger is None:
        from prefect import get_run_logger
        logger = get_run_logger()

    # Use the explicitly passed tracker_flow_run_id.
    if not tracker_flow_run_id:
        logger.error("CRITICAL: tracker_flow_run_id was not provided to video_compression_step. Progress tracking will be incorrect or fail.")
        # Fallback or error based on strictness, for now log and continue, but this is bad.
    
    logger.info(f"video_compression_step invoked with tracker_flow_run_id: {tracker_flow_run_id}")

    from ...api.progress_tracker import get_progress_tracker # Moved import here
    progress_tracker = get_progress_tracker()
    
    # Capture the correct tracker_flow_run_id for the callback
    _effective_tracker_id = tracker_flow_run_id

    def compression_progress_callback(update_data: Dict[str, Any]):
        nonlocal _effective_tracker_id # Ensure we use the captured ID
        if not _effective_tracker_id:
            logger.warning(f"Compression callback for {original_file_path_for_tracking}: Skipping progress update, _effective_tracker_id is missing.")
            return
        
        progress_tracker.update_file_step(
            flow_run_id=_effective_tracker_id,
            file_path=original_file_path_for_tracking,
            step_name=update_data.get('step_name', "video_compression"),
            step_progress=update_data.get('step_progress', 0),
            step_status=update_data.get('step_status', "processing"),
            compression_update=update_data.get('compression_update')
        )
        # logger.debug(f"Compression callback sent for {original_file_path_for_tracking} (tracker_id: {_effective_tracker_id}) data: {update_data.get('compression_update')}")

    base_output_dir = None
    if thumbnails_dir:
        base_output_dir = os.path.dirname(thumbnails_dir)
    else:
        base_output_dir = os.path.dirname(os.path.abspath(actual_file_to_compress))
        logger.warning(f"thumbnails_dir not provided, using fallback output directory: {base_output_dir}")

    compressed_output_dir = os.path.join(base_output_dir, "compressed")
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