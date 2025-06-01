import logging
from typing import Dict, List, Any, Optional
import json
import uuid
from datetime import datetime

# Direct imports from the project's models file
from video_ingest_tool.models import (
    VideoIngestOutput,
    FileInfo,
    VideoDetails, # Renamed from VideoInfo in mapper's placeholder
    VideoCodecDetails,
    VideoResolution,
    VideoColorDetails,
    VideoHDRDetails,
    VideoExposureDetails,
    CameraDetails, # Renamed from CameraInfo
    CameraFocalLength,
    CameraSettings,
    CameraLocation,
    AnalysisDetails, # Renamed from AnalysisInfo
    ComprehensiveAIAnalysis,
    AIAnalysisSummary,
    AudioAnalysis,
    Transcript,
    TranscriptSegment,
    SpeakerAnalysis,
    SoundEvent,
    AudioQuality,
    VisualAnalysis,
    ShotType,
    TechnicalQuality,
    TextAndGraphics,
    DetectedText,
    DetectedLogo,
    KeyframeAnalysis,
    RecommendedKeyframe,
    ContentAnalysis,
    Entities,
    PersonDetail,
    Location as ModelLocation, # Alias to avoid conflict with typing.Location if used
    ObjectOfInterest,
    Activity,
    ContentWarning,
    AudioTrack,
    SubtitleTrack
    # ThumbnailInfo was a placeholder; VideoIngestOutput.thumbnails is List[str]
)

logger = logging.getLogger(__name__)

# TRANSCRIPT_PREVIEW_MAX_LENGTH removed as per user feedback

