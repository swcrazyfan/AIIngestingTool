"""
Core processor for the video ingest tool.

Handles the primary processing logic for video ingestion using the pipeline system.
"""

import os
import datetime
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from .models import (
    VideoIngestOutput, FileInfo, VideoCodecDetails, VideoResolution, VideoHDRDetails,
    VideoColorDetails, VideoExposureDetails, VideoDetails, CameraFocalLength,
    CameraSettings, CameraLocation, CameraDetails, AnalysisDetails,
    AudioTrack, SubtitleTrack, ComprehensiveAIAnalysis, AIAnalysisSummary,
    VisualAnalysis, AudioAnalysis, ContentAnalysis, ShotType, TechnicalQuality,
    TextAndGraphics, DetectedText, DetectedLogo, KeyframeAnalysis, RecommendedKeyframe,
    Transcript, TranscriptSegment, SpeakerAnalysis, Speaker, SoundEvent, AudioQuality,
    Entities, PersonDetail, Location, ObjectOfInterest, Activity, ContentWarning
)
from .utils import calculate_checksum, calculate_aspect_ratio_str
from .extractors import extract_mediainfo, extract_ffprobe_info
from .extractors_extended import extract_exiftool_info, extract_extended_exif_metadata, extract_audio_tracks
from .extractors_hdr import extract_subtitle_tracks, extract_codec_parameters, extract_hdr_metadata
from .processors import generate_thumbnails, analyze_exposure, detect_focal_length_with_ai
from .config import FOCAL_LENGTH_RANGES, HAS_TRANSFORMERS, Config
from .pipeline import ProcessingPipeline, ProcessingStep

# Try to import VideoProcessor - it may not be available if dependencies are missing
try:
    from .video_processor import VideoProcessor
    HAS_VIDEO_PROCESSOR = True
except ImportError as e:
    HAS_VIDEO_PROCESSOR = False
    VIDEO_PROCESSOR_ERROR = str(e)

# Import the centralized config
try:
    from .video_processor import DEFAULT_COMPRESSION_CONFIG
except ImportError:
    # Fallback if circular import issues
    DEFAULT_COMPRESSION_CONFIG = {'fps': 5, 'video_bitrate': '1000k'}

