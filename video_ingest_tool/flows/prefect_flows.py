"""
Prefect-based pipeline orchestration flows for video ingest tool.

Defines per-file and batch flows using Prefect, supporting step enable/disable and concurrency.
"""
from typing import List, Dict, Optional, Any
from prefect import flow, task, get_run_logger
from prefect.tasks import task_input_hash
from datetime import timedelta

# Import all step tasks
from video_ingest_tool.steps import (
    extract_mediainfo_step,
    extract_ffprobe_step,
    extract_exiftool_step,
    extract_extended_exif_step,
    extract_codec_step,
    extract_hdr_step,
    extract_audio_step,
    extract_subtitle_step,
    generate_thumbnails_step,
    analyze_exposure_step,
    detect_focal_length_step,
    ai_video_analysis_step,
    ai_thumbnail_selection_step,
    generate_checksum_step,
    check_duplicate_step,
    video_compression_step,
    consolidate_metadata_step,
    create_model_step,
    database_storage_step,
    generate_embeddings_step,
    upload_thumbnails_step
)
from video_ingest_tool.models import VideoIngestOutput
from video_ingest_tool.config import DEFAULT_COMPRESSION_CONFIG

@flow
def process_video_file_flow(
    file_path: str,
    thumbnails_dir: str,
    config: Optional[Dict[str, bool]] = None,
    compression_fps: int = DEFAULT_COMPRESSION_CONFIG['fps'],
    compression_bitrate: str = DEFAULT_COMPRESSION_CONFIG['video_bitrate'],
    force_reprocess: bool = False,
    step_toggles: Optional[Dict[str, bool]] = None,
) -> Optional[VideoIngestOutput]:
    """
    Prefect flow to process a single video file, with step enable/disable logic.
    """
    logger = get_run_logger()
    data = {
        'file_path': file_path,
        'compression_fps': compression_fps,
        'compression_bitrate': compression_bitrate
    }
    # Step toggles: use config or step_toggles
    toggles = config or step_toggles or {}

    # Extraction steps
    if toggles.get('generate_checksum_step', True):
        data.update(generate_checksum_step.fn(data))
    if toggles.get('check_duplicate_step', True):
        data.update(check_duplicate_step.fn(data, force_reprocess=force_reprocess))
        if data.get('pipeline_stopped'):
            logger.info('Duplicate detected, stopping pipeline.')
            return None
    if toggles.get('video_compression_step', True):
        data.update(video_compression_step.fn(data, compression_fps=compression_fps, compression_bitrate=compression_bitrate))
    if toggles.get('extract_mediainfo_step', True):
        data.update(extract_mediainfo_step.fn(data))
    if toggles.get('extract_ffprobe_step', True):
        data.update(extract_ffprobe_step.fn(data))
    if toggles.get('extract_exiftool_step', True):
        data.update(extract_exiftool_step.fn(data))
    if toggles.get('extract_extended_exif_step', True):
        data.update(extract_extended_exif_step.fn(data))
    if toggles.get('extract_codec_step', True):
        data.update(extract_codec_step.fn(data))
    if toggles.get('extract_hdr_step', True):
        data.update(extract_hdr_step.fn(data))
    if toggles.get('extract_audio_step', True):
        data.update(extract_audio_step.fn(data))
    if toggles.get('extract_subtitle_step', True):
        data.update(extract_subtitle_step.fn(data))
    if toggles.get('generate_thumbnails_step', True):
        data.update(generate_thumbnails_step.fn(data, thumbnails_dir=thumbnails_dir))
    if toggles.get('analyze_exposure_step', True):
        data.update(analyze_exposure_step.fn(data))
    if toggles.get('detect_focal_length_step', True):
        data.update(detect_focal_length_step.fn(data))
    if toggles.get('ai_video_analysis_step', True):
        data.update(ai_video_analysis_step.fn(data))
    if toggles.get('ai_thumbnail_selection_step', True):
        data.update(ai_thumbnail_selection_step.fn(data))
    if toggles.get('consolidate_metadata_step', True):
        data.update(consolidate_metadata_step.fn(data))
    if toggles.get('create_model_step', True):
        data.update(create_model_step.fn(data))
    if toggles.get('database_storage_step', True):
        data.update(database_storage_step.fn(data))
    if toggles.get('generate_embeddings_step', True):
        data.update(generate_embeddings_step.fn(data))
    if toggles.get('upload_thumbnails_step', True):
        data.update(upload_thumbnails_step.fn(data, thumbnails_dir=thumbnails_dir))

    # Return the VideoIngestOutput model if present
    if 'model' in data and isinstance(data['model'], VideoIngestOutput):
        return data['model']
    logger.error('Pipeline did not produce a valid output model')
    return None

