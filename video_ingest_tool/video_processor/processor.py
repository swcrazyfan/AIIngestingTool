"""
Video processor module for handling video compression and analysis.

This module provides the VideoProcessor class that integrates compression and AI analysis.
"""

import os
import json
import logging
from typing import Dict, Any

from ..config import Config
from .compression import VideoCompressor
from .analysis import VideoAnalyzer


class VideoProcessor:
    """Pipeline processor for video analysis."""

    def __init__(self, config: Config, compression_config: Dict[str, Any] = None):
        """
        Initialize the VideoProcessor with configuration.
        
        Args:
            config: Configuration object
            compression_config: Optional compression configuration to override defaults
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Store compression configuration for VideoCompressor
        self.compression_config = compression_config or {}
        
        # Get API key from environment variables (loaded from .env file)
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not found. Check your .env file in the project root.")
            
        self.logger.info("VideoProcessor initialized successfully")
        
    def _display_analysis_summary(self, analysis_json: Dict[str, Any]) -> None:
        """
        Display a comprehensive summary of the analysis results.
        
        Args:
            analysis_json: The complete analysis results dictionary
        """
        self.logger.info("\n" + "="*80)
        self.logger.info("COMPREHENSIVE AI ANALYSIS SUMMARY")
        self.logger.info("="*80)
        
        # Summary section
        summary = analysis_json.get('summary', {})
        self.logger.info(f"\n📝 OVERALL SUMMARY:")
        self.logger.info(f"   Content: {summary.get('overall', 'No summary available')}")
        self.logger.info(f"   Category: {summary.get('content_category', 'Unknown')}")
        
        key_activities = summary.get('key_activities', [])
        if key_activities:
            self.logger.info(f"   Key Activities: {', '.join(key_activities)}")
        
        # Visual Analysis section
        visual = analysis_json.get('visual_analysis', {})
        self.logger.info(f"\n🎬 VISUAL ANALYSIS:")
        
        shot_types = visual.get('shot_types', [])
        if shot_types:
            self.logger.info(f"   Shot Types Detected: {len(shot_types)} different shots")
            for shot in shot_types[:3]:  # Show first 3 shots
                self.logger.info(f"     • {shot['timestamp']}: {shot['shot_type']} - {shot['description']}")
            if len(shot_types) > 3:
                self.logger.info(f"     ... and {len(shot_types) - 3} more shots")
        
        # Technical quality
        tech_quality = visual.get('technical_quality', {})
        if tech_quality:
            self.logger.info(f"   Technical Quality:")
            self.logger.info(f"     • Focus: {tech_quality.get('overall_focus_quality', 'Unknown')}")
            self.logger.info(f"     • Stability: {tech_quality.get('stability_assessment', 'Unknown')}")
            self.logger.info(f"     • Usability: {tech_quality.get('usability_rating', 'Unknown')}")
            
            artifacts = tech_quality.get('detected_artifacts', [])
            if artifacts:
                self.logger.info(f"     • Artifacts Detected: {len(artifacts)} issues found")
                for artifact in artifacts:
                    self.logger.info(f"       - {artifact['type']}: {artifact['severity']} - {artifact['description']}")
        
        # Text and graphics
        text_graphics = visual.get('text_and_graphics', {})
        detected_text = text_graphics.get('detected_text', [])
        detected_logos = text_graphics.get('detected_logos_icons', [])
        
        if detected_text or detected_logos:
            self.logger.info(f"   Text & Graphics:")
            if detected_text:
                self.logger.info(f"     • Text Elements: {len(detected_text)} detected")
                for text in detected_text[:2]:  # Show first 2
                    self.logger.info(f"       - {text['timestamp']}: {text['text_type']} ({text['readability']})")
                    if text.get('text_content'):
                        self.logger.info(f"         Content: \"{text['text_content']}\"")
            
            if detected_logos:
                self.logger.info(f"     • Logos/Icons: {len(detected_logos)} detected")
                for logo in detected_logos[:2]:  # Show first 2
                    self.logger.info(f"       - {logo['timestamp']}: {logo['element_type']} - {logo['description']}")
        
        # Audio Analysis section
        audio = analysis_json.get('audio_analysis', {})
        self.logger.info(f"\n🔊 AUDIO ANALYSIS:")
        
        # Transcript
        transcript = audio.get('transcript', {})
        if transcript and transcript.get('full_text'):
            full_text = transcript['full_text']
            preview_text = full_text[:100] + "..." if len(full_text) > 100 else full_text
            self.logger.info(f"   Transcript Preview: \"{preview_text}\"")
        
        # Speakers
        speaker_analysis = audio.get('speaker_analysis', {})
        speaker_count = speaker_analysis.get('speaker_count', 0)
        if speaker_count > 0:
            self.logger.info(f"   Speakers: {speaker_count} detected")
            speakers = speaker_analysis.get('speakers', [])
            for speaker in speakers:
                self.logger.info(f"     • {speaker['speaker_id']}: {speaker['speaking_time_seconds']:.1f}s speaking time")
        
        # Sound events
        sound_events = audio.get('sound_events', [])
        if sound_events:
            self.logger.info(f"   Sound Events: {len(sound_events)} detected")
            for event in sound_events[:3]:  # Show first 3
                self.logger.info(f"     • {event['timestamp']}: {event['event_type']} - {event['description']}")
        
        # Audio quality
        audio_quality = audio.get('audio_quality', {})
        if audio_quality:
            self.logger.info(f"   Audio Quality:")
            self.logger.info(f"     • Clarity: {audio_quality.get('clarity', 'Unknown')}")
            self.logger.info(f"     • Background Noise: {audio_quality.get('background_noise_level', 'Unknown')}")
            self.logger.info(f"     • Dialogue Intelligibility: {audio_quality.get('dialogue_intelligibility', 'Unknown')}")
        
        # Content Analysis section
        content = analysis_json.get('content_analysis', {})
        self.logger.info(f"\n👥 CONTENT ANALYSIS:")
        
        # Entities
        entities = content.get('entities', {})
        people_count = entities.get('people_count', 0)
        if people_count > 0:
            self.logger.info(f"   People: {people_count} detected")
            people_details = entities.get('people_details', [])
            for person in people_details[:3]:  # Show first 3
                self.logger.info(f"     • {person['description']} ({person.get('role', 'Unknown role')})")
        
        locations = entities.get('locations', [])
        if locations:
            self.logger.info(f"   Locations:")
            for location in locations:
                self.logger.info(f"     • {location['name']} ({location['type']}): {location.get('description', '')}")
        
        objects = entities.get('objects_of_interest', [])
        if objects:
            self.logger.info(f"   Objects of Interest: {len(objects)} detected")
            for obj in objects[:3]:  # Show first 3
                self.logger.info(f"     • {obj['object']}: {obj['significance']}")
        
        # Activity summary
        activities = content.get('activity_summary', [])
        if activities:
            self.logger.info(f"   Key Activities:")
            for activity in activities[:5]:  # Show first 5
                importance_emoji = "🔴" if activity['importance'] == "High" else "🟡" if activity['importance'] == "Medium" else "🟢"
                self.logger.info(f"     {importance_emoji} {activity['timestamp']}: {activity['activity']} ({activity.get('duration', 'Unknown duration')})")
        
        # Content warnings
        warnings = content.get('content_warnings', [])
        if warnings:
            self.logger.info(f"\n⚠️  CONTENT WARNINGS:")
            for warning in warnings:
                self.logger.info(f"   • {warning['type']}: {warning['description']} (at {warning['timestamp']})")
        
        # Keyframe recommendations
        keyframes = visual.get('keyframe_analysis', {}).get('recommended_keyframes', [])
        if keyframes:
            self.logger.info(f"\n🖼️  RECOMMENDED KEYFRAMES:")
            for keyframe in keyframes[:3]:  # Show first 3
                self.logger.info(f"   • {keyframe['timestamp']}: {keyframe['reason']} (Quality: {keyframe['visual_quality']})")
        
        self.logger.info("\n" + "="*80)
        self.logger.info("END OF ANALYSIS SUMMARY")
        self.logger.info("="*80)

    def process(self, file_path: str, output_dir: str = None) -> Dict[str, Any]:
        """
        Process a video file through compression and AI analysis.
        
        Args:
            file_path: Path to video file
            output_dir: Directory to save processed files (optional)
            
        Returns:
            Dict[str, Any]: Processing results with keys:
                - success: Whether processing was successful
                - compressed_path: Path to compressed video (if successful)
                - analysis_json: Analysis results (if successful)
                - error: Error message (if not successful)
        """
        try:
            # Verify file exists
            if not os.path.exists(file_path):
                self.logger.error(f"File not found: {file_path}")
                return {
                    'success': False,
                    'error': f"File not found: {file_path}"
                }
                
            self.logger.info(f"Starting compression for: {file_path}")
            
            # Compress video
            compressor = VideoCompressor(self.compression_config)
            compressed_path = compressor.compress(file_path, output_dir)
            
            self.logger.info(f"Compression successful. Output: {compressed_path}")
            self.logger.info(f"Starting AI analysis...")
            
            # Analyze video
            # Get FPS from compression config, with fallback to default
            fps_for_analysis = self.compression_config.get('fps', 5)
            analyzer = VideoAnalyzer(api_key=self.api_key, fps=fps_for_analysis)
            analysis_results = analyzer.analyze_video(compressed_path)
            
            self.logger.info(f"AI analysis completed successfully")
            
            # Display comprehensive analysis summary
            try:
                self._display_analysis_summary(analysis_results)
            except Exception as e:
                self.logger.error(f"Error displaying analysis summary: {str(e)}")
                
            return {
                'success': True,
                'compressed_path': compressed_path,
                'analysis_json': analysis_results
            }
        
        except Exception as e:
            self.logger.error(f"Video processing failed: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            } 