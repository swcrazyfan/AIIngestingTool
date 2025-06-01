"""
AI video analysis step for the video ingest tool.

This module implements the video analysis step using Gemini Flash 2.5 AI.
"""

import os
from typing import Dict, Any, Optional
from ...config import DEFAULT_COMPRESSION_CONFIG, Config
from prefect import task
from ...video_processor.compression import VideoCompressor # Moved import to top

# Try to import VideoProcessor - it may not be available if dependencies are missing
try:
    from ...video_processor.processor import VideoProcessor
    HAS_VIDEO_PROCESSOR = True
    VIDEO_PROCESSOR_ERROR = ""
except ImportError as e:
    HAS_VIDEO_PROCESSOR = False
    VIDEO_PROCESSOR_ERROR = str(e)


def _create_ai_summary(analysis_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a lightweight summary of AI analysis for inclusion in main JSON.
    
    Args:
        analysis_json: Complete AI analysis data
        
    Returns:
        Dict[str, Any]: Dictionary with summary information
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
                summary['locations_count'] = len(entities.get('locations', []))
                summary['objects_count'] = len(entities.get('objects_of_interest', []))
            
            if 'content_warnings' in content:
                warnings = content['content_warnings']
                summary['has_content_warnings'] = len(warnings) > 0
                if warnings:
                    summary['content_warning_types'] = [w['type'] for w in warnings]
        
        return summary
    except Exception as e:
        return {'error': str(e)}


@task
def ai_video_analysis_step(data: Dict[str, Any], logger=None) -> Dict[str, Any]:
    """
    Run AI video analysis using Gemini Flash 2.5 AI.
    Always returns a dict with all expected keys, even in error cases.
    """
    # Default output structure
    output = {
        'ai_analysis_summary': {},
        'ai_analysis_file_path': None,
        'full_ai_analysis_data': {},
        'compressed_video_path': data.get('compressed_video_path'),
        'ai_analysis_data': {},
    }
    if not HAS_VIDEO_PROCESSOR:
        if logger:
            logger.warning(f"VideoProcessor not available: {VIDEO_PROCESSOR_ERROR}")
        output['error'] = VIDEO_PROCESSOR_ERROR
        return output

    file_path = data.get('file_path')
    compressed_path = data.get('compressed_video_path')

    if not file_path:
        if logger:
            logger.error("No file_path provided for AI analysis")
        output['error'] = 'No file_path provided'
        return output

    try:
        if logger:
            logger.info(f"Starting comprehensive AI analysis for: {os.path.basename(file_path)}")
        from ...config import Config
        # Initialize VideoProcessor with compression configuration
        config = Config()
        # Create compression config with custom parameters
        compression_config = {
            'fps': DEFAULT_COMPRESSION_CONFIG['fps'],
            'video_bitrate': DEFAULT_COMPRESSION_CONFIG['video_bitrate']
        }
        video_processor = VideoProcessor(config, compression_config=compression_config)
        # Determine output directory for compressed files
        run_dir = None
        if data.get('thumbnails_dir'):
            run_dir = os.path.dirname(data['thumbnails_dir'])  # thumbnails_dir is run_dir/thumbnails
        # Use pre-compressed video if available, otherwise compress now
        if compressed_path and os.path.exists(compressed_path):
            if logger:
                logger.info(f"Using pre-compressed video: {compressed_path}")
            video_to_analyze = compressed_path
        else:
            if logger:
                logger.info("No pre-compressed video found, compressing now...")
            # Compress the video now
            # from ...video_processor.compression import VideoCompressor # Already imported at top
            compressor = VideoCompressor(compression_config)
            compressed_path = compressor.compress_video(file_path, run_dir) # Corrected to compress_video
            video_to_analyze = compressed_path
            output['compressed_video_path'] = compressed_path
        # Process the video (this will analyze the compressed video)
        result = video_processor.process(video_to_analyze, run_dir)
        if not result.get('success'):
            if logger:
                logger.error(f"AI analysis failed: {result.get('error', 'Unknown error')}")
            output['error'] = result.get('error', 'Unknown error')
            return output
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
                output.update({
                    'ai_analysis_summary': ai_summary,
                    'ai_analysis_file_path': ai_analysis_path,
                    'full_ai_analysis_data': analysis_json,
                    'compressed_video_path': result.get('compressed_path'),
                })
                return output
            except Exception as e:
                if logger:
                    logger.error(f"Failed to save AI analysis files: {str(e)}")
                output['error'] = str(e)
                return output
        if logger:
            logger.info(f"AI analysis completed successfully")
        return output
    except Exception as e:
        if logger:
            logger.error(f"AI analysis failed with exception: {str(e)}")
        output['error'] = str(e)
        return output 