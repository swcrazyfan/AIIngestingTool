"""
Prefect-based pipeline orchestration flows for video ingest tool.

Defines per-file and batch flows using Prefect, supporting step enable/disable and concurrency.

Prefect flows for video ingest pipeline. Concurrency limits are set at CLI startup, not in the flow.
"""
from typing import List, Dict, Optional, Any
from prefect import flow, task, get_run_logger
from prefect.artifacts import create_progress_artifact, update_progress_artifact
from datetime import timedelta
import os
import uuid

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

@task(cache_policy=None)
def process_video_file_task(
    file_path: str,
    thumbnails_dir: str,
    compression_fps: int = DEFAULT_COMPRESSION_CONFIG['fps'],
    compression_bitrate: str = DEFAULT_COMPRESSION_CONFIG['video_bitrate'],
    force_reprocess: bool = False,
    user_id: Optional[str] = None,
    batch_uuid: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    file_index: Optional[int] = None,
) -> Optional[VideoIngestOutput]:
    """
    Prefect task to process a single video file, orchestrating each pipeline step as Prefect tasks.
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
    
    # Get progress tracker instance
    from ..api.progress_tracker import get_progress_tracker
    progress_tracker = get_progress_tracker()
    
    # Use batch_uuid as flow_run_id for progress tracking
    flow_run_id = batch_uuid or "unknown_batch"
    
    # Create progress artifact for this file
    progress_artifact_id = None
    if file_index is not None:
        progress_artifact_id = create_progress_artifact(
            progress=0.0,
            key=f"video-processing-{batch_uuid}-{file_index}",
            description=f"Processing {file_name}"
        )
    
    # Step 1: Checksum
    progress_tracker.update_file_step(flow_run_id, file_path, "generate_checksum", 5, "processing")
    if progress_artifact_id:
        update_progress_artifact(progress_artifact_id, progress=5.0, description="Generating checksum...")
    
    checksum_result = generate_checksum_step.with_options(
        name=f"{label_prefix} | generate_checksum",
        tags=["generate_checksum_step"]
    ).submit(data)
    data.update(checksum_result.result())
    
    # Step 2: Duplicate check
    progress_tracker.update_file_step(flow_run_id, file_path, "check_duplicate", 10, "processing")
    if progress_artifact_id:
        update_progress_artifact(progress_artifact_id, progress=10.0, description="Checking for duplicates...")
    
    duplicate_result = check_duplicate_step.with_options(
        name=f"{label_prefix} | check_duplicate",
        tags=["check_duplicate_step"]
    ).submit(data, force_reprocess=force_reprocess)
    data.update(duplicate_result.result())
    if data.get('pipeline_stopped'):
        logger.info('Duplicate detected, stopping pipeline.')
        progress_tracker.update_file_step(flow_run_id, file_path, "check_duplicate", 100, "skipped")
        if progress_artifact_id:
            update_progress_artifact(progress_artifact_id, progress=100.0, description="Skipped (duplicate)")
        return None

    # Step 3: Launch all independent steps in parallel
    progress_tracker.update_file_step(flow_run_id, file_path, "parallel_extraction", 20, "processing")
    if progress_artifact_id:
        update_progress_artifact(progress_artifact_id, progress=20.0, description="Starting parallel extraction...")
    
    compression_task = video_compression_step.with_options(
        name=f"{label_prefix} | video_compression",
        tags=["video_compression_step"]
    )
    # Pass the flow_run_id (which is the batch_uuid for tracking) to the compression task
    compression_future = compression_task.submit(
        data,
        compression_fps=compression_fps,
        compression_bitrate=compression_bitrate,
        tracker_flow_run_id=flow_run_id  # flow_run_id in this scope is the batch_uuid
    )
    
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
    progress_tracker.update_file_step(flow_run_id, file_path, "generate_thumbnails", 40, "processing")
    if progress_artifact_id:
        update_progress_artifact(progress_artifact_id, progress=40.0, description="Generating thumbnails...")
    
    thumbnails_result = thumbnails_future.result()
    data['thumbnail_paths'] = thumbnails_result

    # Now call focal length detection (after thumbnails are ready)
    progress_tracker.update_file_step(flow_run_id, file_path, "detect_focal_length", 50, "processing")
    if progress_artifact_id:
        update_progress_artifact(progress_artifact_id, progress=50.0, description="Detecting focal length...")
    
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
    progress_tracker.update_file_step(flow_run_id, file_path, "ai_analysis", 70, "processing")
    if progress_artifact_id:
        update_progress_artifact(progress_artifact_id, progress=70.0, description="Running AI analysis...")
    
    if config and config.get('ai_video_analysis_step', False):
        logger.info(f"Executing AI video analysis step for {file_name}. Config value: {config.get('ai_video_analysis_step')}")
        ai_analysis_task = ai_video_analysis_step.with_options(
            name=f"{label_prefix} | ai_video_analysis",
            tags=["ai_video_analysis_step"]
        )
        ai_analysis_result = ai_analysis_task.submit(data)
        data.update(ai_analysis_result.result())

        # AI Thumbnail selection is often tied to AI analysis
        if config.get('ai_thumbnail_selection_step', False):
            logger.info(f"Executing AI thumbnail selection step for {file_name}. Config value: {config.get('ai_thumbnail_selection_step')}")
            progress_tracker.update_file_step(flow_run_id, file_path, "ai_thumbnail_selection", 75, "processing")
            ai_thumbnail_task = ai_thumbnail_selection_step.with_options(
                name=f"{label_prefix} | ai_thumbnail_selection",
                tags=["ai_thumbnail_selection_step"]
            )
            ai_thumbnail_result = ai_thumbnail_task.submit(data, thumbnails_dir=thumbnails_dir)
            data.update(ai_thumbnail_result.result())
        else:
            logger.info(f"Skipping AI thumbnail selection step for {file_name} based on config (config_value: {config.get('ai_thumbnail_selection_step')})")
    else:
        logger.info(f"Skipping AI video analysis (and AI thumbnail selection) step for {file_name} based on config (config_value: {config.get('ai_video_analysis_step')})")
    
    # Step 5: Transcription (not implemented yet)
    # if progress_artifact_id:
    #     update_progress_artifact(progress_artifact_id, progress=80.0, description="Running transcription...")
    
    # if config and config.get('transcription_step', False):
    #     logger.info(f"Executing transcription step for {file_name}. Config value: {config.get('transcription_step')}")
    #     transcription_task = transcription_step.with_options(
    #         name=f"{label_prefix} | transcription",
    #         tags=["transcription_step"]
    #     )
    #     transcription_result = transcription_task.submit(data)
    #     data.update(transcription_result.result())

    # Step 6: Embedding Generation (depends on transcription for text, or can use vision models)
    progress_tracker.update_file_step(flow_run_id, file_path, "generate_embeddings", 90, "processing")
    if progress_artifact_id:
        update_progress_artifact(progress_artifact_id, progress=90.0, description="Generating embeddings...")

    if config and config.get('embedding_generation_step', False):
        logger.info(f"Executing embedding generation step for {file_name}. Config value: {config.get('embedding_generation_step')}")
        embedding_task = generate_embeddings_step.with_options(
            name=f"{label_prefix} | embedding_generation",
            tags=["embedding_generation_step"]
        )
        embedding_result = embedding_task.submit(data)
        data.update(embedding_result.result())

    # Step 7: Store data in database
    progress_tracker.update_file_step(flow_run_id, file_path, "database_storage", 95, "processing")
    if progress_artifact_id:
        update_progress_artifact(progress_artifact_id, progress=95.0, description="Storing data...")

    if config and config.get('database_storage_step', False):
        logger.info(f"Executing database storage step for {file_name}. Config value: {config.get('database_storage_step')}")
        storage_task = database_storage_step.with_options(
            name=f"{label_prefix} | database_storage",
            tags=["database_storage_step"]
        )
        # Pass only necessary and serializable parts of 'data'
        storage_result = storage_task.submit(data) 
        data['database_storage_result'] = storage_result.result()

    # Step 8: Upload thumbnails
    progress_tracker.update_file_step(flow_run_id, file_path, "upload_thumbnails", 98, "processing")
    if progress_artifact_id:
        update_progress_artifact(progress_artifact_id, progress=98.0, description="Uploading thumbnails...")

    if config and config.get('upload_thumbnails_step', False):
        logger.info(f"Executing upload_thumbnails step for {file_name} (config_value: {config.get('upload_thumbnails_step')})")
        upload_result = upload_thumbnails_step.with_options(
            name=f"{label_prefix} | upload_thumbnails",
            tags=["upload_thumbnails_step"]
        ).submit(data)
        data.update(upload_result.result())
    else:
        logger.info(f"Skipping upload_thumbnails step for {file_name} based on config (config_value: {config.get('upload_thumbnails_step')})")
    
    # Step 9: Create output model (consolidate all data into VideoIngestOutput)
    progress_tracker.update_file_step(flow_run_id, file_path, "create_model", 99, "processing")
    if progress_artifact_id:
        update_progress_artifact(progress_artifact_id, progress=99.0, description="Creating output model...")
    
    logger.info(f"Creating output model for {file_name}")
    model_result = create_model_step.with_options(
        name=f"{label_prefix} | create_model",
        tags=["create_model_step"]
    ).submit(data)
    data.update(model_result.result())
    
    # Mark as completed
    if 'model' in data and isinstance(data['model'], VideoIngestOutput):
        progress_tracker.update_file_step(flow_run_id, file_path, "completed", 100, "completed")
        if progress_artifact_id:
            update_progress_artifact(progress_artifact_id, progress=100.0, description="Completed successfully")
        return data['model']
    
    # Mark as failed if no valid model was produced
    logger.error('Pipeline did not produce a valid output model')
    progress_tracker.update_file_step(flow_run_id, file_path, "failed", 100, "failed")
    if progress_artifact_id:
        update_progress_artifact(progress_artifact_id, progress=100.0, description="Failed - no valid model")
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
    batch_uuid: Optional[str] = None,
) -> List[Optional[VideoIngestOutput]]:
    """
    Prefect flow to process a batch of video files in parallel (per-file), with steps in order per file.
    Each file is processed as a mapped task, so all step-tasks are visible in the UI.
    
    Progress is tracked via Prefect artifacts instead of callbacks to avoid serialization issues.
    """
    logger = get_run_logger()
    if batch_uuid is None:
        batch_uuid = str(uuid.uuid4())
    
    if user_id is None:
        try:
            from video_ingest_tool.auth import AuthManager
            auth_manager = AuthManager()
            user_id = auth_manager.get_user_id()
            if not user_id:
                user_id = "unknown"
        except Exception:
            user_id = "unknown"
    
    # Initialize progress tracking for all files
    from ..api.progress_tracker import get_progress_tracker
    progress_tracker = get_progress_tracker()
    
    # Initialize file details for all files at the start
    for file_path in file_list:
        progress_tracker.update_file_step(batch_uuid, file_path, "pending", 0, "pending")
    
    # Create batch progress artifact
    batch_progress_artifact_id = create_progress_artifact(
        progress=0.0,
        key=f"batch-processing-{batch_uuid}",
        description=f"Processing batch of {len(file_list)} files"
    )
    
    # Prepare lists for map
    thumbnails_dirs = [thumbnails_dir] * len(file_list)
    compression_fps_list = [compression_fps] * len(file_list)
    compression_bitrate_list = [compression_bitrate] * len(file_list)
    force_reprocess_list = [force_reprocess] * len(file_list)
    user_id_list = [user_id] * len(file_list)
    batch_uuid_list = [batch_uuid] * len(file_list)
    config_list = [config] * len(file_list)
    file_indices = list(range(len(file_list)))  # Pass file indices for progress tracking
    
    # Map the per-file task
    futures = process_video_file_task.map(
        file_list,
        thumbnails_dirs,
        compression_fps_list,
        compression_bitrate_list,
        force_reprocess_list,
        user_id_list,
        batch_uuid_list,
        config_list,
        file_indices
    )
    
    # Process results 
    results = [None] * len(futures)
    
    for i, future in enumerate(futures):
        try:
            result = future.result()  # This will block until the future is done
            results[i] = result
            
            # Update batch progress
            completed_count = i + 1
            batch_progress = (completed_count / len(file_list)) * 100
            update_progress_artifact(
                batch_progress_artifact_id, 
                progress=batch_progress,
                description=f"Completed {completed_count}/{len(file_list)} files"
            )
            
        except Exception as e:
            results[i] = None
            logger.error(f"Error processing {file_list[i]}: {str(e)}")
    
    # Final counts
    successful_count = sum(1 for r in results if r is not None)
    failed_count = len(results) - successful_count
    
    # Final batch progress update
    update_progress_artifact(
        batch_progress_artifact_id,
        progress=100.0,
        description=f"Batch completed: {successful_count} successful, {failed_count} failed"
    )
    
    logger.info(f"Batch processing completed: {successful_count} successful, {failed_count} failed")
    
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
    if progress_artifact_id:
        update_progress_artifact(progress_artifact_id, progress=70.0, description="Running AI analysis...")
    
    if config and config.get('ai_video_analysis_step', False):
        logger.info(f"Executing AI video analysis step for {file_name}. Config value: {config.get('ai_video_analysis_step')}")
        ai_analysis_task = ai_video_analysis_step.with_options(
            name=f"{label_prefix} | ai_video_analysis",
            tags=["ai_video_analysis_step"]
        )
        ai_analysis_result = ai_analysis_task.submit(data)
        data.update(ai_analysis_result.result())

        # AI Thumbnail selection is often tied to AI analysis
        if config.get('ai_thumbnail_selection_step', False):
            logger.info(f"Executing AI thumbnail selection step for {file_name}. Config value: {config.get('ai_thumbnail_selection_step')}")
            ai_thumbnail_task = ai_thumbnail_selection_step.with_options(
                name=f"{label_prefix} | ai_thumbnail_selection",
                tags=["ai_thumbnail_selection_step"]
            )
            ai_thumbnail_result = ai_thumbnail_task.submit(data, thumbnails_dir=thumbnails_dir)
            data.update(ai_thumbnail_result.result())
        else:
            logger.info(f"Skipping AI thumbnail selection step for {file_name} based on config (config_value: {config.get('ai_thumbnail_selection_step')})")
    else:
        logger.info(f"Skipping AI video analysis (and AI thumbnail selection) step for {file_name} based on config (config_value: {config.get('ai_video_analysis_step')})")
    
    # Step 5: Transcription (not implemented yet)
    # if progress_artifact_id:
    #     update_progress_artifact(progress_artifact_id, progress=80.0, description="Running transcription...")
    
    # if config and config.get('transcription_step', False):
    #     logger.info(f"Executing transcription step for {file_name}. Config value: {config.get('transcription_step')}")
    #     transcription_task = transcription_step.with_options(
    #         name=f"{label_prefix} | transcription",
    #         tags=["transcription_step"]
    #     )
    #     transcription_result = transcription_task.submit(data)
    #     data.update(transcription_result.result())

    # Step 6: Embedding Generation (depends on transcription for text, or can use vision models)
    if progress_artifact_id:
        update_progress_artifact(progress_artifact_id, progress=90.0, description="Generating embeddings...")

    if config and config.get('embedding_generation_step', False):
        logger.info(f"Executing embedding generation step for {file_name}. Config value: {config.get('embedding_generation_step')}")
        embedding_task = generate_embeddings_step.with_options(
            name=f"{label_prefix} | embedding_generation",
            tags=["embedding_generation_step"]
        )
        embedding_result = embedding_task.submit(data)
        data.update(embedding_result.result())

    # Step 7: Store data in database
    if progress_artifact_id:
        update_progress_artifact(progress_artifact_id, progress=95.0, description="Storing data...")

    if config and config.get('database_storage_step', False):
        logger.info(f"Executing database storage step for {file_name}. Config value: {config.get('database_storage_step')}")
        storage_task = database_storage_step.with_options(
            name=f"{label_prefix} | database_storage",
            tags=["database_storage_step"]
        )
        # Pass only necessary and serializable parts of 'data'
        storage_result = storage_task.submit(data) 
        data['database_storage_result'] = storage_result.result()

    # Step 8: Upload thumbnails
    if progress_artifact_id:
        update_progress_artifact(progress_artifact_id, progress=98.0, description="Uploading thumbnails...")

    if config and config.get('upload_thumbnails_step', False):
        logger.info(f"Executing upload_thumbnails step for {file_name} (config_value: {config.get('upload_thumbnails_step')})")
        upload_result = upload_thumbnails_step.with_options(
            name=f"{label_prefix} | upload_thumbnails",
            tags=["upload_thumbnails_step"]
        ).submit(data)
        data.update(upload_result.result())
    else:
        logger.info(f"Skipping upload_thumbnails step for {file_name} based on config (config_value: {config.get('upload_thumbnails_step')})")
    
    # Step 9: Create output model (consolidate all data into VideoIngestOutput)
    progress_tracker.update_file_step(flow_run_id, file_path, "create_model", 99, "processing")
    if progress_artifact_id:
        update_progress_artifact(progress_artifact_id, progress=99.0, description="Creating output model...")
    
    logger.info(f"Creating output model for {file_name}")
    model_result = create_model_step.with_options(
        name=f"{label_prefix} | create_model",
        tags=["create_model_step"]
    ).submit(data)
    data.update(model_result.result())
    
    # Mark as completed
    if 'model' in data and isinstance(data['model'], VideoIngestOutput):
        progress_tracker.update_file_step(flow_run_id, file_path, "completed", 100, "completed")
        if progress_artifact_id:
            update_progress_artifact(progress_artifact_id, progress=100.0, description="Completed successfully")
        return data['model']
    logger.error('Pipeline did not produce a valid output model')
    return None 