# Create a global pipeline instance
pipeline = ProcessingPipeline()
@pipeline.register_step(
    name="checksum_generation", 
    enabled=True,
    description="Calculate file checksum for deduplication"
)
def generate_checksum(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Generate checksum for a video file.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with checksum information
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    if logger:
        logger.info("Generating checksum", path=file_path)
        
    checksum = calculate_checksum(file_path)
    file_size_bytes = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    
    return {
        'checksum': checksum,
        'file_size_bytes': file_size_bytes,
        'file_name': file_name
    }

@pipeline.register_step(
    name="duplicate_check", 
    enabled=True,
    description="Check database for existing files with same checksum"
)
def check_duplicate_step(data: Dict[str, Any], logger=None, force_reprocess: bool = False) -> Dict[str, Any]:
    """
    Check if a file with the same checksum already exists in the database.
    
    Args:
        data: Pipeline data containing checksum and file info
        logger: Optional logger
        force_reprocess: If True, skip duplicate check and proceed with processing
        
    Returns:
        Dict with duplicate check results
    """
    if force_reprocess:
        if logger:
            logger.info("Force reprocess enabled - skipping duplicate check")
        return {
            'is_duplicate': False,
            'duplicate_check_skipped': True,
            'reason': 'force_reprocess'
        }
    
    from .auth import AuthManager
    
    # Check if database storage is enabled (duplicate check only makes sense with database)
    auth_manager = AuthManager()
    if not auth_manager.get_current_session():
        if logger:
            logger.info("No authentication - skipping duplicate check")
        return {
            'is_duplicate': False,
            'duplicate_check_skipped': True,
            'reason': 'not_authenticated'
        }
    
    checksum = data.get('checksum')
    if not checksum:
        if logger:
            logger.warning("No checksum available for duplicate check")
        return {
            'is_duplicate': False,
            'duplicate_check_skipped': True,
            'reason': 'no_checksum'
        }
    
    try:
        client = auth_manager.get_authenticated_client()
        if not client:
            if logger:
                logger.warning("No authenticated client - skipping duplicate check")
            return {
                'is_duplicate': False,
                'duplicate_check_skipped': True,
                'reason': 'no_client'
            }
        
        # Query database for existing file with same checksum
        result = client.table('clips').select('id, file_name, file_path, processed_at').eq('file_checksum', checksum).execute()
        
        if result.data:
            existing_file = result.data[0]
            if logger:
                logger.info(f"Found duplicate file in database", 
                           existing_id=existing_file['id'],
                           existing_file=existing_file['file_name'],
                           existing_path=existing_file['file_path'],
                           processed_at=existing_file['processed_at'])
            
            return {
                'is_duplicate': True,
                'existing_clip_id': existing_file['id'],
                'existing_file_name': existing_file['file_name'],
                'existing_file_path': existing_file['file_path'],
                'existing_processed_at': existing_file['processed_at']
            }
        else:
            if logger:
                logger.info("No duplicate found - proceeding with processing")
            return {
                'is_duplicate': False
            }
            
    except Exception as e:
        if logger:
            logger.warning(f"Duplicate check failed: {str(e)} - proceeding with processing")
        return {
            'is_duplicate': False,
            'duplicate_check_failed': True,
            'error': str(e)
        }

@pipeline.register_step(
    name="mediainfo_extraction", 
    enabled=True,
    description="Extract metadata using MediaInfo"
)
def extract_mediainfo_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract metadata using MediaInfo.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with mediainfo data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    mediainfo_data = extract_mediainfo(file_path, logger)
    
    return {
        'mediainfo_data': mediainfo_data
    }

@pipeline.register_step(
    name="ffprobe_extraction", 
    enabled=True,
    description="Extract metadata using FFprobe/PyAV"
)
def extract_ffprobe_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract metadata using FFprobe/PyAV.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with ffprobe data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    ffprobe_data = extract_ffprobe_info(file_path, logger)
    
    return {
        'ffprobe_data': ffprobe_data
    }

@pipeline.register_step(
    name="exiftool_extraction", 
    enabled=True,
    description="Extract EXIF metadata"
)
def extract_exiftool_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract metadata using ExifTool.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with exiftool data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    exiftool_data = extract_exiftool_info(file_path, logger)
    
    return {
        'exiftool_data': exiftool_data
    }

@pipeline.register_step(
    name="extended_exif_extraction", 
    enabled=True,
    description="Extract extended EXIF metadata"
)
def extract_extended_exif_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract extended EXIF metadata.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with extended EXIF data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    extended_exif_data = extract_extended_exif_metadata(file_path, logger)
    
    return {
        'extended_exif_data': extended_exif_data
    }

@pipeline.register_step(
    name="codec_extraction", 
    enabled=True,
    description="Extract detailed codec parameters"
)
def extract_codec_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract codec parameters.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with codec data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    codec_params = extract_codec_parameters(file_path, logger)
    
    return {
        'codec_params': codec_params
    }

@pipeline.register_step(
    name="hdr_extraction", 
    enabled=True,
    description="Extract HDR metadata"
)
def extract_hdr_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract HDR metadata.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with HDR data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    hdr_data = extract_hdr_metadata(file_path, logger)
    
    return {
        'hdr_data': hdr_data
    }

@pipeline.register_step(
    name="audio_extraction", 
    enabled=True,
    description="Extract audio track information"
)
def extract_audio_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract audio track information.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with audio track data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    audio_tracks = extract_audio_tracks(file_path, logger)
    
    return {
        'audio_tracks': audio_tracks
    }

@pipeline.register_step(
    name="subtitle_extraction", 
    enabled=True,
    description="Extract subtitle track information"
)
def extract_subtitle_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Extract subtitle track information.
    
    Args:
        data: Pipeline data containing file_path
        logger: Optional logger
        
    Returns:
        Dict with subtitle track data
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("Missing file_path in data")
        
    subtitle_tracks = extract_subtitle_tracks(file_path, logger)
    
    return {
        'subtitle_tracks': subtitle_tracks
    }

@pipeline.register_step(
    name="thumbnail_generation", 
    enabled=True,
    description="Generate thumbnails from video"
)
def generate_thumbnails_step(data: Dict[str, Any], thumbnails_dir=None, logger=None) -> Dict[str, Any]:
    """
    Generate thumbnails for a video file.
    
    Args:
        data: Pipeline data containing file_path and checksum
        thumbnails_dir: Directory to save thumbnails
        logger: Optional logger
        
    Returns:
        Dict with thumbnail paths
    """
    file_path = data.get('file_path')
    checksum = data.get('checksum')
    
    if not file_path or not checksum:
        raise ValueError("Missing file_path or checksum in data")
        
    if not thumbnails_dir:
        raise ValueError("Missing thumbnails_dir parameter")
        
    # Create thumbnail directory with filename first, then checksum
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    thumbnail_dir_name = f"{base_name}_{checksum}"
    thumbnail_dir_for_file = os.path.join(thumbnails_dir, thumbnail_dir_name)
    thumbnail_paths = generate_thumbnails(file_path, thumbnail_dir_for_file, logger=logger)
    
    return {
        'thumbnail_paths': thumbnail_paths
    }

@pipeline.register_step(
    name="exposure_analysis", 
    enabled=True,
    description="Analyze exposure in thumbnails"
)
def analyze_exposure_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Analyze exposure in thumbnails.
    
    Args:
        data: Pipeline data containing thumbnail_paths
        logger: Optional logger
        
    Returns:
        Dict with exposure analysis results
    """
    thumbnail_paths = data.get('thumbnail_paths', [])
    
    if not thumbnail_paths:
        if logger:
            logger.warning("No thumbnails available for exposure analysis")
        return {
            'exposure_data': {}
        }
        
    exposure_data = analyze_exposure(thumbnail_paths[0], logger)
    
    return {
        'exposure_data': exposure_data
    }

@pipeline.register_step(
    name="ai_focal_length", 
    enabled=True,
    description="Detect focal length using AI when EXIF data is not available"
)
def detect_focal_length_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Detect focal length using AI when EXIF data is not available.
    
    Args:
        data: Pipeline data containing thumbnail_paths and metadata
        logger: Optional logger
        
    Returns:
        Dict with focal length data
    """
    # Check if we already have focal length information
    exiftool_data = data.get('exiftool_data', {})
    extended_exif_data = data.get('extended_exif_data', {})
    
    # Check if we have valid focal length data from EXIF (not None/null)
    has_exif_focal_length = (
        exiftool_data.get('focal_length_mm') is not None or
        exiftool_data.get('focal_length_category') is not None or
        extended_exif_data.get('focal_length_mm') is not None or
        extended_exif_data.get('focal_length_category') is not None
    )
    
    if has_exif_focal_length:
        if logger:
            logger.info("Valid focal length available from EXIF, skipping AI detection")
        return {
            'focal_length_source': 'EXIF'
        }
    
    thumbnail_paths = data.get('thumbnail_paths', [])
    
    if not thumbnail_paths:
        if logger:
            logger.warning("No thumbnails available for focal length detection")
        return {
            'focal_length_source': None  # Source is unknown if no thumbnails and no EXIF
        }
    
    if logger:
        logger.info("Focal length not found, attempting AI detection.")
        
    category = detect_focal_length_with_ai(
        thumbnail_paths[0],
        FOCAL_LENGTH_RANGES,
        has_transformers=HAS_TRANSFORMERS,
        logger=logger
    )
    
    if category:
        if logger:
            logger.info(f"AI detected focal length category: {category}")
        return {
            'focal_length_category': category,    # The AI-detected category
            'focal_length_mm': None,              # AI never provides mm value
            'focal_length_source': 'AI'           # Mark as AI-sourced
        }
    
    if logger:
        logger.warning("AI detection failed to determine focal length")
    return {
        'focal_length_category': None,
        'focal_length_mm': None,
        'focal_length_source': None
    }

@pipeline.register_step(
    name="ai_video_analysis", 
    enabled=False,  # Disabled by default due to API costs
    description="Comprehensive video analysis using Gemini Flash 2.5 AI"
)
def ai_video_analysis_step(data: Dict[str, Any], thumbnails_dir=None, logger=None, compression_fps: int = DEFAULT_COMPRESSION_CONFIG['fps'], compression_bitrate: str = DEFAULT_COMPRESSION_CONFIG['video_bitrate']) -> Dict[str, Any]:
    """
    Perform comprehensive AI video analysis using Gemini Flash 2.5.
    
    Args:
        data: Pipeline data containing file_path, checksum, and other metadata
        thumbnails_dir: Directory where thumbnails are stored
        logger: Optional logger
        compression_fps: Frame rate for video compression
        compression_bitrate: Bitrate for video compression
        
    Returns:
        Dict with AI analysis results
    """
    if not HAS_VIDEO_PROCESSOR:
        if logger:
            logger.warning(f"VideoProcessor not available: {VIDEO_PROCESSOR_ERROR}")
        return {
            'ai_analysis_data': {},
            'ai_analysis_file_path': None
        }
    
    file_path = data.get('file_path')
    checksum = data.get('checksum')
    
    if not file_path:
        if logger:
            logger.error("No file_path provided for AI analysis")
        return {
            'ai_analysis_data': {},
            'ai_analysis_file_path': None
        }
    
    try:
        if logger:
            logger.info(f"Starting comprehensive AI analysis for: {os.path.basename(file_path)}")
        
        # Initialize VideoProcessor with compression configuration
        config = Config()
        
        # Create compression config with custom parameters
        compression_config = {
            'fps': compression_fps,
            'video_bitrate': compression_bitrate
        }
        video_processor = VideoProcessor(config, compression_config=compression_config)
        
        # Determine output directory for compressed files
        # Use the parent directory of thumbnails_dir as the run directory
        run_dir = None
        if thumbnails_dir:
            run_dir = os.path.dirname(thumbnails_dir)  # thumbnails_dir is run_dir/thumbnails
        
        # Process the video (this will compress and analyze)
        result = video_processor.process(file_path, run_dir)
        
        if not result.get('success'):
            if logger:
                logger.error(f"AI analysis failed: {result.get('error', 'Unknown error')}")
            return {
                'ai_analysis_data': {},
                'ai_analysis_file_path': None
            }
        
        # Get the analysis results
        analysis_json = result.get('analysis_json', {})
        
        # Create AI-specific JSON file with proper naming
        if analysis_json and file_path:
            try:
                import json
                
                # Create AI analysis directory in run structure (same level as thumbnails)
                if run_dir:
                    ai_analysis_dir = os.path.join(run_dir, "ai_analysis")
                    os.makedirs(ai_analysis_dir, exist_ok=True)
                    
                    input_basename = os.path.basename(file_path)
                    ai_filename = f"{os.path.splitext(input_basename)[0]}_AI_analysis.json"
                    ai_analysis_path = os.path.join(ai_analysis_dir, ai_filename)
                    
                    # Save the complete AI analysis to AI-specific file
                    with open(ai_analysis_path, 'w') as f:
                        json.dump(analysis_json, f, indent=2)
                    
                    if logger:
                        logger.info(f"AI analysis saved to: {ai_analysis_path}")
                else:
                    # No run directory available - skip saving separate AI file
                    ai_analysis_path = None
                    if logger:
                        logger.warning("No run directory available - AI analysis not saved to separate file")
                
                # Create summary for main JSON (lightweight)
                ai_summary = _create_ai_summary(analysis_json)
                
                return {
                    'ai_analysis_summary': ai_summary,  # Lightweight summary for main JSON
                    'ai_analysis_file_path': ai_analysis_path,  # Path to full AI analysis
                    'full_ai_analysis_data': analysis_json,  # Full analysis data for model creation
                    'compressed_video_path': result.get('compressed_path')
                }
                
            except Exception as e:
                if logger:
                    logger.error(f"Failed to save AI analysis files: {str(e)}")
        
        if logger:
            logger.info(f"AI analysis completed successfully")
        
        return {
            'ai_analysis_summary': {},
            'ai_analysis_file_path': None,
            'full_ai_analysis_data': {},
            'compressed_video_path': result.get('compressed_path')
        }
        
    except Exception as e:
        if logger:
            logger.error(f"AI analysis failed with exception: {str(e)}")
        return {
            'ai_analysis_summary': {},
            'ai_analysis_file_path': None,
            'full_ai_analysis_data': {},
            'error': str(e)
        }

def _create_ai_summary(analysis_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a lightweight summary of AI analysis for inclusion in main JSON.
    
    Args:
        analysis_json: Complete AI analysis data
        
    Returns:
        Dict with summary information
    """
    try:
        summary = {}
        
        # Extract key summary information
        if 'summary' in analysis_json:
            summary_data = analysis_json['summary']
            summary['content_category'] = summary_data.get('content_category')
            summary['overall_summary'] = summary_data.get('overall')
            summary['key_activities_count'] = len(summary_data.get('key_activities', []))
        
        # Extract key metrics from visual analysis
        if 'visual_analysis' in analysis_json:
            visual = analysis_json['visual_analysis']
            summary['shot_types_detected'] = len(visual.get('shot_types', []))
            
            if 'technical_quality' in visual:
                tech_quality = visual['technical_quality']
                summary['usability_rating'] = tech_quality.get('usability_rating')
                summary['focus_quality'] = tech_quality.get('overall_focus_quality')
            
            if 'text_and_graphics' in visual:
                text_graphics = visual['text_and_graphics']
                summary['text_elements_detected'] = len(text_graphics.get('detected_text', []))
                summary['logos_icons_detected'] = len(text_graphics.get('detected_logos_icons', []))
        
        # Extract key metrics from audio analysis
        if 'audio_analysis' in analysis_json:
            audio = analysis_json['audio_analysis']
            
            if 'speaker_analysis' in audio:
                speaker_analysis = audio['speaker_analysis']
                summary['speaker_count'] = speaker_analysis.get('speaker_count', 0)
            
            if 'sound_events' in audio:
                summary['sound_events_detected'] = len(audio['sound_events'])
            
            if 'audio_quality' in audio:
                audio_quality = audio['audio_quality']
                summary['audio_clarity'] = audio_quality.get('clarity')
                summary['dialogue_intelligibility'] = audio_quality.get('dialogue_intelligibility')
            
            # Add transcript preview (first 100 chars)
            if 'transcript' in audio and 'full_text' in audio['transcript']:
                full_text = audio['transcript']['full_text']
                if full_text:
                    preview = full_text[:100] + "..." if len(full_text) > 100 else full_text
                    summary['transcript_preview'] = preview
        
        # Extract key metrics from content analysis
        if 'content_analysis' in analysis_json:
            content = analysis_json['content_analysis']
            
            if 'entities' in content:
                entities = content['entities']
                summary['people_count'] = entities.get('people_count', 0)
                summary['locations_detected'] = len(entities.get('locations', []))
                summary['objects_of_interest'] = len(entities.get('objects_of_interest', []))
            
            if 'activity_summary' in content:
                activities = content['activity_summary']
                summary['activities_detected'] = len(activities)
                high_importance_activities = [a for a in activities if a.get('importance') == 'High']
                summary['high_importance_activities'] = len(high_importance_activities)
            
            if 'content_warnings' in content:
                summary['content_warnings_count'] = len(content['content_warnings'])
        
        # Add analysis metadata
        summary['analysis_timestamp'] = datetime.datetime.now().isoformat()
        summary['has_comprehensive_analysis'] = True
        
        return summary
        
    except Exception as e:
        return {
            'analysis_timestamp': datetime.datetime.now().isoformat(),
            'has_comprehensive_analysis': False,
            'error': f"Failed to create summary: {str(e)}"
        }

@pipeline.register_step(
    name="metadata_consolidation", 
    enabled=True,
    description="Consolidate metadata from all sources"
)
def consolidate_metadata_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Consolidate metadata from all sources.
    
    Args:
        data: Pipeline data containing all extracted metadata
        logger: Optional logger
        
    Returns:
        Dict with consolidated metadata
    """
    mediainfo_data = data.get('mediainfo_data', {})
    ffprobe_data = data.get('ffprobe_data', {})
    exiftool_data = data.get('exiftool_data', {})
    extended_exif_data = data.get('extended_exif_data', {})
    codec_params = data.get('codec_params', {})
    hdr_data = data.get('hdr_data', {})
    
    # Get focal length info from AI or EXIF
    focal_length_source = data.get('focal_length_source')
    ai_focal_length_info = {
        'category': data.get('focal_length_category'),
        'mm': data.get('focal_length_mm')
    }
    
    # Initialize the master metadata dictionary
    master_metadata = {}

    # Prioritize sources for technical video properties
    tech_keys = ['codec', 'width', 'height', 'frame_rate', 'bit_rate_kbps', 'bit_depth', 'color_space', 'container', 'duration_seconds', 'profile', 'level', 'chroma_subsampling', 'pixel_format', 'bitrate_mode', 'scan_type', 'field_order', 'cabac', 'ref_frames', 'gop_size']
    for key in tech_keys:
        master_metadata[key] = mediainfo_data.get(key, ffprobe_data.get(key, exiftool_data.get(key, codec_params.get(key))))

    # Prioritize sources for camera/lens info
    camera_keys = ['camera_make', 'camera_model', 'focal_length_mm', 'focal_length_category', 'lens_model', 'iso', 'shutter_speed', 'f_stop', 'exposure_mode', 'white_balance', 'gps_latitude', 'gps_longitude', 'gps_altitude', 'location_name', 'camera_serial_number']
    for key in camera_keys:
        # Prioritize extended_exif_data then exiftool_data for camera specific info
        master_metadata[key] = extended_exif_data.get(key, exiftool_data.get(key, mediainfo_data.get(key, ffprobe_data.get(key))))

    # Prioritize sources for dates
    master_metadata['created_at'] = exiftool_data.get('created_at', mediainfo_data.get('created_at', ffprobe_data.get('created_at')))

    # Merge remaining from specific extractions if not already set or to overwrite with more specific data
    for key, value in codec_params.items():
        if master_metadata.get(key) is None or key in ['profile', 'level', 'pixel_format', 'chroma_subsampling', 'bitrate_mode', 'scan_type', 'field_order', 'cabac', 'ref_frames', 'gop_size']:
            if value is not None: master_metadata[key] = value
    
    for key, value in hdr_data.items():
        if master_metadata.get(key) is None or key in ['hdr_format', 'master_display', 'max_cll', 'max_fall', 'color_primaries', 'transfer_characteristics', 'matrix_coefficients', 'color_range']:
            if value is not None: master_metadata[key] = value

    for key, value in extended_exif_data.items(): # Ensure all extended_exif_data is considered
        if master_metadata.get(key) is None: # Add if not already set
             if value is not None: master_metadata[key] = value
    
    # Handle focal length data from different sources
    if focal_length_source == 'AI':
        # Use AI detected values, overriding any EXIF data
        master_metadata['focal_length_source'] = 'AI'
        master_metadata['focal_length_category'] = ai_focal_length_info['category']
        master_metadata['focal_length_mm'] = None  # AI only provides category
        if logger:
            logger.info("Using AI-detected focal length",
                       source='AI',
                       category=ai_focal_length_info['category'])
    elif focal_length_source == 'EXIF':
        # Keep EXIF values from earlier camera_keys import
        master_metadata['focal_length_source'] = 'EXIF'
        if logger:
            logger.info("Using EXIF focal length",
                       source='EXIF',
                       mm=master_metadata.get('focal_length_mm'),
                       category=master_metadata.get('focal_length_category'))
    else:
        # No focal length data available
        master_metadata['focal_length_source'] = None
        master_metadata['focal_length_category'] = None
        master_metadata['focal_length_mm'] = None
        if logger:
            logger.info("No focal length information available")
    
    return {
        'master_metadata': master_metadata
    }


@pipeline.register_step(
    name="model_creation", 
    enabled=True,
    description="Create Pydantic model from processed data"
)
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
                        shot_type=shot.get('shot_type', ''),
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
                activity_summary = []
                for activity in content_data.get('activity_summary', []):
                    activity_summary.append(Activity(
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
                    activity_summary=activity_summary,
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
        field_order=master_metadata.get('field_order')
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
        location=camera_location_obj
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
            unique_shot_types = set()
            for shot in shot_types:
                shot_type = shot.get('shot_type', '').strip()
                if shot_type:
                    unique_shot_types.add(shot_type)
            
            # Add each unique shot type as a tag
            for shot_type in sorted(unique_shot_types):
                content_tags.append(shot_type)
        
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
        'output': output
    }

@pipeline.register_step(
    name="database_storage", 
    enabled=False,  # Disabled by default
    description="Store video metadata and analysis in Supabase database"
)
def database_storage_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Store video data in Supabase database.
    
    Args:
        data: Pipeline data containing the output model
        logger: Optional logger
        
    Returns:
        Dict with database storage results
    """
    from .auth import AuthManager
    from .database_storage import store_video_in_database
    
    # Check authentication
    auth_manager = AuthManager()
    if not auth_manager.get_current_session():
        if logger:
            logger.warning("Skipping database storage - not authenticated")
        return {
            'database_storage_skipped': True,
            'reason': 'not_authenticated'
        }
    
    output = data.get('output')
    if not output:
        if logger:
            logger.error("No output model found for database storage")
        return {
            'database_storage_failed': True,
            'reason': 'no_output_model'
        }
    
    try:
        result = store_video_in_database(output, logger)
        if logger:
            logger.info(f"Successfully stored video in database: {result.get('clip_id')}")
        return result
        
    except Exception as e:
        if logger:
            logger.error(f"Database storage failed: {str(e)}")
        return {
            'database_storage_failed': True,
            'error': str(e)
        }

@pipeline.register_step(
    name="generate_embeddings", 
    enabled=False,  # Disabled by default
    description="Generate vector embeddings for semantic search"
)
def generate_embeddings_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Generate and store vector embeddings for semantic search.
    
    Args:
        data: Pipeline data containing the output model and clip_id
        logger: Optional logger
        
    Returns:
        Dict with embedding generation results
    """
    from .auth import AuthManager
    from .embeddings import prepare_embedding_content, generate_embeddings, store_embeddings
    
    # Check authentication
    auth_manager = AuthManager()
    if not auth_manager.get_current_session():
        if logger:
            logger.warning("Skipping embedding generation - not authenticated")
        return {
            'embeddings_skipped': True,
            'reason': 'not_authenticated'
        }
    
    # Get clip_id from database storage results
    clip_id = data.get('clip_id')
    if not clip_id:
        if logger:
            logger.error("No clip_id found for embedding generation")
        return {
            'embeddings_failed': True,
            'reason': 'no_clip_id'
        }
    
    # Get output model
    output = data.get('output')
    if not output:
        if logger:
            logger.error("No output model found for embedding generation")
        return {
            'embeddings_failed': True,
            'reason': 'no_output_model'
        }
    
    try:
        # Prepare embedding content using the existing function
        summary_content, keyword_content, metadata = prepare_embedding_content(output)
        
        if logger:
            logger.info(f"Prepared embedding content - Summary: {metadata['summary_tokens']} tokens, Keywords: {metadata['keyword_tokens']} tokens")
        
        # Generate embeddings
        summary_embedding, keyword_embedding = generate_embeddings(
            summary_content, keyword_content, logger
        )
        
        # Store embeddings in database
        original_content = f"Summary: {summary_content}\nKeywords: {keyword_content}"
        store_embeddings(
            clip_id=clip_id,
            summary_embedding=summary_embedding,
            keyword_embedding=keyword_embedding,
            summary_content=summary_content,
            keyword_content=keyword_content,
            original_content=original_content,
            metadata=metadata,
            logger=logger
        )
        
        if logger:
            logger.info(f"Successfully generated and stored embeddings for clip: {clip_id}")
        
        return {
            'embeddings_generated': True,
            'clip_id': clip_id,
            'summary_tokens': metadata['summary_tokens'],
            'keyword_tokens': metadata['keyword_tokens'],
            'truncation_applied': metadata['summary_truncation'] != 'none' or metadata['keyword_truncation'] != 'none'
        }
        
    except Exception as e:
        if logger:
            logger.error(f"Embedding generation failed: {str(e)}")
        return {
            'embeddings_failed': True,
            'error': str(e)
        }

def process_video_file(file_path: str, thumbnails_dir: str, logger=None, config: Dict[str, bool] = None, compression_fps: int = DEFAULT_COMPRESSION_CONFIG['fps'], compression_bitrate: str = DEFAULT_COMPRESSION_CONFIG['video_bitrate'], force_reprocess: bool = False) -> VideoIngestOutput:
    """
    Process a video file using the pipeline.
    
    Args:
        file_path: Path to the video file
        thumbnails_dir: Directory to save thumbnails
        logger: Optional logger
        config: Dictionary of step configurations (enabled/disabled)
        compression_fps: Frame rate for video compression (default: 5)
        compression_bitrate: Bitrate for video compression (default: 500k)
        force_reprocess: Force reprocessing even if file exists in database
        
    Returns:
        VideoIngestOutput: Processed video data object
    """
    if logger:
        logger.info("Processing video file", path=file_path)
    
    # Configure pipeline if config is provided
    if config:
        pipeline.configure_steps(config)
    
    # Initial data
    initial_data = {
        'file_path': file_path,
        'processed_at': datetime.datetime.now()
    }
    
    # Execute pipeline
    result = pipeline.execute_pipeline(
        initial_data, 
        thumbnails_dir=thumbnails_dir,
        logger=logger,
        compression_fps=compression_fps,
        compression_bitrate=compression_bitrate,
        force_reprocess=force_reprocess
    )
    
    # Check if pipeline was stopped due to duplicate detection
    if result.get('pipeline_stopped') and result.get('stop_reason') == 'duplicate_detected':
        if logger:
            logger.info("Skipping file - duplicate detected", 
                       path=file_path,
                       existing_id=result.get('existing_clip_id'),
                       existing_file=result.get('existing_file_name'))
        # Return a special marker indicating this was skipped
        return {
            'skipped': True,
            'reason': 'duplicate_detected',
            'existing_clip_id': result.get('existing_clip_id'),
            'existing_file_name': result.get('existing_file_name'),
            'existing_file_path': result.get('existing_file_path'),
            'existing_processed_at': result.get('existing_processed_at')
        }
    
    # Return the output model
    output = result.get('output')
    if not output:
        raise ValueError("Pipeline did not produce an output model")
    
    if logger:
        logger.info("Video processing complete", path=file_path, id=output.id)
    
    return output

# Optional: Function to get default pipeline configuration
def get_default_pipeline_config() -> Dict[str, bool]:
    """
    Get the default pipeline configuration.
    
    Returns:
        Dict[str, bool]: Dictionary mapping step names to enabled status
    """
    return {step.name: step.enabled for step in pipeline.steps}

# Optional: Function to get available pipeline steps
def get_available_pipeline_steps() -> List[Dict[str, Any]]:
    """
    Get available pipeline steps with descriptions.
    
    Returns:
        List[Dict[str, Any]]: List of dictionaries with step information
    """
    return [
        {
            'name': step.name,
            'enabled': step.enabled,
            'description': step.description
        }
        for step in pipeline.steps
    ]
