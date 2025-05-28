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
        Display only the summary section of the analysis results.
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