def _generate_searchable_content(video_output: VideoIngestOutput) -> Optional[str]:
    """
    Generate a comprehensive searchable content string from all video metadata.
    Extracts and flattens nested data from JSONB structures for full-text search.
    
    Args:
        video_output: The processed video data output model
        
    Returns:
        String containing all searchable content, or None if no content is generated.
    """
    content_parts = []
    
    try:
        def _add_part(value: Any):
            if value is not None:
                s_value = str(value).strip()
                if s_value: # Ensure not empty string after stripping
                    content_parts.append(s_value)

        # Basic file information
        if video_output.file_info:
            _add_part(video_output.file_info.file_name)
        
        # Video details
        if video_output.video:
            if video_output.video.resolution:
                width = video_output.video.resolution.width
                height = video_output.video.resolution.height
                if width is not None and height is not None: # Ensure both exist
                    _add_part(f"{width}x{height}")
            
            if video_output.video.frame_rate is not None: # Check for None before f-string
                _add_part(f"{video_output.video.frame_rate}fps")
            
            if video_output.video.codec:
                codec_name = video_output.video.codec.name or ''
                codec_long = video_output.video.codec.format_long_name or video_output.video.codec.codec_long_name or ''
                combined_codec = f"{codec_name} {codec_long}".strip()
                if combined_codec: # Only add if not empty
                    _add_part(combined_codec)
            
            if video_output.video.color:
                _add_part(video_output.video.color.color_primaries)
                _add_part(video_output.video.color.color_space)
            
        # Camera details
        if video_output.camera:
            _add_part(video_output.camera.make)
            _add_part(video_output.camera.model)
            _add_part(video_output.camera.lens_model)
            
            if video_output.camera.focal_length:
                if video_output.camera.focal_length.value_mm is not None:
                    _add_part(f"focal length {video_output.camera.focal_length.value_mm}mm")
                if video_output.camera.focal_length.category: # category is already a string or None
                    _add_part(f"{video_output.camera.focal_length.category} focal length")
                    _add_part(f"{video_output.camera.focal_length.category} shot")
            
            if video_output.camera.settings:
                if video_output.camera.settings.iso is not None:
                    _add_part(f"ISO {video_output.camera.settings.iso}")
                if video_output.camera.settings.shutter_speed is not None:
                     _add_part(f"shutter speed {video_output.camera.settings.shutter_speed}")
                if video_output.camera.settings.f_stop is not None:
                    _add_part(f"f-stop {video_output.camera.settings.f_stop}")
                _add_part(video_output.camera.settings.exposure_mode)
                _add_part(video_output.camera.settings.white_balance)
            
            if video_output.camera.location:
                _add_part(video_output.camera.location.location_name)
                if video_output.camera.location.gps_latitude is not None and video_output.camera.location.gps_longitude is not None:
                    _add_part(f"gps {video_output.camera.location.gps_latitude},{video_output.camera.location.gps_longitude}")
        
        # Analysis and content data
        if video_output.analysis:
            _add_part(video_output.analysis.content_summary)
            if video_output.analysis.content_tags:
                for tag in video_output.analysis.content_tags:
                    _add_part(tag)
            
            if video_output.analysis.ai_analysis:
                ai = video_output.analysis.ai_analysis
                if ai.summary:
                    _add_part(ai.summary.content_category)
                    _add_part(ai.summary.overall)
                    if ai.summary.key_activities:
                        for activity in ai.summary.key_activities:
                            _add_part(activity)
                
                if ai.visual_analysis:
                    visual = ai.visual_analysis
                    if visual.shot_types:
                        for shot in visual.shot_types:
                            if hasattr(shot, 'shot_attributes_ordered') and shot.shot_attributes_ordered:
                                for attr in shot.shot_attributes_ordered:
                                    _add_part(f"{attr} shot")
                            if hasattr(shot, 'description'):
                                _add_part(shot.description)
                    
                    if visual.technical_quality:
                        tq = visual.technical_quality
                        if tq.overall_focus_quality: _add_part(f"{tq.overall_focus_quality} focus")
                        if tq.stability_assessment: _add_part(f"{tq.stability_assessment} stability")
                        if tq.usability_rating: _add_part(f"{tq.usability_rating} usability")
                        if tq.detected_artifacts:
                            for artifact_obj in tq.detected_artifacts: # Assuming detected_artifacts is a list of objects/dicts
                                if isinstance(artifact_obj, dict): # Example if it's a dict
                                    _add_part(artifact_obj.get("name")) # Or however artifact is structured
                                else: # If it's just a list of strings
                                     _add_part(artifact_obj)
                
                if ai.content_analysis:
                    content = ai.content_analysis
                    if content.entities:
                        entities = content.entities
                        if entities.people_details:
                            for person in entities.people_details:
                                _add_part(person.description)
                                _add_part(person.role)
                        
                        if entities.locations:
                            for loc_item in entities.locations:
                                _add_part(loc_item.name)
                                if loc_item.type: _add_part(f"{loc_item.type} location")
                                _add_part(loc_item.description)
                        
                        if entities.objects_of_interest:
                            for obj in entities.objects_of_interest:
                                _add_part(obj.object)
                                if obj.significance and obj.object: _add_part(f"{obj.significance} {obj.object}")
                    
                    if content.activity_summary:
                        for act_item in content.activity_summary:
                            _add_part(act_item.activity)
                            if act_item.importance and act_item.activity: _add_part(f"{act_item.importance} {act_item.activity}")

                if ai.audio_analysis and ai.audio_analysis.transcript:
                    _add_part(ai.audio_analysis.transcript.full_text)

        if not content_parts:
            return None
        return " ".join(content_parts)

    except AttributeError as e: # Keep existing exception handling
        logger.warning(f"AttributeError while generating searchable content for {video_output.id if video_output else 'N/A'}: {e}. Some data might be missing.")
        if not content_parts: # Check again in case some parts were added before error
            return None
        return " ".join(content_parts) # Join whatever was collected
    except Exception as e:
        logger.error(f"Unexpected error in _generate_searchable_content for {video_output.id if video_output else 'N/A'}: {e}", exc_info=True)
        return None


