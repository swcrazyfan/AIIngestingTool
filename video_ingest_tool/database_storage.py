"""
Database storage pipeline step for Supabase integration.
"""

import os
from typing import Dict, Any, Optional
import structlog

from .auth import AuthManager
from .models import VideoIngestOutput

logger = structlog.get_logger(__name__)

def store_video_in_database(
    video_data: VideoIngestOutput,
    logger=None
) -> Dict[str, Any]:
    """
    Store processed video data in Supabase database.
    
    Args:
        video_data: Processed video data
        logger: Optional logger
        
    Returns:
        Dict with storage results
    """
    auth_manager = AuthManager()
    client = auth_manager.get_authenticated_client()
    
    if not client:
        raise ValueError("Authentication required for database storage")
    
    try:
        # Get current user ID
        user_response = client.auth.get_user()
        if not user_response.user or not user_response.user.id:
            raise ValueError("Unable to get authenticated user ID")
        user_id = user_response.user.id
        
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
            "thumbnails": video_data.thumbnails if video_data.thumbnails else []
        }
        
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
        
        # Store transcript if available
        if (video_data.analysis and video_data.analysis.ai_analysis and 
            video_data.analysis.ai_analysis.audio_analysis and 
            video_data.analysis.ai_analysis.audio_analysis.transcript):
            
            transcript = video_data.analysis.ai_analysis.audio_analysis.transcript
            speaker_analysis = video_data.analysis.ai_analysis.audio_analysis.speaker_analysis
            sound_events = video_data.analysis.ai_analysis.audio_analysis.sound_events
            
            transcript_data = {
                "clip_id": clip_id,
                "user_id": user_id,
                "full_text": transcript.full_text or "",
                "segments": [seg.model_dump() for seg in transcript.segments] if transcript.segments else [],
                "speakers": [speaker.model_dump() for speaker in speaker_analysis.speakers] if speaker_analysis and speaker_analysis.speakers else [],
                "non_speech_events": [event.model_dump() for event in sound_events] if sound_events else []
            }
            
            if existing_clip_id:
                # Delete existing transcript and insert new one
                client.table('transcripts').delete().eq('clip_id', clip_id).execute()
                client.table('transcripts').insert(transcript_data).execute()
                if logger:
                    logger.info(f"Updated transcript for clip: {clip_id}")
            else:
                client.table('transcripts').insert(transcript_data).execute()
                if logger:
                    logger.info(f"Stored transcript for clip: {clip_id}")
        
        # Store AI analysis
        if video_data.analysis and video_data.analysis.ai_analysis:
            ai_analysis = video_data.analysis.ai_analysis
            
            analysis_data = {
                "clip_id": clip_id,
                "user_id": user_id,
                "analysis_type": "comprehensive",
                "analysis_scope": "full_clip",
                "ai_model": "gemini-flash-2.5",
                "content_category": ai_analysis.summary.content_category if ai_analysis.summary else None,
                "usability_rating": None,
                "speaker_count": 0,
                "visual_analysis": ai_analysis.visual_analysis.model_dump() if ai_analysis.visual_analysis else None,
                "audio_analysis": ai_analysis.audio_analysis.model_dump() if ai_analysis.audio_analysis else None,
                "content_analysis": ai_analysis.content_analysis.model_dump() if ai_analysis.content_analysis else None,
                "analysis_summary": ai_analysis.summary.model_dump() if ai_analysis.summary else None,
                "analysis_file_path": ai_analysis.analysis_file_path
            }
            
            # Extract usability rating if available
            if (ai_analysis.visual_analysis and 
                ai_analysis.visual_analysis.technical_quality and 
                ai_analysis.visual_analysis.technical_quality.usability_rating):
                analysis_data["usability_rating"] = ai_analysis.visual_analysis.technical_quality.usability_rating
            
            # Extract speaker count if available
            if (ai_analysis.audio_analysis and 
                ai_analysis.audio_analysis.speaker_analysis and 
                ai_analysis.audio_analysis.speaker_analysis.speaker_count):
                analysis_data["speaker_count"] = ai_analysis.audio_analysis.speaker_analysis.speaker_count
            
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