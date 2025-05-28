"""
Database storage pipeline step for Supabase integration.
"""

import os
import json
from typing import Dict, Any, Optional, List, Union
import structlog

from .auth import AuthManager
from .models import VideoIngestOutput

logger = structlog.get_logger(__name__)

def generate_searchable_content(video_data: VideoIngestOutput) -> str:
    """
    Generate a comprehensive searchable content string from all video metadata.
    Extracts and flattens nested data from JSONB structures for full-text search.
    
    Args:
        video_data: The processed video data output model
        
    Returns:
        String containing all searchable content
    """
    content_parts = []
    
    # Basic file information
    content_parts.append(f"{video_data.file_info.file_name}")
    
    # Video details
    if video_data.video:
        if video_data.video.resolution:
            content_parts.append(f"{video_data.video.resolution.width}x{video_data.video.resolution.height}")
            content_parts.append(f"{video_data.video.resolution.resolution_name}")
        
        if video_data.video.frame_rate:
            content_parts.append(f"{video_data.video.frame_rate}fps")
        
        if video_data.video.codec:
            content_parts.append(f"{video_data.video.codec.name} {video_data.video.codec.long_name}")
        
        if video_data.video.color:
            content_parts.append(f"{video_data.video.color.color_primaries}")
            content_parts.append(f"{video_data.video.color.color_space}")
        
        if video_data.video.exposure:
            content_parts.append(f"{video_data.video.exposure.overall_exposure}")
    
    # Camera details - Extract all camera settings as individual terms
    if video_data.camera:
        # Camera make and model
        if video_data.camera.make:
            content_parts.append(f"{video_data.camera.make}")
        if video_data.camera.model:
            content_parts.append(f"{video_data.camera.model}")
        if video_data.camera.lens_model:
            content_parts.append(f"{video_data.camera.lens_model}")
        
        # Focal length details - separate value and category
        if video_data.camera.focal_length:
            if video_data.camera.focal_length.value_mm:
                content_parts.append(f"focal length {video_data.camera.focal_length.value_mm}mm")
            if video_data.camera.focal_length.category:
                content_parts.append(f"{video_data.camera.focal_length.category} focal length")
                content_parts.append(f"{video_data.camera.focal_length.category} shot")
        
        # Camera settings
        if video_data.camera.settings:
            if video_data.camera.settings.iso:
                content_parts.append(f"ISO {video_data.camera.settings.iso}")
            if video_data.camera.settings.shutter_speed:
                content_parts.append(f"shutter speed {video_data.camera.settings.shutter_speed}")
            if video_data.camera.settings.f_stop:
                content_parts.append(f"f-stop {video_data.camera.settings.f_stop}")
            if video_data.camera.settings.exposure_mode:
                content_parts.append(f"{video_data.camera.settings.exposure_mode} exposure")
            if video_data.camera.settings.white_balance:
                content_parts.append(f"{video_data.camera.settings.white_balance} white balance")
        
        # Location data
        if video_data.camera.location:
            if video_data.camera.location.location_name:
                content_parts.append(f"{video_data.camera.location.location_name}")
            if video_data.camera.location.gps_latitude and video_data.camera.location.gps_longitude:
                content_parts.append(f"gps {video_data.camera.location.gps_latitude},{video_data.camera.location.gps_longitude}")
    
    # Analysis and content data
    if video_data.analysis:
        if video_data.analysis.content_summary:
            content_parts.append(video_data.analysis.content_summary)
        
        if video_data.analysis.content_tags:
            for tag in video_data.analysis.content_tags:
                content_parts.append(tag)
        
        # AI analysis
        if video_data.analysis.ai_analysis:
            # Summary
            if video_data.analysis.ai_analysis.summary:
                summary = video_data.analysis.ai_analysis.summary
                if summary.content_category:
                    content_parts.append(summary.content_category)
                if summary.overall:
                    content_parts.append(summary.overall)
                if summary.key_activities:
                    for activity in summary.key_activities:
                        content_parts.append(activity)
            
            # Visual analysis
            if video_data.analysis.ai_analysis.visual_analysis:
                visual = video_data.analysis.ai_analysis.visual_analysis
                
                # Shot types
                if visual.shot_types:
                    for shot in visual.shot_types:
                        content_parts.append(f"{shot.shot_type} shot")
                        if shot.description:
                            content_parts.append(shot.description)
                
                # Technical quality
                if visual.technical_quality:
                    tq = visual.technical_quality
                    if tq.overall_focus_quality:
                        content_parts.append(f"{tq.overall_focus_quality} focus")
                    if tq.stability_assessment:
                        content_parts.append(f"{tq.stability_assessment} stability")
                    if tq.usability_rating:
                        content_parts.append(f"{tq.usability_rating} usability")
                    if tq.detected_artifacts:
                        for artifact in tq.detected_artifacts:
                            content_parts.append(f"{artifact} artifact")
            
            # Content analysis
            if video_data.analysis.ai_analysis.content_analysis:
                content = video_data.analysis.ai_analysis.content_analysis
                
                # Entities
                if content.entities:
                    entities = content.entities
                    if entities.people_details:
                        for person in entities.people_details:
                            if person.description:
                                content_parts.append(person.description)
                            if person.role:
                                content_parts.append(person.role)
                    
                    if entities.locations:
                        for location in entities.locations:
                            if location.name:
                                content_parts.append(location.name)
                            if location.type:
                                content_parts.append(f"{location.type} location")
                            if location.description:
                                content_parts.append(location.description)
                    
                    if entities.objects_of_interest:
                        for obj in entities.objects_of_interest:
                            if obj.object:
                                content_parts.append(obj.object)
                            if obj.significance:
                                content_parts.append(f"{obj.significance} {obj.object}")
                
                # Activities
                if content.activity_summary:
                    for activity in content.activity_summary:
                        if activity.activity:
                            content_parts.append(activity.activity)
                            if activity.importance:
                                content_parts.append(f"{activity.importance} {activity.activity}")
    
    # Join all parts, filter out empty strings and None values
    searchable_content = " ".join([part for part in content_parts if part])
    return searchable_content

