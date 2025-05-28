"""
Prefect-based pipeline orchestration flows for video ingest tool.

Defines per-file and batch flows using Prefect, supporting step enable/disable and concurrency.

Prefect flows for video ingest pipeline. Concurrency limits are set at CLI startup, not in the flow.
"""
from typing import List, Dict, Optional, Any
from prefect import flow, task, get_run_logger, get_client
from prefect.tasks import task_input_hash
from datetime import timedelta
import os
import uuid
import concurrent.futures
from concurrent.futures import as_completed
import asyncio

# Import all step tasks
from video_ingest_tool.tasks import (
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

@task
def process_video_file_task(
    file_path: str,
    thumbnails_dir: str,
    config: Optional[Dict[str, bool]] = None,
    compression_fps: int = DEFAULT_COMPRESSION_CONFIG['fps'],
    compression_bitrate: str = DEFAULT_COMPRESSION_CONFIG['video_bitrate'],
    force_reprocess: bool = False,
    step_toggles: Optional[Dict[str, bool]] = None,
) -> Optional[VideoIngestOutput]:
    """
    Prefect task to process a single video file, with step enable/disable logic.
    """
    logger = get_run_logger()
    data = {
        'file_path': file_path,
        'compression_fps': compression_fps,
        'compression_bitrate': compression_bitrate
    }
    toggles = config or step_toggles or {}
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
        data.update(ai_thumbnail_selection_step.fn(data, thumbnails_dir=thumbnails_dir))
    if toggles.get('consolidate_metadata_step', True):
        data.update(consolidate_metadata_step.fn(data))
    if toggles.get('create_model_step', True):
        data.update(create_model_step.fn(data))
    if toggles.get('database_storage_step', True):
        data.update(database_storage_step.fn(data))
    if toggles.get('generate_embeddings_step', True):
        data.update(generate_embeddings_step.fn(data))
    if toggles.get('upload_thumbnails_step', True):
        data.update(upload_thumbnails_step.fn(data))
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
    user_id: Optional[str] = None,
) -> List[Optional[VideoIngestOutput]]:
    """
    Prefect flow to process a batch of video files in parallel (per-file), with steps in order per file.
    Each file is processed as a subflow, so all step-tasks are visible in the UI.
    """
    # Generate a unique batch UUID for this run
    batch_uuid = str(uuid.uuid4())
    # Try to get user_id from Supabase if not provided
    if user_id is None:
        try:
            from video_ingest_tool.auth import AuthManager
            auth_manager = AuthManager()
            user_id = auth_manager.get_user_id()
            if not user_id:
                user_id = "unknown"
        except Exception:
            user_id = "unknown"
    # Use ThreadPoolExecutor for per-file parallelism
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency_limit) as executor:
        futures = [
            executor.submit(
                process_video_file_flow.with_options(name=f"{user_id} | {batch_uuid} | {os.path.basename(file_path)} | flow"),
                file_path=file_path,
                thumbnails_dir=thumbnails_dir,
                compression_fps=compression_fps,
                compression_bitrate=compression_bitrate,
                force_reprocess=force_reprocess,
                user_id=user_id,
                batch_uuid=batch_uuid,
                config=config
            )
            for file_path in file_list
        ]
        for f in as_completed(futures):
            results.append(f.result())
    return results

