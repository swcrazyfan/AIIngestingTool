"""
Video compression step for the video ingest tool.

Compresses the video file using ffmpeg and stores the path to the compressed file.
"""

from typing import Any, Dict, Optional, Callable
from ...video_processor.compression import VideoCompressor
from ...config import DEFAULT_COMPRESSION_CONFIG
from ...api.progress_tracker import get_progress_tracker # Import progress tracker
import os
from prefect import task, runtime # Import runtime for flow_run_id

@task
def video_compression_step(
    data: Dict[str, Any],
    logger=None, # Prefect's built-in logger will be used if not None
    compression_fps: int = DEFAULT_COMPRESSION_CONFIG['fps'],
    compression_bitrate: str = DEFAULT_COMPRESSION_CONFIG['video_bitrate'],
    thumbnails_dir: Optional[str] = None # Used to determine base output directory
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
    Returns:
        Dict with 'compressed_video_path'
    """
    actual_file_to_compress = data.get('file_path_for_processing', data.get('file_path'))
    original_file_path_for_tracking = data.get('file_path') # This is the key for the tracker

    if not actual_file_to_compress:
        raise ValueError("Missing 'file_path_for_processing' or 'file_path' in data for compression step")
    if not original_file_path_for_tracking:
        # This should ideally not happen if file_path was present
        raise ValueError("Missing 'file_path' for progress tracking key")

    # Get Prefect logger if none provided
    if logger is None:
        from prefect import get_run_logger
        logger = get_run_logger()

    # Get flow_run_id for progress tracking
    flow_run_id = None
    try:
        # Attempt to get flow_run_id using prefect.runtime.flow_run.id
        # This is generally more reliable within tasks in Prefect 2+
        if runtime.flow_run:
            flow_run_id = str(runtime.flow_run.id)
        else:
            flow_run_id = None
            logger.warning("prefect.runtime.flow_run is not available.")
    except AttributeError:
        logger.warning("prefect.runtime.flow_run.id is not accessible. Trying get_run_context().")
        # Fallback to get_run_context if flow_run attribute isn't there (less common for Prefect 2+)
        try:
            run_context = runtime.get_run_context()
            flow_run_id = str(run_context.flow_run.id) if run_context.flow_run else None
        except Exception as e:
            logger.warning(f"Could not get flow_run_id using get_run_context(): {e}")
            flow_run_id = None # Ensure it's None if all attempts fail
    except Exception as e:
        logger.warning(f"Unexpected error getting flow_run_id: {e}")
        flow_run_id = None


    progress_tracker = get_progress_tracker()

    def compression_progress_callback(update_data: Dict[str, Any]):
        if not flow_run_id:
            logger.debug("Skipping progress update, no flow_run_id.")
            return
        
        # The update_data from VideoCompressor already contains most of what update_file_step needs
        # We just need to ensure flow_run_id and file_path (original) are correctly passed
        progress_tracker.update_file_step(
            flow_run_id=flow_run_id,
            file_path=original_file_path_for_tracking, # Use original path for tracking key
            step_name=update_data.get('step_name', "video_compression"),
            step_progress=update_data.get('step_progress', 0),
            step_status=update_data.get('step_status', "processing"),
            compression_update=update_data.get('compression_update')
        )
        logger.debug(f"Compression progress callback: {update_data.get('compression_update')}")

    # Determine output directory for compressed files
    # It should be relative to a run-specific directory if possible
    base_output_dir = None
    if thumbnails_dir: # thumbnails_dir is expected to be like /path/to/run_id/thumbnails
        base_output_dir = os.path.dirname(thumbnails_dir) # Gives /path/to/run_id/
    else: # Fallback if thumbnails_dir is not provided (e.g. direct task execution)
        base_output_dir = os.path.dirname(os.path.abspath(actual_file_to_compress))
        logger.warning(f"thumbnails_dir not provided, using fallback output directory: {base_output_dir}")

    compressed_output_dir = os.path.join(base_output_dir, "compressed")
    os.makedirs(compressed_output_dir, exist_ok=True)

    compression_config_overrides = {
        'fps': compression_fps,
        'video_bitrate': compression_bitrate
        # Other DEFAULT_COMPRESSION_CONFIG values will be used unless overridden here
    }
    
    # Pass the callback to the compressor

    # Initial progress update to set the step to "video_compression"
    if flow_run_id and original_file_path_for_tracking:
        logger.info(f"Setting initial progress for video_compression: {original_file_path_for_tracking}")
        progress_tracker.update_file_step(
            flow_run_id=flow_run_id,
            file_path=original_file_path_for_tracking,
            step_name="video_compression",
            step_progress=0, # Use step_progress to align with callback
            step_status="processing"
            # No compression_update here, as details are not yet available
        )
    else:
        logger.warning("Could not set initial progress for video_compression: flow_run_id or original_file_path_for_tracking missing.")

    compressor = VideoCompressor(
        config=compression_config_overrides,
        progress_callback=compression_progress_callback if flow_run_id else None
    )

    logger.info(f"Starting video compression for: {actual_file_to_compress} (tracking as {original_file_path_for_tracking})")
    
    try:
        compressed_path = compressor.compress_video(
            input_path=actual_file_to_compress,
            output_dir=compressed_output_dir,
            flow_run_id=flow_run_id, # Pass for internal use by compressor if needed
            file_path_for_tracker=original_file_path_for_tracking # Ensure tracker uses original path
        )
        logger.info(f"Video compression complete. Output: {compressed_path}")
        
        # Final update to mark as completed (VideoCompressor might do this, but good to ensure)
        if flow_run_id:
             compression_progress_callback({
                 'step_name': "video_compression",
                 'step_progress': 100,
                 'step_status': "completed",
                 'compression_update': {} # Empty or could contain final stats
            })

    except Exception as e:
        logger.error(f"Video compression failed for {actual_file_to_compress}: {str(e)}")
        if flow_run_id:
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