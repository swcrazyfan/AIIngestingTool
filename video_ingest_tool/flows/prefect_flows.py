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

# Import all step tasks directly from their submodules
from video_ingest_tool.tasks.extraction import (
    extract_mediainfo_step,
    extract_ffprobe_step,
    extract_exiftool_step,
    extract_extended_exif_step,
    extract_codec_step,
    extract_hdr_step,
    extract_audio_step,
    extract_subtitle_step
)
from video_ingest_tool.tasks.analysis import (
    generate_thumbnails_step,
    analyze_exposure_step,
    detect_focal_length_step,
    ai_video_analysis_step,
    ai_thumbnail_selection_step
)
from video_ingest_tool.tasks.processing import (
    generate_checksum_step,
    check_duplicate_step,
    video_compression_step,
    consolidate_metadata_step # Assuming this is also in .processing
)
from video_ingest_tool.tasks.storage import (
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
    data_base_dir: str,  # Base data directory (e.g., /path/to/data)
    compression_fps: int = DEFAULT_COMPRESSION_CONFIG['fps'],
    compression_bitrate: str = DEFAULT_COMPRESSION_CONFIG['video_bitrate'],
    force_reprocess: bool = False,
    batch_uuid: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    file_index: Optional[int] = None,
    task_to_run: Optional[str] = None,  # New parameter
) -> Any:  # Changed return type
    """
    Prefect task to process a single video file.
    If task_to_run is specified, only that task attempts to run and the function returns the 'data' dictionary.
    Otherwise, the full pipeline runs, returning Optional[VideoIngestOutput].
    """
    logger = get_run_logger()
    data = {
        'file_path': file_path,
        'data_base_dir': data_base_dir,
        'compression_fps': compression_fps,
        'compression_bitrate': compression_bitrate,
        # Ensure other necessary initial values are here if tasks depend on them from 'data'
    }
    file_name = os.path.basename(file_path)
    label_prefix = f"{batch_uuid or 'batch'} | {file_name}"

    from ..api.progress_tracker import get_progress_tracker
    progress_tracker = get_progress_tracker()
    flow_run_id = batch_uuid or "unknown_batch"
    
    progress_artifact_id = None
    if file_index is not None and task_to_run is None: # Only create artifact for full flow
        progress_artifact_id = create_progress_artifact(
            progress=0.0,
            key=f"video-processing-{batch_uuid}-{file_index}",
            description=f"Processing {file_name}"
        )

    def should_execute_step(step_key: str, config_key: Optional[str] = None) -> bool:
        is_the_target_task = (task_to_run == step_key)
        is_run_all_mode = (task_to_run is None)

        step_is_enabled_by_config = True
        if config_key:
            if config:
                step_is_enabled_by_config = config.get(config_key, False)
            else:
                step_is_enabled_by_config = False # Configurable but no config provided
        
        if is_the_target_task:
            logger.info(f"Specific task '{step_key}' requested. Will run if config enabled (if applicable). Config enabled: {step_is_enabled_by_config if config_key else 'N/A'}")
            return step_is_enabled_by_config
        elif is_run_all_mode:
            return step_is_enabled_by_config
        
        return False

    # Step 1: Checksum (Not configurable, always runs if targeted or in full flow)
    if should_execute_step("checksum"):
        if task_to_run is None:
            progress_tracker.update_file_step(flow_run_id, file_path, "generate_checksum", 5, "processing")
            if progress_artifact_id: update_progress_artifact(progress_artifact_id, progress=5.0, description="Generating checksum...")
        logger.info(f"Running generate_checksum_step for {file_name}")
        checksum_result_future = generate_checksum_step.with_options(name=f"{label_prefix} | generate_checksum", tags=["generate_checksum_step"]).submit(data, force_reprocess=force_reprocess)
        checksum_result = checksum_result_future.result()
        data.update(checksum_result)
        logger.info(f"Checksum for {file_name}: {data.get('checksum')}")
        
        # Check if file should be skipped due to duplicate
        if checksum_result.get('status') == 'skipped':
            logger.info(f"Skipping {file_name} due to duplicate checksum - use --force to reprocess")
            if task_to_run is None:  # Only update progress for full flow
                progress_tracker.update_file_step(flow_run_id, file_path, "generate_checksum", 100, "skipped")
                if progress_artifact_id: update_progress_artifact(progress_artifact_id, progress=100.0, description="Skipped (duplicate)")
                return checksum_result  # Return the skip result
            # For single task mode, continue to return the result

    # Step 2: Duplicate check (Not configurable, depends on checksum)
    if should_execute_step("duplicate_check"):
        if 'checksum' not in data:
            logger.warning(f"Skipping duplicate_check for {file_name}: checksum not found in data. Run 'checksum' task first.")
        else:
            if task_to_run is None:
                progress_tracker.update_file_step(flow_run_id, file_path, "check_duplicate", 10, "processing")
                if progress_artifact_id: update_progress_artifact(progress_artifact_id, progress=10.0, description="Checking for duplicates...")
            logger.info(f"Running check_duplicate_step for {file_name}")
            duplicate_result_future = check_duplicate_step.with_options(name=f"{label_prefix} | check_duplicate", tags=["check_duplicate_step"]).submit(data, force_reprocess=force_reprocess)
            data.update(duplicate_result_future.result())
            if data.get('pipeline_stopped'):
                logger.info(f"Duplicate detected for {file_name}, stopping pipeline.")
                if task_to_run is None: # Only update progress and return None for full flow
                    progress_tracker.update_file_step(flow_run_id, file_path, "check_duplicate", 100, "skipped")
                    if progress_artifact_id: update_progress_artifact(progress_artifact_id, progress=100.0, description="Skipped (duplicate)")
                    return None # Stop full pipeline
                # If single task, let it return data so far

    # Initialize futures for parallel tasks
    compression_future, mediainfo_future, ffprobe_future, exiftool_future, extended_exif_future = None, None, None, None, None
    codec_future, hdr_future, audio_future, subtitle_future, thumbnails_future, focal_length_future = None, None, None, None, None, None

    if task_to_run is None: # Only show this general progress for full flow
        progress_tracker.update_file_step(flow_run_id, file_path, "parallel_extraction", 20, "processing")
        if progress_artifact_id: update_progress_artifact(progress_artifact_id, progress=20.0, description="Starting parallel extraction...")

    # Submit parallel tasks conditionally
    if should_execute_step("compress", config_key="video_compression_step"):
        logger.info(f"Submitting video_compression_step for {file_name}")
        compression_task = video_compression_step.with_options(name=f"{label_prefix} | video_compression", tags=["video_compression_step"])
        compression_future = compression_task.submit(data, compression_fps=compression_fps, compression_bitrate=compression_bitrate, data_base_dir=data_base_dir)

    # Submit other parallel extraction tasks
    if should_execute_step("mediainfo"):
        logger.info(f"Submitting extract_mediainfo_step for {file_name}")
        mediainfo_future = extract_mediainfo_step.with_options(name=f"{label_prefix} | extract_mediainfo", tags=["extract_mediainfo_step"]).submit(data)
    if should_execute_step("ffprobe"):
        logger.info(f"Submitting extract_ffprobe_step for {file_name}")
        ffprobe_future = extract_ffprobe_step.with_options(name=f"{label_prefix} | extract_ffprobe", tags=["extract_ffprobe_step"]).submit(data)
    if should_execute_step("exiftool"):
        logger.info(f"Submitting extract_exiftool_step for {file_name}")
        exiftool_future = extract_exiftool_step.with_options(name=f"{label_prefix} | extract_exiftool", tags=["extract_exiftool_step"]).submit(data)
    if should_execute_step("extended_exif"):
        logger.info(f"Submitting extract_extended_exif_step for {file_name}")
        extended_exif_future = extract_extended_exif_step.with_options(name=f"{label_prefix} | extract_extended_exif", tags=["extract_extended_exif_step"]).submit(data)
    if should_execute_step("codec"):
        logger.info(f"Submitting extract_codec_step for {file_name}")
        codec_future = extract_codec_step.with_options(name=f"{label_prefix} | extract_codec", tags=["extract_codec_step"]).submit(data)
    if should_execute_step("hdr"):
        logger.info(f"Submitting extract_hdr_step for {file_name}")
        hdr_future = extract_hdr_step.with_options(name=f"{label_prefix} | extract_hdr", tags=["extract_hdr_step"]).submit(data)
    if should_execute_step("audio"):
        logger.info(f"Submitting extract_audio_step for {file_name}")
        audio_future = extract_audio_step.with_options(name=f"{label_prefix} | extract_audio", tags=["extract_audio_step"]).submit(data)
    if should_execute_step("subtitle"):
        logger.info(f"Submitting extract_subtitle_step for {file_name}")
        subtitle_future = extract_subtitle_step.with_options(name=f"{label_prefix} | extract_subtitle", tags=["extract_subtitle_step"]).submit(data)
    
    if should_execute_step("thumbnails", config_key="generate_thumbnails_step"):
        logger.info(f"Submitting generate_thumbnails_step for {file_name}")
        thumbnails_task = generate_thumbnails_step.with_options(name=f"{label_prefix} | generate_thumbnails", tags=["generate_thumbnails_step"])
        thumbnails_future = thumbnails_task.submit(data, data_base_dir=data_base_dir)

    # Wait for submitted parallel tasks and update data (with proper None checking)
    if compression_future: 
        data.update(compression_future.result())
        logger.info(f"Compression result for {file_name} processed.")
    if mediainfo_future: 
        data.update(mediainfo_future.result())
        logger.info(f"Mediainfo result for {file_name} processed.")
    if ffprobe_future: 
        data.update(ffprobe_future.result())
        logger.info(f"FFprobe result for {file_name} processed.")
    if exiftool_future: 
        data.update(exiftool_future.result())
        logger.info(f"Exiftool result for {file_name} processed.")
    if extended_exif_future: 
        data.update(extended_exif_future.result())
        logger.info(f"Extended EXIF result for {file_name} processed.")
    if codec_future: 
        data.update(codec_future.result())
        logger.info(f"Codec result for {file_name} processed.")
    if hdr_future: 
        data.update(hdr_future.result())
        logger.info(f"HDR result for {file_name} processed.")
    if audio_future: 
        data.update(audio_future.result())
        logger.info(f"Audio result for {file_name} processed.")
    if subtitle_future: 
        data.update(subtitle_future.result())
        logger.info(f"Subtitle result for {file_name} processed.")
    
    if thumbnails_future:
        if task_to_run is None:
            progress_tracker.update_file_step(flow_run_id, file_path, "generate_thumbnails", 40, "processing")
            if progress_artifact_id: update_progress_artifact(progress_artifact_id, progress=40.0, description="Generating thumbnails...")
        thumbnails_res = thumbnails_future.result()
        data.update(thumbnails_res) # Now we have thumbnail_paths in data
        logger.info(f"Thumbnails generated for {file_name}: {data.get('thumbnail_paths')}")

    if should_execute_step("focal_length", config_key="detect_focal_length_step"):
        if 'thumbnail_paths' not in data:
            logger.warning(f"Skipping focal_length for {file_name}: thumbnail_paths not found. Run 'thumbnails' task first.")
        else:
            if task_to_run is None:
                progress_tracker.update_file_step(flow_run_id, file_path, "detect_focal_length", 50, "processing")
                if progress_artifact_id: update_progress_artifact(progress_artifact_id, progress=50.0, description="Detecting focal length...")
            logger.info(f"Submitting detect_focal_length_step for {file_name}")
            focal_length_task = detect_focal_length_step.with_options(name=f"{label_prefix} | detect_focal_length", tags=["detect_focal_length_step"])
            focal_length_future = focal_length_task.submit(data)
            if focal_length_future: 
                data.update(focal_length_future.result())
                logger.info(f"Focal length result for {file_name} processed.")

    # Step 3.5: Consolidate metadata after all extraction steps
    if should_execute_step("consolidate_metadata"):
        if task_to_run is None:
            progress_tracker.update_file_step(flow_run_id, file_path, "consolidate_metadata", 65, "processing")
            if progress_artifact_id: update_progress_artifact(progress_artifact_id, progress=65.0, description="Consolidating metadata...")
        logger.info(f"Consolidating metadata for {file_name}. Current data keys: {list(data.keys())}")
        consolidate_task = consolidate_metadata_step.with_options(
            name=f"{label_prefix} | consolidate_metadata",
            tags=["consolidate_metadata_step"]
        )
        consolidate_result = consolidate_task.submit(data)
        data.update(consolidate_result.result())
        logger.info(f"Metadata consolidation completed for {file_name}. Master metadata available: {'master_metadata' in data}")

    # Step 4: AI analysis
    if should_execute_step("ai_analysis", config_key='ai_video_analysis_step'):
        # AI analysis requires a compressed video from the compression step
        compressed_video_path = data.get('compressed_video_path')
        if not compressed_video_path:
            logger.warning(f"Skipping AI Analysis for {file_name}: no compressed video available. Enable and run 'video_compression_step' first.")
        else:
            if task_to_run is None:
                progress_tracker.update_file_step(flow_run_id, file_path, "ai_analysis", 70, "processing")
                if progress_artifact_id: update_progress_artifact(progress_artifact_id, progress=70.0, description="Running AI analysis...")
            
            logger.info(f"Using compressed video file for AI analysis: {compressed_video_path}")
                
            logger.info(f"Executing AI video analysis step for {file_name}")
            ai_analysis_task_obj = ai_video_analysis_step.with_options(name=f"{label_prefix} | ai_video_analysis", tags=["ai_video_analysis_step"])
            ai_analysis_result_future = ai_analysis_task_obj.submit(data)
            data.update(ai_analysis_result_future.result())
            logger.info(f"AI analysis result for {file_name} updated.")

            if should_execute_step("ai_thumbnails", config_key='ai_thumbnail_selection_step'):
                if 'full_ai_analysis_data' not in data or 'thumbnail_paths' not in data:
                    logger.warning(f"Skipping AI Thumbnails for {file_name}: missing 'full_ai_analysis_data' or 'thumbnail_paths'. Run 'ai_analysis' and 'thumbnails' first.")
                else:
                    if task_to_run is None:
                        progress_tracker.update_file_step(flow_run_id, file_path, "ai_thumbnail_selection", 75, "processing")
                        if progress_artifact_id: update_progress_artifact(progress_artifact_id, progress=75.0, description="Selecting AI thumbnails...")
                    logger.info(f"Executing AI thumbnail selection step for {file_name}")
                    ai_thumbnail_task_obj = ai_thumbnail_selection_step.with_options(name=f"{label_prefix} | ai_thumbnail_selection", tags=["ai_thumbnail_selection_step"])
                    ai_thumbnail_result_future = ai_thumbnail_task_obj.submit(data, data_base_dir=data_base_dir)
                    data.update(ai_thumbnail_result_future.result())
                    logger.info(f"AI thumbnail selection result for {file_name} updated.")

    # Step 6: Create output model (Consolidates data, crucial for full pipeline)
    if should_execute_step("create_model"):
        if task_to_run is None:
            progress_tracker.update_file_step(flow_run_id, file_path, "create_model", 80, "processing")
            if progress_artifact_id: update_progress_artifact(progress_artifact_id, progress=80.0, description="Creating output model...")
        logger.info(f"Creating output model for {file_name}. Current data keys: {list(data.keys())}")
        model_result_future = create_model_step.with_options(name=f"{label_prefix} | create_model", tags=["create_model_step"]).submit(data)
        model_creation_output = model_result_future.result()
        if model_creation_output and 'model' in model_creation_output:
            data.update(model_creation_output) # data['model'] will be VideoIngestOutput
            logger.info(f"Output model created for {file_name}: type {type(data.get('model'))}, ID {data.get('model').id if hasattr(data.get('model'), 'id') else 'N/A'}")
        else:
            logger.error(f"create_model_step for {file_name} did not return 'model'.")

    # Step 7: Embedding Generation (moved AFTER model creation)
    if should_execute_step("embeddings", config_key='generate_embeddings_step'):
        if 'model' not in data or not isinstance(data.get('model'), VideoIngestOutput):
            logger.warning(f"Skipping generate_embeddings_step for {file_name}: 'model' (VideoIngestOutput) not in data. Run 'create_model' first.")
        else:
            if task_to_run is None:
                progress_tracker.update_file_step(flow_run_id, file_path, "generate_embeddings", 85, "processing")
                if progress_artifact_id: update_progress_artifact(progress_artifact_id, progress=85.0, description="Generating embeddings...")
            logger.info(f"Executing embedding generation step for {file_name}")
            embedding_task = generate_embeddings_step.with_options(name=f"{label_prefix} | embedding_generation", tags=["embedding_step"])
            embedding_result_future = embedding_task.submit(data)
            data.update(embedding_result_future.result())
            logger.info(f"Embedding generation result for {file_name} updated.")

    # Step 8: Store data in database
    if should_execute_step("db_storage", config_key='database_storage_step'):
        if 'model' not in data or not isinstance(data.get('model'), VideoIngestOutput):
            logger.warning(f"Skipping database_storage_step for {file_name}: 'model' (VideoIngestOutput) not in data. Run 'create_model' first.")
        else:
            if task_to_run is None:
                progress_tracker.update_file_step(flow_run_id, file_path, "database_storage", 95, "processing")
                if progress_artifact_id: update_progress_artifact(progress_artifact_id, progress=95.0, description="Storing data...")
            logger.info(f"Executing database storage step for {file_name}")
            storage_task = database_storage_step.with_options(name=f"{label_prefix} | database_storage", tags=["database_storage_step"])
            storage_result_future = storage_task.submit(data)
            data['database_storage_result'] = storage_result_future.result()
            logger.info(f"Database storage result for {file_name}: {data.get('database_storage_result')}")

    # Step 9: Upload thumbnails
    if should_execute_step("upload_thumbnails", config_key='upload_thumbnails_step'):
        if 'thumbnail_paths' not in data or 'model' not in data or not hasattr(data.get('model'), 'id'):
             logger.warning(f"Skipping upload_thumbnails_step for {file_name}: missing 'thumbnail_paths' or model.id. Run 'thumbnails' and 'create_model' first.")
        else:
            if task_to_run is None:
                progress_tracker.update_file_step(flow_run_id, file_path, "upload_thumbnails", 98, "processing")
                if progress_artifact_id: update_progress_artifact(progress_artifact_id, progress=98.0, description="Uploading thumbnails...")
            logger.info(f"Executing upload_thumbnails step for {file_name}")
            upload_result = upload_thumbnails_step.with_options(
                name=f"{label_prefix} | upload_thumbnails",
                tags=["upload_thumbnails_step"]
            ).submit(data)
            data.update(upload_result.result())

    # Finalization
    if task_to_run is None: # Full pipeline mode
        if 'model' in data and isinstance(data['model'], VideoIngestOutput):
            progress_tracker.update_file_step(flow_run_id, file_path, "completed", 100, "completed")
            if progress_artifact_id: update_progress_artifact(progress_artifact_id, progress=100.0, description="Completed successfully")
            logger.info(f"Pipeline completed successfully for {file_name}, returning model.")
            return data['model'] # Returns VideoIngestOutput or None
        else:
            logger.error(f"Pipeline for {file_name} did not produce a valid VideoIngestOutput model.")
            progress_tracker.update_file_step(flow_run_id, file_path, "failed", 100, "failed")
            if progress_artifact_id: update_progress_artifact(progress_artifact_id, progress=100.0, description="Failed - no valid model")
            return None
    else: # Single task mode
        logger.info(f"Specific task '{task_to_run}' executed for {file_name}. Returning current data dictionary with keys: {list(data.keys())}")
        return data # Returns Dict[str, Any]

