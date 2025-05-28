"""
Pipeline steps for the video ingest tool.

Re-exports all pipeline steps from the steps directory.
"""

from .extraction import (
    extract_mediainfo_step, extract_ffprobe_step, extract_exiftool_step,
    extract_extended_exif_step, extract_codec_step, extract_hdr_step,
    extract_audio_step, extract_subtitle_step
)
from .analysis import (
    generate_thumbnails_step, analyze_exposure_step, detect_focal_length_step,
    ai_video_analysis_step, ai_thumbnail_selection_step
)
from .processing import (
    generate_checksum_step, check_duplicate_step, consolidate_metadata_step
)
from .storage import (
    create_model_step, database_storage_step, generate_embeddings_step,
    upload_thumbnails_step
)

__all__ = [
    # Extraction steps
    'extract_mediainfo_step',
    'extract_ffprobe_step',
    'extract_exiftool_step',
    'extract_extended_exif_step',
    'extract_codec_step',
    'extract_hdr_step',
    'extract_audio_step',
    'extract_subtitle_step',
    
    # Analysis steps
    'generate_thumbnails_step',
    'analyze_exposure_step',
    'detect_focal_length_step',
    'ai_video_analysis_step',
    'ai_thumbnail_selection_step',
    
    # Processing steps
    'generate_checksum_step',
    'check_duplicate_step',
    'consolidate_metadata_step',
    
    # Storage steps
    'create_model_step',
    'database_storage_step',
    'generate_embeddings_step',
    'upload_thumbnails_step'
]

from typing import Dict, Any
from ..models import VideoIngestOutput
from ..pipeline.registry import get_default_pipeline
from ..config import DEFAULT_COMPRESSION_CONFIG

def reorder_pipeline_steps():
    """
    Reorder the pipeline steps to ensure dependencies are met.
    
    This ensures that steps that depend on data from other steps
    are executed in the correct order.
    """
    pipeline = get_default_pipeline()
    
    # Define the correct order of steps (only those that have dependencies)
    step_order = {
        "checksum_generation": 1,  # Must run first
        "duplicate_check": 2,      # Now runs immediately after checksum
        "video_compression": 3,    # Compress before thumbnails/AI
        "thumbnail_generation": 4, # Depends on checksum
        "exposure_analysis": 5,    # Depends on thumbnails
        "ai_video_analysis": 13,   # Should run after basic extraction steps
        "ai_thumbnail_selection": 14, # Should run after AI video analysis
        "metadata_consolidation": 16, # Should run after all extraction steps
        "model_creation": 17,      # Should run last but before database storage
        "database_storage": 18,    # Should run after model creation
        "generate_embeddings": 19,  # Should run after database storage
        "thumbnail_upload": 20     # Should run after database storage to get clip_id
    }
    
    # Sort the steps based on the predefined order
    sorted_steps = sorted(
        pipeline.steps,
        key=lambda step: step_order.get(step.name, 10)  # Default to 10 for steps without explicit order
    )
    
    # Replace the pipeline steps with the sorted list
    pipeline.steps = sorted_steps

def process_video_file(file_path: str, thumbnails_dir: str, logger=None, config: Dict[str, bool] = None, 
                       compression_fps: int = DEFAULT_COMPRESSION_CONFIG['fps'], 
                       compression_bitrate: str = DEFAULT_COMPRESSION_CONFIG['video_bitrate'], 
                       force_reprocess: bool = False, step_callback=None) -> VideoIngestOutput:
    """
    Process a video file using the pipeline.
    
    This function executes the pipeline with all registered steps from the steps directory.
    All individual step implementations have been refactored into dedicated modules.
    
    Args:
        file_path: Path to the video file
        thumbnails_dir: Directory to save thumbnails
        logger: Optional logger
        config: Dictionary of step configurations (enabled/disabled)
        compression_fps: Frame rate for compressed video
        compression_bitrate: Bitrate for compressed video
        force_reprocess: If True, force reprocessing even if duplicate
        step_callback: Optional callback function after each step
        
    Returns:
        VideoIngestOutput: Pydantic model with all video metadata and analysis
    """
    # Get the default pipeline
    pipeline = get_default_pipeline()
    
    # Reorder the pipeline steps to ensure dependencies are met
    reorder_pipeline_steps()
    
    # Configure the pipeline based on the provided config
    if config:
        for step_name, enabled in config.items():
            pipeline.configure_step(step_name, enabled=enabled)
    
    # Initialize data with input parameters - only include file_path
    data = {
        'file_path': file_path,
        'compression_fps': compression_fps,
        'compression_bitrate': compression_bitrate
    }
    
    # Execute the pipeline, passing force_reprocess and thumbnails_dir as keyword arguments
    result = pipeline.execute(data, logger=logger, step_callback=step_callback, 
                            force_reprocess=force_reprocess, thumbnails_dir=thumbnails_dir)
    
    # The model_creation step should have added a 'model' key with the VideoIngestOutput
    if 'model' in result and isinstance(result['model'], VideoIngestOutput):
        return result['model']
    
    # If for some reason the model wasn't created, raise an error
    raise RuntimeError("Pipeline did not produce a valid output model")