@flow
def process_videos_batch_flow(
    file_list: List[str],
    thumbnails_dir: str,
    config: Optional[Dict[str, bool]] = None,
    compression_fps: int = DEFAULT_COMPRESSION_CONFIG['fps'],
    compression_bitrate: str = DEFAULT_COMPRESSION_CONFIG['video_bitrate'],
    force_reprocess: bool = False,
    concurrency_limit: int = 2,
) -> List[Optional[VideoIngestOutput]]:
    """
    Prefect flow to process a batch of video files in parallel.
    """
    from prefect.task_runners import ConcurrentTaskRunner
    # Use a concurrent runner for parallelism
    with ConcurrentTaskRunner(max_workers=concurrency_limit):
        results = [
            process_video_file_flow.submit(
                file_path,
                thumbnails_dir,
                config=config,
                compression_fps=compression_fps,
                compression_bitrate=compression_bitrate,
                force_reprocess=force_reprocess
            ) for file_path in file_list
        ]
        return [r.result() for r in results]

@flow
def process_video_file_full_flow(
    file_path: str,
    thumbnails_dir: str,
    compression_fps: int = DEFAULT_COMPRESSION_CONFIG['fps'],
    compression_bitrate: str = DEFAULT_COMPRESSION_CONFIG['video_bitrate'],
    force_reprocess: bool = False,
) -> Optional[VideoIngestOutput]:
    """
    Prefect flow to process a single video file, running ALL steps (no disables).
    This is the canonical 'do everything' pipeline. All steps are always run unless a step returns early (e.g., duplicate detection).
    """
    logger = get_run_logger()
    data = {
        'file_path': file_path,
        'compression_fps': compression_fps,
        'compression_bitrate': compression_bitrate
    }
    data.update(generate_checksum_step.fn(data))
    data.update(check_duplicate_step.fn(data, force_reprocess=force_reprocess))
    if data.get('pipeline_stopped'):
        logger.info('Duplicate detected, stopping pipeline.')
        return None
    data.update(video_compression_step.fn(data, compression_fps=compression_fps, compression_bitrate=compression_bitrate))
    data.update(extract_mediainfo_step.fn(data))
    data.update(extract_ffprobe_step.fn(data))
    data.update(extract_exiftool_step.fn(data))
    data.update(extract_extended_exif_step.fn(data))
    data.update(extract_codec_step.fn(data))
    data.update(extract_hdr_step.fn(data))
    data.update(extract_audio_step.fn(data))
    data.update(extract_subtitle_step.fn(data))
    data.update(generate_thumbnails_step.fn(data, thumbnails_dir=thumbnails_dir))
    data.update(analyze_exposure_step.fn(data))
    data.update(detect_focal_length_step.fn(data))
    data.update(ai_video_analysis_step.fn(data))
    data.update(ai_thumbnail_selection_step.fn(data))
    data.update(consolidate_metadata_step.fn(data))
    data.update(create_model_step.fn(data))
    data.update(database_storage_step.fn(data))
    data.update(generate_embeddings_step.fn(data))
    data.update(upload_thumbnails_step.fn(data, thumbnails_dir=thumbnails_dir))
    if 'model' in data and isinstance(data['model'], VideoIngestOutput):
        return data['model']
    logger.error('Pipeline did not produce a valid output model')
    return None

# Next: add a non-AI variant flow for pipelines that skip AI steps 