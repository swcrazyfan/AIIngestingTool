"""
AI video analysis step for the video ingest tool.

This module implements the video analysis step using Gemini Flash 2.5 AI.
"""

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from ...config import DEFAULT_COMPRESSION_CONFIG, Config
from prefect import task

# Load environment variables from .env file (required for Prefect workers)
load_dotenv()


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
    
    This step expects a compressed video to already be available from the video_compression_step.
    """
    # Default output structure
    output = {
        'ai_analysis_summary': {},
        'ai_analysis_file_path': None,
        'full_ai_analysis_data': {},
        'compressed_video_path': data.get('compressed_video_path'),
        'ai_analysis_data': {},
    }
    
    file_path = data.get('file_path')
    compressed_path = data.get('compressed_video_path')

    if not file_path:
        if logger:
            logger.error("No file_path provided for AI analysis")
        output['error'] = 'No file_path provided'
        return output

    # Ensure we have a compressed video to analyze
    if not compressed_path:
        if logger:
            logger.error("No compressed_video_path available for AI analysis. The video_compression_step should run first.")
        output['error'] = 'No compressed video available for analysis. Run video_compression_step first.'
        return output
    
    if not os.path.exists(compressed_path):
        if logger:
            logger.error(f"Compressed video file not found: {compressed_path}")
        output['error'] = f'Compressed video file not found: {compressed_path}'
        return output

    try:
        if logger:
            logger.info(f"Starting comprehensive AI analysis for: {os.path.basename(file_path)}")
            logger.info(f"Using compressed video: {compressed_path}")
        
        # Get FPS from compression config, with fallback to default
        fps_for_analysis = DEFAULT_COMPRESSION_CONFIG.get('fps', 5)
        
        # Import and use VideoAnalyzer directly
        from ...video_processor.analysis import VideoAnalyzer
        analyzer = VideoAnalyzer(api_key=os.getenv('GEMINI_API_KEY'), fps=fps_for_analysis)
        analysis_results = analyzer.analyze_video(compressed_path)
        
        if not analysis_results or 'error' in analysis_results:
            error_msg = analysis_results.get('error', 'Unknown error in AI analysis') if analysis_results else 'No analysis results returned'
            if logger:
                logger.error(f"AI analysis failed: {error_msg}")
            output['error'] = error_msg
            return output
        
        # Get the analysis results
        analysis_json = analysis_results  # VideoAnalyzer returns analysis directly
        
        # Return the analysis data for database storage (no JSON file saving)
        if analysis_json and file_path:
            try:
                # Create summary for database storage
                ai_summary = _create_ai_summary(analysis_json)
                output.update({
                    'ai_analysis_summary': ai_summary,
                    'full_ai_analysis_data': analysis_json,
                    'compressed_video_path': compressed_path,  # Pass through the compressed video path
                })
                if logger:
                    logger.info(f"AI analysis completed successfully")
                return output
            except Exception as e:
                if logger:
                    logger.error(f"Failed to process AI analysis: {str(e)}")
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