def store_video_in_database(
    video_data: VideoIngestOutput,
    logger=None,
    ai_thumbnail_metadata=None
) -> Dict[str, Any]:
    """
    Store video data in the Supabase database.
    
    Args:
        video_data: The processed video data output model
        logger: Optional logger instance
        ai_thumbnail_metadata: Metadata for AI-selected thumbnails
        
    Returns:
        Dict with storage results including clip_id
    """
    auth_manager = AuthManager()
    client = auth_manager.get_authenticated_client()
    
    if not client:
        raise ValueError("Not authenticated")
    
    try:
        # Get current user ID
        user_response = client.auth.get_user()
        if not user_response.user or not user_response.user.id:
            raise ValueError("Unable to get authenticated user ID")
        user_id = user_response.user.id
        
        # Generate comprehensive searchable content
        searchable_content = generate_searchable_content(video_data)
        if logger and searchable_content:
            logger.info(f"Generated searchable content ({len(searchable_content)} chars)")
        
        # Prepare clip data
        clip_data = {
            "user_id": user_id,
            "file_path": video_data.file_info.file_path,
            "local_path": os.path.abspath(video_data.file_info.file_path),
            "file_name": video_data.file_info.file_name,
            "file_checksum": video_data.file_info.file_checksum,
            "file_size_bytes": video_data.file_info.file_size_bytes,
            "duration_seconds": video_data.video.duration_seconds,
            "created_at": video_data.file_info.created_at.isoformat() if video_data.file_info.created_at else None,
            "processed_at": video_data.file_info.processed_at.isoformat(),
            
            # Technical metadata
            "width": video_data.video.resolution.width if video_data.video.resolution else None,
            "height": video_data.video.resolution.height if video_data.video.resolution else None,
            "frame_rate": video_data.video.frame_rate,
            "codec": video_data.video.codec.name if video_data.video.codec else None,
            "camera_make": video_data.camera.make if video_data.camera else None,
            "camera_model": video_data.camera.model if video_data.camera else None,
            "container": video_data.video.container,
            
            # AI analysis summaries
            "content_category": None,
            "content_summary": video_data.analysis.content_summary if video_data.analysis else None,
            "content_tags": video_data.analysis.content_tags if video_data.analysis else [],
            
            # Comprehensive searchable content for full-text search
            "searchable_content": searchable_content,
            
            # Transcript data
            "full_transcript": None,
            "transcript_preview": None,
            
            # Complex metadata as JSONB
            "technical_metadata": {
                "codec_details": video_data.video.codec.model_dump() if video_data.video.codec else {},
                "color_details": video_data.video.color.model_dump() if video_data.video.color else {},
                "exposure_details": video_data.video.exposure.model_dump() if video_data.video.exposure else {}
            },
            "camera_details": video_data.camera.model_dump() if video_data.camera else {},
            "audio_tracks": [track.model_dump() for track in video_data.audio_tracks] if video_data.audio_tracks else [],
            "subtitle_tracks": [track.model_dump() for track in video_data.subtitle_tracks] if video_data.subtitle_tracks else [],
            "thumbnails": video_data.thumbnails if video_data.thumbnails else [],
            # Initialize all_thumbnail_urls as empty array if not already present
            "all_thumbnail_urls": []
        }
        
        # Add AI thumbnail metadata if available
        if ai_thumbnail_metadata:
            # Process AI thumbnails into the all_thumbnail_urls JSONB array
            ai_thumbnails_formatted = []
            for thumbnail in ai_thumbnail_metadata:
                rank = thumbnail.get('rank')
                path = thumbnail.get('path')
                timestamp = thumbnail.get('timestamp')
                description = thumbnail.get('description', '')
                reason = thumbnail.get('reason', '')
                
                if path and rank:
                    # Format thumbnail data (URLs will be added by thumbnail_upload step)
                    filename = os.path.basename(path)
                    ai_thumbnails_formatted.append({
                        "filename": filename,
                        "is_ai_selected": True,
                        "rank": rank,
                        "timestamp": timestamp,
                        "description": description,
                        "reason": reason
                    })
        
        # Extract AI analysis data if available
        if video_data.analysis and video_data.analysis.ai_analysis:
            ai_analysis = video_data.analysis.ai_analysis
            
            # Extract content category and summary
            if ai_analysis.summary:
                clip_data["content_category"] = ai_analysis.summary.content_category
            
            # Extract transcript data
            if ai_analysis.audio_analysis and ai_analysis.audio_analysis.transcript:
                transcript = ai_analysis.audio_analysis.transcript
                clip_data["full_transcript"] = transcript.full_text
                # Set transcript preview (first 500 chars)
                if transcript.full_text:
                    clip_data["transcript_preview"] = transcript.full_text[:500]
        
        # Check if this is a force reprocess - if so, check for existing clip with same checksum
        existing_clip_id = None
        if clip_data.get('file_checksum'):
            existing_result = client.table('clips').select('id').eq('file_checksum', clip_data['file_checksum']).execute()
            if existing_result.data:
                existing_clip_id = existing_result.data[0]['id']
                if logger:
                    logger.info(f"Found existing clip for reprocessing: {existing_clip_id}")
        
        if existing_clip_id:
            # Update existing clip
            clip_result = client.table('clips').update(clip_data).eq('id', existing_clip_id).execute()
            clip_id = existing_clip_id
            if logger:
                logger.info(f"Updated existing clip in database: {clip_id}")
        else:
            # Insert new clip
            clip_result = client.table('clips').insert(clip_data).execute()
            clip_id = clip_result.data[0]['id']
            if logger:
                logger.info(f"Stored new clip in database: {clip_id}")
        
        # Prepare and store AI analysis data separately if available
        if video_data.analysis and video_data.analysis.ai_analysis:
            analysis_data = {
                "clip_id": clip_id,
                "user_id": user_id,
                "analysis_type": "ai",
                "analysis_scope": "full_clip",
                "ai_analysis": video_data.analysis.ai_analysis.model_dump()
            }
            
            if existing_clip_id:
                # Delete existing analysis and insert new one
                client.table('analysis').delete().eq('clip_id', clip_id).execute()
                client.table('analysis').insert(analysis_data).execute()
                if logger:
                    logger.info(f"Updated AI analysis for clip: {clip_id}")
            else:
                client.table('analysis').insert(analysis_data).execute()
                if logger:
                    logger.info(f"Stored AI analysis for clip: {clip_id}")
        
        return {
            'clip_id': clip_id,
            'stored_in_database': True,
            'database_url': f"https://supabase.com/dashboard/project/{os.getenv('SUPABASE_PROJECT_ID', 'unknown')}"
        }
        
    except Exception as e:
        if logger:
            logger.error(f"Failed to store video in database: {str(e)}")
        raise