def prepare_clip_data_for_db(
    video_output: VideoIngestOutput,
    # embeddings: Dict[str, List[float]], # Removed: Embeddings are now in video_output.embeddings
    ai_selected_thumbnail_metadata: Optional[List[Dict[str, Any]]] = None
) -> Optional[Dict[str, Any]]:
    """
    Maps data from VideoIngestOutput and AI selected thumbnail metadata
    to a dictionary suitable for insertion into the 'app_data.clips' table.
    Embeddings are sourced from video_output.embeddings.

    Args:
        video_output: The VideoIngestOutput object (which includes an .embeddings attribute).
        ai_selected_thumbnail_metadata: Optional list of dictionaries, where each dict
                                         contains metadata for an AI-selected thumbnail,
                                         including 'path' and 'rank'. This comes from
                                         the output of ai_thumbnail_selection_step.

    Returns:
        A dictionary formatted for the 'app_data.clips' table, or None if essential data is missing.
    """
    if not isinstance(video_output, VideoIngestOutput):
        logger.error("Invalid video_output type provided to mapper.")
        return None
    if not video_output.file_info or not video_output.file_info.file_checksum:
        logger.error("Essential FileInfo or file_checksum missing in VideoIngestOutput.")
        return None

    try:
        data: Dict[str, Any] = {} # Initialize empty and add keys as we go

        # --- Populate data dictionary ---
        data["id"] = str(video_output.id or uuid.uuid4()) # ID is on VideoIngestOutput directly

        # FileInfo mapping
        fi = video_output.file_info
        data["local_path"] = fi.local_path # Now directly from FileInfo.local_path
        data["file_name"] = fi.file_name
        data["file_checksum"] = fi.file_checksum
        data["file_size_bytes"] = fi.file_size_bytes
        data["created_at"] = fi.created_at or datetime.utcnow()
        data["processed_at"] = fi.processed_at or datetime.utcnow()
        data["updated_at"] = datetime.utcnow() # Always set on map

        # VideoDetails mapping (video_output.video)
        vid = video_output.video
        data["duration_seconds"] = vid.duration_seconds
        data["width"] = vid.resolution.width if vid.resolution else None
        data["height"] = vid.resolution.height if vid.resolution else None
        data["frame_rate"] = vid.frame_rate
        data["codec"] = vid.codec.name if vid.codec else None
        data["container"] = vid.container
        # technical_metadata: Use the VideoCodecDetails as JSON
        data["technical_metadata"] = vid.codec.model_dump_json() if vid.codec else None


        # CameraDetails mapping (video_output.camera)
        cam = video_output.camera
        data["camera_make"] = cam.make
        data["camera_model"] = cam.model
        data["camera_details"] = cam.model_dump_json() # Entire CameraDetails object as JSON

        # AnalysisDetails and ComprehensiveAIAnalysis mapping
        analysis = video_output.analysis
        data["content_summary"] = analysis.content_summary
        data["content_tags"] = analysis.content_tags

        if analysis.ai_analysis:
            ai = analysis.ai_analysis
            data["content_category"] = ai.summary.content_category if ai.summary else None
            
            if ai.audio_analysis and ai.audio_analysis.transcript:
                tr = ai.audio_analysis.transcript
                data["full_transcript"] = tr.full_text
                # Populate transcript_preview with full_text if no other source
                data["transcript_preview"] = tr.full_text
                
                if tr.segments is not None: # Check for None explicitly
                    data["transcript_segments_json"] = json.dumps([s.model_dump() for s in tr.segments]) # Handles empty list to "[]"
                else:
                    data["transcript_segments_json"] = None
            
            if ai.visual_analysis and ai.visual_analysis.keyframe_analysis:
                # primary_thumbnail_path: derived from ai_selected_thumbnail_metadata
                primary_thumb_path = None
                if ai_selected_thumbnail_metadata:
                    # Sort by rank (ensure rank is integer for proper sort if not already)
                    try:
                        sorted_thumbs = sorted(
                            [thumb for thumb in ai_selected_thumbnail_metadata if thumb.get("path")],
                            key=lambda x: int(x.get("rank", 999)) # Use a large default for items without rank or uncastable rank
                        )
                        if sorted_thumbs:
                            primary_thumb_path = sorted_thumbs[0].get("path")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Could not sort AI thumbnails by rank or rank is invalid: {e}")
                
                data["primary_thumbnail_path"] = primary_thumb_path
            
                # ai_selected_thumbnails_json: Use the provided ai_selected_thumbnail_metadata
                # This metadata already includes the local paths from the ai_thumbnail_selection_step.
                if ai_selected_thumbnail_metadata:
                    data["ai_selected_thumbnails_json"] = json.dumps(ai_selected_thumbnail_metadata)
                else:
                    # Fallback to original recommended_keyframes if processed metadata isn't available,
                    # though this won't have paths. This case should ideally not happen if the flow is correct.
                    ka = ai.visual_analysis.keyframe_analysis # ka is already defined if we are in this block
                    if ka and ka.recommended_keyframes:
                         logger.warning("Using original recommended_keyframes for ai_selected_thumbnails_json as processed metadata was not provided. Paths will be missing.")
                         data["ai_selected_thumbnails_json"] = json.dumps([kf.model_dump() for kf in ka.recommended_keyframes])
                    else:
                         data["ai_selected_thumbnails_json"] = None
            
            data["full_ai_analysis_json"] = ai.model_dump_json()
        else: # Handle case where ai_analysis might be None
            data["content_category"] = None
            data["full_transcript"] = None
            data["transcript_preview"] = None
            data["transcript_segments_json"] = None
            data["primary_thumbnail_path"] = None
            data["ai_selected_thumbnails_json"] = None
            data["full_ai_analysis_json"] = None


        # Top-level audio_tracks and subtitle_tracks from VideoIngestOutput
        if video_output.audio_tracks is not None:
            data["audio_tracks"] = json.dumps([track.model_dump() for track in video_output.audio_tracks])
        else:
            data["audio_tracks"] = None
        
        if video_output.subtitle_tracks is not None:
            data["subtitle_tracks"] = json.dumps([track.model_dump() for track in video_output.subtitle_tracks])
        else:
            data["subtitle_tracks"] = None

        # Thumbnails (List[str] from VideoIngestOutput.thumbnails)
        data["thumbnails"] = video_output.thumbnails # This is already List[str]

        # Searchable content
        data["searchable_content"] = _generate_searchable_content(video_output)

        # Embeddings - Sourced from video_output.embeddings model
        if video_output.embeddings:
            data["summary_embedding"] = video_output.embeddings.summary_embedding
            data["keyword_embedding"] = video_output.embeddings.keyword_embedding
            data["thumbnail_1_embedding"] = video_output.embeddings.thumbnail_1_embedding
            data["thumbnail_2_embedding"] = video_output.embeddings.thumbnail_2_embedding
            data["thumbnail_3_embedding"] = video_output.embeddings.thumbnail_3_embedding
        else: # Ensure keys exist even if video_output.embeddings is None
            data["summary_embedding"] = None
            data["keyword_embedding"] = None
            data["thumbnail_1_embedding"] = None
            data["thumbnail_2_embedding"] = None
            data["thumbnail_3_embedding"] = None
        
        # Ensure all expected columns are present in the output dictionary, even if None
        clip_table_columns = [
            "id", "local_path", "file_name", "file_checksum", "file_size_bytes", # Removed file_path
            "duration_seconds", "created_at", "processed_at", "updated_at", "width", "height",
            "frame_rate", "codec", "container", "camera_make", "camera_model", "camera_details",
            "content_category", "content_summary", "content_tags", "searchable_content",
            "full_transcript", "transcript_preview", "transcript_segments_json", "thumbnails",
            "primary_thumbnail_path", "ai_selected_thumbnails_json", "technical_metadata",
            "audio_tracks", "subtitle_tracks", "full_ai_analysis_json", "summary_embedding",
            "keyword_embedding", "thumbnail_1_embedding", "thumbnail_2_embedding", "thumbnail_3_embedding"
        ]
        final_data = {col: data.get(col) for col in clip_table_columns}


        logger.debug(f"Prepared clip data for DB: {final_data.get('id')}")
        return final_data

    except AttributeError as e:
        logger.error(f"AttributeError during data mapping for checksum {video_output.file_info.file_checksum if video_output.file_info else 'N/A'}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error during data mapping for checksum {video_output.file_info.file_checksum if video_output.file_info else 'N/A'}: {e}", exc_info=True)
        return None