@flow
def process_video_file_flow(
    file_path: str,
    thumbnails_dir: str,
    compression_fps: int = DEFAULT_COMPRESSION_CONFIG['fps'],
    compression_bitrate: str = DEFAULT_COMPRESSION_CONFIG['video_bitrate'],
    force_reprocess: bool = False,
    user_id: Optional[str] = None,
    batch_uuid: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[VideoIngestOutput]:
    """
    Prefect flow to process a single video file, orchestrating each pipeline step as a Prefect task.
    Steps that do not depend on each other are launched in parallel for maximum efficiency.
    Concurrency for resource-heavy steps is set via Prefect concurrency limits and tags.
    """
    logger = get_run_logger()
    data = {
        'file_path': file_path,
        'compression_fps': compression_fps,
        'compression_bitrate': compression_bitrate
    }
    file_name = os.path.basename(file_path)
    label_prefix = f"{user_id or 'unknown'} | {batch_uuid or 'batch'} | {file_name}"

    # Step 1: Checksum
    checksum_result = generate_checksum_step.with_options(
        name=f"{label_prefix} | generate_checksum",
        tags=["generate_checksum_step"]
    ).submit(data)
    data.update(checksum_result.result())
    # Step 2: Duplicate check
    duplicate_result = check_duplicate_step.with_options(
        name=f"{label_prefix} | check_duplicate",
        tags=["check_duplicate_step"]
    ).submit(data, force_reprocess=force_reprocess)
    data.update(duplicate_result.result())
    if data.get('pipeline_stopped'):
        logger.info('Duplicate detected, stopping pipeline.')
        return None

    # Step 3: Launch all independent steps in parallel
    compression_task = video_compression_step.with_options(
        name=f"{label_prefix} | video_compression",
        tags=["video_compression_step"]
    )
    compression_future = compression_task.submit(data, compression_fps=compression_fps, compression_bitrate=compression_bitrate)
    mediainfo_future = extract_mediainfo_step.with_options(
        name=f"{label_prefix} | extract_mediainfo",
        tags=["extract_mediainfo_step"]
    ).submit(data)
    ffprobe_future = extract_ffprobe_step.with_options(
        name=f"{label_prefix} | extract_ffprobe",
        tags=["extract_ffprobe_step"]
    ).submit(data)
    exiftool_future = extract_exiftool_step.with_options(
        name=f"{label_prefix} | extract_exiftool",
        tags=["extract_exiftool_step"]
    ).submit(data)
    extended_exif_future = extract_extended_exif_step.with_options(
        name=f"{label_prefix} | extract_extended_exif",
        tags=["extract_extended_exif_step"]
    ).submit(data)
    codec_future = extract_codec_step.with_options(
        name=f"{label_prefix} | extract_codec",
        tags=["extract_codec_step"]
    ).submit(data)
    hdr_future = extract_hdr_step.with_options(
        name=f"{label_prefix} | extract_hdr",
        tags=["extract_hdr_step"]
    ).submit(data)
    audio_future = extract_audio_step.with_options(
        name=f"{label_prefix} | extract_audio",
        tags=["extract_audio_step"]
    ).submit(data)
    subtitle_future = extract_subtitle_step.with_options(
        name=f"{label_prefix} | extract_subtitle",
        tags=["extract_subtitle_step"]
    ).submit(data)
    thumbnails_task = generate_thumbnails_step.with_options(
        name=f"{label_prefix} | generate_thumbnails",
        tags=["generate_thumbnails_step"]
    )
    thumbnails_future = thumbnails_task.submit(data, thumbnails_dir=thumbnails_dir)

    # Wait for thumbnails to be generated and update data
    thumbnails_result = thumbnails_future.result()
    data['thumbnail_paths'] = thumbnails_result

    # Now call focal length detection (after thumbnails are ready)
    focal_length_task = detect_focal_length_step.with_options(
        name=f"{label_prefix} | detect_focal_length",
        tags=["detect_focal_length_step"]
    )
    focal_length_future = focal_length_task.submit(data)

    # Wait for all parallel steps to finish and update data
    data.update(mediainfo_future.result())
    data.update(ffprobe_future.result())
    data.update(exiftool_future.result())
    data.update(extended_exif_future.result())
    data.update(codec_future.result())
    data.update(hdr_future.result())
    data.update(audio_future.result())
    data.update(subtitle_future.result())
    data.update(thumbnails_result)
    data.update(focal_length_future.result())
    data.update(compression_future.result())

    # Step 4: AI analysis and downstream steps that depend on compression
    ai_analysis_task = ai_video_analysis_step.with_options(
        name=f"{label_prefix} | ai_video_analysis",
        tags=["ai_video_analysis_step"]
    )
    ai_analysis_result = ai_analysis_task.submit(data)
    data.update(ai_analysis_result.result())
    ai_thumbnails_result = ai_thumbnail_selection_step.with_options(
        name=f"{label_prefix} | ai_thumbnail_selection",
        tags=["ai_thumbnail_selection_step"]
    ).submit(data, thumbnails_dir=thumbnails_dir)
    data.update(ai_thumbnails_result.result())
    # Step 5: Consolidate metadata
    consolidate_result = consolidate_metadata_step.with_options(
        name=f"{label_prefix} | consolidate_metadata",
        tags=["consolidate_metadata_step"]
    ).submit(data)
    data.update(consolidate_result.result())
    # Step 6: Model creation
    model_result = create_model_step.with_options(
        name=f"{label_prefix} | create_model",
        tags=["create_model_step"]
    ).submit(data)
    data.update(model_result.result())
    # Step 7: Database storage
    db_result = database_storage_step.with_options(
        name=f"{label_prefix} | database_storage",
        tags=["database_storage_step"]
    ).submit(data)
    data.update(db_result.result())
    # Step 8: Embeddings
    embeddings_result = generate_embeddings_step.with_options(
        name=f"{label_prefix} | generate_embeddings",
        tags=["generate_embeddings_step"]
    ).submit(data)
    data.update(embeddings_result.result())
    # Step 9: Upload thumbnails
    upload_result = upload_thumbnails_step.with_options(
        name=f"{label_prefix} | upload_thumbnails",
        tags=["upload_thumbnails_step"]
    ).submit(data)
    data.update(upload_result.result())
    if 'model' in data and isinstance(data['model'], VideoIngestOutput):
        return data['model']
    logger.error('Pipeline did not produce a valid output model')
    return None

# Next: add a non-AI variant flow for pipelines that skip AI steps 