@flow
def process_videos_batch_flow(
    file_list: List[str],
    data_base_dir: str,  # Base data directory (e.g., /path/to/data)
    config: Optional[Dict[str, bool]] = None,
    compression_fps: int = DEFAULT_COMPRESSION_CONFIG['fps'],
    compression_bitrate: str = DEFAULT_COMPRESSION_CONFIG['video_bitrate'],
    force_reprocess: bool = False,
    concurrency_limit: int = 2, # This parameter is not directly used by Prefect 3
    batch_uuid: Optional[str] = None,
    task_to_run: Optional[str] = None,  # Added task_to_run parameter
) -> List[Any]:  # Changed return type to List[Any]
    """
    Prefect flow to process a batch of video files.
    If task_to_run is specified, it's passed to each per-file task.
    The return type is List[Any] to accommodate Dict[str, Any] from single task runs.
    """
    logger = get_run_logger()
    if batch_uuid is None:
        batch_uuid = str(uuid.uuid4())
    
    from ..api.progress_tracker import get_progress_tracker
    progress_tracker = get_progress_tracker()
    
    # Initialize file details only if not running a single task mode for the whole batch
    if task_to_run is None:
        for file_path in file_list:
            progress_tracker.update_file_step(batch_uuid, file_path, "pending", 0, "pending")
    
        batch_progress_artifact_id = create_progress_artifact(
            progress=0.0,
            key=f"batch-processing-{batch_uuid}",
            description=f"Processing batch of {len(file_list)} files"
        )
    else:
        batch_progress_artifact_id = None
        logger.info(f"Batch flow called with task_to_run='{task_to_run}'. Progress artifacts will be per-file if enabled in process_video_file_task.")

    # Prepare lists for map - using the correct parameter naming
    data_base_dirs = [data_base_dir] * len(file_list)
    compression_fps_list = [compression_fps] * len(file_list)
    compression_bitrate_list = [compression_bitrate] * len(file_list)
    force_reprocess_list = [force_reprocess] * len(file_list)
    batch_uuid_list = [batch_uuid] * len(file_list)
    config_list = [config] * len(file_list)
    file_indices = list(range(len(file_list)))
    task_to_run_list = [task_to_run] * len(file_list)

    logger.info(f"Mapping process_video_file_task for {len(file_list)} files. task_to_run for map: {task_to_run}")

    # Map the per-file task
    futures = process_video_file_task.map(
        file_path=file_list,
        data_base_dir=data_base_dirs,
        compression_fps=compression_fps_list,
        compression_bitrate=compression_bitrate_list,
        force_reprocess=force_reprocess_list,
        batch_uuid=batch_uuid_list,
        config=config_list,
        file_index=file_indices,
        task_to_run=task_to_run_list
    )
    
    # Process results
    results: List[Any] = [None] * len(futures)
    
    for i, future in enumerate(futures):
        try:
            result = future.result()  # This will block until the future is done
            results[i] = result
            
            # Update batch progress only if we have the artifact
            if batch_progress_artifact_id:
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
    if batch_progress_artifact_id:
        update_progress_artifact(
            batch_progress_artifact_id,
            progress=100.0,
            description=f"Batch completed: {successful_count} successful, {failed_count} failed"
        )
    
    logger.info(f"Batch processing completed: {successful_count} successful, {failed_count} failed")
    
    return results
