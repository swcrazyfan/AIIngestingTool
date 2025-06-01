"""
Create Pydantic models from processed video data.

This module handles the creation of structured Pydantic models
from all collected video metadata and analysis results.
"""

import os
import datetime
import uuid
from typing import Any, Dict, List, Optional
from ...models import (
    VideoIngestOutput, FileInfo, VideoCodecDetails, VideoResolution, VideoHDRDetails,
    VideoColorDetails, VideoExposureDetails, VideoDetails, CameraFocalLength,
    CameraSettings, CameraLocation, CameraDetails, AnalysisDetails,
    AudioTrack, SubtitleTrack, ComprehensiveAIAnalysis, AIAnalysisSummary,
    VisualAnalysis, AudioAnalysis, ContentAnalysis, ShotType, TechnicalQuality,
    TextAndGraphics, DetectedText, DetectedLogo, KeyframeAnalysis, RecommendedKeyframe,
    Transcript, TranscriptSegment, SpeakerAnalysis, Speaker, SoundEvent, AudioQuality,
    Entities, PersonDetail, Location, ObjectOfInterest, Activity, ContentWarning
)
from ...utils import calculate_aspect_ratio_str
from prefect import task

@task
def create_model_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Create Pydantic model from processed data.
    
    Args:
        data: Pipeline data containing all processed information
        logger: Optional logger
        
    Returns:
        Dict with the output model
    """
    file_path = data.get('file_path')
    file_name = data.get('file_name')
    checksum = data.get('checksum')
    file_size_bytes = data.get('file_size_bytes')
    processed_at_time = datetime.datetime.now()
    
    master_metadata = data.get('master_metadata', {})
    thumbnail_paths = data.get('thumbnail_paths', [])
    exposure_data = data.get('exposure_data', {})
    audio_tracks = data.get('audio_tracks', [])
    subtitle_tracks = data.get('subtitle_tracks', [])
    ai_analysis_summary = data.get('ai_analysis_summary', {})
    ai_analysis_file_path = data.get('ai_analysis_file_path')
    
    # Create complete AI analysis object for main JSON
    ai_analysis_obj = None
    if ai_analysis_summary:
        try:
            # Get the full AI analysis data from the step
            full_ai_analysis = data.get('full_ai_analysis_data', {})
            
            # Create the complete analysis objects if data is available
            visual_analysis_obj = None
            audio_analysis_obj = None
            content_analysis_obj = None
            
            if full_ai_analysis.get('visual_analysis'):
                visual_data = full_ai_analysis['visual_analysis']
                
                # Create shot types
                shot_types = []
                for shot in visual_data.get('shot_types', []):
                    shot_types.append(ShotType(
                        timestamp=shot.get('timestamp', '00:00:000'),
                        duration_seconds=shot.get('duration_seconds'),
                        shot_attributes_ordered=shot.get('shot_attributes_ordered', []),
                        description=shot.get('description', ''),
                        confidence=shot.get('confidence')
                    ))
                
                # Create technical quality
                tech_quality_obj = None
                if visual_data.get('technical_quality'):
                    tq = visual_data['technical_quality']
                    tech_quality_obj = TechnicalQuality(
                        overall_focus_quality=tq.get('overall_focus_quality'),
                        stability_assessment=tq.get('stability_assessment'),
                        detected_artifacts=tq.get('detected_artifacts', []),
                        usability_rating=tq.get('usability_rating')
                    )
                
                # Create text and graphics
                text_graphics_obj = None
                if visual_data.get('text_and_graphics'):
                    tg = visual_data['text_and_graphics']
                    detected_text = []
                    for text in tg.get('detected_text', []):
                        detected_text.append(DetectedText(
                            timestamp=text.get('timestamp', '00:00:000'),
                            text_content=text.get('text_content'),
                            text_type=text.get('text_type'),
                            readability=text.get('readability')
                        ))
                    
                    detected_logos = []
                    for logo in tg.get('detected_logos_icons', []):
                        detected_logos.append(DetectedLogo(
                            timestamp=logo.get('timestamp', '00:00:000'),
                            element_type=logo.get('element_type', ''),
                            size=logo.get('size')
                        ))
                    
                    text_graphics_obj = TextAndGraphics(
                        detected_text=detected_text,
                        detected_logos_icons=detected_logos
                    )
                
                # Create keyframe analysis
                keyframe_analysis_obj = None
                if visual_data.get('keyframe_analysis'):
                    ka = visual_data['keyframe_analysis']
                    recommended_keyframes = []
                    for kf in ka.get('recommended_keyframes', []):
                        recommended_keyframes.append(RecommendedKeyframe(
                            timestamp=kf.get('timestamp', '00:00:000'),
                            reason=kf.get('reason', ''),
                            visual_quality=kf.get('visual_quality', '')
                        ))
                    
                    keyframe_analysis_obj = KeyframeAnalysis(
                        recommended_keyframes=recommended_keyframes
                    )
                
                visual_analysis_obj = VisualAnalysis(
                    shot_types=shot_types,
                    technical_quality=tech_quality_obj,
                    text_and_graphics=text_graphics_obj,
                    keyframe_analysis=keyframe_analysis_obj
                )
            
            if full_ai_analysis.get('audio_analysis'):
                audio_data = full_ai_analysis['audio_analysis']
                
                # Create transcript
                transcript_obj = None
                if audio_data.get('transcript'):
                    t = audio_data['transcript']
                    segments = []
                    for seg in t.get('segments', []):
                        segments.append(TranscriptSegment(
                            timestamp=seg.get('timestamp', '00:00:000'),
                            speaker=seg.get('speaker'),
                            text=seg.get('text', '')
                        ))
                    
                    transcript_obj = Transcript(
                        full_text=t.get('full_text'),
                        segments=segments
                    )
                
                # Create speaker analysis
                speaker_analysis_obj = None
                if audio_data.get('speaker_analysis'):
                    sa = audio_data['speaker_analysis']
                    speakers = []
                    for speaker in sa.get('speakers', []):
                        speakers.append(Speaker(
                            speaker_id=speaker.get('speaker_id', ''),
                            speaking_time_seconds=speaker.get('speaking_time_seconds', 0.0),
                            segments_count=speaker.get('segments_count')
                        ))
                    
                    speaker_analysis_obj = SpeakerAnalysis(
                        speaker_count=sa.get('speaker_count', 0),
                        speakers=speakers
                    )
                
                # Create sound events
                sound_events = []
                for event in audio_data.get('sound_events', []):
                    sound_events.append(SoundEvent(
                        timestamp=event.get('timestamp', '00:00:000'),
                        event_type=event.get('event_type', ''),
                        description=event.get('description'),
                        duration_seconds=event.get('duration_seconds'),
                        prominence=event.get('prominence')
                    ))
                
                # Create audio quality
                audio_quality_obj = None
                if audio_data.get('audio_quality'):
                    aq = audio_data['audio_quality']
                    audio_quality_obj = AudioQuality(
                        clarity=aq.get('clarity'),
                        background_noise_level=aq.get('background_noise_level'),
                        dialogue_intelligibility=aq.get('dialogue_intelligibility')
                    )
                
                audio_analysis_obj = AudioAnalysis(
                    transcript=transcript_obj,
                    speaker_analysis=speaker_analysis_obj,
                    sound_events=sound_events,
                    audio_quality=audio_quality_obj
                )
            
            if full_ai_analysis.get('content_analysis'):
                content_data = full_ai_analysis['content_analysis']
                
                # Create entities
                entities_obj = None
                if content_data.get('entities'):
                    e = content_data['entities']
                    
                    people_details = []
                    for person in e.get('people_details', []):
                        people_details.append(PersonDetail(
                            description=person.get('description'),
                            role=person.get('role'),
                            visibility_duration=person.get('visibility_duration')
                        ))
                    
                    locations = []
                    for location in e.get('locations', []):
                        locations.append(Location(
                            name=location.get('name', ''),
                            type=location.get('type', ''),
                            description=location.get('description')
                        ))
                    
                    objects_of_interest = []
                    for obj in e.get('objects_of_interest', []):
                        objects_of_interest.append(ObjectOfInterest(
                            object=obj.get('object', ''),
                            significance=obj.get('significance', ''),
                            timestamp=obj.get('timestamp')
                        ))
                    
                    entities_obj = Entities(
                        people_count=e.get('people_count', 0),
                        people_details=people_details,
                        locations=locations,
                        objects_of_interest=objects_of_interest
                    )
                
                # Create activity summary
                activities = []
                for activity in content_data.get('activity_summary', []):
                    activities.append(Activity(
                        activity=activity.get('activity', ''),
                        timestamp=activity.get('timestamp'),
                        duration=activity.get('duration'),
                        importance=activity.get('importance', '')
                    ))
                
                # Create content warnings
                content_warnings = []
                for warning in content_data.get('content_warnings', []):
                    content_warnings.append(ContentWarning(
                        type=warning.get('type', ''),
                        description=warning.get('description')
                    ))
                
                content_analysis_obj = ContentAnalysis(
                    entities=entities_obj,
                    activity_summary=activities,
                    content_warnings=content_warnings
                )
            
            # Create AI analysis summary
            summary_obj = AIAnalysisSummary(
                overall=ai_analysis_summary.get('overall_summary'),
                key_activities=full_ai_analysis.get('summary', {}).get('key_activities', []),
                content_category=ai_analysis_summary.get('content_category')
            ) if ai_analysis_summary.get('overall_summary') or ai_analysis_summary.get('content_category') else None
            
            ai_analysis_obj = ComprehensiveAIAnalysis(
                summary=summary_obj,
                visual_analysis=visual_analysis_obj,
                audio_analysis=audio_analysis_obj,
                content_analysis=content_analysis_obj,
                analysis_file_path=ai_analysis_file_path
            )
        except Exception as e:
            if logger:
                logger.warning(f"Failed to create complete AI analysis: {str(e)}")
                logger.debug(f"AI analysis data available: {list(data.keys())}")
            ai_analysis_obj = None
    
    # Create the Pydantic models
    file_info_obj = FileInfo(
        file_path=file_path,
        file_name=file_name,
        file_checksum=checksum,
        file_size_bytes=file_size_bytes,
        created_at=master_metadata.get('created_at'),
        processed_at=processed_at_time
    )

    video_codec_details_obj = VideoCodecDetails(
        name=master_metadata.get('codec'),
        profile=master_metadata.get('profile'),
        level=master_metadata.get('level'),
        bitrate_kbps=master_metadata.get('bit_rate_kbps'),
        bit_depth=master_metadata.get('bit_depth'),
        chroma_subsampling=master_metadata.get('chroma_subsampling'),
        pixel_format=master_metadata.get('pixel_format'),
        bitrate_mode=master_metadata.get('bitrate_mode'),
        cabac=master_metadata.get('cabac'),
        ref_frames=master_metadata.get('ref_frames'),
        gop_size=master_metadata.get('gop_size'),
        scan_type=master_metadata.get('scan_type'),
        field_order=master_metadata.get('field_order'),
        format_name=master_metadata.get('format_name'),
        format_long_name=master_metadata.get('format_long_name'),
        codec_long_name=master_metadata.get('codec_long_name'),
        file_size_bytes=master_metadata.get('file_size_bytes')
    )

    video_resolution_obj = VideoResolution(
        width=master_metadata.get('width'),
        height=master_metadata.get('height'),
        aspect_ratio=calculate_aspect_ratio_str(master_metadata.get('width'), master_metadata.get('height'))
    )

    video_hdr_details_obj = VideoHDRDetails(
        is_hdr=bool(master_metadata.get('hdr_format')),
        format=master_metadata.get('hdr_format'),
        master_display=master_metadata.get('master_display'),
        max_cll=master_metadata.get('max_cll'),
        max_fall=master_metadata.get('max_fall')
    )

    video_color_details_obj = VideoColorDetails(
        color_space=master_metadata.get('color_space'),
        color_primaries=master_metadata.get('color_primaries'),
        transfer_characteristics=master_metadata.get('transfer_characteristics'),
        matrix_coefficients=master_metadata.get('matrix_coefficients'),
        color_range=master_metadata.get('color_range'),
        hdr=video_hdr_details_obj
    )

    video_exposure_details_obj = VideoExposureDetails(
        warning=exposure_data.get('exposure_warning'),
        stops=exposure_data.get('exposure_stops'),
        overexposed_percentage=exposure_data.get('overexposed_percentage'),
        underexposed_percentage=exposure_data.get('underexposed_percentage')
    )

    video_details_obj = VideoDetails(
        duration_seconds=master_metadata.get('duration_seconds'),
        codec=video_codec_details_obj,
        container=master_metadata.get('container'),
        resolution=video_resolution_obj,
        frame_rate=master_metadata.get('frame_rate'),
        color=video_color_details_obj,
        exposure=video_exposure_details_obj
    )

    audio_track_models = [AudioTrack(**track) for track in audio_tracks]
    subtitle_track_models = [SubtitleTrack(**track) for track in subtitle_tracks]

    camera_focal_length_obj = CameraFocalLength(
        value_mm=master_metadata.get('focal_length_mm'),
        category=master_metadata.get('focal_length_category'),
        source=master_metadata.get('focal_length_source')  # Will be either 'EXIF', 'AI', or None
    )
    
    if logger:
        logger.info("Creating focal length object",
                   source=master_metadata.get('focal_length_source'),
                   category=master_metadata.get('focal_length_category'),
                   value_mm=master_metadata.get('focal_length_mm'))

    camera_settings_obj = CameraSettings(
        iso=master_metadata.get('iso'),
        shutter_speed=master_metadata.get('shutter_speed'),
        f_stop=master_metadata.get('f_stop'),
        exposure_mode=master_metadata.get('exposure_mode'),
        white_balance=master_metadata.get('white_balance')
    )

    camera_location_obj = CameraLocation(
        gps_latitude=master_metadata.get('gps_latitude'),
        gps_longitude=master_metadata.get('gps_longitude'),
        gps_altitude=master_metadata.get('gps_altitude'),
        location_name=master_metadata.get('location_name')
    )

    camera_details_obj = CameraDetails(
        make=master_metadata.get('camera_make'),
        model=master_metadata.get('camera_model'),
        lens_model=master_metadata.get('lens_model'),
        focal_length=camera_focal_length_obj,
        settings=camera_settings_obj,
        location=camera_location_obj,
        camera_serial_number=master_metadata.get('camera_serial_number')
    )

    # Extract content tags and summary from AI analysis if available
    content_tags = []
    content_summary = None
    
    if ai_analysis_summary:
        # Use AI analysis to populate content tags and summary
        if ai_analysis_summary.get('content_category'):
            content_tags.append(ai_analysis_summary['content_category'])
        
        # Add key metrics as tags
        if ai_analysis_summary.get('speaker_count', 0) > 0:
            content_tags.append(f"speakers:{ai_analysis_summary['speaker_count']}")
        
        if ai_analysis_summary.get('usability_rating'):
            content_tags.append(f"quality:{ai_analysis_summary['usability_rating'].lower()}")
        
        # Add actual shot types instead of count
        full_ai_analysis = data.get('full_ai_analysis_data', {})
        if full_ai_analysis.get('visual_analysis', {}).get('shot_types'):
            shot_types = full_ai_analysis['visual_analysis']['shot_types']
            unique_shot_attributes = set()
            for shot in shot_types:
                attrs = shot.get('shot_attributes_ordered', [])
                if attrs:
                    # Use the first attribute as the primary for tags
                    unique_shot_attributes.add(attrs[0])
                    # Optionally, add all attributes for richer tags
                    for attr in attrs:
                        unique_shot_attributes.add(attr)
            # Add each unique shot attribute as a tag
            for attr in sorted(unique_shot_attributes):
                content_tags.append(attr)
        
        # Use overall summary as content summary
        content_summary = ai_analysis_summary.get('overall_summary')

    analysis_details_obj = AnalysisDetails(
        scene_changes=[],  # Placeholder for future implementation
        content_tags=content_tags,  # Populated from AI analysis
        content_summary=content_summary,  # Populated from AI analysis
        ai_analysis=ai_analysis_obj  # Minimal AI analysis with file path
    )

    output = VideoIngestOutput(
        id=str(uuid.uuid4()),
        file_info=file_info_obj,
        video=video_details_obj,
        audio_tracks=audio_track_models,
        subtitle_tracks=subtitle_track_models,
        camera=camera_details_obj,
        thumbnails=thumbnail_paths,
        analysis=analysis_details_obj
    )
    
    return {
        'model': output
    } 